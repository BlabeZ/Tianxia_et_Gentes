#!/usr/bin/env python3
"""Cross-platform workflow gate for the Tianxia et Gentes project.

Only Python's standard library is used so the same entry point works on the
Windows full machine and Linux light machines.  Game files are opened read-only;
all generated artifacts are written inside the repository.
"""

from __future__ import annotations

import argparse
import contextlib
import fnmatch
import hashlib
import json
import os
import re
import secrets
import socket
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

try:
    from scripts import game_test as game_test_module
except ImportError:  # Direct execution: python3 scripts/workflow.py
    import game_test as game_test_module

try:
    from scripts import oob_validation
except ImportError:  # Direct execution: python3 scripts/workflow.py
    import oob_validation


ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG = ROOT / ".opencode" / "local.json"
TASKS_JSON = ROOT / "协作" / "tasks.json"
TASKS_MD = ROOT / "协作" / "任务台账.md"
ENV_DIR = ROOT / "协作" / "环境"
SNAPSHOT_DIR = ROOT / "协作" / "扫描快照"
SNAPSHOT_JSON = SNAPSHOT_DIR / "states.json"
SNAPSHOT_MD = SNAPSHOT_DIR / "states-summary.md"
COUNTRY_TAG_SNAPSHOT_JSON = SNAPSHOT_DIR / "country-tags.json"
COUNTRY_TAG_SNAPSHOT_MD = SNAPSHOT_DIR / "country-tags-summary.md"
STATE_OVERRIDE_DIR = ROOT / "协作" / "state-overrides"
POLITICAL_SPECTRUM_DIR = ROOT / "协作" / "政治光谱"
POLITICAL_SPECTRUM_SCHEMA = "political-spectrum.schema.json"
POLITICAL_SPECTRUM_DEFAULT = POLITICAL_SPECTRUM_DIR / "坐标-40子意识形态.json"
POLITICAL_SPECTRUM_PARTIES = POLITICAL_SPECTRUM_DIR / "坐标-国家政党.json"
POLITICAL_DISTANCE_TABLE = POLITICAL_SPECTRUM_DIR / "距离-40子意识形态.json"
MOD_IDEOLOGIES_FILE = ROOT / "mod" / "common" / "ideologies" / "00_ideologies.txt"
MOD_PARTIES_LOCALISATION_EN = ROOT / "mod" / "localisation" / "english" / "txg_parties_l_english.yml"
MOD_GOVERNMENT_EFFECTS_FILE = (
    ROOT / "mod" / "common" / "scripted_effects" / "00_txg_government_scripted_effects.txt"
)
MOD_REGIME_EFFECTS_FILE = (
    ROOT / "mod" / "common" / "scripted_effects" / "00_txg_regime_effects.txt"
)
MOD_ON_ACTIONS_FILE = ROOT / "mod" / "common" / "on_actions" / "00_txg_on_actions.txt"
MOD_IDEOLOGY_LOCALISATIONS = (
    ROOT / "mod" / "localisation" / "simp_chinese" / "txg_ideologies_l_simp_chinese.yml",
    ROOT / "mod" / "localisation" / "english" / "txg_ideologies_l_english.yml",
)
MOD_COUNTRY_HISTORY_DIR = ROOT / "mod" / "history" / "countries"
MOD_OPINION_NETWORK_FILE = (
    ROOT / "mod" / "common" / "scripted_effects" / "00_txg_opinion_network.txt"
)
TASK_SPEC_DIR = ROOT / "任务书"
REQUIREMENT_DIR = ROOT / "需求"
MOD_STATES_DIR = ROOT / "mod" / "history" / "states"
MOD_DEFINES_FILE = ROOT / "mod" / "common" / "defines" / "zz_txg_defines.lua"
DECISION_DIR = ROOT / "协作" / "决策记录"
HANDOFF_DIR = ROOT / "协作" / "交接单"
SCHEMA_DIR = ROOT / "schemas"
LEASE_HOURS = 48
ENV_FRESHNESS_MINUTES = 15
SHARED_FACTORY_KEYS = frozenset({"industrial_complex", "arms_factory", "dockyard"})
SHARED_FACTORY_SLOT_CAP = 50
INITIAL_SHARED_FACTORY_TOTAL = 1919
JAPAN_FACTORY_PLAN = {
    282: {"industrial_complex": 5, "arms_factory": 4, "dockyard": 0},
    1018: {"industrial_complex": 2, "arms_factory": 0, "dockyard": 0},
    1019: {"industrial_complex": 3, "arms_factory": 1, "dockyard": 0},
}
HISTORICAL_BACKFILL_GATE_COMMIT = "33ed2312245caa7c5cd089cd63b8a085570cb74c"

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
    "需求/",
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
FILESYSTEM_MUTATION_TOOLS = (
    "filesystem_write_file",
    "filesystem_edit_file",
    "filesystem_create_directory",
    "filesystem_move_file",
    "filesystem_copy_file",
    "filesystem_delete_file",
    "filesystem_replace_file",
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
TRUSTED_GAME_EXECUTABLES = ("hoi4.exe", "hoi4")
COORDINATOR_LOCK_PATH = ROOT / ".opencode" / "coordinator.lock"


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


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def process_is_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            process_query_limited_information = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(  # type: ignore[attr-defined]
                process_query_limited_information, False, pid
            )
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
            return True
        except (AttributeError, OSError):
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


@contextlib.contextmanager
def runtime_lock(path: Path, operation: str):
    """Acquire a cross-process runtime lock with fail-closed stale handling."""

    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(16)
    record = {
        "schema_version": 1,
        "token": token,
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "operation": operation,
        "created_at": iso_z(utc_now()),
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {"state": "unreadable"}
        pid = existing.get("pid") if isinstance(existing, dict) else None
        state = "active" if process_is_alive(pid) else "stale-or-unknown"
        raise WorkflowError(
            f"{path.name} 已存在（{state}）；默认拒绝并发/猜测性抢占。"
            "请由主代理核实后运行 lock clear"
        ) from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        yield record
    finally:
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            current = None
        if isinstance(current, dict) and current.get("token") == token:
            path.unlink(missing_ok=True)


def clear_runtime_lock(path: Path, force: bool = False) -> None:
    if not path.is_file():
        raise WorkflowError(f"锁不存在：{path.name}")
    try:
        record = read_json(path)
    except WorkflowError:
        record = {}
    pid = record.get("pid") if isinstance(record, dict) else None
    if process_is_alive(pid) and not force:
        raise WorkflowError("锁所属进程仍存活；如已人工核实，须显式使用 --force")
    path.unlink()


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


def resolve_local_schema_ref(
    root_schema: dict[str, Any], reference: str
) -> dict[str, Any] | None:
    if not reference.startswith("#/"):
        return None
    node: Any = root_schema
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, dict) else None


def validate_schema_instance(
    value: Any,
    schema: dict[str, Any],
    location: str = "$",
    *,
    root_schema: dict[str, Any] | None = None,
) -> list[str]:
    """Validate the JSON Schema subset used by this repository.

    Keeping this deliberately small preserves the zero-dependency Python 3
    gate while making the committed schemas executable rather than decorative.
    """

    root_schema = schema if root_schema is None else root_schema
    reference = schema.get("$ref")
    if isinstance(reference, str):
        resolved = resolve_local_schema_ref(root_schema, reference)
        if resolved is None:
            return [f"{location}: 无法解析本地 schema 引用 {reference!r}"]
        return validate_schema_instance(
            value, resolved, location, root_schema=root_schema
        )

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
        maximum = schema.get("maximum")
        if isinstance(maximum, (int, float)) and value > maximum:
            errors.append(f"{location}: 不得大于 {maximum}")
    if isinstance(value, list):
        minimum = schema.get("minItems")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append(f"{location}: 项目数不得小于 {minimum}")
        maximum = schema.get("maxItems")
        if isinstance(maximum, int) and len(value) > maximum:
            errors.append(f"{location}: 项目数不得大于 {maximum}")
        if schema.get("uniqueItems") is True:
            encoded = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{location}: 数组项必须唯一")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    validate_schema_instance(
                        item,
                        item_schema,
                        f"{location}[{index}]",
                        root_schema=root_schema,
                    )
                )
    if isinstance(value, dict):
        minimum = schema.get("minProperties")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append(f"{location}: 字段数不得小于 {minimum}")
        maximum = schema.get("maxProperties")
        if isinstance(maximum, int) and len(value) > maximum:
            errors.append(f"{location}: 字段数不得大于 {maximum}")
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
                errors.extend(
                    validate_schema_instance(
                        value[key],
                        child,
                        f"{location}.{key}",
                        root_schema=root_schema,
                    )
                )
        additional = schema.get("additionalProperties", True)
        for key in set(value) - set(properties):
            if additional is False:
                errors.append(f"{location}: 不允许额外字段 {key}")
            elif isinstance(additional, dict):
                errors.extend(
                    validate_schema_instance(
                        value[key],
                        additional,
                        f"{location}.{key}",
                        root_schema=root_schema,
                    )
                )
    alternatives = schema.get("oneOf")
    if isinstance(alternatives, list):
        matches = sum(
            not validate_schema_instance(
                value, alternative, location, root_schema=root_schema
            )
            for alternative in alternatives
            if isinstance(alternative, dict)
        )
        if matches != 1:
            errors.append(f"{location}: 必须且只能匹配 oneOf 中的一个分支")
    condition = schema.get("if")
    if isinstance(condition, dict):
        condition_matches = not validate_schema_instance(
            value, condition, location, root_schema=root_schema
        )
        branch_name = "then" if condition_matches else "else"
        branch = schema.get(branch_name)
        if isinstance(branch, dict):
            errors.extend(
                validate_schema_instance(
                    value, branch, location, root_schema=root_schema
                )
            )
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


def repo_relative_posix(path: Any, root: Any = ROOT) -> str:
    """Return a persisted repository path with tool- and OS-neutral separators."""
    return path.relative_to(root).as_posix()


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


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


def state_category_files(game_path: Path) -> list[Path]:
    categories = game_path / "common" / "state_category"
    if not categories.is_dir():
        raise WorkflowError(f"game_path 缺少 common/state_category：{categories}")
    files = sorted(categories.glob("*.txt"), key=lambda item: item.name.casefold())
    if not files:
        raise WorkflowError(f"未找到 state_category 文件：{categories}")
    return files


