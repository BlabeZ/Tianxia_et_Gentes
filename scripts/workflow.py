#!/usr/bin/env python3
"""Cross-platform workflow gate for the Tianxia et Gentes project.

Only Python's standard library is used so the same entry point works on the
Windows full machine and Linux light machines.  Game files are opened read-only;
all generated artifacts are written inside the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Iterable

try:
    from scripts import state_transform
except ImportError:  # Direct execution: python3 scripts/workflow.py
    import state_transform


ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG = ROOT / ".opencode" / "local.json"
TASKS_JSON = ROOT / "协作" / "tasks.json"
TASKS_MD = ROOT / "协作" / "任务台账.md"
ENV_DIR = ROOT / "协作" / "环境"
SNAPSHOT_DIR = ROOT / "协作" / "扫描快照"
SNAPSHOT_JSON = SNAPSHOT_DIR / "states.json"
SNAPSHOT_MD = SNAPSHOT_DIR / "states-summary.md"
STATE_OVERRIDE_DIR = ROOT / "协作" / "state-overrides"
TASK_SPEC_DIR = ROOT / "任务书"
MOD_STATES_DIR = ROOT / "mod" / "history" / "states"
DECISION_DIR = ROOT / "协作" / "决策记录"
HANDOFF_DIR = ROOT / "协作" / "交接单"
SCHEMA_DIR = ROOT / "schemas"
LEASE_HOURS = 48
ENV_FRESHNESS_MINUTES = 15

TASK_STATUSES = {
    "todo": "待办",
    "in_progress": "进行中",
    "pending_validation": "待验证",
    "pending_test": "待测试",
    "ready_to_merge": "待合并",
    "decision_required": "待决策",
    "done": "完成",
    "blocked": "阻塞",
    "stale": "已过期",
}

CAPABILITY_KEYS = (
    "dialog_development",
    "snapshot_export",
    "mod_execution",
    "static_validation",
    "load_test",
)

CORE_PATTERNS = (
    "AGENTS.md",
    "CLAUDE.md",
    "docs/协作框架.md",
    "协作/README.md",
    "协作/决策协议.md",
    ".github/workflows/",
    ".opencode/agent/",
    ".opencode/command/",
    ".opencode/skills/",
    ".githooks/",
    "scripts/workflow.py",
    "schemas/",
)

PENDING_MARKERS = ("待定", "待确认", "【拟定】", "【待推演】")
PENDING_MARKER_RE = re.compile(
    r"待定\s*/\s*待确认|待确认\s*/\s*待定|待定|待确认|【拟定】|【待推演】"
)

INTERVIEW_PROTOCOL_MARKERS = (
    "当前假设",
    "低于约 `70%`",
    "当前猜测及其理由",
    "如果不需要向任何人证明这个选择，你真正想要什么？",
    "接下来三个问题",
    "为何现在（Why now）",
    "不包含（Out of scope）",
    "`whatever you think`",
    "`sounds good`",
    "`sure, let's go`",
    "明确确认门槛",
)

TASK_LIFECYCLE_FIELDS = {
    "status",
    "owner",
    "branch",
    "lease_generation",
    "claimed_at",
    "heartbeat_at",
    "lease_expires_at",
    "base_commit",
    "head_commit",
    "handoff",
    "blocker",
    "previous_owner",
    "validation_report",
    "test_report",
    "failure_count",
    "failure_stage",
    "stage_failure_count",
    "checkpoint_commit",
}

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ISO_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


@dataclass(frozen=True)
class PendingRemoval:
    path: str
    line_sha256: str
    excerpt: str


class WorkflowError(RuntimeError):
    """Expected validation or workflow failure."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_z(value: str) -> datetime:
    if not ISO_Z_RE.fullmatch(value):
        raise WorkflowError(f"时间必须是 UTC ISO-8601 秒级格式：{value!r}")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(f"缺少文件：{path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"JSON 无效：{path.relative_to(ROOT)}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, newline="\n"
    ) as handle:
        handle.write(payload)
        temp_name = handle.name
    os.replace(temp_name, path)


def schema_type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return False


