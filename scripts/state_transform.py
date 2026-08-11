#!/usr/bin/env python3
"""Safe, source-preserving transformations for HOI4 state files.

The module has no knowledge of local game paths.  Callers provide already
gated source text and declarative overrides; unchanged source text is retained
byte-for-byte after UTF-8 decoding.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
STATE_PATH_RE = re.compile(r"^history/states/[^/\\]+\.txt$")
TAG_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PATCH_FIELDS = {
    "owner",
    "controller",
    "add_core_of",
    "add_claim_by",
    "manpower",
    "state_category",
    "resources",
    "buildings",
}


class StateTransformError(RuntimeError):
    """Raised when a source file or override is ambiguous or unsafe."""


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class Assignment:
    key: str
    key_token: int
    value_token: int
    value_end_token: int
    start: int
    end: int
    block_open: int | None = None
    block_close: int | None = None


@dataclass(frozen=True)
class Edit:
    start: int
    end: int
    replacement: str


@dataclass(frozen=True)
class BuiltState:
    relative_path: str
    text: str


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char == "#":
            newline = text.find("\n", index)
            index = len(text) if newline < 0 else newline + 1
            continue
        if char in "{}=":
            tokens.append(Token(char, char, index, index + 1))
            index += 1
            continue
        if char == '"':
            start = index
            index += 1
            escaped = False
            while index < len(text):
                current = text[index]
                if current == '"' and not escaped:
                    index += 1
                    break
                escaped = current == "\\" and not escaped
                if current != "\\":
                    escaped = False
                index += 1
            else:
                raise StateTransformError("state 文件存在未闭合字符串")
            tokens.append(Token("atom", text[start:index], start, index))
            continue
        start = index
        while index < len(text) and not text[index].isspace() and text[index] not in '#{}="':
            index += 1
        if start == index:
            raise StateTransformError(f"无法识别 state 字符：{text[index]!r}")
        tokens.append(Token("atom", text[start:index], start, index))
    return tokens


def matching_braces(tokens: list[Token]) -> dict[int, int]:
    stack: list[int] = []
    pairs: dict[int, int] = {}
    for index, token in enumerate(tokens):
        if token.kind == "{":
            stack.append(index)
        elif token.kind == "}":
            if not stack:
                raise StateTransformError("state 文件存在多余的右花括号")
            opening = stack.pop()
            pairs[opening] = index
    if stack:
        raise StateTransformError("state 文件存在未闭合花括号")
    return pairs


def assignments_in_range(
    tokens: list[Token], pairs: dict[int, int], start: int, end: int
) -> list[Assignment]:
    result: list[Assignment] = []
    index = start
    while index < end:
        if (
            tokens[index].kind == "atom"
            and index + 2 < end
            and tokens[index + 1].kind == "="
        ):
            value_index = index + 2
            value = tokens[value_index]
            if value.kind == "{":
                close = pairs.get(value_index)
                if close is None or close >= end:
                    raise StateTransformError(f"字段 {tokens[index].text} 的块范围无效")
                result.append(
                    Assignment(
                        key=tokens[index].text.strip('"'),
                        key_token=index,
                        value_token=value_index,
                        value_end_token=close + 1,
                        start=tokens[index].start,
                        end=tokens[close].end,
                        block_open=value_index,
                        block_close=close,
                    )
                )
                index = close + 1
                continue
            result.append(
                Assignment(
                    key=tokens[index].text.strip('"'),
                    key_token=index,
                    value_token=value_index,
                    value_end_token=value_index + 1,
                    start=tokens[index].start,
                    end=value.end,
                )
            )
            index = value_index + 1
            continue
        if tokens[index].kind == "{":
            close = pairs.get(index)
            if close is None or close >= end:
                raise StateTransformError("匿名块范围无效")
            index = close + 1
            continue
        index += 1
    return result


def select_assignments(assignments: Iterable[Assignment], key: str) -> list[Assignment]:
    return [item for item in assignments if item.key == key]


def require_unique(assignments: Iterable[Assignment], key: str, context: str) -> Assignment | None:
    matches = select_assignments(assignments, key)
    if len(matches) > 1:
        raise StateTransformError(f"{context} 中字段 {key} 重复，拒绝猜测应修改哪一项")
    return matches[0] if matches else None


def require_block(node: Assignment | None, key: str, context: str) -> Assignment:
    if node is None or node.block_open is None or node.block_close is None:
        raise StateTransformError(f"{context} 缺少唯一块字段 {key}")
    return node


def scalar_text(value: Any, field: str) -> str:
    if isinstance(value, bool):
        raise StateTransformError(f"{field} 不接受布尔值")
    if isinstance(value, int):
        if value < 0:
            raise StateTransformError(f"{field} 不得为负数")
        return str(value)
    if isinstance(value, str):
        return value
    raise StateTransformError(f"{field} 必须是整数或标识符")


def line_indent(text: str, offset: int) -> str:
    start = text.rfind("\n", 0, offset) + 1
    prefix = text[start:offset]
    if prefix.strip():
        raise StateTransformError("待修改字段不在独立行，拒绝进行不明确的文本变换")
    return prefix


def block_insertion(
    text: str,
    tokens: list[Token],
    block: Assignment,
    lines: list[str],
) -> Edit | None:
    if not lines:
        return None
    assert block.block_close is not None
    closing = tokens[block.block_close]
    line_start = text.rfind("\n", 0, closing.start) + 1
    closing_prefix = text[line_start:closing.start]
    if closing_prefix.strip():
        raise StateTransformError("目标块不是多行格式，拒绝猜测插入位置")
    child_indent = closing_prefix + "\t"
    payload = "".join(f"{child_indent}{line}\n" for line in lines)
    return Edit(line_start, line_start, payload)


def replace_or_insert_scalar(
    text: str,
    tokens: list[Token],
    assignments: list[Assignment],
    block: Assignment,
    key: str,
    value: Any,
    context: str,
    edits: list[Edit],
    insertions: dict[int, list[str]],
) -> None:
    node = require_unique(assignments, key, context)
    if value is None:
        if node is not None:
            edits.append(Edit(node.start, node.end, ""))
        return
    replacement = scalar_text(value, key)
    if node is None:
        assert block.block_close is not None
        insertions.setdefault(block.block_close, []).append(f"{key} = {replacement}")
        return
    if node.block_open is not None:
        raise StateTransformError(f"{context}.{key} 预期为标量但实际为块")
    value_token = tokens[node.value_token]
    edits.append(Edit(value_token.start, value_token.end, replacement))


def replace_repeated_scalars(
    text: str,
    assignments: list[Assignment],
    block: Assignment,
    key: str,
    values: list[str],
    context: str,
    edits: list[Edit],
    insertions: dict[int, list[str]],
) -> None:
    nodes = select_assignments(assignments, key)
    for value in values:
        if not isinstance(value, str) or TAG_RE.fullmatch(value) is None:
            raise StateTransformError(f"{context}.{key} 含无效 tag：{value!r}")
    if len(values) != len(set(values)):
        raise StateTransformError(f"{context}.{key} 不得包含重复 tag")
    for node in nodes:
        if node.block_open is not None:
            raise StateTransformError(f"{context}.{key} 预期为标量但实际为块")
    if nodes:
        indent = line_indent(text, nodes[0].start)
        replacement = ""
        if values:
            replacement = f"{key} = {values[0]}" + "".join(
                f"\n{indent}{key} = {value}" for value in values[1:]
            )
        edits.append(Edit(nodes[0].start, nodes[0].end, replacement))
        for node in nodes[1:]:
            edits.append(Edit(node.start, node.end, ""))
    elif values:
        assert block.block_close is not None
        insertions.setdefault(block.block_close, []).extend(
            f"{key} = {value}" for value in values
        )


def merge_scalar_block(
    text: str,
    tokens: list[Token],
    pairs: dict[int, int],
    parent_assignments: list[Assignment],
    parent_block: Assignment,
    key: str,
    values: dict[str, Any],
    context: str,
    edits: list[Edit],
    insertions: dict[int, list[str]],
) -> None:
    node = require_unique(parent_assignments, key, context)
    if node is None:
        non_null = {name: value for name, value in values.items() if value is not None}
        if not non_null:
            return
        for name, value in non_null.items():
            if IDENTIFIER_RE.fullmatch(name) is None:
                raise StateTransformError(f"{context}.{key} 含无效键：{name!r}")
            scalar_text(value, f"{key}.{name}")
        assert parent_block.block_close is not None
        lines = [f"{key} = {{"]
        lines.extend(f"\t{name} = {scalar_text(value, name)}" for name, value in non_null.items())
        lines.append("}")
        insertions.setdefault(parent_block.block_close, []).extend(lines)
        return
    node = require_block(node, key, context)
    assert node.block_open is not None and node.block_close is not None
    children = assignments_in_range(tokens, pairs, node.block_open + 1, node.block_close)
    for name, value in values.items():
        if IDENTIFIER_RE.fullmatch(name) is None:
            raise StateTransformError(f"{context}.{key} 含无效键：{name!r}")
        replace_or_insert_scalar(
            text,
            tokens,
            children,
            node,
            name,
            value,
            f"{context}.{key}",
            edits,
            insertions,
        )


def apply_edits(text: str, edits: list[Edit]) -> str:
    ordered = sorted(edits, key=lambda item: (item.start, item.end))
    previous_end = -1
    for edit in ordered:
        if edit.start < previous_end:
            raise StateTransformError("内部错误：state 文本改写范围重叠")
        previous_end = max(previous_end, edit.end)
    result = text
    for edit in reversed(ordered):
        result = result[: edit.start] + edit.replacement + result[edit.end :]
    return result


def validate_override_document(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["顶层必须是对象"]
    fingerprint = data.get("source_fingerprint")
    if not isinstance(fingerprint, str) or SHA256_RE.fullmatch(fingerprint) is None:
        errors.append("source_fingerprint 必须是64位小写 SHA-256")
    overrides = data.get("overrides")
    if not isinstance(overrides, list) or not overrides:
        return errors + ["overrides 必须是非空数组"]
    seen_ids: set[int] = set()
    seen_paths: set[str] = set()
    for index, item in enumerate(overrides):
        prefix = f"overrides[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} 必须是对象")
            continue
        state_id = item.get("state_id")
        path = item.get("source_relative_path")
        digest = item.get("source_sha256")
        if not isinstance(state_id, int) or isinstance(state_id, bool) or state_id <= 0:
            errors.append(f"{prefix}.state_id 必须是正整数")
        elif state_id in seen_ids:
            errors.append(f"{prefix}.state_id 重复：{state_id}")
        else:
            seen_ids.add(state_id)
        if not isinstance(path, str) or STATE_PATH_RE.fullmatch(path) is None:
            errors.append(f"{prefix}.source_relative_path 无效")
        elif path in seen_paths:
            errors.append(f"{prefix}.source_relative_path 重复：{path}")
        else:
            seen_paths.add(path)
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            errors.append(f"{prefix}.source_sha256 必须是64位小写 SHA-256")
        if not (set(item) & PATCH_FIELDS):
            errors.append(f"{prefix} 至少声明一个改写字段")
        for field in ("owner", "controller"):
            value = item.get(field)
            if field in item and value is not None and (
                not isinstance(value, str) or TAG_RE.fullmatch(value) is None
            ):
                errors.append(f"{prefix}.{field} 必须是有效 tag 或 null")
        for field in ("add_core_of", "add_claim_by"):
            if field in item:
                values = item[field]
                if not isinstance(values, list) or any(
                    not isinstance(value, str) or TAG_RE.fullmatch(value) is None
                    for value in values
                ):
                    errors.append(f"{prefix}.{field} 必须是 tag 数组")
                elif len(values) != len(set(values)):
                    errors.append(f"{prefix}.{field} 不得重复")
        if "manpower" in item and (
            not isinstance(item["manpower"], int)
            or isinstance(item["manpower"], bool)
            or item["manpower"] < 0
        ):
            errors.append(f"{prefix}.manpower 必须是非负整数")
        if "state_category" in item and (
            not isinstance(item["state_category"], str)
            or IDENTIFIER_RE.fullmatch(item["state_category"]) is None
        ):
            errors.append(f"{prefix}.state_category 必须是小写标识符")
        for field in ("resources", "buildings"):
            if field not in item:
                continue
            values = item[field]
            if not isinstance(values, dict):
                errors.append(f"{prefix}.{field} 必须是对象")
                continue
            for name, value in values.items():
                if IDENTIFIER_RE.fullmatch(name) is None:
                    errors.append(f"{prefix}.{field} 含无效键 {name!r}")
                if value is not None and (
                    not isinstance(value, int) or isinstance(value, bool) or value < 0
                ):
                    errors.append(f"{prefix}.{field}.{name} 必须是非负整数或 null")
    return errors


def transform_state(text: str, override: dict[str, Any]) -> str:
    document_errors = validate_override_document(
        {
            "source_fingerprint": "0" * 64,
            "overrides": [override],
        }
    )
    if document_errors:
        raise StateTransformError("；".join(document_errors))
    tokens = tokenize(text)
    pairs = matching_braces(tokens)
    top = assignments_in_range(tokens, pairs, 0, len(tokens))
    state = require_block(require_unique(top, "state", "文件顶层"), "state", "文件顶层")
    assert state.block_open is not None and state.block_close is not None
    state_fields = assignments_in_range(tokens, pairs, state.block_open + 1, state.block_close)
    state_id_node = require_unique(state_fields, "id", "state")
    if state_id_node is None or state_id_node.block_open is not None:
        raise StateTransformError("state 缺少唯一标量 id")
    try:
        source_state_id = int(tokens[state_id_node.value_token].text)
    except ValueError as exc:
        raise StateTransformError("state.id 不是整数") from exc
    if source_state_id != override["state_id"]:
        raise StateTransformError(
            f"state ID 不匹配：文件为 {source_state_id}，改写声明为 {override['state_id']}"
        )
    history = require_block(
        require_unique(state_fields, "history", "state"), "history", "state"
    )
    assert history.block_open is not None and history.block_close is not None
    history_fields = assignments_in_range(
        tokens, pairs, history.block_open + 1, history.block_close
    )
    edits: list[Edit] = []
    insertions: dict[int, list[str]] = {}

    for key in ("manpower", "state_category"):
        if key in override:
            replace_or_insert_scalar(
                text,
                tokens,
                state_fields,
                state,
                key,
                override[key],
                "state",
                edits,
                insertions,
            )
    for key in ("owner", "controller"):
        if key in override:
            replace_or_insert_scalar(
                text,
                tokens,
                history_fields,
                history,
                key,
                override[key],
                "state.history",
                edits,
                insertions,
            )
    for key in ("add_core_of", "add_claim_by"):
        if key in override:
            replace_repeated_scalars(
                text,
                history_fields,
                history,
                key,
                override[key],
                "state.history",
                edits,
                insertions,
            )
    if "resources" in override:
        merge_scalar_block(
            text,
            tokens,
            pairs,
            state_fields,
            state,
            "resources",
            override["resources"],
            "state",
            edits,
            insertions,
        )
    if "buildings" in override:
        merge_scalar_block(
            text,
            tokens,
            pairs,
            history_fields,
            history,
            "buildings",
            override["buildings"],
            "state.history",
            edits,
            insertions,
        )

    block_lookup = {state.block_close: state, history.block_close: history}
    for node in state_fields + history_fields:
        if node.block_close is not None:
            block_lookup[node.block_close] = node
    for close_index, lines in insertions.items():
        insertion = block_insertion(text, tokens, block_lookup[close_index], lines)
        if insertion is not None:
            edits.append(insertion)
    transformed = apply_edits(text, edits)
    # A second parse catches unbalanced output before anything reaches mod/.
    matching_braces(tokenize(transformed))
    return transformed


def merge_override_documents(
    documents: Iterable[dict[str, Any]], snapshot_fingerprint: str
) -> dict[int, dict[str, Any]]:
    merged: dict[int, dict[str, Any]] = {}
    paths: set[str] = set()
    for document in documents:
        errors = validate_override_document(document)
        if errors:
            raise StateTransformError("；".join(errors))
        if document["source_fingerprint"] != snapshot_fingerprint:
            raise StateTransformError("改写清单 source_fingerprint 与受控快照不一致")
        for override in document["overrides"]:
            state_id = override["state_id"]
            path = override["source_relative_path"]
            if state_id in merged:
                raise StateTransformError(f"多个改写清单同时修改 state {state_id}")
            if path in paths:
                raise StateTransformError(f"多个改写清单重复使用来源路径 {path}")
            merged[state_id] = override
            paths.add(path)
    return merged


def build_state_outputs(
    game_path: Path,
    snapshot: dict[str, Any],
    documents: Iterable[dict[str, Any]],
) -> list[BuiltState]:
    fingerprint = snapshot.get("source", {}).get("fingerprint")
    if not isinstance(fingerprint, str) or SHA256_RE.fullmatch(fingerprint) is None:
        raise StateTransformError("受控快照缺少有效 source.fingerprint")
    overrides = merge_override_documents(documents, fingerprint)
    snapshot_states = snapshot.get("states")
    if not isinstance(snapshot_states, list) or not snapshot_states:
        raise StateTransformError("受控快照 states 为空")
    snapshot_by_id = {item.get("state_id"): item for item in snapshot_states if isinstance(item, dict)}
    unknown = set(overrides) - set(snapshot_by_id)
    if unknown:
        raise StateTransformError(f"改写清单包含快照中不存在的 state：{sorted(unknown)}")
    outputs: list[BuiltState] = []
    state_root = (game_path / "history" / "states").resolve()
    for item in snapshot_states:
        state_id = item["state_id"]
        relative_path = item["relative_path"]
        if STATE_PATH_RE.fullmatch(relative_path) is None:
            raise StateTransformError(f"快照来源路径无效：{relative_path!r}")
        source = (game_path / PurePosixPath(relative_path)).resolve()
        try:
            source.relative_to(state_root)
        except ValueError as exc:
            raise StateTransformError(f"来源路径越界：{relative_path}") from exc
        if not source.is_file():
            raise StateTransformError(f"本体 state 文件不存在：{relative_path}")
        digest = sha256_path(source)
        if digest != item.get("sha256"):
            raise StateTransformError(f"本体 state 指纹变化：{relative_path}")
        override = overrides.get(state_id)
        if override is not None:
            if override["source_relative_path"] != relative_path:
                raise StateTransformError(f"state {state_id} 的来源路径与快照不一致")
            if override["source_sha256"] != digest:
                raise StateTransformError(f"state {state_id} 的来源 SHA 与快照不一致")
        text = source.read_text(encoding="utf-8-sig", errors="strict")
        output = transform_state(text, override) if override is not None else text
        outputs.append(BuiltState(relative_path=relative_path, text=output))
    return outputs


def write_state_outputs(outputs: Iterable[BuiltState], output_root: Path) -> int:
    output_root.mkdir(parents=True, exist_ok=True)
    built = list(outputs)
    expected_names = {PurePosixPath(item.relative_path).name for item in built}
    if len(expected_names) != len(built):
        raise StateTransformError("生成结果包含重复文件名")
    unexpected = sorted(path.name for path in output_root.glob("*.txt") if path.name not in expected_names)
    if unexpected:
        raise StateTransformError(f"mod states 目录含快照之外的 txt 文件：{unexpected}")
    with tempfile.TemporaryDirectory(prefix="txg-states-", dir=output_root.parent) as directory:
        staging = Path(directory)
        for item in built:
            name = PurePosixPath(item.relative_path).name
            target = staging / name
            target.write_text(item.text, encoding="utf-8", newline="")
        for item in built:
            name = PurePosixPath(item.relative_path).name
            os.replace(staging / name, output_root / name)
    return len(built)
