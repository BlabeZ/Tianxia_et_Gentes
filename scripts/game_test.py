"""游戏自动化测试执行器——纯逻辑核心（T-042 Phase 1，规划：docs/加载测试自动化规划.md）。

本模块不含进程启动/杀灭与实机 IO；只提供：
  1. 会话数据模型（Session/LogBaseline/LogDiff/RuleHit）
  2. 增量日志隔离算法（identity + 尾部哈希连续性）
  3. 日志规则引擎（required/fatal/ignore/redaction，fatal 优先于 ignore）
  4. 判定模型（PASS/FAIL/INCONCLUSIVE）
  5. 报告构建与 JSON→Markdown 可重复渲染
  6. 路径/凭证脱敏

仅使用 Python 标准库；CI 只跑 mock/fixture，不启动真实游戏。
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERDICTS = ("PASS", "FAIL", "INCONCLUSIVE")
REGISTRABLE_PROFILES = ("menu-debug", "map-load", "scenario-load")

ASCII_ONLY = re.compile(r"^[\x20-\x7e]+$")
ABSOLUTE_PATH_RE = re.compile(
    r"(?i)(?:^|[^A-Za-z0-9])([A-Za-z]:[\\/][^\s\"'<>]+|/[^\s\"'<>]+)"
)
USERNAME_RE = re.compile(r"(?i)(?:C:[\\/])Users[\\/]([^\\/]+)")
STEAM_ID_RE = re.compile(r"7656\d{13}")
TOKEN_RE = re.compile(r"(?i)(token|secret|password|apikey)\s*[:=]\s*\S+")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_session_id() -> str:
    return "txg-" + secrets.token_hex(8)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_tail(data: bytes, size: int = 256) -> bytes:
    return data[-size:] if data else b""


def head_tail_hashes(data: bytes) -> tuple[str, str]:
    return sha256_hex(data[:256]), sha256_hex(stable_tail(data))


@dataclass
class LogBaseline:
    """启动前对单个日志文件的记录（规划七）。"""

    path: str
    exists: bool
    size: int
    identity: str | None
    created_at: str | None
    head_hash: str | None
    tail_hash: str | None
    captured_at: str


@dataclass
class LogDiff:
    """结束后对单个日志文件的增量结果。"""

    path: str
    baseline_size: int
    new_size: int
    appended_bytes: int = 0
    rotated: bool = False
    continuity_ok: bool = True
    no_new_evidence: bool = False
    text: str = ""
    encoding: str | None = None
    replacement_chars: int = 0

    def summary(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "baseline_size": self.baseline_size,
            "new_size": self.new_size,
            "appended_bytes": self.appended_bytes,
            "rotated": self.rotated,
            "continuity_ok": self.continuity_ok,
            "no_new_evidence": self.no_new_evidence,
            "encoding": self.encoding,
            "replacement_chars": self.replacement_chars,
        }


@dataclass
class RuleHit:
    rule_id: str
    kind: str
    log_path: str
    line_number: int | None
    matched_text: str
    context_before: str = ""
    context_after: str = ""


@dataclass
class MarkerEvidence:
    """required_markers 命中的证据（含顺序与来源）。"""

    marker_id: str
    log_path: str
    first_seen_relative_ms: int | None
    capture: str | None
    count: int = 0


@dataclass
class SessionResult:
    """一次会话的最终判定与证据。"""

    verdict: str
    reasons: list[str]
    hits: list[RuleHit] = field(default_factory=list)
    markers: list[MarkerEvidence] = field(default_factory=list)
    log_diffs: list[LogDiff] = field(default_factory=list)
    crash_evidence: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- 日志规则


@dataclass
class LogRule:
    """repo 内受控 profile 规则条目。"""

    rule_id: str
    kind: str  # required_marker | fatal | ignore | redaction | invalidating
    pattern: str
    log: str | None = None
    order: int = 0
    capture_group: int | None = None
    min_count: int = 1
    max_count: int | None = None
    case_sensitive: bool = False

    def compile(self) -> re.Pattern:
        flags = 0 if self.case_sensitive else re.IGNORECASE
        try:
            return re.compile(self.pattern, flags)
        except re.error as exc:  # pragma: no cover - 配置错误在加载时校验
            raise ValueError(f"规则 {self.rule_id} 正则非法: {exc}") from exc


def compile_rules(rules: Iterable[dict[str, Any]]) -> list[LogRule]:
    compiled: list[LogRule] = []
    for item in rules:
        rule = LogRule(
            rule_id=str(item["rule_id"]),
            kind=str(item["kind"]),
            pattern=str(item["pattern"]),
            log=item.get("log"),
            order=int(item.get("order", 0)),
            capture_group=item.get("capture_group"),
            min_count=int(item.get("min_count", 1)),
            max_count=item.get("max_count"),
            case_sensitive=bool(item.get("case_sensitive", False)),
        )
        if rule.kind not in ("required_marker", "fatal", "ignore", "redaction", "invalidating"):
            raise ValueError(f"规则 {rule.rule_id} 未知类型 {rule.kind}")
        compiled.append(rule)
    return compiled


def scan_text(
    text: str,
    rules: Iterable[LogRule],
    log_path: str,
    ignored_lines: set[int] | None = None,
) -> tuple[list[RuleHit], dict[str, MarkerEvidence]]:
    """按行扫描增量文本。

    fatal 优先于 ignore：fatal 命中即使同一行命中 ignore 也保留。
    required_marker 记录首次出现与计数。
    """
    hits: list[RuleHit] = []
    markers: dict[str, MarkerEvidence] = {}
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        for rule in rules:
            match = getattr(rule, "_regex", None)
            if match is None:
                match = rule.compile()
                rule._regex = match  # type: ignore[attr-defined]
            found = match.search(line)
            if not found:
                continue
            if rule.log and rule.log not in log_path:
                continue
            if rule.kind == "fatal":
                hits.append(
                    RuleHit(
                        rule_id=rule.rule_id,
                        kind="fatal",
                        log_path=log_path,
                        line_number=index,
                        matched_text=line,
                        context_before=(lines[index - 2] if index >= 2 else ""),
                        context_after=(lines[index] if index < len(lines) else ""),
                    )
                )
            elif rule.kind == "required_marker":
                evidence = markers.setdefault(
                    rule.rule_id,
                    MarkerEvidence(
                        marker_id=rule.rule_id,
                        log_path=log_path,
                        first_seen_relative_ms=None,
                        capture=None,
                        count=0,
                    ),
                )
                evidence.count += 1
                if evidence.capture is None and rule.capture_group is not None:
                    try:
                        evidence.capture = found.group(rule.capture_group)
                    except IndexError:
                        evidence.capture = found.group(0)
            elif rule.kind in ("ignore", "redaction", "invalidating"):
                hits.append(
                    RuleHit(
                        rule_id=rule.rule_id,
                        kind=rule.kind,
                        log_path=log_path,
                        line_number=index,
                        matched_text=line,
                    )
                )
    return hits, markers


# ---------------------------------------------------------------- 判定


def evaluate(
    markers: dict[str, MarkerEvidence],
    fatal_hits: list[RuleHit],
    invalidating_hits: list[RuleHit],
    crash_evidence: list[str],
    any_new_evidence: bool,
    all_logs_consistent: bool,
    ready_reached: bool,
    survived_after_ready: bool,
    required_marker_ids: list[str],
) -> SessionResult:
    """判定优先级：证据不可靠→INCONCLUSIVE；fatal/crash→FAIL；全满足→PASS。"""

    reasons: list[str] = []
    if not all_logs_consistent:
        return SessionResult(
            verdict="INCONCLUSIVE",
            reasons=["日志截断/替换/轮转导致证据无法可靠解释"],
            hits=fatal_hits + invalidating_hits,
            markers=list(markers.values()),
        )
    if not any_new_evidence:
        return SessionResult(
            verdict="INCONCLUSIVE",
            reasons=["日志无新增证据"],
            hits=fatal_hits + invalidating_hits,
            markers=list(markers.values()),
        )
    if fatal_hits:
        reasons.append(
            f"新增日志命中 fatal 规则：{sorted({h.rule_id for h in fatal_hits})}"
        )
    if crash_evidence:
        reasons.append(f"新增 crash 证据：{sorted(crash_evidence)}")
    if fatal_hits or crash_evidence:
        return SessionResult(
            verdict="FAIL",
            reasons=reasons,
            hits=fatal_hits + invalidating_hits,
            markers=list(markers.values()),
            crash_evidence=list(crash_evidence),
        )
    missing = [m for m in required_marker_ids if m not in markers]
    if missing:
        return SessionResult(
            verdict="INCONCLUSIVE",
            reasons=[f"readiness 标志未齐（缺失 {missing}），无明确失败证据"],
            hits=invalidating_hits,
            markers=list(markers.values()),
        )
    if not ready_reached:
        return SessionResult(
            verdict="INCONCLUSIVE",
            reasons=["未到达 readiness 且无明确失败证据"],
            hits=invalidating_hits,
            markers=list(markers.values()),
        )
    if invalidating_hits:
        return SessionResult(
            verdict="FAIL",
            reasons=[f"ready 后出现失效标志：{sorted({h.rule_id for h in invalidating_hits})}"],
            hits=fatal_hits + invalidating_hits,
            markers=list(markers.values()),
        )
    if not survived_after_ready:
        return SessionResult(
            verdict="INCONCLUSIVE",
            reasons=["ready 后未达到存活时长"],
            markers=list(markers.values()),
        )
    return SessionResult(
        verdict="PASS",
        reasons=["mod-loaded + readiness + ready 后存活 + 无 fatal/crash 证据齐备"],
        hits=[],
        markers=list(markers.values()),
    )


# ---------------------------------------------------------------- 脱敏


def redact_text(text: str) -> str:
    text = USERNAME_RE.sub(r"C:\\Users\\<redacted>", text)
    text = STEAM_ID_RE.sub("<steam-id-redacted>", text)
    text = TOKEN_RE.sub(r"\1=<redacted>", text)
    text = ABSOLUTE_PATH_RE.sub("<abs-path-redacted>", text)
    return text


def redact_dict(data: Any) -> Any:
    if isinstance(data, dict):
        return {str(key): redact_dict(value) for key, value in data.items()}
    if isinstance(data, list):
        return [redact_dict(item) for item in data]
    if isinstance(data, str):
        return redact_text(data)
    return data


def contains_absolute_path(data: Any) -> bool:
    if isinstance(data, dict):
        return any(contains_absolute_path(v) for v in data.values())
    if isinstance(data, list):
        return any(contains_absolute_path(v) for v in data)
    if isinstance(data, str):
        return bool(ABSOLUTE_PATH_RE.search(data))
    return False


# ---------------------------------------------------------------- 报告


def build_report(
    *,
    session_id: str,
    task_id: str,
    generation: int,
    profile: str,
    game_version: str | None,
    executable_sha256: str | None,
    baseline_contract_id: str | None,
    mod_descriptor_sha256: str | None,
    mod_tree_sha256: str | None,
    git_head: str,
    git_dirty: bool,
    runner_commit: str,
    profile_hash: str,
    rules_hash: str,
    started_at: str,
    ended_at: str,
    durations: dict[str, float],
    executable_basename: str | None,
    sanitized_argv: list[str],
    markers: list[MarkerEvidence],
    exit_code: int | None,
    terminated_by_runner: bool,
    log_diffs: list[LogDiff],
    result: SessionResult,
    registrable: bool,
    consumed_by: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": 1,
        "session_id": session_id,
        "task_id": task_id,
        "generation": generation,
        "profile": profile,
        "game_version": game_version,
        "executable_sha256": executable_sha256,
        "baseline_contract_id": baseline_contract_id,
        "mod_descriptor_sha256": mod_descriptor_sha256,
        "mod_tree_sha256": mod_tree_sha256,
        "git_head": git_head,
        "git_dirty": git_dirty,
        "runner_commit": runner_commit,
        "profile_hash": profile_hash,
        "rules_hash": rules_hash,
        "started_at": started_at,
        "ended_at": ended_at,
        "durations": durations,
        "executable_basename": executable_basename,
        "argv": sanitized_argv,
        "markers": [
            {
                "marker_id": m.marker_id,
                "log": m.log_path,
                "first_seen_relative_ms": m.first_seen_relative_ms,
                "capture": m.capture,
                "count": m.count,
            }
            for m in markers
        ],
        "exit": {"code": exit_code, "terminated_by_runner": terminated_by_runner},
        "logs": [diff.summary() for diff in log_diffs],
        "crash_evidence": result.crash_evidence,
        "verdict": result.verdict,
        "reasons": result.reasons,
        "hits": [
            {
                "rule_id": h.rule_id,
                "kind": h.kind,
                "log": h.log_path,
                "line": h.line_number,
                "text": redact_text(h.matched_text)[:512],
                "context_before": redact_text(h.context_before)[:512],
                "context_after": redact_text(h.context_after)[:512],
            }
            for h in result.hits
        ][:100],
        "registrable": registrable,
        "consumed_by": consumed_by,
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# 加载测试报告 {report['task_id']}（{report['profile']}）",
        "",
        f"- 会话：{report['session_id']}",
        f"- 结论：**{report['verdict']}**（registrable={report['registrable']}）",
        f"- 时间：{report['started_at']} → {report['ended_at']}",
        f"- 游戏版本：{report.get('game_version') or '未知'}",
        f"- 可执行文件：{report.get('executable_basename') or '未知'}（SHA256 {report.get('executable_sha256') or '未知'}）",
        f"- baseline_contract_id：{report.get('baseline_contract_id') or '未知'}",
        f"- mod 树哈希：{report.get('mod_tree_sha256') or '未知'}",
        f"- git：{report['git_head']}{'（工作树脏）' if report['git_dirty'] else ''}",
        "",
        "## 判定理由",
        "",
    ]
    for reason in report["reasons"]:
        lines.append(f"- {reason}")
    if report["markers"]:
        lines.extend(["", "## readiness 标志", ""])
        for m in report["markers"]:
            lines.append(
                f"- {m['marker_id']}：{m['log']}，count={m['count']}，capture={m.get('capture') or '—'}"
            )
    if report["hits"]:
        lines.extend(["", "## 规则命中", ""])
        for h in report["hits"]:
            lines.append(f"- [{h['kind']}] {h['rule_id']} @ {h['log']}:{h['line']}")
    if report["crash_evidence"]:
        lines.extend(["", "## crash 证据", ""])
        for c in report["crash_evidence"]:
            lines.append(f"- {c}")
    lines.extend(["", "## 日志增量", ""])
    for log in report["logs"]:
        rotated = "（轮转）" if log["rotated"] else ""
        lines.append(
            f"- {log['path']}：+{log['appended_bytes']} bytes{rotated}"
        )
    lines.extend(
        [
            "",
            f"## 退出",
            "",
            f"- 退出码：{report['exit']['code']}（runner 主动终止：{report['exit']['terminated_by_runner']}）",
            "",
            "> 本报告由 game-test 执行器生成；原始日志不入库；所有路径与凭证已脱敏。",
            "",
        ]
    )
    return "\n".join(lines)


def report_files_valid(report: dict[str, Any], markdown_text: str) -> list[str]:
    """校验 Markdown 是否由当前 JSON 可重复渲染（规划十一）。"""

    errors: list[str] = []
    if report.get("verdict") not in VERDICTS:
        errors.append(f"verdict 非法：{report.get('verdict')}")
    if report.get("registrable") and report.get("profile") not in REGISTRABLE_PROFILES:
        errors.append(
            f"registrable=true 但 profile {report.get('profile')} 不可登记"
        )
    if contains_absolute_path(report):
        errors.append("报告包含本机绝对路径")
    rendered = render_markdown(report)
    if rendered != markdown_text:
        errors.append("Markdown 与 JSON 渲染不一致")
    return errors