def validate_schema_instance(value: Any, schema: dict[str, Any], location: str = "$") -> list[str]:
    """Validate the JSON Schema subset used by this repository.

    Keeping this deliberately small preserves the zero-dependency Python 3
    gate while making the committed schemas executable rather than decorative.
    """

    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        expected_types = expected if isinstance(expected, list) else [expected]
        if not any(schema_type_matches(value, item) for item in expected_types):
            errors.append(f"{location}: 类型必须是 {expected_types}")
            return errors
    if "const" in schema and value != schema["const"]:
        errors.append(f"{location}: 必须等于 {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{location}: 必须是 {schema['enum']!r} 之一")

    if isinstance(value, str):
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.fullmatch(pattern, value) is None:
            errors.append(f"{location}: 不匹配 {pattern!r}")
        minimum = schema.get("minLength")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append(f"{location}: 长度不得小于 {minimum}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"{location}: 不得小于 {minimum}")
    if isinstance(value, list):
        minimum = schema.get("minItems")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append(f"{location}: 项目数不得小于 {minimum}")
        if schema.get("uniqueItems") is True:
            encoded = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{location}: 数组项必须唯一")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(validate_schema_instance(item, item_schema, f"{location}[{index}]"))
    if isinstance(value, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    errors.append(f"{location}: 缺少必填字段 {key}")
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        for key, child in properties.items():
            if key in value and isinstance(child, dict):
                errors.extend(validate_schema_instance(value[key], child, f"{location}.{key}"))
        additional = schema.get("additionalProperties", True)
        for key in set(value) - set(properties):
            if additional is False:
                errors.append(f"{location}: 不允许额外字段 {key}")
            elif isinstance(additional, dict):
                errors.extend(validate_schema_instance(value[key], additional, f"{location}.{key}"))
    return errors


def validate_named_schema(value: Any, schema_name: str, label: str) -> list[str]:
    schema = read_json(SCHEMA_DIR / schema_name)
    if not isinstance(schema, dict):
        return [f"{label}: schema 顶层必须是对象"]
    return [f"{label}: {error}" for error in validate_schema_instance(value, schema)]


def string_contains_absolute_path(value: str) -> bool:
    if PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute():
        return True
    if re.search(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]", value):
        return True
    if re.search(r"(?:^|[\s:=：(])/(?!/)[^\s`'\"<>]+", value):
        return True
    if re.search(r"\\\\[^\\\s]+\\[^\s]+", value):
        return True
    return False


def absolute_path_strings(value: Any) -> set[str]:
    hits: set[str] = set()
    if isinstance(value, str):
        if string_contains_absolute_path(value):
            hits.add(value)
    elif isinstance(value, list):
        for item in value:
            hits.update(absolute_path_strings(item))
    elif isinstance(value, dict):
        for item in value.values():
            hits.update(absolute_path_strings(item))
    return hits


def run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def state_files(game_path: Path) -> list[Path]:
    states = game_path / "history" / "states"
    if not states.is_dir():
        raise WorkflowError(f"game_path 缺少 history/states：{states}")
    files = sorted(states.glob("*.txt"), key=lambda item: item.name.casefold())
    if not files:
        raise WorkflowError(f"未找到 state 文件：{states}")
    return files


def fingerprint_files(files: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def strip_hoi_comments(text: str) -> str:
    return re.sub(r"#.*$", "", text, flags=re.MULTILINE)


def parse_state(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    clean = strip_hoi_comments(text)
    id_match = re.search(r"\bid\s*=\s*(\d+)", clean)
    if not id_match:
        raise WorkflowError(f"state 文件缺少 id：{path.name}")
    state_id = int(id_match.group(1))
    provinces_match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", clean, re.DOTALL)
    provinces: list[int] = []
    if provinces_match:
        provinces = [int(value) for value in re.findall(r"\b\d+\b", provinces_match.group(1))]
    return {
        "state_id": state_id,
        "localisation_key": f"STATE_{state_id}",
        "relative_path": f"history/states/{path.name}",
        "province_count": len(provinces),
        "provinces": provinces,
        "sha256": sha256_file(path),
    }


def detect_game_version(game_path: Path) -> str | None:
    version_txt = game_path / "version.txt"
    if version_txt.is_file():
        value = version_txt.read_text(encoding="utf-8-sig", errors="replace").strip()
        if value:
            return value
    launcher = game_path / "launcher-settings.json"
    if launcher.is_file():
        try:
            data = json.loads(launcher.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            data = {}
        for key in ("gameVersion", "version"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def validate_local_config(data: Any) -> list[str]:
    errors = validate_named_schema(data, "local.schema.json", ".opencode/local.json")
    if not isinstance(data, dict):
        return errors
    machine_id = data.get("machine_id")
    if not isinstance(machine_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", machine_id):
        errors.append("machine_id 必须由字母、数字、下划线或连字符组成")
    if data.get("os") not in {"windows", "linux", "ubuntu", "macos"}:
        errors.append("os 必须是 windows/linux/ubuntu/macos")
    for field in ("game_path", "workshop_path", "user_docs_path"):
        value = data.get(field)
        if value is not None and not isinstance(value, str):
            errors.append(f"{field} 必须是字符串或 null")
        elif isinstance(value, str) and (not value.strip() or not Path(value).expanduser().is_absolute()):
            errors.append(f"{field} 必须是绝对路径或 null")
    return errors


def load_local_config() -> tuple[dict[str, Any], list[str]]:
    if not LOCAL_CONFIG.is_file():
        return {}, [".opencode/local.json 缺失，按默认拒绝处理"]
    try:
        data = json.loads(LOCAL_CONFIG.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [f".opencode/local.json JSON 无效：{exc}"]
    errors = validate_local_config(data)
    return data if isinstance(data, dict) else {}, errors


def snapshot_metadata() -> dict[str, Any] | None:
    if not SNAPSHOT_JSON.is_file():
        return None
    try:
        data = read_json(SNAPSHOT_JSON)
    except WorkflowError:
        return None
    if snapshot_data_errors(data):
        return None
    return data


def snapshot_data_errors(data: Any) -> list[str]:
    """Validate the security-relevant subset of the snapshot schema.

    The project intentionally has no third-party runtime dependencies.  These
    checks mirror the committed JSON Schema fields that gate mod execution and
    add cross-field checks JSON Schema alone would not express clearly.

    Schema v2 (D-20260811-018) adds the per-state province ID list and the
    global uniqueness invariant: every province belongs to exactly one state.
    """

    errors: list[str] = []
    if not isinstance(data, dict):
        return ["顶层必须是对象"]
    if data.get("schema_version") != 2:
        errors.append("schema_version 必须是 2（v1 已由 D-20260811-018 升级为含 province 列表）")
    generated_at = data.get("generated_at")
    if not isinstance(generated_at, str) or not ISO_Z_RE.fullmatch(generated_at):
        errors.append("generated_at 格式无效")
    machine = data.get("generated_by_machine")
    if not isinstance(machine, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", machine):
        errors.append("generated_by_machine 无效")

    source = data.get("source")
    if not isinstance(source, dict):
        errors.append("source 必须是对象")
        source = {}
    if source.get("relative_root") != "history/states":
        errors.append("source.relative_root 必须是 history/states")
    fingerprint = source.get("fingerprint")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        errors.append("source.fingerprint 必须是64位小写 SHA-256")

    states = data.get("states")
    if not isinstance(states, list) or not states:
        errors.append("states 必须是非空数组")
        states = []
    file_count = source.get("file_count")
    if not isinstance(file_count, int) or isinstance(file_count, bool) or file_count != len(states):
        errors.append("source.file_count 必须与 states 数量一致")

    seen_ids: set[int] = set()
    seen_paths: set[str] = set()
    seen_provinces: set[int] = set()
    previous_id = -1
    for index, state in enumerate(states):
        prefix = f"states[{index}]"
        if not isinstance(state, dict):
            errors.append(f"{prefix} 必须是对象")
            continue
        state_id = state.get("state_id")
        if not isinstance(state_id, int) or isinstance(state_id, bool) or state_id <= 0:
            errors.append(f"{prefix}.state_id 必须是正整数")
        else:
            if state_id in seen_ids:
                errors.append(f"{prefix}.state_id 重复：{state_id}")
            if state_id <= previous_id:
                errors.append("states 必须按 state_id 严格递增排序")
            seen_ids.add(state_id)
            previous_id = state_id
            if state.get("localisation_key") != f"STATE_{state_id}":
                errors.append(f"{prefix}.localisation_key 与 state_id 不一致")
        relative_path = state.get("relative_path")
        if (
            not isinstance(relative_path, str)
            or not relative_path.startswith("history/states/")
            or not relative_path.endswith(".txt")
            or ".." in Path(relative_path).parts
            or Path(relative_path).is_absolute()
        ):
            errors.append(f"{prefix}.relative_path 必须是 history/states 下的相对 txt 路径")
        elif relative_path in seen_paths:
            errors.append(f"{prefix}.relative_path 重复：{relative_path}")
        else:
            seen_paths.add(relative_path)
        province_count = state.get("province_count")
        if (
            not isinstance(province_count, int)
            or isinstance(province_count, bool)
            or province_count < 0
        ):
            errors.append(f"{prefix}.province_count 必须是非负整数")
        provinces = state.get("provinces")
        if not isinstance(provinces, list):
            errors.append(f"{prefix}.provinces 必须是数组")
            provinces = []
        else:
            if len(provinces) != len(set(provinces)):
                errors.append(f"{prefix}.provinces 内不得重复")
            for province_id in provinces:
                if (
                    not isinstance(province_id, int)
                    or isinstance(province_id, bool)
                    or province_id <= 0
                ):
                    errors.append(f"{prefix}.provinces 必须全是正整数")
            if province_count != len(provinces):
                errors.append(
                    f"{prefix}.province_count 必须与 provinces 列表长度一致"
                )
            for province_id in provinces:
                if isinstance(province_id, int) and province_id > 0 and province_id in seen_provinces:
                    errors.append(
                        f"{prefix}.provinces 与之前的 state 重复归属：{province_id}"
                    )
                if isinstance(province_id, int) and province_id > 0:
                    seen_provinces.add(province_id)
        digest = state.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append(f"{prefix}.sha256 必须是64位小写 SHA-256")
    return errors


def render_snapshot_summary(data: dict[str, Any]) -> str:
    lines = [
        "# HOI4 states 受控快照摘要",
        "",
        "> 本文件由 `python3 scripts/workflow.py snapshot-export` 自动生成（Windows 使用 `py -3`）；不得手工编辑。",
        "> 仅包含元数据和校验和，不包含游戏本体脚本正文。",
        "> schema v2（D-20260811-018）：province 编号列表与全局唯一归属见 `states.json`。",
        "",
        f"- 生成时间：`{data['generated_at']}`",
        f"- 游戏版本：`{data['game_version'] or 'unknown'}`",
        f"- 文件数量：`{data['source']['file_count']}`",
        f"- 指纹：`{data['source']['fingerprint']}`",
        "",
        "| state_id | localisation_key | 文件 | provinces | sha256 |",
        "| ---: | --- | --- | ---: | --- |",
    ]
    for item in data["states"]:
        lines.append(
            f"| {item['state_id']} | {item['localisation_key']} | "
            f"`{item['relative_path']}` | {item['province_count']} | `{item['sha256']}` |"
        )
    return "\n".join(lines) + "\n"


def has_game_executable(game_path: Path) -> bool:
    candidates = ("hoi4.exe", "hoi4", "dowser.exe", "dowser")
    return any((game_path / candidate).is_file() for candidate in candidates)


def derive_environment(
    config: dict[str, Any], config_errors: list[str], *, probe_external: bool = True
) -> dict[str, Any]:
    warnings = list(config_errors)
    game_path_value = config.get("game_path")
    # Invalid local configuration must never grant access to external paths.  A
    # committed snapshot can still be consumed because it is repository data.
    # Non-publishing checks are used by subagents and intentionally never probe
    # external paths; only the main agent's --publish check may do so.
    game_path = (
        Path(game_path_value).expanduser()
        if probe_external and not config_errors and isinstance(game_path_value, str)
        else None
    )
    game_valid = bool(game_path and game_path.is_dir())
    files: list[Path] = []
    live_fingerprint: str | None = None
    if game_valid and game_path is not None:
        try:
            files = state_files(game_path)
            live_fingerprint = fingerprint_files(files)
        except WorkflowError as exc:
            warnings.append(str(exc))

    snapshot = snapshot_metadata()
    if SNAPSHOT_JSON.is_file() and snapshot is None:
        warnings.append("受控快照结构无效：已按 missing 处理并封锁依赖能力")
    if snapshot is None:
        snapshot_status = "missing"
    elif live_fingerprint is None:
        snapshot_status = "available"
    elif snapshot.get("source", {}).get("fingerprint") == live_fingerprint:
        snapshot_status = "current"
    else:
        snapshot_status = "stale"

    user_docs_value = config.get("user_docs_path")
    user_docs = (
        Path(user_docs_value).expanduser()
        if probe_external and not config_errors and isinstance(user_docs_value, str)
        else None
    )
    snapshot_export = bool(game_valid and files)
    mod_execution = snapshot_status in {"current", "available"}
    load_test = bool(
        game_valid
        and game_path is not None
        and has_game_executable(game_path)
        and user_docs
        and user_docs.is_dir()
    )
    capabilities = {
        "dialog_development": True,
        "snapshot_export": snapshot_export,
        "mod_execution": mod_execution,
        "static_validation": True,
        "load_test": load_test,
    }
    if snapshot_status == "stale":
        warnings.append("本体 state 指纹已变化：依赖快照的执行与测试必须阻断，直至显式刷新")
        capabilities["mod_execution"] = False
        capabilities["load_test"] = False

    if all(capabilities[name] for name in ("snapshot_export", "mod_execution", "load_test")):
        profile = "full"
    elif any(capabilities[name] for name in ("snapshot_export", "mod_execution", "load_test")):
        profile = "partial"
    else:
        profile = "light"

    legacy_mode = config.get("capability_mode")
    if legacy_mode and legacy_mode != profile:
        warnings.append(f"旧 capability_mode={legacy_mode} 与实测 profile={profile} 不一致；以实测为准")

    return {
        "schema_version": 1,
        "machine_id": config.get("machine_id", "unknown"),
        "os": config.get("os", sys.platform),
        "checked_at": iso_z(utc_now()),
        "profile": profile,
        "config_valid": not config_errors,
        "capabilities": capabilities,
        "snapshot": {
            "status": snapshot_status,
            "game_version": detect_game_version(game_path) if game_valid and game_path else None,
            "fingerprint": live_fingerprint or (snapshot or {}).get("source", {}).get("fingerprint"),
        },
        "warnings": warnings,
    }


def env_check(args: argparse.Namespace) -> int:
    config, errors = load_local_config()
    result = derive_environment(config, errors, probe_external=args.publish)
    if args.publish:
        if errors:
            raise WorkflowError("无法发布环境快照：" + "；".join(errors))
        write_json(ENV_DIR / f"{result['machine_id']}.json", result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("== 环境自检 / Environment Gate ==")
        print(f"machine_id: {result['machine_id']}")
        print(f"os: {result['os']}")
        print(f"profile: {result['profile']}")
        print(f"snapshot_status: {result['snapshot']['status']}")
        for key in CAPABILITY_KEYS:
            print(f"capability.{key}: {str(result['capabilities'][key]).lower()}")
        git_status = run_git("status", "--short", check=False).stdout.strip()
        print(f"git_status: {'clean' if not git_status else 'dirty'}")
        for warning in result["warnings"]:
            print(f"WARNING: {warning}")
        if args.publish:
            print(f"published: 协作/环境/{result['machine_id']}.json")
    return 0


def snapshot_export(_: argparse.Namespace) -> int:
    config, errors = load_local_config()
    if errors:
        raise WorkflowError("；".join(errors))
    game_value = config.get("game_path")
    if not isinstance(game_value, str):
        raise WorkflowError("当前机器没有有效 game_path，不能导出本体快照")
    game_path = Path(game_value).expanduser()
    files = state_files(game_path)
    states = [parse_state(path) for path in files]
    ids = [item["state_id"] for item in states]
    if len(ids) != len(set(ids)):
        raise WorkflowError("本体 state id 存在重复，拒绝生成快照")
    generated_at = iso_z(utc_now())
    data = {
        "schema_version": 2,
        "generated_at": generated_at,
        "generated_by_machine": config["machine_id"],
        "game_version": detect_game_version(game_path),
        "source": {
            "relative_root": "history/states",
            "file_count": len(files),
            "fingerprint": fingerprint_files(files),
        },
        "states": sorted(states, key=lambda item: item["state_id"]),
    }
    write_json(SNAPSHOT_JSON, data)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_MD.write_text(render_snapshot_summary(data), encoding="utf-8", newline="\n")
    print(f"已生成 {len(states)} 个 state 的受控快照。")
    return 0


def resolve_override_path(value: str) -> Path:
    supplied = Path(value)
    if supplied.is_absolute():
        raise WorkflowError("state 改写清单必须使用仓库内相对路径")
    path = (ROOT / supplied).resolve()
    try:
        path.relative_to(STATE_OVERRIDE_DIR.resolve())
    except ValueError as exc:
        raise WorkflowError("state 改写清单必须位于 协作/state-overrides/") from exc
    if path.suffix.lower() != ".json" or not path.is_file():
        raise WorkflowError(f"state 改写清单不存在或不是 JSON：{value}")
    return path


def load_override_document(path: Path) -> dict[str, Any]:
    data = read_json(path)
    label = str(path.relative_to(ROOT))
    errors = validate_named_schema(data, "state-overrides.schema.json", label)
    errors.extend(f"{label}: {item}" for item in state_transform.validate_override_document(data))
    if isinstance(data, dict):
        decision_id = data.get("decision_id")
        if not isinstance(decision_id, str) or not (DECISION_DIR / f"{decision_id}.json").is_file():
            errors.append(f"{label}: decision_id 对应的决策记录不存在")
    if errors:
        raise WorkflowError("；".join(errors))
    assert isinstance(data, dict)
    return data


def state_build(args: argparse.Namespace) -> int:
    config, config_errors = load_local_config()
    if config_errors:
        raise WorkflowError("本机配置无效，拒绝读取本体：" + "；".join(config_errors))
    environment = derive_environment(config, config_errors, probe_external=True)
    capabilities = environment.get("capabilities", {})
    snapshot_status = environment.get("snapshot", {}).get("status")
    if capabilities.get("snapshot_export") is not True:
        raise WorkflowError("本机不具备 snapshot_export，禁止读取本体 state")
    if capabilities.get("mod_execution") is not True or snapshot_status != "current":
        raise WorkflowError("受控快照不是 current，禁止生成 mod state")
    game_path_value = config.get("game_path")
    if not isinstance(game_path_value, str):
        raise WorkflowError("本机缺少 game_path")
    snapshot = read_json(SNAPSHOT_JSON)
    snapshot_errors = snapshot_data_errors(snapshot)
    if snapshot_errors:
        raise WorkflowError("受控快照无效：" + "；".join(snapshot_errors))
    documents = [load_override_document(resolve_override_path(value)) for value in args.override]
    try:
        output_root = MOD_STATES_DIR.resolve()
        try:
            output_root.relative_to(ROOT.resolve())
        except ValueError as exc:
            raise WorkflowError("mod/history/states 解析到工作区之外，拒绝写入") from exc
        outputs = state_transform.build_state_outputs(
            Path(game_path_value).expanduser(), snapshot, documents
        )
        count = state_transform.write_state_outputs(outputs, output_root)
    except (OSError, UnicodeError, state_transform.StateTransformError) as exc:
        raise WorkflowError(f"state 受控转换失败：{exc}") from exc
    print(f"已从受控本体输入生成 {count} 个完整 state 文件。")
    return 0


def load_tasks() -> dict[str, Any]:
    data = read_json(TASKS_JSON)
    if not isinstance(data, dict):
        raise WorkflowError("协作/tasks.json 顶层必须是对象")
    return data


def task_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        raise WorkflowError("协作/tasks.json 的 tasks 必须是数组")
    result: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("id"), str):
            raise WorkflowError("每个任务必须是含 id 的对象")
        if task["id"] in result:
            raise WorkflowError(f"重复任务 ID：{task['id']}")
        result[task["id"]] = task
    return result


def md_cell(value: Any) -> str:
    if value is None or value == "" or value == []:
        return "—"
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value)
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_tasks(data: dict[str, Any]) -> str:
    lines = [
        "# 任务台账",
        "",
        "> 本文件由 `协作/tasks.json` 自动生成；不得手工编辑。",
        "> 只有主调度器可以通过 `python3 scripts/workflow.py task ...`（Windows 用 `py -3`）修改任务状态。",
        f"> 默认租约：{data.get('policy', {}).get('lease_hours', LEASE_HOURS)} 小时；过期自动回收并递增隔离令牌。",
        "",
        "| 任务ID | 模块 | 状态 | 负责人 | 分支 | 隔离代数 | 领取时间 | 租约到期 | 交接点 | 产出文件 | 阻塞项 |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for task in data.get("tasks", []):
        status = TASK_STATUSES.get(task.get("status"), f"未知:{task.get('status')}")
        row = [
            task.get("id"),
            task.get("module"),
            status,
            task.get("owner"),
            task.get("branch"),
            task.get("lease_generation", 0),
            task.get("claimed_at"),
            task.get("lease_expires_at"),
            task.get("handoff"),
            task.get("outputs"),
            task.get("blocker"),
        ]
        lines.append("| " + " | ".join(md_cell(value) for value in row) + " |")
    lines.extend(
        [
            "",
            "## 状态流转",
            "",
            "`待办 → 进行中 → 待验证 → 待测试/待合并 → 完成`；重大决策缺失时使用“待决策”，不得被执行 agent 领取。",
            "",
            "自动回收只由主调度器执行。旧 `lease_generation` 的心跳、交接和验证结果一律拒绝。",
        ]
    )
    return "\n".join(lines) + "\n"


def render_tasks_command(args: argparse.Namespace) -> int:
    rendered = render_tasks(load_tasks())
    if args.check:
        existing = TASKS_MD.read_text(encoding="utf-8") if TASKS_MD.is_file() else ""
        if existing != rendered:
            raise WorkflowError("协作/任务台账.md 与协作/tasks.json 不一致；请运行 render-tasks")
    else:
        TASKS_MD.write_text(rendered, encoding="utf-8", newline="\n")
        print("已生成 协作/任务台账.md")
    return 0


def find_task(data: dict[str, Any], task_id: str) -> dict[str, Any]:
    tasks = task_index(data)
    if task_id not in tasks:
        raise WorkflowError(f"未知任务：{task_id}")
    return tasks[task_id]


def owner_machine(owner: str) -> str:
    return owner.split("/", 1)[0]


def require_clean_main(
    allowed_paths: Iterable[str] = (), operation: str = "task assign"
) -> str:
    branch = run_git("symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if branch.returncode != 0 or branch.stdout.strip() != "main":
        raise WorkflowError(f"{operation} 只能在 main 分支运行")
    status = run_git(
        "-c",
        "core.quotePath=false",
        "status",
        "--porcelain",
        "--untracked-files=all",
        check=False,
    )
    if status.returncode != 0:
        raise WorkflowError(f"无法检查 Git 工作区：{status.stderr.strip()}")
    changed: set[str] = set()
    for line in status.stdout.splitlines():
        if len(line) < 4:
            raise WorkflowError("无法解析 Git 工作区状态")
        changed.add(line[3:])
    unexpected = changed - set(allowed_paths)
    if unexpected:
        raise WorkflowError(
            f"{operation} 除明确允许的状态文件外要求干净工作区；"
            f"请先处理：{', '.join(sorted(unexpected))}"
        )
    return run_git("rev-parse", "HEAD").stdout.strip()


def ref_exists(ref: str) -> bool:
    return run_git("show-ref", "--verify", "--quiet", ref, check=False).returncode == 0


def commit_scoped_changes(
    message: str,
    required_paths: Iterable[str],
    allowed_paths: Iterable[str],
    scope_label: str,
) -> str:
    required = set(required_paths)
    allowed = set(allowed_paths) | required
    add = run_git("add", "--", *sorted(allowed), check=False)
    if add.returncode != 0:
        raise WorkflowError(f"无法暂存{scope_label}：{add.stderr.strip()}")
    staged_result = run_git(
        "-c", "core.quotePath=false", "diff", "--cached", "--name-only", check=False
    )
    if staged_result.returncode != 0:
        raise WorkflowError(f"无法核对{scope_label}提交范围：{staged_result.stderr.strip()}")
    staged = {line.strip() for line in staged_result.stdout.splitlines() if line.strip()}
    if not required.issubset(staged) or not staged.issubset(allowed):
        raise WorkflowError(
            f"{scope_label}提交范围异常；必须包含 "
            f"{', '.join(sorted(required))}，且不得包含其他文件"
        )
    commit = run_git("commit", "-m", message, check=False)
    if commit.returncode != 0:
        raise WorkflowError(f"无法提交{scope_label}：{commit.stderr.strip()}")
    return run_git("rev-parse", "HEAD").stdout.strip()


def commit_lease_and_create_branch(
    task_id: str,
    generation: int,
    owner: str,
    branch: str,
    environment_path: Path,
    task_spec_path: Path | None = None,
) -> str:
    if ref_exists(f"refs/heads/{branch}") or ref_exists(f"refs/remotes/origin/{branch}"):
        raise WorkflowError(f"任务分支已存在，拒绝覆盖：{branch}")
    task_path = TASKS_JSON.relative_to(ROOT).as_posix()
    task_md_path = TASKS_MD.relative_to(ROOT).as_posix()
    env_path = environment_path.relative_to(ROOT).as_posix()
    required = {task_path, task_md_path}
    allowed = {task_path, task_md_path, env_path}
    if task_spec_path is not None:
        spec_path = task_spec_path.relative_to(ROOT).as_posix()
        required.add(spec_path)
        allowed.add(spec_path)
    message = f"lease {task_id} g{generation} @ {owner}"
    lease_commit = commit_scoped_changes(
        message,
        required,
        allowed,
        "环境快照与租约台账",
    )
    create = run_git("branch", branch, lease_commit, check=False)
    if create.returncode != 0:
        raise WorkflowError(
            f"租约提交 {lease_commit} 已创建，但分支创建失败：{create.stderr.strip()}"
        )
    return lease_commit


def assert_environment_capabilities(
    machine_id: str,
    required_capabilities: Iterable[str],
    now: datetime,
    subject: str,
) -> Path:
    env_path = ENV_DIR / f"{machine_id}.json"
    if not env_path.is_file():
        raise WorkflowError(f"缺少{subject}环境快照：{env_path.relative_to(ROOT)}")
    env = read_json(env_path)
    label = str(env_path.relative_to(ROOT))
    schema_errors = validate_named_schema(env, "environment.schema.json", label)
    if schema_errors:
        raise WorkflowError("；".join(schema_errors))
    if env.get("machine_id") != machine_id:
        raise WorkflowError(f"{subject}环境快照 machine_id 不一致")
    checked_at = parse_iso_z(env["checked_at"])
    if checked_at > now:
        raise WorkflowError(
            f"{subject}环境快照 checked_at 来自未来；"
            "请先同步系统时钟再重新运行 env-check --publish"
        )
    if now - checked_at > timedelta(minutes=ENV_FRESHNESS_MINUTES):
        raise WorkflowError(
            f"{subject}环境快照已超过 {ENV_FRESHNESS_MINUTES} 分钟；"
            "请重新运行 env-check --publish"
        )
    capabilities = env.get("capabilities", {})
    missing = [name for name in required_capabilities if not capabilities.get(name)]
    if missing:
        raise WorkflowError(f"{subject}缺少任务能力：{', '.join(missing)}")
    return env_path


def assert_owner_capabilities(
    task: dict[str, Any], owner: str, now: datetime
) -> Path:
    return assert_environment_capabilities(
        owner_machine(owner),
        task.get("required_capabilities", []),
        now,
        "负责人",
    )


def current_coordinator_environment_path(now: datetime | None = None) -> Path:
    config, errors = load_local_config()
    if errors:
        raise WorkflowError("无法确定主调度器环境：" + "；".join(errors))
    machine_id = config.get("machine_id")
    if not isinstance(machine_id, str) or not machine_id:
        raise WorkflowError("无法确定主调度器 machine_id")
    return assert_environment_capabilities(
        machine_id,
        ("static_validation",),
        now or utc_now(),
        "主调度器",
    )


def lifecycle_preflight(
    operation: str, extra_allowed_paths: Iterable[str] = ()
) -> tuple[Path, str]:
    environment_path = current_coordinator_environment_path()
    environment_relative = environment_path.relative_to(ROOT).as_posix()
    allowed = set(extra_allowed_paths) | {environment_relative}
    main_head = require_clean_main(allowed, operation)
    return environment_path, main_head


def commit_task_state(
    task_id: str,
    generation: int,
    action: str,
    environment_path: Path,
    required_artifacts: Iterable[Path] = (),
    optional_artifacts: Iterable[Path] = (),
) -> str:
    task_path = TASKS_JSON.relative_to(ROOT).as_posix()
    task_md_path = TASKS_MD.relative_to(ROOT).as_posix()
    env_path = environment_path.relative_to(ROOT).as_posix()
    required = {task_path, task_md_path}
    required.update(path.relative_to(ROOT).as_posix() for path in required_artifacts)
    allowed = required | {env_path}
    allowed.update(path.relative_to(ROOT).as_posix() for path in optional_artifacts)
    return commit_scoped_changes(
        f"{action} {task_id} g{generation}",
        required,
        allowed,
        f"任务 {task_id} {action} 状态",
    )


def resolve_task_branch_tip(branch: str) -> str:
    local_ref = f"refs/heads/{branch}"
    remote_ref = f"refs/remotes/origin/{branch}"
    local = run_git("rev-parse", "--verify", local_ref, check=False)
    remote = run_git("rev-parse", "--verify", remote_ref, check=False)
    local_tip = local.stdout.strip() if local.returncode == 0 else None
    remote_tip = remote.stdout.strip() if remote.returncode == 0 else None
    if local_tip and remote_tip and local_tip != remote_tip:
        raise WorkflowError(
            f"本地与 origin 任务分支 tip 不一致："
            f"{local_ref}={local_tip}，{remote_ref}={remote_tip}"
        )
    tip = local_tip or remote_tip
    if not tip:
        raise WorkflowError(
            f"记录的任务分支不存在：{branch}；"
            "跨机交接请先显式执行 git fetch origin"
        )
    return tip


def task_assign(args: argparse.Namespace) -> int:
    data = load_tasks()
    task = find_task(data, args.id)
    if task.get("status") not in {"todo", "stale"}:
        raise WorkflowError(f"任务 {args.id} 当前状态不可分配：{task.get('status')}")
    tasks = task_index(data)
    incomplete = [
        dep for dep in task.get("dependencies", []) if tasks[dep].get("status") != "done"
    ]
    if incomplete:
        raise WorkflowError(f"任务依赖尚未完成：{', '.join(incomplete)}")
    now = parse_iso_z(args.now) if args.now else utc_now()
    environment_path = assert_owner_capabilities(task, args.owner, now)
    environment_relative = environment_path.relative_to(ROOT).as_posix()
    base_commit = require_clean_main({environment_relative}, "task assign")
    task_spec_path = resolve_task_spec_inputs(args.id, base_commit)
    generation = int(task.get("lease_generation", 0))
    if generation == 0:
        generation = 1
    task.update(
        {
            "status": "in_progress",
            "owner": args.owner,
            "lease_generation": generation,
            "branch": f"task/{args.id}-g{generation}",
            "base_commit": base_commit,
            "head_commit": None,
            "checkpoint_commit": base_commit,
            "failure_count": 0,
            "failure_stage": None,
            "stage_failure_count": 0,
            "claimed_at": iso_z(now),
            "heartbeat_at": iso_z(now),
            "lease_expires_at": iso_z(now + timedelta(hours=data["policy"]["lease_hours"])),
            "blocker": None,
        }
    )
    write_json(TASKS_JSON, data)
    TASKS_MD.write_text(render_tasks(data), encoding="utf-8", newline="\n")
    lease_commit = commit_lease_and_create_branch(
        args.id,
        generation,
        args.owner,
        task["branch"],
        environment_path,
        task_spec_path,
    )
    print(
        f"已分配 {args.id} → {args.owner}，generation={generation}，"
        f"branch={task['branch']}，lease_commit={lease_commit}"
    )
    return 0


def task_heartbeat(args: argparse.Namespace) -> int:
    data = load_tasks()
    task = find_task(data, args.id)
    if task.get("status") != "in_progress":
        raise WorkflowError(f"任务不在进行中：{args.id}")
    if int(task.get("lease_generation", -1)) != args.generation:
        raise WorkflowError("隔离令牌已过期，拒绝心跳")
    now = parse_iso_z(args.now) if args.now else utc_now()
    if parse_iso_z(task["lease_expires_at"]) < now:
        raise WorkflowError("租约已经过期；必须由主调度器先执行 reclaim-stale")
    task["heartbeat_at"] = iso_z(now)
    task["lease_expires_at"] = iso_z(now + timedelta(hours=data["policy"]["lease_hours"]))
    write_json(TASKS_JSON, data)
    TASKS_MD.write_text(render_tasks(data), encoding="utf-8", newline="\n")
    print(f"已续租 {args.id} generation={args.generation}")
    return 0


def task_reclaim(args: argparse.Namespace) -> int:
    data = load_tasks()
    now = parse_iso_z(args.now) if args.now else utc_now()
    reclaimed: list[str] = []
    for task in data.get("tasks", []):
        if task.get("status") != "in_progress" or not task.get("lease_expires_at"):
            continue
        if parse_iso_z(task["lease_expires_at"]) >= now:
            continue
        old_owner = task.get("owner")
        task.update(
            {
                "status": "stale",
                "previous_owner": old_owner,
                "owner": None,
                "lease_generation": int(task.get("lease_generation", 0)) + 1,
                "branch": None,
                "claimed_at": None,
                "heartbeat_at": None,
                "lease_expires_at": None,
                "head_commit": None,
                "blocker": f"租约于 {iso_z(now)} 自动回收；旧负责人={old_owner}",
            }
        )
        reclaimed.append(task["id"])
    write_json(TASKS_JSON, data)
    TASKS_MD.write_text(render_tasks(data), encoding="utf-8", newline="\n")
    print("已回收：" + (", ".join(reclaimed) if reclaimed else "无"))
    return 0


def task_handoff(args: argparse.Namespace) -> int:
    environment_path, _ = lifecycle_preflight("task handoff")
    data = load_tasks()
    task = find_task(data, args.id)
    if task.get("status") != "in_progress":
        raise WorkflowError(f"任务不在进行中：{args.id}")
    if int(task.get("lease_generation", -1)) != args.generation:
        raise WorkflowError("隔离令牌已过期，拒绝交接")
    if parse_iso_z(task["lease_expires_at"]) < utc_now():
        raise WorkflowError("租约已经过期；必须由主调度器先执行 reclaim-stale")
    if not SHA_RE.fullmatch(args.head):
        raise WorkflowError("head 必须是40位小写 Git SHA")
    base = task.get("base_commit")
    if not isinstance(base, str) or not SHA_RE.fullmatch(base):
        raise WorkflowError("任务 base_commit 无效")
    for label, commit in (("base", base), ("head", args.head)):
        exists = run_git("cat-file", "-e", f"{commit}^{{commit}}", check=False)
        if exists.returncode != 0:
            raise WorkflowError(f"{label} 提交在当前仓库中不存在：{commit}")
    ancestor = run_git("merge-base", "--is-ancestor", base, args.head, check=False)
    if ancestor.returncode != 0:
        raise WorkflowError("head 不是 base 的后代，拒绝交接")
    branch_tip = resolve_task_branch_tip(task["branch"])
    if branch_tip != args.head:
        raise WorkflowError(
            f"head 不是任务分支 tip：{task['branch']}={branch_tip}"
        )
    actual_files = sorted(changed_files(base, args.head))
    if not actual_files:
        raise WorkflowError("base..head 没有任何变更，拒绝空交接")
    declared_files = sorted(set(args.changed_file))
    if declared_files and declared_files != actual_files:
        raise WorkflowError("--changed-file 与 base..head 的实际变更文件不一致")
    spec = load_task_spec(args.id)
    if spec is not None:
        declared_outputs = set(spec.get("outputs") or [])
        out_of_scope = sorted(set(actual_files) - declared_outputs)
        if out_of_scope:
            raise WorkflowError(
                "base..head 存在任务书 outputs 之外的文件（scope 强制，D-20260811-021）："
                + ", ".join(out_of_scope)
            )
        limits = task_spec_limits(spec)
        max_files = limits.get("max_files")
        if isinstance(max_files, int) and len(actual_files) > max_files:
            raise WorkflowError(
                f"变更文件数 {len(actual_files)} 超过 limits.max_files={max_files}"
            )
    handoff = {
        "schema_version": 1,
        "task_id": args.id,
        "lease_generation": args.generation,
        "branch": task["branch"],
        "base_commit": task["base_commit"],
        "head_commit": args.head,
        "decision_ids": task.get("decision_ids", []),
        "submitted_at": iso_z(utc_now()),
        "changed_files": actual_files,
        "notes": args.notes,
    }
    handoff_path = HANDOFF_DIR / f"{args.id}-g{args.generation}.json"
    write_json(handoff_path, handoff)
    task["status"] = "pending_validation"
    task["head_commit"] = args.head
    task["handoff"] = str(handoff_path.relative_to(ROOT))
    task["lease_expires_at"] = None
    write_json(TASKS_JSON, data)
    TASKS_MD.write_text(render_tasks(data), encoding="utf-8", newline="\n")
    state_commit = commit_task_state(
        args.id,
        args.generation,
        "handoff",
        environment_path,
        required_artifacts=(handoff_path,),
    )
    print(
        f"已登记交接：{handoff_path.relative_to(ROOT)}；"
        f"state_commit={state_commit}"
    )
    return 0


def checked_report_path(value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        raise WorkflowError("审查报告必须使用工作区相对路径")
    candidate = (ROOT / path).resolve()
    review_root = (ROOT / "协作" / "审查记录").resolve()
    try:
        candidate.relative_to(review_root)
    except ValueError as exc:
        raise WorkflowError("审查报告必须位于 协作/审查记录/") from exc
    if not candidate.is_file():
        raise WorkflowError(f"审查报告不存在：{value}")
    return candidate.relative_to(ROOT).as_posix()


def assert_task_generation(task: dict[str, Any], generation: int) -> None:
    if int(task.get("lease_generation", -1)) != generation:
        raise WorkflowError("隔离令牌已过期，拒绝操作")


def load_task_spec(task_id: str) -> dict[str, Any] | None:
    path = TASK_SPEC_DIR / f"{task_id}.json"
    if not path.is_file():
        return None
    try:
        data = read_json(path)
    except WorkflowError:
        return None
    return data if isinstance(data, dict) else None


def resolve_task_spec_inputs(task_id: str, base_commit: str) -> Path | None:
    """Resolve dynamic task inputs before the lease commit is created."""
    path = TASK_SPEC_DIR / f"{task_id}.json"
    if not path.is_file():
        return None
    data = read_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("inputs"), dict):
        raise WorkflowError(f"{path.relative_to(ROOT)}: inputs 无效")
    snapshot = snapshot_metadata()
    if snapshot is None:
        raise WorkflowError("当前受控快照无效，无法解析任务书输入")
    fingerprint = snapshot.get("source", {}).get("fingerprint")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise WorkflowError("当前受控快照缺少有效 fingerprint")
    if not SHA_RE.fullmatch(base_commit):
        raise WorkflowError("无法解析任务书 base_commit")
    data["inputs"]["snapshot_fingerprint"] = fingerprint
    data["inputs"]["base_commit"] = base_commit
    write_json(path, data)
    return path


def task_spec_limits(spec: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(spec, dict) or not isinstance(spec.get("limits"), dict):
        return {}
    return spec["limits"]


def rollback_task_branch(task: dict[str, Any], now: datetime, reason: str) -> None:
    checkpoint = task.get("checkpoint_commit")
    branch = task.get("branch")
    new_generation = int(task.get("lease_generation", 0)) + 1
    if isinstance(checkpoint, str) and SHA_RE.fullmatch(checkpoint) and branch:
        new_branch = f"task/{task['id']}-g{new_generation}"
        created = run_git("branch", "-f", new_branch, checkpoint, check=False)
        if created.returncode == 0:
            task["branch"] = new_branch
            rollback_note = f"已回滚：分支 {new_branch} 重置至 checkpoint={checkpoint}"
        else:
            rollback_note = "分支重置失败，仅递增代数使旧交付失效"
    else:
        rollback_note = "无有效 checkpoint，仅递增代数使旧交付失效"
    task.update(
        {
            "status": "in_progress",
            "lease_generation": new_generation,
            "head_commit": None,
            "handoff": None,
            "heartbeat_at": iso_z(now),
            "lease_expires_at": iso_z(now + timedelta(hours=LEASE_HOURS)),
            "blocker": f"{reason}；{rollback_note}；代数递增至 g{new_generation}",
        }
    )


def reopen_task(
    task: dict[str, Any],
    data: dict[str, Any],
    now: datetime,
    reason: str,
    stage: str | None = None,
) -> None:
    spec = load_task_spec(task["id"])
    limits = task_spec_limits(spec)
    max_retries = limits.get("max_retries", 3)
    max_same_error = limits.get("max_same_error")
    failure_count = int(task.get("failure_count", 0)) + 1
    prev_stage = task.get("failure_stage")
    stage_count = int(task.get("stage_failure_count", 0)) + 1 if prev_stage == stage else 1
    task["failure_count"] = failure_count
    task["failure_stage"] = stage
    task["stage_failure_count"] = stage_count
    over_limit = failure_count >= max_retries or bool(
        max_same_error and stage_count >= max_same_error
    )
    if over_limit:
        task.update(
            {
                "status": "blocked",
                "lease_expires_at": None,
                "head_commit": None,
                "handoff": None,
                "blocker": (
                    f"{reason}；连续失败 {failure_count} 次"
                    f"（{stage} 阶段连续 {stage_count} 次），达到 limits 上限，"
                    "停止并保存现场（FAIL）"
                ),
            }
        )
        return
    if spec and spec.get("revert_on_fail"):
        rollback_task_branch(task, now, reason)
        return
    task.update(
        {
            "status": "in_progress",
            "heartbeat_at": iso_z(now),
            "lease_expires_at": iso_z(now + timedelta(hours=data["policy"]["lease_hours"])),
            "head_commit": None,
            "handoff": None,
            "blocker": reason,
        }
    )


def advance_checkpoint(task: dict[str, Any]) -> None:
    spec = load_task_spec(task["id"])
    if spec is not None and spec.get("checkpoint_policy") == "manual":
        return
    head = task.get("head_commit")
    if isinstance(head, str) and SHA_RE.fullmatch(head):
        task["checkpoint_commit"] = head


def reset_failure_counters(task: dict[str, Any]) -> None:
    task["failure_count"] = 0
    task["failure_stage"] = None
    task["stage_failure_count"] = 0


def task_validation_result(args: argparse.Namespace) -> int:
    report = checked_report_path(args.report)
    report_path = ROOT / report
    environment_path, _ = lifecycle_preflight(
        "task validation-result", (report,)
    )
    data = load_tasks()
    task = find_task(data, args.id)
    if task.get("status") != "pending_validation":
        raise WorkflowError(f"任务不在待验证状态：{args.id}")
    assert_task_generation(task, args.generation)
    task["validation_report"] = report
    if args.result == "pass":
        task["status"] = "pending_test" if args.requires_load_test else "ready_to_merge"
        task["blocker"] = None
        reset_failure_counters(task)
        advance_checkpoint(task)
    else:
        now = parse_iso_z(args.now) if args.now else utc_now()
        reopen_task(task, data, now, f"验证失败：{report}", stage="validation")
    write_json(TASKS_JSON, data)
    TASKS_MD.write_text(render_tasks(data), encoding="utf-8", newline="\n")
    state_commit = commit_task_state(
        args.id,
        args.generation,
        f"validation-{args.result}",
        environment_path,
        optional_artifacts=(report_path,),
    )
    print(
        f"已登记验证结果：{args.id} -> {task['status']}；"
        f"state_commit={state_commit}"
    )
    return 0


def task_test_result(args: argparse.Namespace) -> int:
    report = checked_report_path(args.report)
    report_path = ROOT / report
    environment_path, _ = lifecycle_preflight("task test-result", (report,))
    data = load_tasks()
    task = find_task(data, args.id)
    if task.get("status") != "pending_test":
        raise WorkflowError(f"任务不在待测试状态：{args.id}")
    assert_task_generation(task, args.generation)
    task["test_report"] = report
    if args.result == "pass":
        task["status"] = "ready_to_merge"
        task["blocker"] = None
        reset_failure_counters(task)
        advance_checkpoint(task)
    else:
        now = parse_iso_z(args.now) if args.now else utc_now()
        reopen_task(task, data, now, f"加载测试失败：{report}", stage="test")
    write_json(TASKS_JSON, data)
    TASKS_MD.write_text(render_tasks(data), encoding="utf-8", newline="\n")
    state_commit = commit_task_state(
        args.id,
        args.generation,
        f"test-{args.result}",
        environment_path,
        optional_artifacts=(report_path,),
    )
    print(
        f"已登记测试结果：{args.id} -> {task['status']}；"
        f"state_commit={state_commit}"
    )
    return 0


def task_complete(args: argparse.Namespace) -> int:
    environment_path, main_head = lifecycle_preflight("task complete")
    data = load_tasks()
    task = find_task(data, args.id)
    if task.get("status") != "ready_to_merge":
        raise WorkflowError(f"任务不在待合并状态：{args.id}")
    assert_task_generation(task, args.generation)
    head = task.get("head_commit")
    if not isinstance(head, str) or not SHA_RE.fullmatch(head):
        raise WorkflowError("任务 head_commit 无效")
    merged = run_git("merge-base", "--is-ancestor", head, main_head, check=False)
    if merged.returncode != 0:
        raise WorkflowError("任务 head 尚未进入 main，拒绝标记完成")
    task.update(
        {
            "status": "done",
            "heartbeat_at": None,
            "lease_expires_at": None,
            "blocker": None,
        }
    )
    write_json(TASKS_JSON, data)
    TASKS_MD.write_text(render_tasks(data), encoding="utf-8", newline="\n")
    state_commit = commit_task_state(
        args.id,
        args.generation,
        "complete",
        environment_path,
    )
    print(
        f"已确认 {args.id} head 进入 main，状态 -> done；"
        f"state_commit={state_commit}"
    )
    return 0


def task_checkpoint(args: argparse.Namespace) -> int:
    environment_path, _ = lifecycle_preflight("task checkpoint")
    data = load_tasks()
    task = find_task(data, args.id)
    if task.get("status") not in {"in_progress", "pending_validation", "pending_test"}:
        raise WorkflowError(f"任务 {args.id} 当前状态不可登记 checkpoint：{task.get('status')}")
    assert_task_generation(task, args.generation)
    commit = args.commit
    if not isinstance(commit, str) or not SHA_RE.fullmatch(commit):
        raise WorkflowError("checkpoint 必须是40位小写 Git SHA")
    exists = run_git("cat-file", "-e", f"{commit}^{{commit}}", check=False)
    if exists.returncode != 0:
        raise WorkflowError(f"checkpoint 提交在当前仓库中不存在：{commit}")
    base = task.get("base_commit")
    if not isinstance(base, str) or not SHA_RE.fullmatch(base):
        raise WorkflowError("任务 base_commit 无效")
    ancestor = run_git("merge-base", "--is-ancestor", base, commit, check=False)
    if ancestor.returncode != 0:
        raise WorkflowError("checkpoint 必须是 base_commit 的后代")
    task["checkpoint_commit"] = commit
    write_json(TASKS_JSON, data)
    TASKS_MD.write_text(render_tasks(data), encoding="utf-8", newline="\n")
    state_commit = commit_task_state(
        args.id,
        args.generation,
        "checkpoint",
        environment_path,
    )
    print(
        f"已登记 {args.id} checkpoint={commit}；"
        f"state_commit={state_commit}"
    )
    return 0


def validate_tasks(errors: list[str]) -> None:
    try:
        data = load_tasks()
        tasks = task_index(data)
    except WorkflowError as exc:
        errors.append(str(exc))
        return
    errors.extend(validate_named_schema(data, "tasks.schema.json", "协作/tasks.json"))
    policy = data.get("policy", {})
    if data.get("schema_version") != 1:
        errors.append("tasks.json schema_version 必须是 1")
    if policy.get("coordinator") != "main_agent_only":
        errors.append("tasks.json policy.coordinator 必须是 main_agent_only")
    if policy.get("lease_hours") != LEASE_HOURS:
        errors.append(f"tasks.json lease_hours 必须是 {LEASE_HOURS}")
    for task_id, task in tasks.items():
        status = task.get("status")
        if status not in TASK_STATUSES:
            errors.append(f"{task_id}: 未知状态 {status!r}")
        generation = task.get("lease_generation")
        if not isinstance(generation, int) or generation < 0:
            errors.append(f"{task_id}: lease_generation 必须是非负整数")
        for dep in task.get("dependencies", []):
            if dep not in tasks:
                errors.append(f"{task_id}: 未知依赖 {dep}")
        unknown_capabilities = set(task.get("required_capabilities", [])) - set(CAPABILITY_KEYS)
        if unknown_capabilities:
            errors.append(f"{task_id}: 未知能力 {sorted(unknown_capabilities)}")
        if status == "in_progress":
            for field in ("owner", "branch", "base_commit", "claimed_at", "heartbeat_at", "lease_expires_at"):
                if not task.get(field):
                    errors.append(f"{task_id}: 进行中任务缺少 {field}")
            if task.get("branch") != f"task/{task_id}-g{generation}":
                errors.append(f"{task_id}: 分支名与隔离代数不一致")
            if task.get("base_commit") and not SHA_RE.fullmatch(task["base_commit"]):
                errors.append(f"{task_id}: base_commit 无效")
            for field in ("claimed_at", "heartbeat_at", "lease_expires_at"):
                if task.get(field):
                    try:
                        parse_iso_z(task[field])
                    except WorkflowError as exc:
                        errors.append(f"{task_id}: {exc}")
        if status in {"pending_validation", "pending_test", "ready_to_merge"}:
            for field in ("branch", "base_commit", "head_commit", "handoff"):
                if not task.get(field):
                    errors.append(f"{task_id}: {status} 任务缺少 {field}")
            if task.get("lease_expires_at") is not None:
                errors.append(f"{task_id}: {status} 任务不应保留活动租约")
        if status in {"pending_test", "ready_to_merge"} and not task.get("validation_report"):
            errors.append(f"{task_id}: {status} 任务缺少 validation_report")
        for decision_id in task.get("decision_ids", []):
            if not (DECISION_DIR / f"{decision_id}.json").is_file():
                errors.append(f"{task_id}: 决策记录不存在 {decision_id}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            errors.append(f"tasks.json 存在循环依赖：{task_id}")
            return
        if task_id in visited:
            return
        visiting.add(task_id)
        for dep in tasks[task_id].get("dependencies", []):
            if dep in tasks:
                visit(dep)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in tasks:
        visit(task_id)
    rendered = render_tasks(data)
    actual = TASKS_MD.read_text(encoding="utf-8") if TASKS_MD.is_file() else ""
    if actual != rendered:
        errors.append("协作/任务台账.md 不是由当前 tasks.json 生成")


def validate_environment(errors: list[str]) -> None:
    seen: set[str] = set()
    for path in sorted(ENV_DIR.glob("*.json")):
        try:
            data = read_json(path)
        except WorkflowError as exc:
            errors.append(str(exc))
            continue
        errors.extend(
            validate_named_schema(data, "environment.schema.json", str(path.relative_to(ROOT)))
        )
        machine_id = data.get("machine_id")
        if data.get("schema_version") != 1:
            errors.append(f"{path.relative_to(ROOT)}: schema_version 必须是 1")
        if machine_id != path.stem:
            errors.append(f"{path.relative_to(ROOT)}: machine_id 必须等于文件名")
        if machine_id in seen:
            errors.append(f"重复 machine_id：{machine_id}")
        seen.add(machine_id)
        if data.get("profile") not in {"light", "partial", "full"}:
            errors.append(f"{path.relative_to(ROOT)}: profile 无效")
        caps = data.get("capabilities", {})
        for key in CAPABILITY_KEYS:
            if not isinstance(caps.get(key), bool):
                errors.append(f"{path.relative_to(ROOT)}: capability.{key} 必须是布尔值")
        expected_profile = (
            "full"
            if all(caps.get(name) is True for name in ("snapshot_export", "mod_execution", "load_test"))
            else "partial"
            if any(caps.get(name) is True for name in ("snapshot_export", "mod_execution", "load_test"))
            else "light"
        )
        if data.get("profile") != expected_profile:
            errors.append(f"{path.relative_to(ROOT)}: profile 与分项能力不一致")
        if not isinstance(data.get("checked_at"), str) or not ISO_Z_RE.fullmatch(data["checked_at"]):
            errors.append(f"{path.relative_to(ROOT)}: checked_at 格式无效")
        path_hits = absolute_path_strings(data)
        if path_hits:
            errors.append(
                f"{path.relative_to(ROOT)}: 包含绝对路径片段 {sorted(path_hits)!r}"
            )


def validate_snapshot(errors: list[str]) -> None:
    if not SNAPSHOT_JSON.is_file():
        if SNAPSHOT_MD.is_file():
            errors.append("协作/扫描快照/states-summary.md 存在，但缺少 states.json")
        return
    try:
        data = read_json(SNAPSHOT_JSON)
    except WorkflowError as exc:
        errors.append(str(exc))
        return
    errors.extend(
        validate_named_schema(data, "snapshot.schema.json", "协作/扫描快照/states.json")
    )
    snapshot_errors = snapshot_data_errors(data)
    for error in snapshot_errors:
        errors.append(f"协作/扫描快照/states.json: {error}")
    if snapshot_errors:
        return
    expected = render_snapshot_summary(data)
    actual = SNAPSHOT_MD.read_text(encoding="utf-8") if SNAPSHOT_MD.is_file() else ""
    if actual != expected:
        errors.append("协作/扫描快照/states-summary.md 不是由当前 states.json 生成")


def validate_state_overrides(errors: list[str]) -> None:
    documents: list[dict[str, Any]] = []
    for path in sorted(STATE_OVERRIDE_DIR.glob("*.json")):
        label = str(path.relative_to(ROOT))
        try:
            data = read_json(path)
        except WorkflowError as exc:
            errors.append(str(exc))
            continue
        schema_errors = validate_named_schema(data, "state-overrides.schema.json", label)
        semantic_errors = state_transform.validate_override_document(data)
        errors.extend(schema_errors)
        errors.extend(f"{label}: {item}" for item in semantic_errors)
        if isinstance(data, dict):
            decision_id = data.get("decision_id")
            if not isinstance(decision_id, str) or not (DECISION_DIR / f"{decision_id}.json").is_file():
                errors.append(f"{label}: decision_id 对应的决策记录不存在")
            if not schema_errors and not semantic_errors:
                documents.append(data)
    if not documents:
        return
    fingerprints = {item["source_fingerprint"] for item in documents}
    if len(fingerprints) != 1:
        errors.append("协作/state-overrides/: 所有改写清单必须绑定同一快照指纹")
        return
    fingerprint = next(iter(fingerprints))
    try:
        state_transform.merge_override_documents(documents, fingerprint)
    except state_transform.StateTransformError as exc:
        errors.append(f"协作/state-overrides/: {exc}")
    snapshot = snapshot_metadata()
    if snapshot is not None and snapshot["source"]["fingerprint"] != fingerprint:
        errors.append("协作/state-overrides/: 改写清单指纹与当前受控快照不一致")


def validate_task_specs(errors: list[str]) -> None:
    """Validate the minimal task specification layer (D-20260811-020).

    Each spec must match its filename, reference an existing task, and once a
    task has left `todo` the dynamic input fields (snapshot fingerprint and
    base commit) must be resolved to real values.
    """
    if not TASK_SPEC_DIR.is_dir():
        return
    task_data = load_tasks()
    tasks = task_index(task_data)
    for path in sorted(TASK_SPEC_DIR.glob("T-*.json")):
        try:
            label = str(path.relative_to(ROOT))
        except ValueError:
            label = path.name
        try:
            data = read_json(path)
        except WorkflowError as exc:
            errors.append(str(exc))
            continue
        schema_errors = validate_named_schema(data, "task-spec.schema.json", label)
        errors.extend(schema_errors)
        if schema_errors or not isinstance(data, dict):
            continue
        if data.get("spec_id") != path.stem:
            errors.append(f"{label}: spec_id 必须等于文件名")
            continue
        task = tasks.get(path.stem)
        if task is None:
            errors.append(f"{label}: 对应任务不存在于 tasks.json")
            continue
        status = task.get("status")
        if status not in (None, "todo"):
            inputs = data.get("inputs") or {}
            if not isinstance(inputs.get("snapshot_fingerprint"), str):
                errors.append(f"{label}: 任务已离开 todo，snapshot_fingerprint 必须已解析")
            if not isinstance(inputs.get("base_commit"), str):
                errors.append(f"{label}: 任务已离开 todo，base_commit 必须已解析")
        for entry in data.get("source_matrix", []):
            if entry.get("pending") and not status == "decision_required":
                errors.append(f"{label}: source_matrix 含待定项，任务应处于 decision_required")
    for path in sorted(TASK_SPEC_DIR.glob("*.json")):
        if not re.fullmatch(r"T-\d{3}\.json", path.name):
            errors.append(f"{path.relative_to(ROOT)}: 任务书文件名必须是 T-XXX.json")


def validate_decisions(errors: list[str]) -> None:
    for path in sorted(DECISION_DIR.glob("D-*.json")):
        try:
            data = read_json(path)
        except WorkflowError as exc:
            errors.append(str(exc))
            continue
        errors.extend(validate_named_schema(data, "decision.schema.json", str(path.relative_to(ROOT))))
        if data.get("decision_id") != path.stem:
            errors.append(f"{path.relative_to(ROOT)}: decision_id 必须等于文件名")
        if not isinstance(data.get("decisions"), list) or not data["decisions"]:
            errors.append(f"{path.relative_to(ROOT)}: decisions 必须是非空数组")
        if not isinstance(data.get("confirmed_at"), str) or not ISO_Z_RE.fullmatch(data["confirmed_at"]):
            errors.append(f"{path.relative_to(ROOT)}: confirmed_at 格式无效")
        if data.get("schema_version") != 1 or data.get("status") != "confirmed":
            errors.append(f"{path.relative_to(ROOT)}: 必须是 schema_version=1 的 confirmed 决策")
        for entry in data.get("resolved_pending", []):
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                continue
            if not decision_applies_to_paths(data, {entry["path"]}):
                errors.append(
                    f"{path.relative_to(ROOT)}: resolved_pending.path "
                    f"未被 affected_files 覆盖：{entry['path']}"
                )
        summary = path.with_suffix(".md")
        if not summary.is_file():
            errors.append(f"{path.relative_to(ROOT)}: 缺少同名 Markdown 摘要")


def validate_handoffs(errors: list[str]) -> None:
    task_data = load_tasks()
    tasks = task_index(task_data)
    for path in sorted(HANDOFF_DIR.glob("T-*-g*.json")):
        try:
            data = read_json(path)
        except WorkflowError as exc:
            errors.append(str(exc))
            continue
        errors.extend(validate_named_schema(data, "handoff.schema.json", str(path.relative_to(ROOT))))
        task = tasks.get(data.get("task_id"))
        if task is None:
            errors.append(f"{path.relative_to(ROOT)}: 对应任务不存在")
            continue
        if data.get("lease_generation") != task.get("lease_generation"):
            errors.append(f"{path.relative_to(ROOT)}: 隔离令牌已过期")
        if data.get("schema_version") != 1:
            errors.append(f"{path.relative_to(ROOT)}: schema_version 必须是 1")
        if data.get("branch") != task.get("branch"):
            errors.append(f"{path.relative_to(ROOT)}: branch 与任务不一致")
        if data.get("base_commit") != task.get("base_commit"):
            errors.append(f"{path.relative_to(ROOT)}: base_commit 与任务不一致")
        if data.get("head_commit") != task.get("head_commit"):
            errors.append(f"{path.relative_to(ROOT)}: head_commit 与任务不一致")
        if data.get("decision_ids") != task.get("decision_ids", []):
            errors.append(f"{path.relative_to(ROOT)}: decision_ids 与任务不一致")
        for field in ("base_commit", "head_commit"):
            if not isinstance(data.get(field), str) or not SHA_RE.fullmatch(data[field]):
                errors.append(f"{path.relative_to(ROOT)}: {field} 无效")
        if data.get("base_commit") == data.get("head_commit"):
            errors.append(f"{path.relative_to(ROOT)}: base/head 不得相同")
        base = data.get("base_commit")
        head = data.get("head_commit")
        if isinstance(base, str) and SHA_RE.fullmatch(base) and isinstance(head, str) and SHA_RE.fullmatch(head):
            try:
                actual_files = changed_files(base, head)
            except WorkflowError as exc:
                errors.append(f"{path.relative_to(ROOT)}: {exc}")
            else:
                declared = data.get("changed_files")
                if not isinstance(declared, list) or set(declared) != actual_files:
                    errors.append(f"{path.relative_to(ROOT)}: changed_files 与提交区间不一致")


def count_table_rows(text: str, start_heading: str, end_heading: str) -> int:
    start = text.find(start_heading)
    end = text.find(end_heading, start + 1)
    if start < 0 or end < 0:
        return -1
    section = text[start:end]
    count = 0
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and cells[0] not in {"政权", "----"} and not set(cells[0]) <= {"-", ":"}:
            count += 1
    return count


def interview_protocol_errors(protocol: str, adapter: str) -> list[str]:
    errors = [
        f"决策协议缺少 interview-me 规则锚点：{marker}"
        for marker in INTERVIEW_PROTOCOL_MARKERS
        if marker not in protocol
    ]
    if "协作/决策协议.md" not in adapter or "必须完整读取并执行" not in adapter:
        errors.append("teg-interview-me 必须完整引用跨工具中立协议")
    if len(adapter.splitlines()) > 12:
        errors.append("teg-interview-me 只能作为短适配器，不得复制第二套流程正文")
    return errors


def validate_static_files(errors: list[str]) -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    if ".opencode/opencode.json" not in gitignore:
        errors.append(".gitignore 必须忽略 .opencode/opencode.json")
    for name in ("scan", "verify"):
        text = (ROOT / ".opencode" / "agent" / f"{name}.md").read_text(encoding="utf-8")
        if '"git *": allow' in text:
            errors.append(f"{name} agent 禁止使用宽泛 git * 权限")
    execute = (ROOT / ".opencode" / "agent" / "execute.md").read_text(encoding="utf-8")
    if '"*": allow' in execute.split("bash:", 1)[0]:
        errors.append("execute agent 的 edit 权限不得默认 allow")
    if '"mod/*": allow' in execute or '"协作/state-overrides/*": allow' not in execute:
        errors.append("execute agent 只能提交受控 state 改写清单，不得直接写 mod")
    protocol = (ROOT / "协作" / "决策协议.md").read_text(encoding="utf-8")
    interview_adapter = (
        ROOT / ".opencode" / "skills" / "teg-interview-me" / "SKILL.md"
    ).read_text(encoding="utf-8")
    errors.extend(interview_protocol_errors(protocol, interview_adapter))
    scan_output = (ROOT / "协作" / "扫描产出.md").read_text(encoding="utf-8")
    reused = count_table_rows(scan_output, "### 复用原版 tag", "### 新建 tag")
    created = count_table_rows(scan_output, "### 新建 tag", "### 背景层处理")
    if reused != 25 or created != 13 or reused + created != 38:
        errors.append(f"tag 数量必须是复用25+新建13=38，实际 {reused}+{created}")
    hook_requirements = {
        "run-python": ("py -3", "python3"),
        "pre-commit": ("validate --staged", "unittest discover -s tests -v"),
        "pre-push": ("while read -r local_ref", "--base \"$base_sha\" --head \"$local_sha\""),
    }
    for name, markers in hook_requirements.items():
        path = ROOT / ".githooks" / name
        if not path.is_file():
            errors.append(f"缺少入库 Git hook：.githooks/{name}")
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                errors.append(f".githooks/{name} 缺少规则锚点：{marker}")
        if os.name != "nt" and not os.access(path, os.X_OK):
            errors.append(f".githooks/{name} 必须具有可执行权限")


def changed_files(base: str, head: str) -> set[str]:
    result = run_git(
        "-c", "core.quotePath=false", "diff", "--name-only", f"{base}..{head}", check=False
    )
    if result.returncode != 0:
        raise WorkflowError(f"无法读取变更范围：{result.stderr.strip()}")
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def normalized_task_registry(data: Any) -> Any:
    """Remove lease/runtime state while preserving task definitions and policy."""

    if not isinstance(data, dict):
        return data
    normalized = json.loads(json.dumps(data, ensure_ascii=False))
    tasks = normalized.get("tasks")
    if not isinstance(tasks, list):
        return normalized
    for task in tasks:
        if isinstance(task, dict):
            for field in TASK_LIFECYCLE_FIELDS:
                task.pop(field, None)
    return normalized


def git_json_at(commit: str, path: str) -> Any | None:
    result = run_git("show", f"{commit}:{path}", check=False)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"{commit}:{path} JSON 无效：{exc}") from exc


def task_registry_policy_changed(base: str, head: str) -> bool:
    before = git_json_at(base, "协作/tasks.json")
    after = git_json_at(head, "协作/tasks.json")
    if before is None or after is None:
        return before != after
    return normalized_task_registry(before) != normalized_task_registry(after)


def path_matches_pattern(path: str, pattern: str) -> bool:
    normalized = pattern.replace("\\", "/")
    return path == normalized or (normalized.endswith("/") and path.startswith(normalized))


def is_core_path(path: str) -> bool:
    return any(path_matches_pattern(path, pattern) for pattern in CORE_PATTERNS)


def decision_applies_to_paths(decision: Any, paths: set[str]) -> bool:
    if not isinstance(decision, dict):
        return False
    affected = decision.get("affected_files")
    if not isinstance(affected, list):
        return False
    return any(
        isinstance(pattern, str) and path_matches_pattern(path, pattern)
        for pattern in affected
        for path in paths
    )


def commits_in_range(base: str, head: str) -> list[str]:
    ancestor = run_git("merge-base", "--is-ancestor", base, head, check=False)
    if ancestor.returncode != 0:
        raise WorkflowError("--base 不是 --head 的祖先")
    result = run_git("rev-list", "--reverse", f"{base}..{head}", check=False)
    if result.returncode != 0:
        raise WorkflowError(f"无法枚举提交区间：{result.stderr.strip()}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def first_parent(commit: str) -> str:
    result = run_git("rev-parse", f"{commit}^1", check=False)
    if result.returncode != 0:
        raise WorkflowError(f"无法读取提交父节点：{commit}")
    return result.stdout.strip()


def added_revision_rows(parent: str, commit: str) -> list[str]:
    result = run_git(
        "-c",
        "core.quotePath=false",
        "diff",
        "--unified=0",
        parent,
        commit,
        "--",
        "设定书/00-总览与索引.md",
        check=False,
    )
    if result.returncode != 0:
        raise WorkflowError(f"无法读取00卷修订差异：{commit}")
    return [
        line[1:].strip()
        for line in result.stdout.splitlines()
        if line.startswith("+|") and not line.startswith("+++")
    ]


def staged_files() -> set[str]:
    result = run_git(
        "-c",
        "core.quotePath=false",
        "diff",
        "--cached",
        "--name-only",
        check=False,
    )
    if result.returncode != 0:
        raise WorkflowError(f"无法读取暂存区文件：{result.stderr.strip()}")
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def git_json_from_index(path: str) -> Any | None:
    result = run_git("show", f":{path}", check=False)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"暂存区:{path} JSON 无效：{exc}") from exc


def staged_task_registry_policy_changed() -> bool:
    before = git_json_at("HEAD", "协作/tasks.json")
    after = git_json_from_index("协作/tasks.json")
    if before is None or after is None:
        return before != after
    return normalized_task_registry(before) != normalized_task_registry(after)


def added_staged_revision_rows() -> list[str]:
    result = run_git(
        "-c",
        "core.quotePath=false",
        "diff",
        "--cached",
        "--unified=0",
        "--",
        "设定书/00-总览与索引.md",
        check=False,
    )
    if result.returncode != 0:
        raise WorkflowError("无法读取暂存区00卷修订差异")
    return [
        line[1:].strip()
        for line in result.stdout.splitlines()
        if line.startswith("+|") and not line.startswith("+++")
    ]


def normalize_pending_line(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def pending_marker_count(value: str) -> int:
    return len(PENDING_MARKER_RE.findall(value))


def pending_line_sha256(value: str) -> str:
    normalized = normalize_pending_line(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def pending_removals_from_diff(diff_text: str) -> list[PendingRemoval]:
    """Return pending-marker occurrences that semantically disappear in a diff.

    Exact moved lines cancel across hunks. Within one hunk, any added pending
    occurrence cancels one removed occurrence, so wording changes that preserve
    pending semantics are not treated as resolutions.
    """

    current_path: str | None = None
    hunk_removed: list[PendingRemoval] = []
    hunk_added: list[str] = []
    unmatched_removed: list[PendingRemoval] = []
    unmatched_added: list[str] = []

    def flush_hunk() -> None:
        if not hunk_removed and not hunk_added:
            return
        added_counts = Counter(hunk_added)
        remaining_removed: list[PendingRemoval] = []
        for removal in hunk_removed:
            normalized = normalize_pending_line(removal.excerpt)
            if added_counts[normalized] > 0:
                added_counts[normalized] -= 1
            else:
                remaining_removed.append(removal)
        remaining_added = [
            line
            for line, count in added_counts.items()
            for _ in range(count)
        ]
        generic_cancellations = min(len(remaining_removed), len(remaining_added))
        unmatched_removed.extend(remaining_removed[generic_cancellations:])
        unmatched_added.extend(remaining_added[generic_cancellations:])
        hunk_removed.clear()
        hunk_added.clear()

    for line in diff_text.splitlines():
        if line.startswith("--- "):
            flush_hunk()
            raw_path = line[4:]
            current_path = None if raw_path == "/dev/null" else raw_path.removeprefix("a/")
            continue
        if line.startswith("+++ "):
            continue
        if line.startswith("@@"):
            flush_hunk()
            continue
        if line.startswith("-") and not line.startswith("---") and current_path:
            content = line[1:]
            if not (current_path.startswith("Settings/") or current_path.startswith("设定书/")):
                continue
            for _ in range(pending_marker_count(content)):
                hunk_removed.append(
                    PendingRemoval(
                        path=current_path,
                        line_sha256=pending_line_sha256(content),
                        excerpt=normalize_pending_line(content),
                    )
                )
        elif line.startswith("+") and not line.startswith("+++"):
            content = line[1:]
            for _ in range(pending_marker_count(content)):
                hunk_added.append(normalize_pending_line(content))
    flush_hunk()

    added_counts = Counter(unmatched_added)
    result: list[PendingRemoval] = []
    for removal in unmatched_removed:
        normalized = normalize_pending_line(removal.excerpt)
        if added_counts[normalized] > 0:
            added_counts[normalized] -= 1
        else:
            result.append(removal)
    return result


def pending_removals_for_git_diff(*args: str) -> list[PendingRemoval]:
    result = run_git(
        "-c",
        "core.quotePath=false",
        "diff",
        "--no-ext-diff",
        "--unified=0",
        *args,
        "--",
        "Settings",
        "设定书",
        check=False,
    )
    if result.returncode != 0:
        raise WorkflowError(f"无法检查待定标记变化：{result.stderr.strip()}")
    return pending_removals_from_diff(result.stdout)


def validate_pending_resolutions(
    label: str,
    removals: Iterable[PendingRemoval],
    decisions: Iterable[dict[str, Any]],
    errors: list[str],
) -> None:
    needed = Counter((item.path, item.line_sha256) for item in removals)
    examples = {(item.path, item.line_sha256): item.excerpt for item in removals}
    authorized: Counter[tuple[str, str]] = Counter()
    for decision in decisions:
        entries = decision.get("resolved_pending", [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            line_sha256 = entry.get("line_sha256")
            occurrences = entry.get("occurrences", 1)
            if (
                isinstance(path, str)
                and isinstance(line_sha256, str)
                and type(occurrences) is int
                and occurrences > 0
                and decision_applies_to_paths(decision, {path})
            ):
                authorized[(path, line_sha256)] += occurrences
    for key, count in sorted(needed.items()):
        missing = count - authorized[key]
        if missing > 0:
            path, line_sha256 = key
            errors.append(
                f"{label}: 待定标记净消失缺少 resolved_pending 授权："
                f"{path} line_sha256={line_sha256} occurrences={missing}；"
                f"原行={examples[key][:160]!r}"
            )


def collect_historical_backfill() -> dict[str, str]:
    """Return {commit_sha: reason} for confirmed historical backfill exemptions.

    A committed decision record may declare `historical_backfill` entries to
    exempt specific pre-existing commits from the per-commit decision-JSON rule.
    This preserves full replayable validation without rewriting Git history:
    the exemption itself is an auditable, user-confirmed decision object.
    """

    mapping: dict[str, str] = {}
    for path in sorted(DECISION_DIR.glob("D-*.json")):
        try:
            data = read_json(path)
        except WorkflowError:
            continue
        if not isinstance(data, dict):
            continue
        entries = data.get("historical_backfill")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            commit = entry.get("commit")
            reason = entry.get("reason")
            if (
                isinstance(commit, str)
                and SHA_RE.fullmatch(commit)
                and isinstance(reason, str)
                and reason.strip()
            ):
                mapping[commit] = reason
    return mapping


def validate_commit_rules(base: str, head: str, errors: list[str]) -> None:
    backfill = collect_historical_backfill()
    for commit in commits_in_range(base, head):
        if commit in backfill:
            continue
        parent = first_parent(commit)
        files = changed_files(parent, commit)
        setting_files = {
            path
            for path in files
            if path.startswith("Settings/") or path.startswith("设定书/")
        }
        core_files = {path for path in files if is_core_path(path)}
        if "协作/tasks.json" in files and task_registry_policy_changed(parent, commit):
            core_files.add("协作/tasks.json")
        relevant_files = setting_files | core_files
        if not relevant_files:
            continue

        decision_paths = sorted(
            path
            for path in files
            if path.startswith("协作/决策记录/D-") and path.endswith(".json")
        )
        decisions: list[dict[str, Any]] = []
        for path in decision_paths:
            data = git_json_at(commit, path)
            if isinstance(data, dict):
                decisions.append(data)
        short = commit[:12]
        if not decisions:
            errors.append(f"{short}: 设定或协作核心变更必须同 commit 更新结构化决策 JSON")
            continue
        matching = [item for item in decisions if decision_applies_to_paths(item, relevant_files)]
        if not matching:
            errors.append(f"{short}: 决策 affected_files 与当前设定/核心变更无匹配")

        if setting_files:
            validate_pending_resolutions(
                short,
                pending_removals_for_git_diff(parent, commit),
                matching,
                errors,
            )
            index_path = "设定书/00-总览与索引.md"
            if index_path not in files:
                errors.append(f"{short}: 设定层变更必须同 commit 更新00卷修订记录")
                continue
            rows = added_revision_rows(parent, commit)
            decision_ids = {
                item.get("decision_id")
                for item in matching
                if isinstance(item.get("decision_id"), str)
            }
            if not rows:
                errors.append(f"{short}: 00卷必须新增修订记录表格行")
            elif not any(
                len([cell for cell in row.strip("|").split("|")]) >= 4
                and any(decision_id in row for decision_id in decision_ids)
                for row in rows
            ):
                errors.append(f"{short}: 00卷新增修订行必须含四列并引用当前 decision_id")


def validate_staged_commit_rules(errors: list[str]) -> None:
    files = staged_files()
    setting_files = {
        path for path in files if path.startswith("Settings/") or path.startswith("设定书/")
    }
    core_files = {path for path in files if is_core_path(path)}
    if "协作/tasks.json" in files and staged_task_registry_policy_changed():
        core_files.add("协作/tasks.json")
    relevant_files = setting_files | core_files
    if not relevant_files:
        return

    decision_paths = sorted(
        path
        for path in files
        if path.startswith("协作/决策记录/D-") and path.endswith(".json")
    )
    decisions = [
        data
        for path in decision_paths
        if isinstance((data := git_json_from_index(path)), dict)
    ]
    label = "暂存区"
    if not decisions:
        errors.append(f"{label}: 设定或协作核心变更必须同 commit 更新结构化决策 JSON")
        return
    matching = [item for item in decisions if decision_applies_to_paths(item, relevant_files)]
    if not matching:
        errors.append(f"{label}: 决策 affected_files 与当前设定/核心变更无匹配")

    if setting_files:
        validate_pending_resolutions(
            label,
            pending_removals_for_git_diff("--cached"),
            matching,
            errors,
        )
        index_path = "设定书/00-总览与索引.md"
        if index_path not in files:
            errors.append(f"{label}: 设定层变更必须同 commit 更新00卷修订记录")
            return
        rows = added_staged_revision_rows()
        decision_ids = {
            item.get("decision_id")
            for item in matching
            if isinstance(item.get("decision_id"), str)
        }
        if not rows:
            errors.append(f"{label}: 00卷必须新增修订记录表格行")
        elif not any(
            len([cell for cell in row.strip("|").split("|")]) >= 4
            and any(decision_id in row for decision_id in decision_ids)
            for row in rows
        ):
            errors.append(f"{label}: 00卷新增修订行必须含四列并引用当前 decision_id")


def validate_change_range(base: str, head: str, errors: list[str]) -> None:
    files = changed_files(base, head)
    if not files:
        return
    decision_changed = any(
        path.startswith("协作/决策记录/D-") and path.endswith(".json") for path in files
    )
    settings_changed = any(path.startswith("Settings/") or path.startswith("设定书/") for path in files)
    if settings_changed:
        if "设定书/00-总览与索引.md" not in files:
            errors.append("设定层变更必须同一变更范围更新 设定书/00-总览与索引.md")
        if not decision_changed:
            errors.append("设定层变更必须关联本次新增或更新的结构化决策记录")
    core_changed = any(is_core_path(path) for path in files)
    if "协作/tasks.json" in files and task_registry_policy_changed(base, head):
        core_changed = True
    if core_changed and not decision_changed:
        errors.append("协作核心规则变更必须关联结构化决策记录")
    validate_commit_rules(base, head, errors)


def validate(args: argparse.Namespace) -> int:
    errors: list[str] = []
    validate_tasks(errors)
    validate_task_specs(errors)
    validate_environment(errors)
    validate_snapshot(errors)
    validate_state_overrides(errors)
    validate_decisions(errors)
    validate_handoffs(errors)
    validate_static_files(errors)
    staged = bool(getattr(args, "staged", False))
    if staged and (args.base or args.head):
        errors.append("--staged 不得与 --base/--head 同时使用")
    elif staged:
        try:
            validate_staged_commit_rules(errors)
        except WorkflowError as exc:
            errors.append(str(exc))
    elif bool(args.base) != bool(args.head):
        errors.append("--base 与 --head 必须同时提供")
    elif args.base and args.head and args.base != "0" * 40:
        try:
            validate_change_range(args.base, args.head, errors)
        except WorkflowError as exc:
            errors.append(str(exc))
    if errors:
        print("WORKFLOW VALIDATION FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("WORKFLOW VALIDATION PASSED")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="天下与万邦跨工具工作流门禁")
    sub = parser.add_subparsers(dest="command", required=True)

    env_parser = sub.add_parser("env-check", help="校验本机环境并派生能力")
    env_parser.add_argument("--publish", action="store_true", help="写入脱敏的每机能力快照")
    env_parser.add_argument("--json", action="store_true", help="输出 JSON")
    env_parser.set_defaults(func=env_check)

    snapshot_parser = sub.add_parser("snapshot-export", help="从本体只读导出 state 元数据快照")
    snapshot_parser.set_defaults(func=snapshot_export)

    state_build_parser = sub.add_parser(
        "state-build", help="在受控 full/partial 机上生成完整 mod state 文件"
    )
    state_build_parser.add_argument(
        "--override",
        action="append",
        required=True,
        help="协作/state-overrides/ 下的仓库相对 JSON 路径；可重复",
    )
    state_build_parser.set_defaults(func=state_build)

    render_parser = sub.add_parser("render-tasks", help="从 tasks.json 生成 Markdown 台账")
    render_parser.add_argument("--check", action="store_true")
    render_parser.set_defaults(func=render_tasks_command)

    validate_parser = sub.add_parser("validate", help="运行工作流和协作层验证")
    validate_parser.add_argument("--ci", action="store_true", help="CI 标记（保留用于输出兼容）")
    validate_parser.add_argument("--base")
    validate_parser.add_argument("--head")
    validate_parser.add_argument("--staged", action="store_true", help="校验 Git index 中即将形成的提交")
    validate_parser.set_defaults(func=validate)

    task_parser = sub.add_parser("task", help="仅供主调度器使用的任务状态操作")
    task_sub = task_parser.add_subparsers(dest="task_command", required=True)
    assign = task_sub.add_parser("assign")
    assign.add_argument("--id", required=True)
    assign.add_argument("--owner", required=True)
    assign.add_argument("--now")
    assign.set_defaults(func=task_assign)
    heartbeat = task_sub.add_parser("heartbeat")
    heartbeat.add_argument("--id", required=True)
    heartbeat.add_argument("--generation", required=True, type=int)
    heartbeat.add_argument("--now")
    heartbeat.set_defaults(func=task_heartbeat)
    reclaim = task_sub.add_parser("reclaim-stale")
    reclaim.add_argument("--now")
    reclaim.set_defaults(func=task_reclaim)
    handoff = task_sub.add_parser("handoff")
    handoff.add_argument("--id", required=True)
    handoff.add_argument("--generation", required=True, type=int)
    handoff.add_argument("--head", required=True)
    handoff.add_argument("--changed-file", action="append", default=[])
    handoff.add_argument("--notes", default="")
    handoff.set_defaults(func=task_handoff)
    validation = task_sub.add_parser("validation-result")
    validation.add_argument("--id", required=True)
    validation.add_argument("--generation", required=True, type=int)
    validation.add_argument("--result", required=True, choices=("pass", "fail"))
    validation.add_argument("--report", required=True)
    validation.add_argument("--requires-load-test", action="store_true")
    validation.add_argument("--now")
    validation.set_defaults(func=task_validation_result)
    test_result = task_sub.add_parser("test-result")
    test_result.add_argument("--id", required=True)
    test_result.add_argument("--generation", required=True, type=int)
    test_result.add_argument("--result", required=True, choices=("pass", "fail"))
    test_result.add_argument("--report", required=True)
    test_result.add_argument("--now")
    test_result.set_defaults(func=task_test_result)
    complete = task_sub.add_parser("complete")
    complete.add_argument("--id", required=True)
    complete.add_argument("--generation", required=True, type=int)
    complete.set_defaults(func=task_complete)
    checkpoint = task_sub.add_parser("checkpoint")
    checkpoint.add_argument("--id", required=True)
    checkpoint.add_argument("--generation", required=True, type=int)
    checkpoint.add_argument("--commit", required=True)
    checkpoint.set_defaults(func=task_checkpoint)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except WorkflowError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