def fingerprint_files(files: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def fingerprint_relative_files(root: Path, files: Iterable[Path]) -> str:
    """Hash a file set using repository-like relative paths, never local roots."""
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix().casefold()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def files_under_game_root(game_path: Path, relative_root: str) -> list[Path]:
    directory = game_path.joinpath(*PurePosixPath(relative_root).parts)
    if not directory.is_dir():
        raise WorkflowError(f"game_path 缺少 {relative_root}")
    return sorted(
        directory.rglob("*.txt"),
        key=lambda item: item.relative_to(game_path).as_posix().casefold(),
    )


def country_tag_files(game_path: Path) -> list[Path]:
    files = files_under_game_root(game_path, "common/country_tags")
    if not files:
        raise WorkflowError("未找到 country tag 注册文件")
    return files


def parse_country_tag_file(path: Path, game_path: Path) -> list[dict[str, Any]]:
    clean = strip_hoi_comments(
        path.read_text(encoding="utf-8-sig", errors="replace")
    )
    registry_relative_path = path.relative_to(game_path).as_posix()
    registry_sha256 = sha256_file(path)
    registrations: list[dict[str, Any]] = []
    for line_number, line in enumerate(clean.splitlines(), start=1):
        if not line.strip():
            continue
        assignment = re.fullmatch(
            r"\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*(.*?)\s*", line
        )
        if assignment is None:
            continue
        key, raw_value = assignment.groups()
        if re.fullmatch(r"[A-Z][A-Z0-9_]{2}", key) is None:
            continue
        quoted = re.fullmatch(r'"([^"\r\n]+)"', raw_value)
        if quoted is None:
            raise WorkflowError(
                f"country tag 注册值必须是唯一引号路径：{registry_relative_path}:{line_number}:{key}"
            )
        registered_path = quoted.group(1)
        pure_path = PurePosixPath(registered_path)
        if (
            not registered_path.startswith("countries/")
            or not registered_path.endswith(".txt")
            or pure_path.is_absolute()
            or ".." in pure_path.parts
            or "\\" in registered_path
        ):
            raise WorkflowError(
                f"country tag definition 路径越界：{registry_relative_path}:{line_number}:{key}"
            )
        definition_relative_path = f"common/{registered_path}"
        definition_path = game_path.joinpath(
            *PurePosixPath(definition_relative_path).parts
        )
        definition_exists = definition_path.is_file()
        registrations.append(
            {
                "tag": key,
                "registry_relative_path": registry_relative_path,
                "registry_sha256": registry_sha256,
                "definition": {
                    "relative_path": definition_relative_path,
                    "exists": definition_exists,
                    "sha256": sha256_file(definition_path) if definition_exists else None,
                },
            }
        )
    return registrations


def collect_country_tag_metadata(game_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    registry_files = country_tag_files(game_path)
    definition_files = files_under_game_root(game_path, "common/countries")
    history_files = files_under_game_root(game_path, "history/countries")
    registrations: list[dict[str, Any]] = []
    seen_tags: set[str] = set()
    for path in registry_files:
        for item in parse_country_tag_file(path, game_path):
            tag = item["tag"]
            if tag in seen_tags:
                raise WorkflowError(f"country tag 重复注册：{tag}")
            seen_tags.add(tag)
            registrations.append(item)
    if not registrations:
        raise WorkflowError("country tag 注册文件中没有可识别的 tag")

    for item in registrations:
        tag = item["tag"]
        pattern = re.compile(rf"^{re.escape(tag)}(?:\s*-\s*.*)?\.txt$")
        matches = [path for path in history_files if pattern.fullmatch(path.name)]
        if len(matches) > 1:
            paths = [path.relative_to(game_path).as_posix() for path in matches]
            raise WorkflowError(f"country history 文件不唯一：{tag} -> {paths}")
        item["history"] = {
            "exists": bool(matches),
            "files": [
                {
                    "relative_path": path.relative_to(game_path).as_posix(),
                    "sha256": sha256_file(path),
                }
                for path in matches
            ],
        }

    sources = {
        "registries": {
            "relative_root": "common/country_tags",
            "file_count": len(registry_files),
            "fingerprint": fingerprint_relative_files(game_path, registry_files),
        },
        "definitions": {
            "relative_root": "common/countries",
            "file_count": len(definition_files),
            "fingerprint": fingerprint_relative_files(game_path, definition_files),
        },
        "histories": {
            "relative_root": "history/countries",
            "file_count": len(history_files),
            "fingerprint": fingerprint_relative_files(game_path, history_files),
        },
    }
    return sources, sorted(registrations, key=lambda item: item["tag"])


def strip_hoi_comments(text: str) -> str:
    return re.sub(r"#.*$", "", text, flags=re.MULTILINE)


def parse_state(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    clean = strip_hoi_comments(text)
    id_match = re.search(r"\bid\s*=\s*(\d+)", clean)
    if not id_match:
        raise WorkflowError(f"state 文件缺少 id：{path.name}")
    state_id = int(id_match.group(1))
    category_matches = re.findall(
        r"\bstate_category\s*=\s*\"?([a-z][a-z0-9_]*)\"?", clean
    )
    if not category_matches:
        raise WorkflowError(
            f"state 文件缺少 state_category：{path.name}"
        )
    if len(category_matches) > 1:
        print(
            f"WARNING: {path.name} 重复声明 state_category"
            f"（{len(category_matches)} 次）；按 HOI4 解析语义后者生效"
            f"（D-20260812-029）：{category_matches}"
        )
    # D-20260812-029：本体存在重复声明（4/1081 文件）；一致重复取唯一值，
    # 矛盾重复按 HOI4 解析语义后者生效（用户拍板）
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
        "state_category": category_matches[-1],
        "sha256": sha256_file(path),
    }


def parse_state_category_file(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        tokens = state_transform.tokenize(text)
        pairs = state_transform.matching_braces(tokens)
        top_level = state_transform.assignments_in_range(tokens, pairs, 0, len(tokens))
        # HOI4 原版 common/state_category 统一使用 state_categories = { ... } 包装块
        # （机器 A 实测 13/13 文件均为该格式），解包一层后按类别块解析
        wrappers = [node for node in top_level if node.key == "state_categories"]
        if len(wrappers) == 1 and wrappers[0].block_open is not None:
            inner = state_transform.assignments_in_range(
                tokens, pairs, wrappers[0].block_open + 1, wrappers[0].block_close
            )
            if inner:
                top_level = inner
    except state_transform.StateTransformError as exc:
        raise WorkflowError(f"state_category 文件解析失败：{path.name}：{exc}") from exc

    digest = sha256_file(path)
    relative_path = f"common/state_category/{path.name}"
    categories: list[dict[str, Any]] = []
    for node in top_level:
        if node.block_open is None or node.block_close is None:
            raise WorkflowError(
                f"state_category 顶层字段必须是类别块：{path.name}:{node.key}"
            )
        if re.fullmatch(r"[a-z][a-z0-9_]*", node.key) is None:
            raise WorkflowError(f"state_category 名称无效：{path.name}:{node.key}")
        fields = state_transform.assignments_in_range(
            tokens, pairs, node.block_open + 1, node.block_close
        )
        slot_fields = [item for item in fields if item.key == "local_building_slots"]
        if len(slot_fields) != 1 or slot_fields[0].block_open is not None:
            raise WorkflowError(
                f"state_category 必须有唯一标量 local_building_slots：{path.name}:{node.key}"
            )
        raw_slots = tokens[slot_fields[0].value_token].text
        if re.fullmatch(r"\d+", raw_slots) is None:
            raise WorkflowError(
                f"state_category.local_building_slots 必须是非负整数：{path.name}:{node.key}"
            )
        categories.append(
            {
                "name": node.key,
                "local_building_slots": int(raw_slots),
                "source_relative_path": relative_path,
                "source_sha256": digest,
            }
        )
    if not categories:
        raise WorkflowError(f"state_category 文件没有类别定义：{path.name}")
    return categories


def collect_state_categories(files: Iterable[Path]) -> list[dict[str, Any]]:
    categories: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in files:
        for item in parse_state_category_file(path):
            name = item["name"]
            if name in seen:
                raise WorkflowError(f"state_category 重复定义：{name}")
            seen.add(name)
            categories.append(item)
    return sorted(categories, key=lambda item: item["name"])


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

    Schema v2 (D-20260811-018) adds province IDs.  Schema v3
    (D-20260812-014) adds each state's original state_category and the
    category-to-local_building_slots metadata required for initial slot gates.
    """

    errors: list[str] = []
    if not isinstance(data, dict):
        return ["顶层必须是对象"]
    schema_version = data.get("schema_version")
    if schema_version not in {2, 3}:
        errors.append("schema_version 必须是 2 或 3")
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

    category_names: set[str] = set()
    if schema_version == 3:
        category_source = data.get("state_category_source")
        if not isinstance(category_source, dict):
            errors.append("state_category_source 必须是对象")
            category_source = {}
        if category_source.get("relative_root") != "common/state_category":
            errors.append("state_category_source.relative_root 必须是 common/state_category")
        category_fingerprint = category_source.get("fingerprint")
        if not isinstance(category_fingerprint, str) or not re.fullmatch(
            r"[0-9a-f]{64}", category_fingerprint
        ):
            errors.append("state_category_source.fingerprint 必须是64位小写 SHA-256")
        categories = data.get("state_categories")
        if not isinstance(categories, list) or not categories:
            errors.append("state_categories 必须是非空数组")
            categories = []
        category_file_count = category_source.get("file_count")
        category_paths: set[str] = set()
        previous_name = ""
        for index, category in enumerate(categories):
            prefix = f"state_categories[{index}]"
            if not isinstance(category, dict):
                errors.append(f"{prefix} 必须是对象")
                continue
            name = category.get("name")
            if not isinstance(name, str) or re.fullmatch(r"[a-z][a-z0-9_]*", name) is None:
                errors.append(f"{prefix}.name 必须是小写标识符")
            else:
                if name in category_names:
                    errors.append(f"{prefix}.name 重复：{name}")
                if name <= previous_name:
                    errors.append("state_categories 必须按 name 严格递增排序")
                category_names.add(name)
                previous_name = name
            slots = category.get("local_building_slots")
            if not isinstance(slots, int) or isinstance(slots, bool) or slots < 0:
                errors.append(f"{prefix}.local_building_slots 必须是非负整数")
            category_path = category.get("source_relative_path")
            if (
                not isinstance(category_path, str)
                or not category_path.startswith("common/state_category/")
                or not category_path.endswith(".txt")
                or ".." in Path(category_path).parts
                or Path(category_path).is_absolute()
            ):
                errors.append(
                    f"{prefix}.source_relative_path 必须是 common/state_category 下的相对 txt 路径"
                )
            else:
                category_paths.add(category_path)
            category_digest = category.get("source_sha256")
            if not isinstance(category_digest, str) or not re.fullmatch(
                r"[0-9a-f]{64}", category_digest
            ):
                errors.append(f"{prefix}.source_sha256 必须是64位小写 SHA-256")
        if (
            not isinstance(category_file_count, int)
            or isinstance(category_file_count, bool)
            or category_file_count != len(category_paths)
        ):
            errors.append(
                "state_category_source.file_count 必须与类别来源文件数量一致"
            )

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
        if schema_version == 3:
            state_category = state.get("state_category")
            if (
                not isinstance(state_category, str)
                or re.fullmatch(r"[a-z][a-z0-9_]*", state_category) is None
            ):
                errors.append(f"{prefix}.state_category 必须是小写标识符")
            elif state_category not in category_names:
                errors.append(
                    f"{prefix}.state_category 引用了未知类别：{state_category}"
                )
        digest = state.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append(f"{prefix}.sha256 必须是64位小写 SHA-256")
    return errors


def render_snapshot_summary(data: dict[str, Any]) -> str:
    schema_version = data.get("schema_version", 2)
    lines = [
        "# HOI4 states 受控快照摘要",
        "",
        "> 本文件由 `python3 scripts/workflow.py snapshot-export` 自动生成（Windows 使用 `py -3`）；不得手工编辑。",
        "> 仅包含元数据和校验和，不包含游戏本体脚本正文。",
        (
            "> schema v3（D-20260812-014）：另含原版 state_category 与基础槽位元数据。"
            if schema_version == 3
            else "> schema v2（D-20260811-018）：province 编号列表与全局唯一归属见 `states.json`。"
        ),
        "",
        f"- 生成时间：`{data['generated_at']}`",
        f"- 游戏版本：`{data['game_version'] or 'unknown'}`",
        f"- 文件数量：`{data['source']['file_count']}`",
        f"- 指纹：`{data['source']['fingerprint']}`",
    ]
    if schema_version == 3:
        lines.extend(
            [
                f"- 州类别文件数量：`{data['state_category_source']['file_count']}`",
                f"- 州类别指纹：`{data['state_category_source']['fingerprint']}`",
                "",
                "## 州类别基础槽位",
                "",
                "| state_category | local_building_slots | 来源 | sha256 |",
                "| --- | ---: | --- | --- |",
            ]
        )
        for category in data["state_categories"]:
            lines.append(
                f"| {category['name']} | {category['local_building_slots']} | "
                f"`{category['source_relative_path']}` | `{category['source_sha256']}` |"
            )
        lines.extend(
            [
                "",
                "## State 元数据",
                "",
                "| state_id | localisation_key | state_category | 文件 | provinces | sha256 |",
                "| ---: | --- | --- | --- | ---: | --- |",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "| state_id | localisation_key | 文件 | provinces | sha256 |",
                "| ---: | --- | --- | ---: | --- |",
            ]
        )
    for item in data["states"]:
        if schema_version == 3:
            lines.append(
                f"| {item['state_id']} | {item['localisation_key']} | "
                f"{item['state_category']} | `{item['relative_path']}` | "
                f"{item['province_count']} | `{item['sha256']}` |"
            )
        else:
            lines.append(
                f"| {item['state_id']} | {item['localisation_key']} | "
                f"`{item['relative_path']}` | {item['province_count']} | `{item['sha256']}` |"
            )
    return "\n".join(lines) + "\n"


def country_tag_snapshot_errors(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["顶层必须是对象"]
    if data.get("schema_version") != 1:
        errors.append("schema_version 必须是 1")
    generated_at = data.get("generated_at")
    if not isinstance(generated_at, str) or not ISO_Z_RE.fullmatch(generated_at):
        errors.append("generated_at 格式无效")
    machine = data.get("generated_by_machine")
    if not isinstance(machine, str) or re.fullmatch(r"[A-Za-z0-9_-]+", machine) is None:
        errors.append("generated_by_machine 无效")
    path_hits = absolute_path_strings(data)
    if path_hits:
        errors.append(f"包含绝对路径片段 {sorted(path_hits)!r}")

    sources = data.get("sources")
    if not isinstance(sources, dict):
        errors.append("sources 必须是对象")
        sources = {}
    expected_roots = {
        "registries": "common/country_tags",
        "definitions": "common/countries",
        "histories": "history/countries",
    }
    source_counts: dict[str, int] = {}
    for key, expected_root in expected_roots.items():
        source = sources.get(key)
        if not isinstance(source, dict):
            errors.append(f"sources.{key} 必须是对象")
            continue
        if source.get("relative_root") != expected_root:
            errors.append(f"sources.{key}.relative_root 必须是 {expected_root}")
        count = source.get("file_count")
        minimum = 1 if key == "registries" else 0
        if not isinstance(count, int) or isinstance(count, bool) or count < minimum:
            errors.append(f"sources.{key}.file_count 必须是不小于 {minimum} 的整数")
        else:
            source_counts[key] = count
        fingerprint = source.get("fingerprint")
        if not isinstance(fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
            errors.append(f"sources.{key}.fingerprint 必须是64位小写 SHA-256")

    tags = data.get("tags")
    if not isinstance(tags, list) or not tags:
        errors.append("tags 必须是非空数组")
        tags = []
    seen_tags: set[str] = set()
    registry_paths: set[str] = set()
    existing_definition_paths: set[str] = set()
    history_paths: set[str] = set()
    previous_tag = ""
    for index, item in enumerate(tags):
        prefix = f"tags[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} 必须是对象")
            continue
        tag = item.get("tag")
        if not isinstance(tag, str) or re.fullmatch(r"[A-Z][A-Z0-9_]{2}", tag) is None:
            errors.append(f"{prefix}.tag 无效")
        else:
            if tag in seen_tags:
                errors.append(f"{prefix}.tag 重复：{tag}")
            if tag <= previous_tag:
                errors.append("tags 必须按 tag 严格递增排序")
            seen_tags.add(tag)
            previous_tag = tag
        registry_path = item.get("registry_relative_path")
        if not safe_snapshot_relative_path(registry_path, "common/country_tags"):
            errors.append(f"{prefix}.registry_relative_path 越界或无效")
        else:
            registry_paths.add(registry_path)
        registry_sha = item.get("registry_sha256")
        if not isinstance(registry_sha, str) or re.fullmatch(r"[0-9a-f]{64}", registry_sha) is None:
            errors.append(f"{prefix}.registry_sha256 无效")

        definition = item.get("definition")
        if not isinstance(definition, dict):
            errors.append(f"{prefix}.definition 必须是对象")
            definition = {}
        definition_path = definition.get("relative_path")
        if not safe_snapshot_relative_path(definition_path, "common/countries"):
            errors.append(f"{prefix}.definition.relative_path 越界或无效")
        elif definition.get("exists") is True:
            existing_definition_paths.add(definition_path)
        definition_exists = definition.get("exists")
        definition_sha = definition.get("sha256")
        if not isinstance(definition_exists, bool):
            errors.append(f"{prefix}.definition.exists 必须是布尔值")
        if definition_exists is True:
            if not isinstance(definition_sha, str) or re.fullmatch(r"[0-9a-f]{64}", definition_sha) is None:
                errors.append(f"{prefix}.definition 存在时必须有有效 SHA-256")
        elif definition_exists is False and definition_sha is not None:
            errors.append(f"{prefix}.definition 不存在时 sha256 必须为 null")

        history = item.get("history")
        if not isinstance(history, dict):
            errors.append(f"{prefix}.history 必须是对象")
            history = {}
        history_exists = history.get("exists")
        history_files = history.get("files")
        if not isinstance(history_exists, bool):
            errors.append(f"{prefix}.history.exists 必须是布尔值")
        if not isinstance(history_files, list):
            errors.append(f"{prefix}.history.files 必须是数组")
            history_files = []
        if len(history_files) > 1:
            errors.append(f"{prefix}.history 文件不得多于一个")
        if isinstance(history_exists, bool) and history_exists != bool(history_files):
            errors.append(f"{prefix}.history.exists 必须与 files 是否非空一致")
        for file_index, history_file in enumerate(history_files):
            history_prefix = f"{prefix}.history.files[{file_index}]"
            if not isinstance(history_file, dict):
                errors.append(f"{history_prefix} 必须是对象")
                continue
            history_path = history_file.get("relative_path")
            if not safe_snapshot_relative_path(history_path, "history/countries"):
                errors.append(f"{history_prefix}.relative_path 越界或无效")
            elif history_path in history_paths:
                errors.append(f"{history_prefix}.relative_path 被多个 tag 复用")
            else:
                history_paths.add(history_path)
            history_sha = history_file.get("sha256")
            if not isinstance(history_sha, str) or re.fullmatch(r"[0-9a-f]{64}", history_sha) is None:
                errors.append(f"{history_prefix}.sha256 无效")

    minimum_counts = {
        "registries": len(registry_paths),
        "definitions": len(existing_definition_paths),
        "histories": len(history_paths),
    }
    for key, minimum_count in minimum_counts.items():
        if key in source_counts and source_counts[key] < minimum_count:
            errors.append(f"sources.{key}.file_count 小于快照引用的唯一文件数量")
    return errors


def safe_snapshot_relative_path(value: Any, expected_root: str) -> bool:
    if not isinstance(value, str) or "\\" in value or not value.endswith(".txt"):
        return False
    path = PurePosixPath(value)
    root = PurePosixPath(expected_root)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and path.parts[: len(root.parts)] == root.parts
        and len(path.parts) > len(root.parts)
    )


def render_country_tag_snapshot_summary(data: dict[str, Any]) -> str:
    sources = data["sources"]
    lines = [
        "# HOI4 国家 tag 受控快照摘要",
        "",
        "> 本文件由 `python3 scripts/workflow.py country-snapshot-export` 自动生成（Windows 使用 `py -3`）；不得手工编辑。",
        "> 仅包含 tag、相对路径、存在状态与校验和，不包含游戏本体国家脚本正文。",
        "",
        f"- 生成时间：`{data['generated_at']}`",
        f"- 游戏版本：`{data['game_version'] or 'unknown'}`",
        f"- tag 数量：`{len(data['tags'])}`",
        f"- 注册文件：`{sources['registries']['file_count']}` / `{sources['registries']['fingerprint']}`",
        f"- definition 文件：`{sources['definitions']['file_count']}` / `{sources['definitions']['fingerprint']}`",
        f"- history 文件：`{sources['histories']['file_count']}` / `{sources['histories']['fingerprint']}`",
        "",
        "| tag | 注册来源 | country definition | definition SHA-256 | country history | history SHA-256 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in data["tags"]:
        definition = item["definition"]
        history_files = item["history"]["files"]
        history_path = history_files[0]["relative_path"] if history_files else "—"
        history_sha = history_files[0]["sha256"] if history_files else "—"
        definition_sha = definition["sha256"] or "—"
        lines.append(
            f"| {item['tag']} | `{item['registry_relative_path']}` | "
            f"`{definition['relative_path']}` ({'有' if definition['exists'] else '缺'}) | "
            f"`{definition_sha}` | "
            f"{'`' + history_path + '`' if history_files else '—'} | "
            f"`{history_sha}` |"
        )
    return "\n".join(lines) + "\n"


def has_game_executable(game_path: Path) -> bool:
    return any((game_path / candidate).is_file() for candidate in TRUSTED_GAME_EXECUTABLES)


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
    category_files: list[Path] = []
    live_fingerprint: str | None = None
    live_category_fingerprint: str | None = None
    if game_valid and game_path is not None:
        try:
            files = state_files(game_path)
            live_fingerprint = fingerprint_files(files)
            category_files = state_category_files(game_path)
            live_category_fingerprint = fingerprint_files(category_files)
        except WorkflowError as exc:
            warnings.append(
                "本体 state/state_category 元数据不可用；"
                f"已拒绝 snapshot_export（{exc.__class__.__name__}）"
            )

    snapshot = snapshot_metadata()
    if SNAPSHOT_JSON.is_file() and snapshot is None:
        warnings.append("受控快照结构无效：已按 missing 处理并封锁依赖能力")
    if snapshot is None:
        snapshot_status = "missing"
    elif not game_valid:
        snapshot_status = "available"
    elif (
        live_fingerprint is not None
        and live_category_fingerprint is not None
        and snapshot.get("schema_version") == 3
        and snapshot.get("source", {}).get("fingerprint") == live_fingerprint
        and snapshot.get("state_category_source", {}).get("fingerprint")
        == live_category_fingerprint
    ):
        snapshot_status = "current"
    else:
        snapshot_status = "stale"

    user_docs_value = config.get("user_docs_path")
    user_docs = (
        Path(user_docs_value).expanduser()
        if probe_external and not config_errors and isinstance(user_docs_value, str)
        else None
    )
    snapshot_export = bool(game_valid and files and category_files)
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
        warnings.append(
            "本体 state/state_category 指纹或快照 schema 已变化："
            "依赖快照的执行与测试必须阻断，直至显式刷新"
        )
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
    category_files = state_category_files(game_path)
    categories = collect_state_categories(category_files)
    states = [parse_state(path) for path in files]
    ids = [item["state_id"] for item in states]
    if len(ids) != len(set(ids)):
        raise WorkflowError("本体 state id 存在重复，拒绝生成快照")
    known_categories = {item["name"] for item in categories}
    unknown_categories = sorted(
        {item["state_category"] for item in states} - known_categories
    )
    if unknown_categories:
        raise WorkflowError(
            f"state 引用了未定义的 state_category：{unknown_categories}"
        )
    generated_at = iso_z(utc_now())
    data = {
        "schema_version": 3,
        "generated_at": generated_at,
        "generated_by_machine": config["machine_id"],
        "game_version": detect_game_version(game_path),
        "source": {
            "relative_root": "history/states",
            "file_count": len(files),
            "fingerprint": fingerprint_files(files),
        },
        "state_category_source": {
            "relative_root": "common/state_category",
            "file_count": len(category_files),
            "fingerprint": fingerprint_files(category_files),
        },
        "state_categories": categories,
        "states": sorted(states, key=lambda item: item["state_id"]),
    }
    export_errors = validate_named_schema(
        data, "snapshot.schema.json", "受控快照导出"
    )
    export_errors.extend(snapshot_data_errors(data))
    if export_errors:
        raise WorkflowError("；".join(export_errors))
    write_json(SNAPSHOT_JSON, data)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_MD.write_text(render_snapshot_summary(data), encoding="utf-8", newline="\n")
    print(
        f"已生成 {len(states)} 个 state、{len(categories)} 个 state_category 的受控快照。"
    )
    return 0


def country_snapshot_export(_: argparse.Namespace) -> int:
    config, errors = load_local_config()
    if errors:
        raise WorkflowError("；".join(errors))
    game_value = config.get("game_path")
    if not isinstance(game_value, str):
        raise WorkflowError("当前机器没有有效 game_path，不能导出国家 tag 快照")
    game_path = Path(game_value).expanduser()
    sources, tags = collect_country_tag_metadata(game_path)
    data = {
        "schema_version": 1,
        "generated_at": iso_z(utc_now()),
        "generated_by_machine": config["machine_id"],
        "game_version": detect_game_version(game_path),
        "sources": sources,
        "tags": tags,
    }
    export_errors = validate_named_schema(
        data,
        "country-tag-snapshot.schema.json",
        "国家 tag 受控快照导出",
    )
    export_errors.extend(country_tag_snapshot_errors(data))
    if export_errors:
        raise WorkflowError("；".join(export_errors))
    write_json(COUNTRY_TAG_SNAPSHOT_JSON, data)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    COUNTRY_TAG_SNAPSHOT_MD.write_text(
        render_country_tag_snapshot_summary(data), encoding="utf-8", newline="\n"
    )
    missing_definitions = sum(
        1 for item in tags if item["definition"]["exists"] is False
    )
    missing_histories = sum(1 for item in tags if item["history"]["exists"] is False)
    print(
        f"已生成 {len(tags)} 个 country tag 的受控快照；"
        f"缺 definition {missing_definitions}，缺 history {missing_histories}。"
    )
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
        merged = state_transform.merge_override_documents(documents, snapshot["source"]["fingerprint"])
        uniqueness = state_transform.province_uniqueness_errors(merged, snapshot)
        if uniqueness:
            raise WorkflowError(
                "全局 province 唯一归属校验失败（T-041）：" + "；".join(uniqueness)
            )
        moves = state_transform.province_move_summary(merged, snapshot)
        if getattr(args, "dry_run", False):
            summary = state_transform.diff_state_outputs(outputs, output_root)
            print(
                f"干跑（未落盘）：生成 {summary['total']} 个州；"
                f"新增 {summary['added']} / 修改 {summary['changed']} / "
                f"不变 {summary['unchanged']} / 遗留 {len(summary['leftover'])}"
            )
            for name in summary["added_samples"]:
                print(f"  新增: {name}")
            for name in summary["changed_samples"]:
                print(f"  修改: {name}")
            if summary["leftover"]:
                print("  遗留（目标目录存在但生成结果不含）: " + ", ".join(summary["leftover"]))
            if moves:
                print(f"  省粒度移动清单（T-041，共 {len(moves)} 条）:")
                for move in moves[:30]:
                    print(
                        f"    province {move['province']}: "
                        f"{move['from_state'] or '（新增）'} -> {move['to_state'] or '（移除）'}"
                    )
            return 0
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
        "| 任务ID | 需求 | 模块 | 状态 | 负责人 | 分支 | 隔离代数 | 领取时间 | 租约到期 | 交接点 | 产出文件 | 阻塞项 |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for task in sorted(data.get("tasks", []), key=lambda item: (str(item.get("requirement_id") or ""), item.get("id"))):
        status = TASK_STATUSES.get(task.get("status"), f"未知:{task.get('status')}")
        row = [
            task.get("id"),
            task.get("requirement_id"),
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
    staged: set[str] = set()
    for line in status.stdout.splitlines():
        if len(line) < 4:
            raise WorkflowError("无法解析 Git 工作区状态")
        path = line[3:]
        changed.add(path)
        if line[0] not in {" ", "?"}:
            staged.add(path)
    unexpected = changed - set(allowed_paths)
    if unexpected:
        raise WorkflowError(
            f"{operation} 除明确允许的状态文件外要求干净工作区；"
            f"请先处理：{', '.join(sorted(unexpected))}"
        )
    if staged:
        raise WorkflowError(
            f"{operation} 不接受预先暂存的文件；请先处理："
            f"{', '.join(sorted(staged))}"
        )
    return run_git("rev-parse", "HEAD").stdout.strip()


def transaction_path(value: Path | str) -> tuple[str, Path]:
    path = value if isinstance(value, Path) else Path(value)
    candidate = path.resolve() if path.is_absolute() else (ROOT / path).resolve()
    try:
        relative = candidate.relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise WorkflowError(f"事务路径必须位于工作区：{value}") from exc
    return relative, candidate


@contextlib.contextmanager
def workspace_transaction(
    paths: Iterable[Path | str], managed_refs: Iterable[str] = ()
):
    """Restore repository state when a lifecycle mutation cannot commit.

    ``require_clean_main`` guarantees that the index starts at HEAD.  Allowed
    environment/report files may already be modified or untracked, so their
    exact bytes are captured instead of restoring them blindly from Git.
    """

    resolved = dict(transaction_path(path) for path in paths if path is not None)
    snapshots = {
        relative: candidate.read_bytes() if candidate.is_file() else None
        for relative, candidate in resolved.items()
    }
    branch_result = run_git("symbolic-ref", "--quiet", "HEAD", check=False)
    branch_ref = branch_result.stdout.strip() if branch_result.returncode == 0 else None
    head_result = run_git("rev-parse", "HEAD", check=False)
    if head_result.returncode != 0:
        raise WorkflowError("无法记录生命周期事务起始 HEAD")
    initial_head = head_result.stdout.strip()
    ref_snapshots: dict[str, str | None] = {}
    for ref in managed_refs:
        result = run_git("rev-parse", "--verify", ref, check=False)
        ref_snapshots[ref] = result.stdout.strip() if result.returncode == 0 else None
    try:
        yield
    except BaseException as original:
        rollback_errors: list[str] = []
        current_head_result = run_git("rev-parse", "HEAD", check=False)
        current_head = (
            current_head_result.stdout.strip()
            if current_head_result.returncode == 0
            else None
        )
        if branch_ref and current_head and current_head != initial_head:
            moved = run_git(
                "update-ref", branch_ref, initial_head, current_head, check=False
            )
            if moved.returncode != 0:
                rollback_errors.append("无法恢复生命周期事务起始 HEAD")
        for ref, original_target in ref_snapshots.items():
            current = run_git("rev-parse", "--verify", ref, check=False)
            current_target = current.stdout.strip() if current.returncode == 0 else None
            if original_target is None and current_target is not None:
                restored = run_git("update-ref", "-d", ref, current_target, check=False)
            elif original_target is not None and current_target != original_target:
                args = ("update-ref", ref, original_target)
                if current_target is not None:
                    args += (current_target,)
                restored = run_git(*args, check=False)
            else:
                continue
            if restored.returncode != 0:
                rollback_errors.append(f"无法恢复受控引用 {ref}")
        relative_paths = sorted(resolved)
        if relative_paths:
            reset = run_git(
                "restore", "--staged", "--source=HEAD", "--", *relative_paths,
                check=False,
            )
            if reset.returncode != 0:
                rollback_errors.append("无法恢复生命周期事务 index")
        for relative, candidate in resolved.items():
            payload = snapshots[relative]
            try:
                if payload is None:
                    candidate.unlink(missing_ok=True)
                else:
                    candidate.parent.mkdir(parents=True, exist_ok=True)
                    candidate.write_bytes(payload)
            except OSError:
                rollback_errors.append(f"无法恢复 {relative}")
        if rollback_errors:
            raise WorkflowError(
                f"生命周期操作失败且回滚不完整：{'；'.join(rollback_errors)}"
            ) from original
        raise


def origin_main_divergence() -> tuple[int, int]:
    for ref in ("refs/heads/main", "refs/remotes/origin/main"):
        if not ref_exists(ref):
            raise WorkflowError(f"缺少 Git 引用 {ref}；请先显式 fetch origin")
    result = run_git(
        "rev-list", "--left-right", "--count", "origin/main...main", check=False
    )
    if result.returncode != 0:
        raise WorkflowError("无法计算 origin/main 与 main 的同步状态")
    try:
        behind, ahead = (int(value) for value in result.stdout.split())
    except (TypeError, ValueError) as exc:
        raise WorkflowError("无法解析 origin/main 同步状态") from exc
    return behind, ahead


def require_origin_main_synchronized(operation: str) -> None:
    behind, ahead = origin_main_divergence()
    if behind or ahead:
        raise WorkflowError(
            f"{operation} 要求 origin/main 与 main 双向同步；"
            f"当前落后 {behind}、领先 {ahead}。请先显式 fetch/pull/push"
        )


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
    extra_allowed_paths: Iterable[Path] = (),
) -> str:
    task_path = TASKS_JSON.relative_to(ROOT).as_posix()
    task_md_path = TASKS_MD.relative_to(ROOT).as_posix()
    env_path = environment_path.relative_to(ROOT).as_posix()
    required = {task_path, task_md_path}
    required.update(path.relative_to(ROOT).as_posix() for path in required_artifacts)
    allowed = required | {env_path}
    allowed.update(path.relative_to(ROOT).as_posix() for path in optional_artifacts)
    allowed.update(path.relative_to(ROOT).as_posix() for path in extra_allowed_paths)
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


def task_output_base(task: dict[str, Any], head: str) -> str:
    """Return the commit after assignment from which task outputs are measured.

    New task branches are created at an atomic lease commit.  A failed stage may
    reopen the task at a validated checkpoint under a new generation without a
    second lease commit.  Scope checks therefore use that checkpoint for later
    generations, excluding already-validated output from the new handoff.
    """
    base = task.get("base_commit")
    if not isinstance(base, str) or not SHA_RE.fullmatch(base):
        raise WorkflowError("任务 base_commit 无效")
    history = run_git(
        "rev-list", "--ancestry-path", "--reverse", f"{base}..{head}", check=False
    )
    if history.returncode != 0:
        raise WorkflowError(
            "无法解析任务提交路径：" + (history.stderr.strip() or history.stdout.strip())
        )
    commits = [line.strip() for line in history.stdout.splitlines() if line.strip()]
    if not commits:
        return base
    first = commits[0]
    subject_result = run_git("show", "-s", "--format=%s", first, check=False)
    if subject_result.returncode != 0:
        raise WorkflowError(
            "无法读取任务首个提交："
            + (subject_result.stderr.strip() or subject_result.stdout.strip())
        )
    expected = (
        f"lease {task.get('id')} g{task.get('lease_generation')} "
        f"@ {task.get('owner')}"
    )
    if subject_result.stdout.strip() == expected:
        return first
    generation = int(task.get("lease_generation", 0))
    checkpoint = task.get("checkpoint_commit")
    if generation > 1 and isinstance(checkpoint, str) and SHA_RE.fullmatch(checkpoint):
        checkpoint_result = run_git(
            "merge-base", "--is-ancestor", checkpoint, head, check=False
        )
        if checkpoint_result.returncode == 0:
            return checkpoint
    return base


def handoff_output_base(handoff: dict[str, Any], head: str) -> str:
    """Resolve a handoff's output base without consulting mutable task state.

    Completed or rejected handoffs remain immutable evidence after a task is
    reopened under a later lease generation.  Their generation/owner fields no
    longer match the live registry, so historical verification must derive the
    atomic lease boundary from the recorded commit range itself.
    """
    base = handoff.get("base_commit")
    task_id = handoff.get("task_id")
    generation = handoff.get("lease_generation")
    if not isinstance(base, str) or not SHA_RE.fullmatch(base):
        raise WorkflowError("交接单 base_commit 无效")
    history = run_git(
        "rev-list", "--ancestry-path", "--reverse", f"{base}..{head}", check=False
    )
    if history.returncode != 0:
        raise WorkflowError(
            "无法解析交接提交路径："
            + (history.stderr.strip() or history.stdout.strip())
        )
    commits = [line.strip() for line in history.stdout.splitlines() if line.strip()]
    if not commits:
        return base
    first = commits[0]
    subject_result = run_git("show", "-s", "--format=%s", first, check=False)
    if subject_result.returncode != 0:
        raise WorkflowError(
            "无法读取交接首个提交："
            + (subject_result.stderr.strip() or subject_result.stdout.strip())
        )
    lease_prefix = f"lease {task_id} g{generation} @ "
    if subject_result.stdout.strip().startswith(lease_prefix):
        return first
    return base


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
    local_config, local_errors = load_local_config()
    if local_errors:
        raise WorkflowError("无法确定主调度器机器：" + "；".join(local_errors))
    if owner_machine(args.owner) != local_config.get("machine_id"):
        require_origin_main_synchronized("跨机 task assign")
    generation = int(task.get("lease_generation", 0))
    if generation == 0:
        generation = 1
    branch = f"task/{args.id}-g{generation}"
    task_spec_path = find_task_spec_path(args.id)
    transaction_paths: list[Path] = [TASKS_JSON, TASKS_MD, environment_path]
    if task_spec_path is not None:
        transaction_paths.append(task_spec_path)
    with workspace_transaction(
        transaction_paths, managed_refs=(f"refs/heads/{branch}",)
    ):
        task_spec_path = resolve_task_spec_inputs(args.id, base_commit)
        task.update(
            {
                "status": "in_progress",
                "owner": args.owner,
                "lease_generation": generation,
                "branch": branch,
                "base_commit": base_commit,
                "head_commit": None,
                "checkpoint_commit": base_commit,
                "validation_report": None,
                "test_report": None,
                "failure_count": 0,
                "failure_stage": None,
                "stage_failure_count": 0,
                "claimed_at": iso_z(now),
                "heartbeat_at": iso_z(now),
                "lease_expires_at": iso_z(
                    now + timedelta(hours=data["policy"]["lease_hours"])
                ),
                "blocker": None,
            }
        )
        write_json(TASKS_JSON, data)
        TASKS_MD.write_text(render_tasks(data), encoding="utf-8", newline="\n")
        lease_commit = commit_lease_and_create_branch(
            args.id,
            generation,
            args.owner,
            branch,
            environment_path,
            task_spec_path,
        )
    print(
        f"已分配 {args.id} → {args.owner}，generation={generation}，"
        f"branch={task['branch']}，lease_commit={lease_commit}"
    )
    return 0


def task_heartbeat(args: argparse.Namespace) -> int:
    environment_path, _ = lifecycle_preflight("task heartbeat")
    data = load_tasks()
    task = find_task(data, args.id)
    if task.get("status") != "in_progress":
        raise WorkflowError(f"任务不在进行中：{args.id}")
    if int(task.get("lease_generation", -1)) != args.generation:
        raise WorkflowError("隔离令牌已过期，拒绝心跳")
    now = parse_iso_z(args.now) if args.now else utc_now()
    if parse_iso_z(task["lease_expires_at"]) < now:
        raise WorkflowError("租约已经过期；必须由主调度器先执行 reclaim-stale")
    with workspace_transaction((TASKS_JSON, TASKS_MD, environment_path)):
        task["heartbeat_at"] = iso_z(now)
        task["lease_expires_at"] = iso_z(
            now + timedelta(hours=data["policy"]["lease_hours"])
        )
        write_json(TASKS_JSON, data)
        TASKS_MD.write_text(render_tasks(data), encoding="utf-8", newline="\n")
        state_commit = commit_task_state(
            args.id, args.generation, "heartbeat", environment_path
        )
    print(
        f"已续租 {args.id} generation={args.generation}；"
        f"state_commit={state_commit}"
    )
    return 0


def task_reclaim(args: argparse.Namespace) -> int:
    environment_path, _ = lifecycle_preflight("task reclaim-stale")
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
    if not reclaimed:
        print("已回收：无")
        return 0
    with workspace_transaction((TASKS_JSON, TASKS_MD, environment_path)):
        write_json(TASKS_JSON, data)
        TASKS_MD.write_text(render_tasks(data), encoding="utf-8", newline="\n")
        state_commit = commit_scoped_changes(
            "reclaim stale leases: " + ", ".join(reclaimed),
            ("协作/tasks.json", "协作/任务台账.md"),
            (
                "协作/tasks.json",
                "协作/任务台账.md",
                environment_path.relative_to(ROOT).as_posix(),
            ),
            "任务租约回收状态",
        )
    print(f"已回收：{', '.join(reclaimed)}；state_commit={state_commit}")
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
    local_config, local_errors = load_local_config()
    if local_errors:
        raise WorkflowError("无法确定主调度器机器：" + "；".join(local_errors))
    if owner_machine(task["owner"]) != local_config.get("machine_id"):
        require_origin_main_synchronized("跨机 task handoff")
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
    output_base = task_output_base(task, args.head)
    actual_files = sorted(changed_files(output_base, args.head))
    if not actual_files:
        raise WorkflowError("base..head 没有任何变更，拒绝空交接")
    declared_files = sorted(set(args.changed_file))
    if declared_files and declared_files != actual_files:
        raise WorkflowError("--changed-file 与 base..head 的实际变更文件不一致")
    spec = load_task_spec(args.id)
    if spec is not None:
        declared_outputs = set(spec.get("outputs") or [])
        out_of_scope = sorted(
            path
            for path in actual_files
            if not any(path_matches_pattern(path, pattern) for pattern in declared_outputs)
        )
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
        "schema_version": 2,
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
    with workspace_transaction((TASKS_JSON, TASKS_MD, environment_path, handoff_path)):
        write_json(handoff_path, handoff)
        task["status"] = "pending_validation"
        task["head_commit"] = args.head
        task["handoff"] = repo_relative_posix(handoff_path)
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
        f"已登记交接：{repo_relative_posix(handoff_path)}；"
        f"state_commit={state_commit}"
    )
    return 0


def checked_review_path(value: str, *, must_exist: bool = True) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise WorkflowError("审查报告必须使用工作区相对路径")
    candidate = (ROOT / path).resolve()
    review_root = (ROOT / "协作" / "审查记录").resolve()
    try:
        candidate.relative_to(review_root)
    except ValueError as exc:
        raise WorkflowError("审查报告必须位于 协作/审查记录/") from exc
    if must_exist and not candidate.is_file():
        raise WorkflowError(f"审查报告不存在：{value}")
    return candidate


def checked_report_path(value: str) -> str:
    return checked_review_path(value).relative_to(ROOT).as_posix()


def checked_game_test_report_pair(value: str) -> tuple[Path, Path, dict[str, Any]]:
    supplied = checked_review_path(value)
    if supplied.suffix not in {".json", ".md"}:
        raise WorkflowError("加载测试报告必须是同名 .json/.md 报告对")
    json_path = supplied.with_suffix(".json")
    markdown_path = supplied.with_suffix(".md")
    if not json_path.name.startswith("加载测试-"):
        raise WorkflowError("加载测试报告文件名必须以 加载测试- 开头")
    if not json_path.is_file() or not markdown_path.is_file():
        raise WorkflowError("加载测试报告必须同时存在同名 JSON 与 Markdown")
    report = read_json(json_path)
    if not isinstance(report, dict):
        raise WorkflowError("加载测试报告顶层必须是对象")
    errors = validate_named_schema(
        report,
        "game-test-report.schema.json",
        str(json_path.relative_to(ROOT)),
    )
    markdown = markdown_path.read_text(encoding="utf-8")
    errors.extend(game_test_module.report_files_valid(report, markdown))
    if errors:
        raise WorkflowError("加载测试报告无效：" + "；".join(errors))
    return json_path, markdown_path, report


def render_validation_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# 静态验证报告：{report.get('task_id', 'unknown')}",
        "",
        f"- 代数：`g{report.get('lease_generation')}`",
        f"- 判定：`{report.get('verdict')}`",
        f"- base：`{report.get('base_commit')}`",
        f"- head：`{report.get('head_commit')}`",
        f"- runner：`{report.get('runner_machine')}` / `{report.get('runner_commit')}`",
        f"- 时间：`{report.get('started_at')}` → `{report.get('finished_at')}`",
        "",
        "## 检查",
        "",
        "| 名称 | 退出码 | 命令 |",
        "| --- | ---: | --- |",
    ]
    for check in report.get("checks", []):
        command = str(check.get("command", "")).replace("|", "\\|")
        lines.append(
            f"| {check.get('name', '')} | {check.get('exit_code', '')} | `{command}` |"
        )
    lines.extend(
        [
            "",
            "## 验证证据",
            "",
            "| 检查项 | 结果 | 证据 |",
            "| --- | --- | --- |",
        ]
    )
    for item in report.get("evidence", []):
        detail = str(item.get("detail", "")).replace("|", "\\|")
        lines.append(
            f"| {item.get('name', '')} | {item.get('result', '')} | {detail} |"
        )
    consumed = report.get("consumed_by")
    lines.extend(
        [
            "",
            "## 登记状态",
            "",
            (
                f"已消费：`{consumed.get('task_id')}` g{consumed.get('generation')} "
                f"/ `{consumed.get('result')}` / `{consumed.get('consumed_at')}`"
                if isinstance(consumed, dict)
                else "未消费"
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def checked_validation_report_pair(
    value: str,
) -> tuple[Path, Path, dict[str, Any]]:
    supplied = checked_review_path(value)
    if supplied.suffix not in {".json", ".md"}:
        raise WorkflowError("静态验证报告必须是同名 .json/.md 报告对")
    json_path = supplied.with_suffix(".json")
    markdown_path = supplied.with_suffix(".md")
    if not json_path.name.startswith("验证-"):
        raise WorkflowError("静态验证报告文件名必须以 验证- 开头")
    if not json_path.is_file() or not markdown_path.is_file():
        raise WorkflowError("静态验证报告必须同时存在同名 JSON 与 Markdown")
    report = read_json(json_path)
    if not isinstance(report, dict):
        raise WorkflowError("静态验证报告顶层必须是对象")
    errors = validate_named_schema(
        report,
        "validation-report.schema.json",
        str(json_path.relative_to(ROOT)),
    )
    markdown = markdown_path.read_text(encoding="utf-8")
    expected_markdown = render_validation_markdown(report)
    if markdown != expected_markdown:
        errors.append("Markdown 与结构化报告不可重复渲染")
    if errors:
        raise WorkflowError("静态验证报告无效：" + "；".join(errors))
    return json_path, markdown_path, report


def render_validation_report_command(args: argparse.Namespace) -> int:
    json_path = checked_review_path(args.report)
    if json_path.suffix != ".json" or not json_path.name.startswith("验证-"):
        raise WorkflowError("--report 必须指向 验证-*.json")
    report = read_json(json_path)
    errors = validate_named_schema(
        report,
        "validation-report.schema.json",
        str(json_path.relative_to(ROOT)),
    )
    if errors:
        raise WorkflowError("静态验证报告无效：" + "；".join(errors))
    markdown_path = json_path.with_suffix(".md")
    markdown_path.write_text(
        render_validation_markdown(report), encoding="utf-8", newline="\n"
    )
    print(f"已生成 {markdown_path.relative_to(ROOT).as_posix()}")
    return 0


def validate_validation_report_for_task(
    report: dict[str, Any], task: dict[str, Any], requested_result: str
) -> None:
    expected_verdict = "PASS" if requested_result == "pass" else "FAIL"
    current = run_git("rev-parse", "HEAD").stdout.strip()
    checks = (
        (report.get("task_id") == task.get("id"), "task_id 与任务不匹配"),
        (
            report.get("lease_generation") == task.get("lease_generation"),
            "lease_generation 与任务不匹配",
        ),
        (report.get("base_commit") == task.get("base_commit"), "base_commit 与任务不匹配"),
        (report.get("head_commit") == task.get("head_commit"), "head_commit 与任务不匹配"),
        (report.get("verdict") == expected_verdict, "verdict 与命令结果不匹配"),
        (report.get("runner_commit") == current, "runner_commit 不是当前控制面 HEAD"),
        (report.get("git_dirty") is False, "验证运行时工作区不是干净状态"),
        (report.get("registrable") is True, "报告不可登记"),
        (report.get("consumed_by") is None, "报告已经被消费，拒绝重放"),
    )
    failures = [message for ok, message in checks if not ok]
    if failures:
        raise WorkflowError("；".join(failures))
    commands = report.get("checks", [])
    names = {item.get("name") for item in commands if isinstance(item, dict)}
    if not {"range-validation", "unit-tests"}.issubset(names):
        raise WorkflowError("静态验证报告缺少 range-validation 或 unit-tests")
    range_check = next(item for item in commands if item.get("name") == "range-validation")
    range_command = range_check.get("command", "")
    required_range_tokens = (
        "scripts/workflow.py validate",
        f"--base {report['base_commit']}",
        f"--head {report['head_commit']}",
    )
    if not all(token in range_command for token in required_range_tokens):
        raise WorkflowError("range-validation 命令未绑定报告 base/head")
    unit_check = next(item for item in commands if item.get("name") == "unit-tests")
    if "unittest discover -s tests" not in unit_check.get("command", ""):
        raise WorkflowError("unit-tests 命令不是项目完整测试入口")
    exit_codes = [item.get("exit_code") for item in commands if isinstance(item, dict)]
    if requested_result == "pass" and any(code != 0 for code in exit_codes):
        raise WorkflowError("PASS 报告包含失败命令")
    if requested_result == "fail" and not any(code != 0 for code in exit_codes):
        raise WorkflowError("FAIL 报告没有失败命令")
    evidence_results = [
        item.get("result") for item in report.get("evidence", []) if isinstance(item, dict)
    ]
    if requested_result == "pass" and any(result != "PASS" for result in evidence_results):
        raise WorkflowError("PASS 报告包含失败验证证据")
    if requested_result == "fail" and not any(result == "FAIL" for result in evidence_results):
        raise WorkflowError("FAIL 报告没有失败验证证据")
    try:
        started_at = parse_iso_z(report["started_at"])
        finished_at = parse_iso_z(report["finished_at"])
    except (KeyError, TypeError, WorkflowError) as exc:
        raise WorkflowError("静态验证报告时间无效") from exc
    if finished_at < started_at:
        raise WorkflowError("静态验证报告 finished_at 早于 started_at")
    runner_machine = report.get("runner_machine")
    local_config, local_errors = load_local_config()
    if local_errors:
        raise WorkflowError("本机配置无效：" + "；".join(local_errors))
    if runner_machine != local_config.get("machine_id"):
        raise WorkflowError("静态验证结果只能在原 runner 机器登记")
    environment_path = ENV_DIR / f"{runner_machine}.json"
    environment = read_json(environment_path)
    if report.get("runner_environment_checked_at") != environment.get("checked_at"):
        raise WorkflowError("runner_environment_checked_at 与当前环境快照不匹配")
    checked_at = parse_iso_z(environment["checked_at"])
    if checked_at > started_at or started_at - checked_at > timedelta(
        minutes=ENV_FRESHNESS_MINUTES
    ):
        raise WorkflowError("静态验证报告绑定的环境快照在验证开始时不新鲜")
    if not environment.get("capabilities", {}).get("static_validation"):
        raise WorkflowError("runner 机器没有 static_validation 能力")
    for label, commit in (
        ("base_commit", report["base_commit"]),
        ("head_commit", report["head_commit"]),
        ("runner_commit", report["runner_commit"]),
    ):
        exists = run_git("cat-file", "-e", f"{commit}^{{commit}}", check=False)
        if exists.returncode != 0:
            raise WorkflowError(f"{label} 在当前仓库中不存在")


def mod_tree_sha256() -> str:
    mod_root = ROOT / "mod"
    digest = hashlib.sha256()
    if not mod_root.is_dir():
        return digest.hexdigest()
    for path in sorted(item for item in mod_root.rglob("*") if item.is_file()):
        relative = path.relative_to(mod_root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        payload = path.read_bytes()
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def validate_test_report_for_task(
    report: dict[str, Any], task: dict[str, Any], requested_result: str
) -> None:
    expected_verdict = "PASS" if requested_result == "pass" else "FAIL"
    profiles = game_test_profiles()
    profile = profiles.get(report.get("profile"))
    expected_profile_hash = canonical_json_sha256(profile) if isinstance(profile, dict) else None
    expected_rules_hash = (
        canonical_json_sha256(profile.get("rules", []))
        if isinstance(profile, dict)
        else None
    )
    current = run_git("rev-parse", "HEAD").stdout.strip()
    checks = (
        (report.get("task_id") == task.get("id"), "task_id 与任务不匹配"),
        (
            report.get("generation") == task.get("lease_generation"),
            "generation 与任务不匹配",
        ),
        (report.get("git_head") == current, "git_head 与当前被测提交不匹配"),
        (report.get("git_dirty") is False, "报告绑定了 dirty 工作树"),
        (report.get("verdict") == expected_verdict, f"verdict 必须为 {expected_verdict}"),
        (report.get("registrable") is True, "报告不可登记"),
        (report.get("consumed_by") is None, "报告已经被消费，拒绝重放"),
        (
            report.get("profile") in game_test_module.REGISTRABLE_PROFILES,
            "profile 不可登记",
        ),
        (
            isinstance(report.get("baseline_contract_id"), str)
            and bool(report.get("baseline_contract_id")),
            "缺少 baseline_contract_id",
        ),
        (
            report.get("mod_tree_sha256") == mod_tree_sha256(),
            "mod_tree_sha256 与当前 mod 内容树不匹配",
        ),
        (
            report.get("profile_hash") == expected_profile_hash,
            "profile_hash 与当前受控 profile 不匹配",
        ),
        (
            report.get("rules_hash") == expected_rules_hash,
            "rules_hash 与当前受控规则不匹配",
        ),
        (
            isinstance(report.get("executable_sha256"), str),
            "可登记报告缺少 executable_sha256",
        ),
        (
            isinstance(report.get("mod_descriptor_sha256"), str),
            "可登记报告缺少 mod_descriptor_sha256",
        ),
    )
    for valid, message in checks:
        if not valid:
            raise WorkflowError(message)
    runner_machine = report.get("runner_machine_id")
    if not isinstance(runner_machine, str) or not runner_machine:
        raise WorkflowError("缺少 runner_machine_id")
    environment_path = ENV_DIR / f"{runner_machine}.json"
    if not environment_path.is_file():
        raise WorkflowError("缺少 runner 机器环境快照")
    runner_environment = read_json(environment_path)
    environment_errors = validate_named_schema(
        runner_environment,
        "environment.schema.json",
        str(environment_path.relative_to(ROOT)),
    )
    if environment_errors:
        raise WorkflowError("runner 环境快照无效：" + "；".join(environment_errors))
    if runner_environment.get("machine_id") != runner_machine:
        raise WorkflowError("runner 环境快照 machine_id 不匹配")
    if not runner_environment.get("capabilities", {}).get("load_test"):
        raise WorkflowError("runner 机器没有 load_test 能力")
    try:
        started_at = parse_iso_z(report["started_at"])
        report_checked_at = parse_iso_z(report["runner_environment_checked_at"])
        current_checked_at = parse_iso_z(runner_environment["checked_at"])
    except (KeyError, TypeError, WorkflowError) as exc:
        raise WorkflowError("报告或 runner 环境时间无效") from exc
    if report_checked_at > started_at or started_at - report_checked_at > timedelta(
        minutes=ENV_FRESHNESS_MINUTES
    ):
        raise WorkflowError("报告绑定的 runner 环境快照在测试开始时不新鲜")
    if current_checked_at < report_checked_at:
        raise WorkflowError("当前 runner 环境快照早于报告绑定快照")

    local_config, local_errors = load_local_config()
    if local_errors:
        raise WorkflowError("本机配置无效：" + "；".join(local_errors))
    if local_config.get("machine_id") != runner_machine:
        raise WorkflowError("加载测试结果只能在原 runner 机器登记")
    live_environment = derive_environment(local_config, [], probe_external=True)
    if not live_environment.get("capabilities", {}).get("load_test"):
        raise WorkflowError("本机实时复核没有 load_test 能力")
    game_test_config = local_config.get("game_test")
    if not isinstance(game_test_config, dict):
        raise WorkflowError("本机缺少 game_test 配置")
    executable_value = game_test_config.get("executable_path")
    descriptor_value = game_test_config.get("mod_descriptor_path")
    game_path_value = local_config.get("game_path")
    if not all(
        isinstance(value, str) and value
        for value in (executable_value, descriptor_value, game_path_value)
    ):
        raise WorkflowError("本机 game_test 路径配置不完整")
    executable = Path(executable_value).expanduser().resolve()
    descriptor = Path(descriptor_value).expanduser().resolve()
    game_root = Path(game_path_value).expanduser().resolve()
    trusted = {(game_root / name).resolve() for name in TRUSTED_GAME_EXECUTABLES}
    if executable not in trusted or not executable.is_file():
        raise WorkflowError("本机 HOI4 可执行文件不受信或不存在")
    if not descriptor.is_file():
        raise WorkflowError("本机 mod 描述符不存在")
    if report.get("executable_sha256") != sha256_file(executable):
        raise WorkflowError("executable_sha256 与 runner 实机不匹配")
    if report.get("mod_descriptor_sha256") != sha256_file(descriptor):
        raise WorkflowError("mod_descriptor_sha256 与 runner 实机不匹配")
    task_head = task.get("head_commit")
    if not isinstance(task_head, str) or not SHA_RE.fullmatch(task_head):
        raise WorkflowError("任务 head_commit 无效")
    task_ancestor = run_git(
        "merge-base", "--is-ancestor", task_head, report["git_head"], check=False
    )
    if task_ancestor.returncode != 0:
        raise WorkflowError("任务 head 不是被测提交的祖先")
    runner = report.get("runner_commit")
    if not isinstance(runner, str) or not SHA_RE.fullmatch(runner):
        raise WorkflowError("runner_commit 无效")
    exists = run_git("cat-file", "-e", f"{runner}^{{commit}}", check=False)
    if exists.returncode != 0:
        raise WorkflowError("runner_commit 在当前仓库不存在")
    ancestor = run_git("merge-base", "--is-ancestor", runner, current, check=False)
    if ancestor.returncode != 0:
        raise WorkflowError("runner_commit 不是当前控制面提交的祖先")


def assert_task_generation(task: dict[str, Any], generation: int) -> None:
    if int(task.get("lease_generation", -1)) != generation:
        raise WorkflowError("隔离令牌已过期，拒绝操作")


def find_task_spec_path(task_id: str) -> Path | None:
    """Locate a task spec by id, searching the active layer only (D-20260812-021).

    Archived specs under ``_归档/`` are excluded so completed tasks never
    participate in runtime gates.  Duplicate active hits fail closed instead of
    guessing.
    """
    if not TASK_SPEC_DIR.is_dir():
        return None
    hits = sorted(
        path
        for path in TASK_SPEC_DIR.rglob("T-*.json")
        if path.stem == task_id and "_归档" not in path.parts
    )
    if len(hits) > 1:
        raise WorkflowError(f"任务书 {task_id} 在活动层重复存在：" + ", ".join(str(p) for p in hits))
    return hits[0] if hits else None


def load_task_spec(task_id: str) -> dict[str, Any] | None:
    path = find_task_spec_path(task_id)
    if path is None:
        return None
    try:
        data = read_json(path)
    except WorkflowError:
        return None
    return data if isinstance(data, dict) else None


def resolve_task_spec_inputs(task_id: str, base_commit: str) -> Path | None:
    """Resolve dynamic task inputs before the lease commit is created."""
    path = find_task_spec_path(task_id)
    if path is None:
        return None
    data = read_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("inputs"), dict):
        raise WorkflowError(f"{path.relative_to(ROOT)}: inputs 无效")
    snapshot = snapshot_metadata()
    if snapshot is None:
        raise WorkflowError("当前受控快照无效，无法解析任务书输入")
    required_snapshot_schema = data["inputs"].get("snapshot_schema_version")
    if (
        isinstance(required_snapshot_schema, int)
        and snapshot.get("schema_version") != required_snapshot_schema
    ):
        raise WorkflowError(
            f"任务 {task_id} 要求 snapshot schema v{required_snapshot_schema}，"
            f"当前为 v{snapshot.get('schema_version')}"
        )
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
    json_path, markdown_path, report_data = checked_validation_report_pair(args.report)
    report_paths = tuple(
        path.relative_to(ROOT).as_posix() for path in (json_path, markdown_path)
    )
    environment_path, _ = lifecycle_preflight(
        "task validation-result", report_paths
    )
    data = load_tasks()
    task = find_task(data, args.id)
    if task.get("status") != "pending_validation":
        raise WorkflowError(f"任务不在待验证状态：{args.id}")
    assert_task_generation(task, args.generation)
    validate_validation_report_for_task(report_data, task, args.result)
    managed_refs = (f"refs/heads/task/{args.id}-g{args.generation + 1}",)
    with workspace_transaction(
        (TASKS_JSON, TASKS_MD, environment_path, json_path, markdown_path),
        managed_refs=managed_refs,
    ):
        report_data["consumed_by"] = {
            "task_id": args.id,
            "generation": args.generation,
            "result": args.result,
            "consumed_at": iso_z(utc_now()),
        }
        write_json(json_path, report_data)
        markdown_path.write_text(
            render_validation_markdown(report_data), encoding="utf-8", newline="\n"
        )
        task["validation_report"] = markdown_path.relative_to(ROOT).as_posix()
        if args.result == "pass":
            spec = load_task_spec(args.id)
            acceptance = spec.get("acceptance", {}) if isinstance(spec, dict) else {}
            spec_requires_load_test = (
                isinstance(acceptance, dict)
                and acceptance.get("requires_load_test") is True
            )
            task["status"] = (
                "pending_test"
                if args.requires_load_test or spec_requires_load_test
                else "ready_to_merge"
            )
            task["blocker"] = None
            reset_failure_counters(task)
            advance_checkpoint(task)
        else:
            now = parse_iso_z(args.now) if args.now else utc_now()
            reopen_task(
                task,
                data,
                now,
                f"验证失败：{markdown_path.relative_to(ROOT).as_posix()}",
                stage="validation",
            )
        write_json(TASKS_JSON, data)
        TASKS_MD.write_text(render_tasks(data), encoding="utf-8", newline="\n")
        state_commit = commit_task_state(
            args.id,
            args.generation,
            f"validation-{args.result}",
            environment_path,
            required_artifacts=(json_path,),
            optional_artifacts=(markdown_path,),
        )
    print(
        f"已登记验证结果：{args.id} -> {task['status']}；"
        f"state_commit={state_commit}"
    )
    return 0


def task_test_result(args: argparse.Namespace) -> int:
    json_path, markdown_path, report_data = checked_game_test_report_pair(args.report)
    report_paths = tuple(
        path.relative_to(ROOT).as_posix() for path in (json_path, markdown_path)
    )
    environment_path, _ = lifecycle_preflight("task test-result", report_paths)
    data = load_tasks()
    task = find_task(data, args.id)
    if task.get("status") != "pending_test":
        raise WorkflowError(f"任务不在待测试状态：{args.id}")
    assert_task_generation(task, args.generation)
    require_origin_main_synchronized("task test-result")
    validate_test_report_for_task(report_data, task, args.result)
    managed_refs = (f"refs/heads/task/{args.id}-g{args.generation + 1}",)
    with workspace_transaction(
        (TASKS_JSON, TASKS_MD, environment_path, json_path, markdown_path),
        managed_refs=managed_refs,
    ):
        task["test_report"] = markdown_path.relative_to(ROOT).as_posix()
        report_data["consumed_by"] = {
            "task_id": args.id,
            "generation": args.generation,
            "result": args.result,
            "consumed_at": iso_z(utc_now()),
        }
        write_json(json_path, report_data)
        markdown_path.write_text(
            game_test_module.render_markdown(report_data), encoding="utf-8", newline="\n"
        )
        if args.result == "pass":
            task["status"] = "ready_to_merge"
            task["blocker"] = None
            reset_failure_counters(task)
            advance_checkpoint(task)
        else:
            now = parse_iso_z(args.now) if args.now else utc_now()
            reopen_task(task, data, now, f"加载测试失败：{json_path.relative_to(ROOT)}", stage="test")
        write_json(TASKS_JSON, data)
        TASKS_MD.write_text(render_tasks(data), encoding="utf-8", newline="\n")
        state_commit = commit_task_state(
            args.id,
            args.generation,
            f"test-{args.result}",
            environment_path,
            required_artifacts=(json_path,),
            optional_artifacts=(markdown_path,),
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
    spec_source = find_task_spec_path(args.id)
    archived_spec: Path | None = None
    if spec_source is not None:
        requirement_dir = spec_source.parent
        if requirement_dir == TASK_SPEC_DIR or "_归档" in requirement_dir.parts:
            raise WorkflowError(
                f"任务书 {args.id} 未位于需求子目录，无法确定归档位置"
            )
        archived_spec = requirement_dir / "_归档" / spec_source.name
    transaction_paths: list[Path] = [TASKS_JSON, TASKS_MD, environment_path]
    if spec_source is not None and archived_spec is not None:
        transaction_paths.extend((spec_source, archived_spec))
    with workspace_transaction(transaction_paths):
        if spec_source is not None and archived_spec is not None:
            archived_spec.parent.mkdir(parents=True, exist_ok=True)
            # 用纯文件移动（不动 git index）：commit_scoped_changes 的 git add
            # 会同时暂存旧路径删除与新路径新增。
            try:
                spec_source.replace(archived_spec)
            except OSError as exc:
                raise WorkflowError(f"任务书归档失败（{args.id}）：{exc}") from exc
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
            extra_allowed_paths=(archived_spec, spec_source)
            if archived_spec is not None
            else (),
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
    with workspace_transaction((TASKS_JSON, TASKS_MD, environment_path)):
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


def task_merge(args: argparse.Namespace) -> int:
    _, _ = lifecycle_preflight("task merge")
    data = load_tasks()
    task = find_task(data, args.id)
    spec = load_task_spec(args.id)
    load_test_pending = (
        task.get("status") == "pending_test"
        and isinstance(spec, dict)
        and spec.get("acceptance", {}).get("requires_load_test") is True
    )
    if task.get("status") != "ready_to_merge" and not load_test_pending:
        raise WorkflowError(f"任务不在待合并状态：{args.id}")
    assert_task_generation(task, args.generation)
    head = task.get("head_commit")
    branch = task.get("branch")
    if not isinstance(head, str) or not SHA_RE.fullmatch(head):
        raise WorkflowError("任务 head_commit 无效")
    if not isinstance(branch, str) or not branch:
        raise WorkflowError("任务 branch 无效")
    branch_tip = resolve_task_branch_tip(branch)
    if branch_tip != head:
        raise WorkflowError(f"任务分支 tip 与已验证 head 不一致：{branch_tip}")
    merge_check(argparse.Namespace(head=head))
    environment = os.environ.copy()
    environment["TEG_MERGE_HEAD"] = head
    result = subprocess.run(
        ["git", "merge", "--no-ff", "--no-edit", branch],
        cwd=ROOT,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        abort = run_git("merge", "--abort", check=False)
        abort_note = "已自动恢复合并前现场" if abort.returncode == 0 else "自动恢复失败，需主代理检查"
        detail = result.stderr.strip() or result.stdout.strip()
        raise WorkflowError(f"受控合并失败：{detail}；{abort_note}")
    merged = run_git("merge-base", "--is-ancestor", head, "main", check=False)
    if merged.returncode != 0:
        raise WorkflowError("受控合并返回成功，但任务 head 未进入 main")
    print(f"已受控合并 {args.id} g{args.generation}: {head}")
    return 0


def merge_check(args: argparse.Namespace) -> int:
    candidate = args.head
    if not isinstance(candidate, str) or not SHA_RE.fullmatch(candidate):
        raise WorkflowError("merge-check --head 必须是40位小写 Git SHA")
    exists = run_git("cat-file", "-e", f"{candidate}^{{commit}}", check=False)
    if exists.returncode != 0:
        raise WorkflowError(f"待合并提交不存在：{candidate}")
    current = run_git("rev-parse", "HEAD").stdout.strip()
    data = load_tasks()
    blocked: list[str] = []
    for task in data.get("tasks", []):
        if task.get("status") in {"ready_to_merge", "done"}:
            continue
        commit = task.get("head_commit")
        if not isinstance(commit, str) or not SHA_RE.fullmatch(commit):
            branch = task.get("branch")
            if not isinstance(branch, str):
                continue
            tip = run_git("rev-parse", "--verify", f"refs/heads/{branch}", check=False)
            if tip.returncode != 0:
                continue
            commit = tip.stdout.strip()
        introduced = run_git(
            "merge-base", "--is-ancestor", commit, candidate, check=False
        ).returncode == 0
        already_present = run_git(
            "merge-base", "--is-ancestor", commit, current, check=False
        ).returncode == 0
        if introduced and not already_present:
            spec = load_task_spec(task.get("id"))
            load_test_pending = (
                task.get("status") == "pending_test"
                and isinstance(spec, dict)
                and spec.get("acceptance", {}).get("requires_load_test") is True
            )
            if not load_test_pending:
                blocked.append(f"{task.get('id')}={task.get('status')}")
    if blocked:
        raise WorkflowError(
            "待合并提交包含尚未达到 ready_to_merge 的任务：" + ", ".join(blocked)
        )
    print(f"MERGE GATE PASSED: {candidate}")
    return 0


def sync_check_command(args: argparse.Namespace) -> int:
    behind, ahead = origin_main_divergence()
    if behind or ahead:
        raise WorkflowError(
            f"origin/main 与 main 未同步：落后 {behind}、领先 {ahead}"
        )
    print("ORIGIN SYNC PASSED: behind=0 ahead=0")
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
        if task.get("legacy") is True:
            continue
        valid_commits: dict[str, str] = {}
        for field in ("base_commit", "head_commit", "checkpoint_commit"):
            commit = task.get(field)
            if commit is None:
                continue
            if not isinstance(commit, str) or not SHA_RE.fullmatch(commit):
                errors.append(f"{task_id}: {field} 无效")
                continue
            exists = run_git("cat-file", "-e", f"{commit}^{{commit}}", check=False)
            if exists.returncode != 0:
                errors.append(f"{task_id}: {field} 引用的提交不存在：{commit}")
                continue
            valid_commits[field] = commit
        base = valid_commits.get("base_commit")
        head = valid_commits.get("head_commit")
        checkpoint = valid_commits.get("checkpoint_commit")
        if base and head:
            ancestor = run_git("merge-base", "--is-ancestor", base, head, check=False)
            if ancestor.returncode != 0:
                errors.append(f"{task_id}: head_commit 不是 base_commit 的后代")
        if base and checkpoint:
            ancestor = run_git(
                "merge-base", "--is-ancestor", base, checkpoint, check=False
            )
            if ancestor.returncode != 0:
                errors.append(f"{task_id}: checkpoint_commit 不是 base_commit 的后代")
        if head and checkpoint:
            ancestor = run_git(
                "merge-base", "--is-ancestor", checkpoint, head, check=False
            )
            if ancestor.returncode != 0:
                errors.append(f"{task_id}: checkpoint_commit 不是 head_commit 的祖先")
        merged_into_main = False
        if head and ref_exists("refs/heads/main"):
            merged_into_main = run_git(
                "merge-base", "--is-ancestor", head, "main", check=False
            ).returncode == 0
        if status == "done" and head and not merged_into_main:
            errors.append(f"{task_id}: done 任务 head_commit 尚未进入 main")
        exception = task.get("premature_merge_exception")
        exception_valid = False
        if exception is not None:
            if status not in {"pending_validation", "pending_test"}:
                errors.append(f"{task_id}: 仅待验证/待测试任务可登记提前合并异常")
            elif not isinstance(exception, dict):
                errors.append(f"{task_id}: premature_merge_exception 必须是对象")
            else:
                decision_id = exception.get("decision_id")
                exception_valid = (
                    exception.get("head_commit") == head
                    and isinstance(decision_id, str)
                    and (DECISION_DIR / f"{decision_id}.json").is_file()
                )
                if not exception_valid:
                    errors.append(f"{task_id}: 提前合并异常未绑定当前 head 与任务决策")
                elif not merged_into_main:
                    errors.append(f"{task_id}: 提前合并异常登记与 Git 历史不一致")
        if (
            status in {"pending_validation", "pending_test"}
            and head
            and merged_into_main
            and not exception_valid
        ):
            spec = load_task_spec(task_id)
            load_test_pending = (
                status == "pending_test"
                and isinstance(spec, dict)
                and spec.get("acceptance", {}).get("requires_load_test") is True
            )
            if not load_test_pending:
                errors.append(f"{task_id}: {status} 的 head_commit 已提前进入 main")

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


def validate_country_tag_snapshot(errors: list[str]) -> None:
    json_exists = COUNTRY_TAG_SNAPSHOT_JSON.is_file()
    md_exists = COUNTRY_TAG_SNAPSHOT_MD.is_file()
    if not json_exists:
        if md_exists:
            errors.append("协作/扫描快照/country-tags-summary.md 存在，但缺少 country-tags.json")
        return
    try:
        data = read_json(COUNTRY_TAG_SNAPSHOT_JSON)
    except WorkflowError as exc:
        errors.append(str(exc))
        return
    errors.extend(
        validate_named_schema(
            data,
            "country-tag-snapshot.schema.json",
            "协作/扫描快照/country-tags.json",
        )
    )
    semantic_errors = country_tag_snapshot_errors(data)
    errors.extend(
        f"协作/扫描快照/country-tags.json: {item}"
        for item in semantic_errors
    )
    if semantic_errors:
        return
    expected = render_country_tag_snapshot_summary(data)
    actual = (
        COUNTRY_TAG_SNAPSHOT_MD.read_text(encoding="utf-8") if md_exists else ""
    )
    if actual != expected:
        errors.append(
            "协作/扫描快照/country-tags-summary.md 不是由当前 country-tags.json 生成"
        )


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
        if path.name == "经济与工业.json" and isinstance(data, dict):
            errors.extend(
                f"{label}: {item}" for item in industrial_override_policy_errors(data)
            )
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
        merged = state_transform.merge_override_documents(documents, fingerprint)
        snapshot = snapshot_metadata()
        uniqueness = state_transform.province_uniqueness_errors(merged, snapshot)
        if uniqueness:
            errors.extend(f"协作/state-overrides/: {item}" for item in uniqueness)
    except state_transform.StateTransformError as exc:
        errors.append(f"协作/state-overrides/: {exc}")
    except state_transform.StateTransformError as exc:
        errors.append(f"协作/state-overrides/: {exc}")
    snapshot = snapshot_metadata()
    if snapshot is not None and snapshot["source"]["fingerprint"] != fingerprint:
        errors.append("协作/state-overrides/: 改写清单指纹与当前受控快照不一致")


def base_slot_capacity(state_id: int) -> int | None:
    """原版基础槽位（快照 v3 state_category → local_building_slots）。"""

    snapshot = snapshot_metadata()
    if snapshot is None:
        return None
    categories = {
        item.get("name"): item.get("local_building_slots")
        for item in snapshot.get("state_categories", [])
        if isinstance(item, dict)
    }
    for state in snapshot.get("states", []):
        if not isinstance(state, dict) or state.get("state_id") != state_id:
            continue
        category = state.get("state_category")
        if category in categories and isinstance(categories[category], int):
            return categories[category]
        return None
    return None


def industrial_override_policy_errors(data: dict[str, Any]) -> list[str]:
    """Enforce D-20260812-014/066 on the dedicated initial-industry document."""

    errors: list[str] = []
    total = 0
    overrides = data.get("overrides")
    if not isinstance(overrides, list):
        return ["overrides 必须是数组"]
    japan_seen: dict[int, dict] = {}
    for item in overrides:
        if not isinstance(item, dict):
            continue
        state_id = item.get("state_id", "?")
        buildings = item.get("buildings")
        if not isinstance(buildings, dict):
            errors.append(f"state {state_id} 缺少 buildings")
            continue
        unknown = sorted(set(buildings) - SHARED_FACTORY_KEYS)
        if unknown:
            errors.append(f"state {state_id} 使用非共享工厂引擎键：{unknown}")
        values = [
            value
            for key, value in buildings.items()
            if key in SHARED_FACTORY_KEYS and isinstance(value, int) and value >= 0
        ]
        state_total = sum(values)
        total += state_total
        if state_total > SHARED_FACTORY_SLOT_CAP:
            errors.append(
                f"state {state_id} 共享工厂 {state_total} 超过上限 {SHARED_FACTORY_SLOT_CAP}"
            )
        if isinstance(state_id, int) and state_id in JAPAN_FACTORY_PLAN:
            japan_seen[state_id] = buildings
    if total != INITIAL_SHARED_FACTORY_TOTAL:
        errors.append(
            f"初始共享工厂总数必须保持 {INITIAL_SHARED_FACTORY_TOTAL}，实际 {total}"
        )
    for state_id, plan in JAPAN_FACTORY_PLAN.items():
        if state_id not in japan_seen:
            errors.append(
                f"日本列岛 {state_id} 州工厂条目缺失（D-20260812-066 计划 {plan}）"
            )
            continue
        actual = japan_seen[state_id]
        if any(actual.get(key) != value for key, value in plan.items()):
            errors.append(
                f"日本列岛 {state_id} 州工厂 {actual} 与 D-20260812-066 计划 {plan} 不符"
            )
        capacity = base_slot_capacity(state_id)
        plan_total = sum(plan.values())
        if isinstance(capacity, int) and plan_total > capacity:
            errors.append(
                f"日本列岛 {state_id} 州计划 {plan_total} 厂超过原版基础槽位 {capacity}"
            )
    return errors


def building_slot_define_errors(text: str) -> list[str]:
    matches = re.findall(
        r"^\s*NDefines\.NBuildings\.MAX_SHARED_SLOTS\s*=\s*(\d+)\s*(?:--.*)?$",
        text,
        flags=re.MULTILINE,
    )
    expected = str(SHARED_FACTORY_SLOT_CAP)
    if matches != [expected]:
        return [
            "mod/common/defines/zz_txg_defines.lua 必须且只能声明一次 "
            f"NDefines.NBuildings.MAX_SHARED_SLOTS = {expected}"
        ]
    return []


def parse_ideology_poles(text: str) -> dict[str, str]:
    poles: dict[str, str] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        pole_match = re.fullmatch(
            r"(democratic|communism|fascism|neutrality)\s*=\s*\{", line
        )
        if pole_match:
            current = pole_match.group(1)
            continue
        if current is None:
            continue
        subtype_match = re.fullmatch(
            r"([a-z][a-z0-9_]*)\s*=\s*\{\s*can_be_randomly_selected\s*=\s*no\s*\}\s*",
            line,
        )
        if subtype_match:
            poles[subtype_match.group(1)] = current
    return poles


AXIS_KEYS = ("e", "p", "f", "l", "o")


def engine_pole_of(
    e: int, p: int, f: int, l: int, o: int, thresholds: dict[str, int]
) -> str | None:
    required = (
        "communism_l_max",
        "communism_e_min",
        "communism_o_max",
        "fascism_l_min",
        "fascism_f_min",
        "fascism_p_min",
        "democratic_p_max",
    )
    values = [thresholds.get(key) for key in required]
    if any(not isinstance(value, int) for value in values):
        return None
    communism_l_max, communism_e_min, communism_o_max = values[0:3]
    fascism_l_min, fascism_f_min, fascism_p_min = values[3:6]
    democratic_p_max = values[6]
    assert isinstance(communism_l_max, int) and isinstance(communism_e_min, int)
    assert isinstance(communism_o_max, int) and isinstance(fascism_l_min, int)
    assert isinstance(fascism_f_min, int) and isinstance(fascism_p_min, int)
    assert isinstance(democratic_p_max, int)
    if l <= communism_l_max and e >= communism_e_min and o <= communism_o_max:
        return "communism"
    if l >= fascism_l_min and f >= fascism_f_min and p >= fascism_p_min:
        return "fascism"
    if p <= democratic_p_max:
        return "democratic"
    return "neutrality"


def validate_political_spectrum(errors: list[str]) -> None:
    if not POLITICAL_SPECTRUM_DEFAULT.is_file():
        return
    defaults_raw = read_json(POLITICAL_SPECTRUM_DEFAULT)
    errors.extend(
        validate_named_schema(
            defaults_raw,
            POLITICAL_SPECTRUM_SCHEMA,
            display_path(POLITICAL_SPECTRUM_DEFAULT),
        )
    )
    if not POLITICAL_SPECTRUM_PARTIES.is_file():
        errors.append(f"{POLITICAL_SPECTRUM_PARTIES.relative_to(ROOT)} 不存在")
        return
    parties_raw = read_json(POLITICAL_SPECTRUM_PARTIES)
    errors.extend(
        validate_named_schema(
            parties_raw,
            POLITICAL_SPECTRUM_SCHEMA,
            display_path(POLITICAL_SPECTRUM_PARTIES),
        )
    )
    ideologies_text = MOD_IDEOLOGIES_FILE.read_text(encoding="utf-8")
    poles = parse_ideology_poles(ideologies_text)
    if not poles:
        errors.append("mod/common/ideologies/00_ideologies.txt 未解析出任何子类型")
    default_coords = defaults_raw.get("default_coordinates", {})
    missing_in_ideologies = sorted(set(default_coords) - set(poles))
    if missing_in_ideologies:
        errors.append(
            "坐标-40子意识形态.json 子类型未在 00_ideologies.txt 定义："
            + ", ".join(missing_in_ideologies)
        )
    missing_in_defaults = sorted(set(poles) - set(default_coords))
    if missing_in_defaults:
        errors.append(
            "00_ideologies.txt 子类型缺少默认坐标："
            + ", ".join(missing_in_defaults)
        )
    thresholds = defaults_raw.get("thresholds", {})
    engine_pole = thresholds.get("engine_pole", {})
    for key, coord in default_coords.items():
        if key not in poles:
            continue
        derived = engine_pole_of(
            int(coord.get("e", 0)),
            int(coord.get("p", 0)),
            int(coord.get("f", 0)),
            int(coord.get("l", 0)),
            int(coord.get("o", 0)),
            engine_pole,
        )
        if derived is not None and derived != poles[key]:
            errors.append(
                f"{key}: 五轴默认坐标四极判型 {derived} 与 00_ideologies.txt 归属 {poles[key]} 不一致"
            )
    party_coords = parties_raw.get("party_coordinates", {})
    for key, party in party_coords.items():
        if not re.fullmatch(r"TXG_[A-Z][A-Z0-9_]{1,}_[a-z][a-z0-9_]*", key):
            errors.append(f"{key}: 政党 key 不符合 TXG_<TAG>_<party> 规范")
        country_tag = party.get("country_tag")
        if country_tag and not key.startswith(f"TXG_{country_tag}_"):
            errors.append(f"{key}: key 前缀与 country_tag 不一致")
        subtype = party.get("subtype")
        if subtype and subtype not in poles:
            errors.append(f"{key}: 绑定的子类型 {subtype} 不在 40 子类型清单")
            continue
        if subtype in poles:
            derived = engine_pole_of(
                int(party.get("e", 0)),
                int(party.get("p", 0)),
                int(party.get("f", 0)),
                int(party.get("l", 0)),
                int(party.get("o", 0)),
                engine_pole,
            )
            if derived is not None and derived != poles[subtype]:
                errors.append(
                    f"{key}: 国家政党坐标四极判型 {derived} "
                    f"与 subtype {subtype} 归属 {poles[subtype]} 不一致"
                )
    default_decision = defaults_raw.get("decision_id")
    parties_decision = parties_raw.get("decision_id")
    if default_decision and parties_decision and default_decision != parties_decision:
        errors.append(
            "两个坐标 JSON 的 decision_id 不一致："
            f"{default_decision} vs {parties_decision}"
        )
    validate_political_runtime_contract(errors, set(poles))
    validate_country_political_history(errors)
    validate_political_distance_table(errors, defaults_raw)
    validate_opinion_network(errors)
    validate_party_localisation(errors)


def localisation_keys(text: str) -> set[str]:
    return set(re.findall(r"^\s*([A-Za-z0-9_]+):(?:0|1)\s", text, flags=re.MULTILINE))


def validate_political_runtime_contract(
    errors: list[str], subtype_keys: set[str]
) -> None:
    for path in MOD_IDEOLOGY_LOCALISATIONS:
        if not path.is_file():
            errors.append(f"{path.relative_to(ROOT)} 不存在")
            continue
        keys = localisation_keys(path.read_text(encoding="utf-8-sig"))
        missing = sorted(
            key
            for subtype in subtype_keys
            for key in (subtype, f"{subtype}_desc")
            if key not in keys
        )
        if missing:
            errors.append(
                f"{path.relative_to(ROOT)} 缺少意识形态本地化："
                + ", ".join(missing)
            )

    government_text = MOD_GOVERNMENT_EFFECTS_FILE.read_text(encoding="utf-8")
    regime_text = MOD_REGIME_EFFECTS_FILE.read_text(encoding="utf-8")
    on_actions_text = MOD_ON_ACTIONS_FILE.read_text(encoding="utf-8")
    government_markers = (
        "TXG_set_project_party = {",
        "value = token:$PROJECT_PARTY$",
        "value = token:$SUBTYPE$",
        "value = token:$ENGINE_POLE$",
        "ruling_party = $ENGINE_POLE$",
        "set_country_flag = $GOVERNMENT_FLAG$",
    )
    for marker in government_markers:
        if marker not in government_text:
            errors.append(f"项目党派原子入口缺少契约标记：{marker}")
    regime_markers = (
        "TXG_validate_project_party_state = {",
        "TXG_party_state_missing",
        "TXG_party_state_mismatch",
        "modifier = $BAND$",
    )
    for marker in regime_markers:
        if marker not in regime_text:
            errors.append(f"政治状态校验/好感入口缺少契约标记：{marker}")
    if "modifier = TXG_opinion_close" in re.sub(
        r"remove_opinion_modifier\s*=\s*\{[^}]+\}", "", regime_text
    ):
        errors.append("TXG_apply_opinion_band 不得保留固定 close 占位")
    if on_actions_text.count("TXG_validate_project_party_state = yes") < 2:
        errors.append("on_startup 与 on_ruling_party_change 必须都调用项目党派状态校验")
    if "TXG_clear_government_flags = yes" in on_actions_text:
        errors.append("on_actions 不得只清空 8 大政府旗标而不经同步入口重建")


def validate_country_political_history(errors: list[str]) -> None:
    legal_poles = {"communism", "democratic", "fascism", "neutrality"}
    for path in sorted(MOD_COUNTRY_HISTORY_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        values = re.findall(r"\bruling_party\s*=\s*([A-Za-z0-9_]+)", text)
        invalid = sorted(set(values) - legal_poles)
        if invalid:
            errors.append(
                f"{display_path(path)} ruling_party 只能使用引擎四极："
                + ", ".join(invalid)
            )
        if values and "TXG_set_project_party" not in text:
            errors.append(
                f"{display_path(path)} 设置 ruling_party 时必须同步调用 "
                "TXG_set_project_party"
            )
        # K-001 防回归（D-20260817-003）：CHI capital 必须为 608（北京）；
        # 顶层（非日期块）禁止残留 PRC hostile opinion（本世界无 PRC）
        if path.name.startswith("CHI"):
            if not re.search(r"^capital\s*=\s*608", text, re.MULTILINE):
                errors.append(
                    f"{display_path(path)} capital 必须为 608（北京，"
                    "D-20260811-013/D-20260817-003 防回归）"
                )
            depth = 0
            top_level_prc = False
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                depth += line.count("{") - line.count("}")
                if (
                    depth == 0
                    and "target = PRC" in line
                    and "modifier = hostile_status" in line
                ):
                    top_level_prc = True
            if top_level_prc:
                errors.append(
                    f"{display_path(path)} 顶层残留 PRC hostile opinion"
                    "（D-20260817-003 防回归）"
                )


def opinion_band_key(
    subtype_a: str, coord_a: dict[str, int], subtype_b: str, coord_b: dict[str, int]
) -> str:
    """好感档 key（D-20260812-063）：同子类型优先 same_subtype；
    否则按五轴等权曼哈顿距离分档 close/neutral/distant/opposite，
    外交认同差（|Δf|>=80 且 F 符号相反）追加 +FGAP。
    """
    if subtype_a == subtype_b:
        return "same_subtype"
    domestic, _ = political_distance(coord_a, coord_b)
    foreign = abs(int(coord_a.get("f", 0)) - int(coord_b.get("f", 0)))
    band, foreign_gap = opinion_band_for(
        domestic, foreign, int(coord_a.get("f", 0)), int(coord_b.get("f", 0))
    )
    return band + ("+FGAP" if foreign_gap else "")


def validate_opinion_network(errors: list[str]) -> None:
    """好感网络一致性（T-046 g2）：00_txg_opinion_network.txt 的每对档位
    必须与坐标表执政党数据重算一致；每个网络 effect 必须在 on_actions 分派。
    """
    if not MOD_COUNTRY_HISTORY_DIR.is_dir() or not POLITICAL_SPECTRUM_PARTIES.is_file():
        return
    if not MOD_OPINION_NETWORK_FILE.is_file():
        errors.append(f"{display_path(MOD_OPINION_NETWORK_FILE)} 不存在（好感网络）")
        return
    parties = read_json(POLITICAL_SPECTRUM_PARTIES).get("party_coordinates", {})
    ruling: dict[str, tuple[str, dict[str, int]]] = {}
    for path in sorted(MOD_COUNTRY_HISTORY_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        match = re.search(
            r"TXG_project_party value = token:(TXG_[A-Za-z0-9_]+)", text
        )
        if not match:
            continue
        key = match.group(1)
        data = parties.get(key)
        if not data:
            errors.append(f"{display_path(path)} 执政党 {key} 不在坐标表")
            continue
        tag = data.get("country_tag")
        if not isinstance(tag, str) or not tag.isupper():
            errors.append(f"{display_path(path)} 政党 {key} 缺少合法 country_tag")
            continue
        ruling[tag] = (str(data.get("subtype", "")), data)
    tags = sorted(ruling)
    if len(tags) < 2:
        errors.append("好感网络需要至少两个拥有项目执政党的国家")
        return
    expected: dict[tuple[str, str], str] = {}
    for a in tags:
        for b in tags:
            if a >= b:
                continue
            expected[(a, b)] = opinion_band_key(
                ruling[a][0], ruling[a][1], ruling[b][0], ruling[b][1]
            )
    text = MOD_OPINION_NETWORK_FILE.read_text(encoding="utf-8")
    for a in tags:
        block = re.search(
            r"TXG_opinion_network_%s\s*=\s*\{(.*?)\n\}" % a, text, re.S
        )
        if block is None:
            errors.append(
                f"{display_path(MOD_OPINION_NETWORK_FILE)} 缺少 TXG_opinion_network_{a}"
            )
            continue
        adds: dict[str, set[str]] = {}
        for line in block.group(1).splitlines():
            add = re.search(
                r"add_opinion_modifier\s*=\s*\{\s*target\s*=\s*(\w+)"
                r"\s+modifier\s*=\s*(TXG_opinion_\w+)\s*\}",
                line,
            )
            if add:
                adds.setdefault(add.group(1), set()).add(add.group(2))
        for b in tags:
            if a == b:
                continue
            exp = expected[(a, b) if a < b else (b, a)]
            want = {"TXG_opinion_" + exp.replace("+FGAP", "")}
            if "+FGAP" in exp:
                want.add("TXG_opinion_foreign_gap")
            actual = adds.get(b)
            if actual != want:
                errors.append(
                    f"{display_path(MOD_OPINION_NETWORK_FILE)} {a}->{b} "
                    f"档 {sorted(actual or [])} 与坐标重算 {sorted(want)} 不一致"
                )
    if MOD_ON_ACTIONS_FILE.is_file():
        on_actions_text = MOD_ON_ACTIONS_FILE.read_text(encoding="utf-8")
        for a in tags:
            if "TXG_opinion_network_%s = yes" % a not in on_actions_text:
                errors.append(f"on_actions 缺少 TXG_opinion_network_{a} 分派")


POLITICAL_DISTANCE_AXES = ("e", "p", "f", "l", "o")
POLITICAL_DISTANCE_WEIGHTS = {"e": 1, "p": 1, "f": 1, "l": 1, "o": 1}


def political_distance(
    coord_a: dict[str, int], coord_b: dict[str, int]
) -> tuple[int, int]:
    domestic = 0
    for axis in POLITICAL_DISTANCE_AXES:
        weight = POLITICAL_DISTANCE_WEIGHTS[axis]
        delta = int(coord_a.get(axis, 0)) - int(coord_b.get(axis, 0))
        domestic += weight * abs(delta)
    foreign = abs(int(coord_a.get("f", 0)) - int(coord_b.get("f", 0)))
    return domestic, foreign


def compute_distance_table(default_coords: dict[str, dict]) -> dict[str, dict]:
    keys = sorted(default_coords)
    table: dict[str, dict] = {}
    for key_a in keys:
        row: dict[str, dict] = {}
        for key_b in keys:
            if key_a == key_b:
                continue
            domestic, foreign = political_distance(
                default_coords[key_a], default_coords[key_b]
            )
            row[key_b] = {"domestic": domestic, "foreign": foreign}
        table[key_a] = row
    return table


def validate_party_localisation(errors: list[str]) -> None:
    """防回归（D-20260817-002）：坐标表每个政党 key 必须在政党 localisation 有显示名
    （缺省时 UI 显示原始 key，游戏体验缺陷）。"""

    if not POLITICAL_SPECTRUM_PARTIES.is_file():
        return
    if not MOD_PARTIES_LOCALISATION_EN.is_file():
        errors.append(f"{MOD_PARTIES_LOCALISATION_EN.relative_to(ROOT)} 不存在（政党本地化）")
        return
    parties = read_json(POLITICAL_SPECTRUM_PARTIES).get("party_coordinates", {})
    text = MOD_PARTIES_LOCALISATION_EN.read_text(encoding="utf-8-sig")
    for key in parties:
        if f"{key}:" not in text:
            errors.append(
                f"政党 {key} 缺少本地化显示名（{MOD_PARTIES_LOCALISATION_EN.relative_to(ROOT)}）"
            )


def validate_political_distance_table(
    errors: list[str], defaults_raw: dict
) -> None:
    if not POLITICAL_DISTANCE_TABLE.is_file():
        return
    table_raw = read_json(POLITICAL_DISTANCE_TABLE)
    default_coords = defaults_raw.get("default_coordinates", {})
    if table_raw.get("schema_version") != 1:
        errors.append("距离-40子意识形态.json schema_version 必须是 1")
    if table_raw.get("decision_id") != defaults_raw.get("decision_id"):
        errors.append("距离表 decision_id 必须与坐标-40子意识形态.json 一致")
    weights = table_raw.get("weights")
    if weights != POLITICAL_DISTANCE_WEIGHTS:
        errors.append(
            "距离表 weights 必须等于 "
            f"{POLITICAL_DISTANCE_WEIGHTS}"
        )
    distances = table_raw.get("distances", {})
    if set(distances) != set(default_coords):
        errors.append("距离表 key 集合与 40 子类型清单不一致")
    for key_a, row in distances.items():
        for key_b, pair in row.items():
            if key_a == key_b:
                errors.append(f"距离表 {key_a} 含自对条目")
                continue
            if key_b not in default_coords:
                errors.append(f"距离表 {key_a}→{key_b} 目标不在 40 子类型清单")
                continue
            expected = political_distance(
                default_coords[key_a], default_coords[key_b]
            )
            actual = (pair.get("domestic"), pair.get("foreign"))
            if actual != expected:
                errors.append(
                    f"距离表 {key_a}→{key_b} 值 {actual} 与坐标重算 {expected} 不一致"
                )


def opinion_band_for(
    domestic: int, foreign: int, f_a: int, f_b: int
) -> tuple[str, bool]:
    """分档（D-20260812-063）：返回 (档名, 是否加 foreign_gap 修正)。

    domestic 为五轴等权曼哈顿距离；foreign 为 F 轴差。
    foreign_gap 修正条件：|Δf| ≥ 80 且两国 F 符号相反（国际主义 vs 民族主义）。
    """
    if domestic <= 200:
        band = "close"
    elif domestic <= 400:
        band = "neutral"
    elif domestic <= 600:
        band = "distant"
    else:
        band = "opposite"
    foreign_gap = foreign >= 80 and (f_a < 0) != (f_b < 0)
    return band, foreign_gap



def validate_task_specs(errors: list[str]) -> None:
    """Validate the task specification layer (D-20260811-020 / D-20260812-021).

    Active-layer specs (not under ``_归档/``) are fully validated: filename,
    requirement_ref, task linkage, resolved inputs, limits and load-test gating.
    Archived specs only get JSON + schema validation.  A done task whose spec
    still sits in the active layer is reported so archive failures surface.
    """
    if not TASK_SPEC_DIR.is_dir():
        return
    task_data = load_tasks()
    tasks = task_index(task_data)
    requirements = {path.stem for path in REQUIREMENT_DIR.glob("R-*.json")} if REQUIREMENT_DIR.is_dir() else set()
    for path in sorted(TASK_SPEC_DIR.rglob("T-*.json")):
        try:
            label = str(path.relative_to(ROOT))
        except ValueError:
            label = path.name
        archived = "_归档" in path.parts
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
        if archived:
            continue
        requirement_ref = data.get("requirement_ref")
        if not isinstance(requirement_ref, str) or requirement_ref not in requirements:
            errors.append(f"{label}: requirement_ref 必须指向存在的需求登记（需求/R-XXX.json）")
        task = tasks.get(path.stem)
        if task is None:
            errors.append(f"{label}: 对应任务不存在于 tasks.json")
            continue
        if task.get("status") == "done":
            errors.append(f"{label}: 任务已完成但任务书仍在活动层，应归档至 _归档/")
            continue
        if task.get("requirement_id") != requirement_ref:
            errors.append(f"{label}: tasks.json requirement_id 与任务书 requirement_ref 不一致")
        status = task.get("status")
        if status not in (None, "todo", "decision_required"):
            inputs = data.get("inputs") or {}
            if not isinstance(inputs.get("snapshot_fingerprint"), str):
                errors.append(f"{label}: 任务已离开 todo，snapshot_fingerprint 必须已解析")
            if not isinstance(inputs.get("base_commit"), str):
                errors.append(f"{label}: 任务已离开 todo，base_commit 必须已解析")
            required_snapshot_schema = inputs.get("snapshot_schema_version")
            if isinstance(required_snapshot_schema, int):
                snapshot = snapshot_metadata()
                current_snapshot_schema = (
                    snapshot.get("schema_version") if isinstance(snapshot, dict) else None
                )
                if current_snapshot_schema != required_snapshot_schema:
                    errors.append(
                        f"{label}: 要求 snapshot schema v{required_snapshot_schema}，"
                        f"当前为 v{current_snapshot_schema}"
                    )
        for entry in data.get("source_matrix", []):
            if entry.get("pending") and not status == "decision_required":
                errors.append(f"{label}: source_matrix 含待定项，任务应处于 decision_required")
        outputs = data.get("outputs") or []
        limits = task_spec_limits(data)
        if "mod/history/states/" in outputs:
            snapshot = snapshot_metadata()
            file_count = (
                snapshot.get("source", {}).get("file_count")
                if isinstance(snapshot, dict)
                else None
            )
            max_files = limits.get("max_files")
            if (
                isinstance(file_count, int)
                and isinstance(max_files, int)
                and max_files < file_count
            ):
                errors.append(
                    f"{label}: limits.max_files={max_files} 小于完整 states 文件数 {file_count}"
                )
        scope = data.get("scope") or {}
        tags = scope.get("tags", []) if isinstance(scope, dict) else []
        if "mod/history/countries/" in outputs and isinstance(tags, list) and tags:
            max_files = limits.get("max_files")
            if isinstance(max_files, int) and max_files < len(tags):
                errors.append(
                    f"{label}: limits.max_files={max_files} "
                    f"小于 scope.tags 的 {len(tags)} 个国家历史文件"
                )
        acceptance = data.get("acceptance") or {}
        if not isinstance(acceptance, dict) or not isinstance(
            acceptance.get("requires_load_test"), bool
        ):
            errors.append(f"{label}: 活动任务 acceptance.requires_load_test 必须显式为布尔值")
        if (
            isinstance(acceptance, dict)
            and acceptance.get("requires_load_test") is True
            and "load_test" not in task.get("required_capabilities", [])
        ):
            errors.append(f"{label}: requires_load_test=true 时任务必须要求 load_test 能力")
        if task.get("outputs") != data.get("outputs"):
            errors.append(f"{label}: tasks.json outputs 必须与活动任务书 outputs 完全一致")
    for path in sorted(TASK_SPEC_DIR.rglob("*.json")):
        if not re.fullmatch(r"T-\d{3}\.json", path.name):
            errors.append(f"{path.relative_to(ROOT)}: 任务书文件名必须是 T-XXX.json")
    for path in sorted(REQUIREMENT_DIR.rglob("R-*.json")) if REQUIREMENT_DIR.is_dir() else []:
        try:
            label = str(path.relative_to(ROOT))
        except ValueError:
            label = path.name
        try:
            data = read_json(path)
        except WorkflowError as exc:
            errors.append(str(exc))
            continue
        errors.extend(validate_named_schema(data, "requirement.schema.json", label))
        if data.get("requirement_id") != path.stem:
            errors.append(f"{label}: requirement_id 必须等于文件名")


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
        if data.get("historical_backfill") is not None and data.get("confirmed_by") != "user":
            errors.append(
                f"{path.relative_to(ROOT)}: historical_backfill 只能由 confirmed_by=user 的决策声明"
            )
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
        relative_path = path.relative_to(ROOT).as_posix()
        expected_name = (
            f"{data.get('task_id')}-g{data.get('lease_generation')}.json"
        )
        if path.name != expected_name:
            errors.append(f"{relative_path}: 文件名与 task_id/lease_generation 不一致")
        if data.get("schema_version") not in {1, 2}:
            errors.append(f"{path.relative_to(ROOT)}: schema_version 必须是 1 或 2")
        expected_branch = (
            f"task/{data.get('task_id')}-g{data.get('lease_generation')}"
        )
        if data.get("branch") != expected_branch:
            errors.append(f"{relative_path}: branch 与交接隔离令牌不一致")
        is_current = task.get("handoff") == relative_path
        if is_current:
            if data.get("lease_generation") != task.get("lease_generation"):
                errors.append(f"{relative_path}: 隔离令牌已过期")
            if data.get("branch") != task.get("branch"):
                errors.append(f"{relative_path}: branch 与任务不一致")
            if data.get("base_commit") != task.get("base_commit"):
                errors.append(f"{relative_path}: base_commit 与任务不一致")
            if data.get("head_commit") != task.get("head_commit"):
                errors.append(f"{relative_path}: head_commit 与任务不一致")
            if data.get("decision_ids") != task.get("decision_ids", []):
                errors.append(f"{relative_path}: decision_ids 与任务不一致")
        for field in ("base_commit", "head_commit"):
            if not isinstance(data.get(field), str) or not SHA_RE.fullmatch(data[field]):
                errors.append(f"{path.relative_to(ROOT)}: {field} 无效")
        if data.get("base_commit") == data.get("head_commit"):
            errors.append(f"{path.relative_to(ROOT)}: base/head 不得相同")
        base = data.get("base_commit")
        head = data.get("head_commit")
        if isinstance(base, str) and SHA_RE.fullmatch(base) and isinstance(head, str) and SHA_RE.fullmatch(head):
            try:
                output_base = (
                    (
                        task_output_base(task, head)
                        if is_current
                        else handoff_output_base(data, head)
                    )
                    if data.get("schema_version") == 2
                    else base
                )
                actual_files = changed_files(output_base, head)
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


def filesystem_permission_errors(agent_name: str, text: str) -> list[str]:
    """Require explicit deny entries for filesystem MCP mutation tools."""

    errors = []
    for tool in FILESYSTEM_MUTATION_TOOLS:
        if re.search(rf"^\s+{re.escape(tool)}:\s+deny\s*$", text, re.MULTILINE) is None:
            errors.append(f"{agent_name} agent 必须显式拒绝 {tool}")
    return errors


def external_directory_permission_errors(agent_name: str, text: str) -> list[str]:
    if re.search(r"^\s+external_directory:\s+deny\s*$", text, re.MULTILINE) is None:
        return [f"{agent_name} agent 必须显式拒绝 external_directory"]
    return []


def validate_static_files(errors: list[str]) -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    if ".opencode/opencode.json" not in gitignore:
        errors.append(".gitignore 必须忽略 .opencode/opencode.json")
    for name in ("scan", "verify"):
        text = (ROOT / ".opencode" / "agent" / f"{name}.md").read_text(encoding="utf-8")
        errors.extend(filesystem_permission_errors(name, text))
        errors.extend(external_directory_permission_errors(name, text))
        if '"git *": allow' in text:
            errors.append(f"{name} agent 禁止使用宽泛 git * 权限")
    execute = (ROOT / ".opencode" / "agent" / "execute.md").read_text(encoding="utf-8")
    errors.extend(filesystem_permission_errors("execute", execute))
    errors.extend(external_directory_permission_errors("execute", execute))
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
    if not MOD_DEFINES_FILE.is_file():
        errors.append("缺少 mod/common/defines/zz_txg_defines.lua")
    else:
        errors.extend(
            building_slot_define_errors(MOD_DEFINES_FILE.read_text(encoding="utf-8"))
        )
    hook_requirements = {
        "run-python": ("py -3", "python3"),
        "pre-commit": ("validate --staged", "unittest discover -s tests -v"),
        "pre-merge-commit": ("MERGE_HEAD", "merge-check --head"),
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


def validate_game_test_reports(errors: list[str]) -> None:
    """校验 协作/审查记录/加载测试-*.json 通过报告 schema 且 Markdown 可重复渲染（规划十一）。"""

    gt = game_test_module
    review_dir = ROOT / "协作" / "审查记录"
    if not review_dir.is_dir():
        return
    schema = read_json(SCHEMA_DIR / "game-test-report.schema.json")
    for path in sorted(review_dir.glob("加载测试-*.json")):
        label = str(path.relative_to(ROOT))
        try:
            report = read_json(path)
        except WorkflowError as exc:
            errors.append(f"{label}: {exc}")
            continue
        errors.extend(
            f"{label}: {item}" for item in validate_schema_instance(report, schema)
        )
        markdown_path = path.with_suffix(".md")
        if not markdown_path.is_file():
            errors.append(f"{label}: 缺少同名 Markdown 报告")
            continue
        markdown_text = markdown_path.read_text(encoding="utf-8")
        errors.extend(
            f"{label}: {item}"
            for item in gt.report_files_valid(report, markdown_text)
        )


MOD_ON_ACTIONS_FILE = ROOT / "mod" / "common" / "on_actions" / "00_txg_on_actions.txt"
TXG_TAGS = (
    "CHI", "ENG", "FRA", "GER", "TUR", "PER", "CAN", "USA",
    "BRA", "ARG", "CHL", "PRU", "COL", "BOL", "ECU", "PAR",
)


def validate_game_test_consistency(errors: list[str]) -> None:
    """防回归（D-20260817-001/002）：on_ruling_party_change 国家判定必须用 tag 触发器；
    on_startup 好感网络调用必须在 <TAG> 作用域内（none 作用域静默失效）；
    意识形态四极壳必须声明 ai_<ideology> 键。"""

    if MOD_ON_ACTIONS_FILE.is_file():
        text = MOD_ON_ACTIONS_FILE.read_text(encoding="utf-8")
        ruling_section = text.split("on_ruling_party_change", 1)[-1]
        startup_section = text.split("on_startup", 1)[-1].split(
            "on_ruling_party_change", 1
        )[0]
        for tag in TXG_TAGS:
            if f"has_country_flag = {tag}" in ruling_section:
                errors.append(
                    f"on_ruling_party_change 使用 has_country_flag = {tag}（应 tag = {tag}，"
                    "D-20260817-001 防回归）"
                )
            if f"tag = {tag}" not in ruling_section:
                errors.append(
                    f"on_ruling_party_change 缺少 tag = {tag} 好感重算分派"
                )
            if f"TXG_opinion_network_{tag} = yes" in startup_section:
                expected = (
                    f"\t\t{tag} = {{\n"
                    f"\t\t\tif = {{\n"
                    f"\t\t\t\tlimit = {{ has_country_flag = TXG_party_state_ready }}\n"
                    f"\t\t\t\tTXG_opinion_network_{tag} = yes\n"
                    f"\t\t\t}}\n"
                    f"\t\t}}"
                )
                if expected not in startup_section:
                    errors.append(
                        f"on_startup 中 TXG_opinion_network_{tag} 调用缺少 {tag} 作用域包裹"
                        "（none 作用域下静默失效，D-20260817-002 防回归）"
                    )
    ideologies_text = MOD_IDEOLOGIES_FILE.read_text(encoding="utf-8")
    for key in ("ai_democratic = yes", "ai_communism = yes",
                "ai_fascist = yes", "ai_neutral = yes"):
        if key not in ideologies_text:
            errors.append(f"00_ideologies.txt 缺少 {key}（D-20260817-001 防回归）")


def validate_validation_reports(errors: list[str]) -> None:
    review_dir = ROOT / "协作" / "审查记录"
    if not review_dir.is_dir():
        return
    schema = read_json(SCHEMA_DIR / "validation-report.schema.json")
    for path in sorted(review_dir.glob("验证-*.json")):
        label = str(path.relative_to(ROOT))
        try:
            report = read_json(path)
        except WorkflowError as exc:
            errors.append(f"{label}: {exc}")
            continue
        errors.extend(
            f"{label}: {item}" for item in validate_schema_instance(report, schema)
        )
        markdown_path = path.with_suffix(".md")
        if not markdown_path.is_file():
            errors.append(f"{label}: 缺少同名 Markdown 报告")
            continue
        if markdown_path.read_text(encoding="utf-8") != render_validation_markdown(report):
            errors.append(f"{label}: Markdown 与结构化报告不可重复渲染")


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
    if path == normalized or (normalized.endswith("/") and path.startswith(normalized)):
        return True
    if any(char in normalized for char in "*?["):
        return fnmatch.fnmatchcase(path, normalized)
    return False


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


def historical_backfill_commit_eligible(commit: str) -> bool:
    """Return whether commit is strictly older than the per-commit gate.

    Git ancestry, rather than author/committer timestamps, makes the boundary
    deterministic across machines and resistant to clock skew.  Unknown or
    unreachable commits fail closed because merge-base returns non-zero.
    """

    if commit == HISTORICAL_BACKFILL_GATE_COMMIT:
        return False
    result = run_git(
        "merge-base",
        "--is-ancestor",
        commit,
        HISTORICAL_BACKFILL_GATE_COMMIT,
        check=False,
    )
    return result.returncode == 0


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
        if data.get("status") != "confirmed" or data.get("confirmed_by") != "user":
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
                and historical_backfill_commit_eligible(commit)
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


def validate_1910_oobs(errors: list[str]) -> None:
    errors.extend(oob_validation.validate_project_oobs(ROOT))


def validate(args: argparse.Namespace) -> int:
    errors: list[str] = []
    validate_tasks(errors)
    validate_task_specs(errors)
    validate_environment(errors)
    validate_snapshot(errors)
    validate_country_tag_snapshot(errors)
    validate_state_overrides(errors)
    validate_political_spectrum(errors)
    validate_game_test_reports(errors)
    validate_game_test_consistency(errors)
    validate_validation_reports(errors)
    validate_decisions(errors)
    validate_handoffs(errors)
    validate_static_files(errors)
    validate_1910_oobs(errors)
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


GAME_TEST_PROFILES_PATH = ROOT / "config" / "game-test-profiles.json"
GAME_TEST_LOCK_PATH = ROOT / ".opencode" / "game-test.lock"
GAME_TEST_BASELINE_PREFIX = "txg-baseline-"


def game_test_profiles() -> dict[str, Any]:
    if not GAME_TEST_PROFILES_PATH.is_file():
        raise WorkflowError("config/game-test-profiles.json 不存在")
    try:
        data = read_json(GAME_TEST_PROFILES_PATH)
    except WorkflowError as exc:
        raise WorkflowError(f"game-test profiles 解析失败：{exc}") from exc
    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise WorkflowError("game-test profiles 为空")
    return profiles


def game_test_preflight_errors(args: argparse.Namespace) -> list[str]:
    """前置校验错误列表；非空时不得启动游戏，返回 2（INCONCLUSIVE/配置错误）。"""

    gt = game_test_module
    errors: list[str] = []
    try:
        report_path = checked_review_path(args.report, must_exist=False)
    except WorkflowError as exc:
        errors.append(str(exc))
        report_path = None
    if report_path is not None and report_path.suffix != ".md":
        errors.append("game-test --report 必须指定 Markdown 路径（同名 JSON 自动生成）")
    if report_path is not None and not report_path.name.startswith("加载测试-"):
        errors.append("game-test 报告文件名必须以 加载测试- 开头")
    if report_path is not None and (
        report_path.exists() or report_path.with_suffix(".json").exists()
    ):
        errors.append("报告目标已存在，拒绝覆盖或重放旧会话")
    local_config, local_errors = load_local_config()
    environment = derive_environment(local_config, local_errors, probe_external=True)
    capabilities = environment.get("capabilities", {})
    if not capabilities.get("load_test"):
        errors.append("本机不具备 load_test 能力，禁止实机运行")
    try:
        data = load_tasks()
        task = find_task(data, args.task)
    except WorkflowError as exc:
        errors.append(str(exc))
        return errors
    if task.get("status") != "pending_test":
        errors.append(f"任务不在待测试状态：{task.get('status')}")
    if task.get("lease_generation") != args.generation:
        errors.append(
            f"generation 不匹配：任务 {task.get('lease_generation')} vs 参数 {args.generation}"
        )
    try:
        profiles = game_test_profiles()
    except WorkflowError as exc:
        errors.append(str(exc))
        return errors
    profile_name = args.profile or "map-load"
    profile = profiles.get(profile_name)
    if profile is None:
        errors.append(f"profile 不存在：{profile_name}")
        return errors
    if profile.get("registrable", False) and not profile.get("required_markers"):
        errors.append(
            f"profile {profile_name} 的 required_markers 为空（Gate 0 基线未完成）；"
            "拒绝执行，不得用固定等待时间伪造 PASS"
        )
    local_config = read_json(LOCAL_CONFIG) if LOCAL_CONFIG.is_file() else {}
    game_test_config = local_config.get("game_test")
    if not isinstance(game_test_config, dict):
        errors.append(".opencode/local.json 缺少 game_test 配置")
        return errors
    executable_path = game_test_config.get("executable_path")
    descriptor_path = game_test_config.get("mod_descriptor_path")
    if not isinstance(executable_path, str) or not executable_path:
        errors.append("game_test.executable_path 未配置")
    if not isinstance(descriptor_path, str) or not descriptor_path:
        errors.append("game_test.mod_descriptor_path 未配置")
    if isinstance(descriptor_path, str) and not gt.ASCII_ONLY.fullmatch(descriptor_path):
        errors.append("mod_descriptor_path 必须 ASCII-only")
    if isinstance(descriptor_path, str) and not Path(descriptor_path).is_file():
        errors.append("mod_descriptor_path 不存在")
    game_path_value = local_config.get("game_path")
    if isinstance(executable_path, str) and executable_path:
        executable = Path(executable_path).expanduser().resolve()
        if not executable.is_file():
            errors.append("game_test.executable_path 不存在")
        if isinstance(game_path_value, str) and game_path_value:
            game_root = Path(game_path_value).expanduser().resolve()
            trusted = {(game_root / name).resolve() for name in TRUSTED_GAME_EXECUTABLES}
            if executable not in trusted:
                errors.append("game_test.executable_path 不是 game_path 下受信 HOI4 可执行文件")
        else:
            errors.append("game_path 未配置，无法验证受信可执行文件")
    status = run_git("status", "--porcelain", check=False)
    if status.stdout.strip():
        errors.append("工作树不干净，拒绝执行（测试必须绑定干净提交内容树）")
    return errors


def game_test_run_preflight_only(args: argparse.Namespace) -> int:
    """T-042 Phase 1/2 交付形态：完整前置校验 + 配置错误分类。

    真实启动/readiness 轮询/受控退出（Phase 3）在机器 A Gate 0 完成后由同一
    命令路径执行；本阶段在无完整基线时一律 INCONCLUSIVE（返回 2）。
    """

    errors = game_test_preflight_errors(args)
    if errors:
        for error in errors:
            print(f"INCONCLUSIVE: {error}", file=sys.stderr)
        return 2
    print(
        "INCONCLUSIVE: 前置校验通过但实机执行路径（launch/readiness/terminate）"
        "需 Gate 0 基线完成后方可用；请勿用固定等待时间伪造 PASS",
        file=sys.stderr,
    )
    return 2


def run_game_test_session(args: argparse.Namespace) -> int:
    """T-048 Phase 3/4：真实启动/readiness 轮询/受控退出/日志增量/判定/报告。

    状态机（docs/加载测试自动化规划.md 六）：PREFLIGHT->BASELINE->LAUNCHING->
    WAITING_READY->SOAKING->STOPPING->VERIFY_STOPPED->COLLECTING->WRITING_REPORT。
    """
    import subprocess
    import time

    gt = game_test_module
    report = checked_review_path(args.report, must_exist=False)
    profile_name = args.profile or "map-load"
    profiles = game_test_profiles()
    profile = profiles[profile_name]
    local_config = read_json(LOCAL_CONFIG) if LOCAL_CONFIG.is_file() else {}
    game_test_config = local_config.get("game_test") or {}
    user_docs = Path(local_config["user_docs_path"]).expanduser()
    executable = Path(game_test_config["executable_path"]).expanduser().resolve()
    descriptor = Path(game_test_config["mod_descriptor_path"]).expanduser().resolve()
    registry_name = game_test_config.get("mod_registry_name", "pdx_39436001.mod")

    log_paths = [user_docs / rel for rel in profile.get("logs", [])]
    crash_dir = user_docs / profile.get("crashes_dir", "crashes")
    rules = gt.compile_rules(profile.get("rules", []))
    required_marker_ids = list(profile.get("required_markers", []))
    startup_timeout = float(args.startup_timeout or profile.get("startup_timeout_seconds", 300))
    run_seconds = float(args.run_seconds or profile.get("run_seconds_after_ready", 30))
    shutdown_grace = float(profile.get("shutdown_grace_seconds", 15))
    min_alive = float(profile.get("min_alive_seconds", 0))

    started_at = gt.utc_now()
    session_id = gt.new_session_id()
    runs: dict[str, float] = {}
    crashes_before = {p.name for p in crash_dir.glob("hoi4_*")} if crash_dir.is_dir() else set()

    # 1. 受控例外预置 mod 激活（门禁 A：dlc_load 无 BOM + 注册文件）
    mod_dir = descriptor.parent
    gt.write_mod_registry(user_docs, registry_name, mod_dir)
    gt.write_dlc_load(user_docs, registry_name)
    docs_before = gt.snapshot_user_docs(user_docs)

    # 2. 日志基线（增量隔离）
    baselines: dict[str, gt.LogBaseline] = {}
    for path in log_paths:
        exists = path.is_file()
        size = path.stat().st_size if exists else 0
        head = tail = None
        if exists:
            data = path.read_bytes()
            head, tail = gt.head_tail_hashes(data)
        baselines[str(path)] = gt.LogBaseline(
            path=str(path), exists=exists, size=size, identity=None,
            created_at=None, head_hash=head, tail_hash=tail,
            captured_at=gt.utc_now(),
        )

    # 3. 启动（基线 argv：hoi4.exe -debug）
    argv = [str(executable), "-debug"]
    t0 = time.monotonic()
    runs["launch"] = 0.0
    proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 4. 轮询 readiness（增量扫描）
    offsets = {str(p): p.stat().st_size if p.is_file() else 0 for p in log_paths}
    hits: list[gt.RuleHit] = []
    markers: dict[str, gt.MarkerEvidence] = {}
    ready_reached = False
    fatal_hits: list[gt.RuleHit] = []
    crash_evidence: list[str] = []
    state = "LAUNCHING"
    ready_at = 0.0
    deadline = time.monotonic() + startup_timeout
    while time.monotonic() < deadline:
        proc.poll()
        for path in log_paths:
            if not path.is_file():
                continue
            size = path.stat().st_size
            base = offsets.get(str(path), 0)
            if size < base:
                # 游戏启动重建 system.log 等：清空重写视为从头开始（基线事实）
                base = 0
                offsets[str(path)] = 0
            if size > base:
                with open(path, "rb") as handle:
                    handle.seek(base)
                    chunk = handle.read(size - base)
                offsets[str(path)] = size
                text = chunk.decode("utf-8", errors="replace")
                new_hits, new_markers = gt.scan_text(
                    text, rules, str(path.relative_to(user_docs))
                )
                hits.extend(new_hits)
                for key, evidence in new_markers.items():
                    if evidence.first_seen_relative_ms is None:
                        evidence.first_seen_relative_ms = int(
                            (time.monotonic() - t0) * 1000
                        )
                    if key in markers:
                        markers[key].count += evidence.count
                    else:
                        markers[key] = evidence
                for hit in new_hits:
                    if hit.kind == "fatal":
                        fatal_hits.append(hit)
        if crash_dir.is_dir():
            new_crashes = [
                p.name for p in crash_dir.glob("hoi4_*") if p.name not in crashes_before
            ]
            crash_evidence.extend(new_crashes)
            if new_crashes:
                fatal_hits.append(
                    gt.RuleHit(
                        rule_id="crash-dump", kind="fatal",
                        log_path="crashes/", line_number=None,
                        matched_text="new crash dirs: " + ", ".join(sorted(new_crashes)),
                    )
                )
        if proc.poll() is not None:
            break
        if state == "LAUNCHING":
            if (time.monotonic() - t0) >= min_alive:
                state = "WAITING_READY"
        if state == "WAITING_READY":
            if (not required_marker_ids) or all(
                m in markers for m in required_marker_ids
            ):
                ready_reached = True
                state = "SOAKING"
                ready_at = time.monotonic()
        elif state == "SOAKING":
            if (time.monotonic() - ready_at) >= run_seconds:
                break
        time.sleep(2.0)
    runs["session"] = time.monotonic() - t0

    # 5. 受控退出（仅本 PID 树，taskkill /T）
    terminated_by_runner = False
    exit_code: int | None = None
    if proc.poll() is None:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True, text=True,
        )
        terminated_by_runner = True
        try:
            proc.wait(timeout=shutdown_grace)
        except subprocess.TimeoutExpired:
            pass
    exit_code = proc.returncode

    # 6. 日志增量采集 + 判定
    diffs: list[gt.LogDiff] = []
    for path in log_paths:
        baseline = baselines[str(path)]
        new_size = path.stat().st_size if path.is_file() else 0
        appended = max(0, new_size - baseline.size)
        continuity_ok = True
        rotated = False
        no_new = appended == 0
        expected_rotation = False
        if appended > 0:
            data = path.read_bytes()
            if baseline.head_hash and baseline.head_hash != gt.head_tail_hashes(data)[0]:
                rotated = True
                expected_rotation = True
            if baseline.tail_hash != gt.head_tail_hashes(data)[1] and not expected_rotation:
                continuity_ok = False
            text = data[baseline.size:].decode("utf-8", errors="replace")
            extra_hits, extra_markers = gt.scan_text(
                text, rules, str(path.relative_to(user_docs))
            )
            hits.extend(extra_hits)
            for key, evidence in extra_markers.items():
                if key in markers:
                    markers[key].count += evidence.count
                else:
                    markers[key] = evidence
            for hit in extra_hits:
                if hit.kind == "fatal":
                    fatal_hits.append(hit)
        else:
            text = ""
            if new_size < baseline.size:
                rotated = True
                expected_rotation = True
                no_new = False
        diffs.append(
            gt.LogDiff(
                path=str(path.relative_to(user_docs)),
                baseline_size=baseline.size,
                new_size=new_size,
                appended_bytes=appended,
                rotated=rotated,
                expected_rotation=expected_rotation,
                continuity_ok=continuity_ok,
                no_new_evidence=no_new,
                text=text,
            )
        )
    any_new_evidence = any(not d.no_new_evidence for d in diffs) or bool(markers) or bool(hits)
    all_consistent = all(
        d.continuity_ok and (not d.rotated or d.expected_rotation) for d in diffs
    )
    survived_after_ready = ready_reached and (
        (time.monotonic() - ready_at) >= run_seconds
    )
    result = gt.evaluate(
        markers=markers,
        fatal_hits=fatal_hits,
        invalidating_hits=[],
        crash_evidence=crash_evidence,
        any_new_evidence=any_new_evidence,
        all_logs_consistent=all_consistent,
        ready_reached=ready_reached,
        survived_after_ready=survived_after_ready,
        required_marker_ids=required_marker_ids,
    )
    docs_after = gt.snapshot_user_docs(user_docs)
    docs_diff = gt.diff_user_docs(docs_before, docs_after)

    # 7. 报告（脱敏 + 原子写）
    ended_at = gt.utc_now()
    git_head = run_git("rev-parse", "HEAD", check=False).stdout.strip()
    env_snapshot_path = ENV_DIR / f"{local_config.get('machine_id', 'A')}.json"
    env_checked_at = gt.utc_now()
    env_snapshot: dict[str, Any] = {}
    if env_snapshot_path.is_file():
        try:
            env_snapshot = read_json(env_snapshot_path)
            if isinstance(env_snapshot.get("checked_at"), str):
                env_checked_at = env_snapshot["checked_at"]
        except WorkflowError:
            env_snapshot = {}
    report_data = gt.build_report(
        session_id=session_id,
        task_id=args.task,
        generation=args.generation,
        profile=profile_name,
        game_version=(
            env_snapshot.get("snapshot", {}).get("game_version")
            if isinstance(env_snapshot, dict)
            else None
        ),
        executable_sha256=gt.sha256_hex(executable.read_bytes()),
        baseline_contract_id=GAME_TEST_BASELINE_PREFIX + gt.sha256_hex(
            (
                str(executable)
                + "|"
                + "|".join(argv)
                + "|"
                + gt.sha256_hex(descriptor.read_bytes())
                + "|"
                + mod_tree_sha256()
                + "|"
                + canonical_json_sha256(profile)
            ).encode("utf-8")
        ),
        mod_descriptor_sha256=gt.sha256_hex(descriptor.read_bytes()),
        mod_tree_sha256=mod_tree_sha256(),
        git_head=git_head,
        git_dirty=bool(run_git("status", "--porcelain", check=False).stdout.strip()),
        runner_commit=git_head,
        runner_machine_id=local_config.get("machine_id", "A"),
        runner_environment_checked_at=env_checked_at,
        profile_hash=canonical_json_sha256(profile),
        rules_hash=canonical_json_sha256(profile.get("rules", [])),
        started_at=started_at,
        ended_at=ended_at,
        durations=runs,
        executable_basename=executable.name,
        sanitized_argv=[gt.redact_text(a) for a in argv],
        markers=list(markers.values()),
        exit_code=exit_code,
        terminated_by_runner=terminated_by_runner,
        log_diffs=diffs,
        result=result,
        registrable=profile.get("registrable", False),
    )
    report_data["user_docs_write_diff"] = docs_diff
    redacted = gt.redact_dict(report_data)
    json_text = json.dumps(redacted, ensure_ascii=False, indent=2)
    markdown_text = gt.render_markdown(redacted)
    json_path = report.with_suffix(".json")
    json_path.write_text(json_text, encoding="utf-8", newline="\n")
    report.write_text(markdown_text, encoding="utf-8", newline="\n")
    print(f"会话 {session_id} 判定：{result.verdict}")
    for reason in result.reasons:
        print(f"  - {reason}")
    return 0 if result.verdict == "PASS" else (1 if result.verdict == "FAIL" else 2)


def game_test_command(args: argparse.Namespace) -> int:
    with runtime_lock(GAME_TEST_LOCK_PATH, f"game-test:{args.task}:{args.profile or 'map-load'}"):
        errors = game_test_preflight_errors(args)
        if errors:
            for error in errors:
                print(f"INCONCLUSIVE: {error}", file=sys.stderr)
            return 2
        return run_game_test_session(args)


def lock_clear_command(args: argparse.Namespace) -> int:
    path = COORDINATOR_LOCK_PATH if args.name == "coordinator" else GAME_TEST_LOCK_PATH
    clear_runtime_lock(path, force=args.force)
    print(f"已清除运行时锁：{path.name}")
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

    country_snapshot_parser = sub.add_parser(
        "country-snapshot-export",
        help="从本体只读导出独立的 country tag/definition/history 元数据快照",
    )
    country_snapshot_parser.set_defaults(func=country_snapshot_export)

    state_build_parser = sub.add_parser(
        "state-build", help="在受控 full/partial 机上生成完整 mod state 文件"
    )
    state_build_parser.add_argument(
        "--override",
        action="append",
        required=True,
        help="协作/state-overrides/ 下的仓库相对 JSON 路径；可重复",
    )
    state_build_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只生成并输出差异统计，不写入 mod/history/states",
    )
    state_build_parser.set_defaults(func=state_build)

    render_parser = sub.add_parser("render-tasks", help="从 tasks.json 生成 Markdown 台账")
    render_parser.add_argument("--check", action="store_true")
    render_parser.set_defaults(func=render_tasks_command)

    validation_report_parser = sub.add_parser(
        "render-validation-report", help="从结构化静态验证 JSON 生成同名 Markdown"
    )
    validation_report_parser.add_argument("--report", required=True)
    validation_report_parser.set_defaults(func=render_validation_report_command)

    validate_parser = sub.add_parser("validate", help="运行工作流和协作层验证")
    validate_parser.add_argument("--ci", action="store_true", help="CI 标记（保留用于输出兼容）")
    validate_parser.add_argument("--base")
    validate_parser.add_argument("--head")
    validate_parser.add_argument("--staged", action="store_true", help="校验 Git index 中即将形成的提交")
    validate_parser.set_defaults(func=validate)

    merge_parser = sub.add_parser("merge-check", help="检查候选提交是否包含未验收任务")
    merge_parser.add_argument("--head", required=True)
    merge_parser.set_defaults(func=merge_check)

    sync_parser = sub.add_parser("sync-check", help="检查 main 与 origin/main 双向同步")
    sync_parser.set_defaults(func=sync_check_command)

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
    merge_task = task_sub.add_parser("merge")
    merge_task.add_argument("--id", required=True)
    merge_task.add_argument("--generation", required=True, type=int)
    merge_task.set_defaults(func=task_merge)

    game_test_parser = sub.add_parser(
        "game-test", help="游戏自动化测试执行器（T-042；仅 load_test 机器可实机运行）"
    )
    game_test_parser.add_argument("--task", required=True)
    game_test_parser.add_argument("--generation", required=True, type=int)
    game_test_parser.add_argument(
        "--profile", choices=("process-smoke", "menu-debug", "map-load", "scenario-load")
    )
    game_test_parser.add_argument("--report", required=True, help="报告 Markdown 路径（JSON 同目录同名）")
    game_test_parser.add_argument("--startup-timeout", type=int)
    game_test_parser.add_argument("--run-seconds", type=int)
    game_test_parser.set_defaults(func=game_test_command)

    lock_parser = sub.add_parser("lock", help="主代理显式管理运行时锁")
    lock_sub = lock_parser.add_subparsers(dest="lock_command", required=True)
    lock_clear = lock_sub.add_parser("clear")
    lock_clear.add_argument("--name", required=True, choices=("coordinator", "game-test"))
    lock_clear.add_argument("--force", action="store_true")
    lock_clear.set_defaults(func=lock_clear_command)
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
        if args.command == "task":
            with runtime_lock(
                COORDINATOR_LOCK_PATH, f"task:{getattr(args, 'task_command', 'unknown')}"
            ):
                return int(args.func(args))
        return int(args.func(args))
    except WorkflowError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
