#!/usr/bin/env python3
"""Static checks for directly referenced 1910 HOI4 OOB files.

The structural contract follows the checked-in OOB references:
- division templates precede deployments in the same OOB file;
- division/task-force locations and naval bases are province ids;
- naval deployments use fleet -> task_force -> ship -> equipment.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TOKEN_RE = re.compile(r'"(?:\\.|[^"\\])*"|#[^\n]*|[{}=]|[^\s{}=#"]+')
DATE_BLOCK_RE = re.compile(r"^\s*\d{4}\.\d{1,2}\.\d{1,2}\s*=\s*\{", re.MULTILINE)
LAND_REF_RE = re.compile(r'\bset_oob\s*=\s*"([^"]+)"')
NAVAL_REF_RE = re.compile(r'\bset_naval_oob\s*=\s*"([^"]+)"')


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class Assignment:
    key: str
    value: str | tuple["Assignment", ...]

    @property
    def block(self) -> tuple["Assignment", ...] | None:
        return self.value if isinstance(self.value, tuple) else None


def _tokens(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(text) if not token.startswith("#")]


def parse_script(text: str) -> tuple[Assignment, ...]:
    tokens = _tokens(text)
    index = 0

    def parse_assignments(stop_at_brace: bool) -> tuple[Assignment, ...]:
        nonlocal index
        result: list[Assignment] = []
        while index < len(tokens):
            if tokens[index] == "}":
                if not stop_at_brace:
                    raise ParseError("unexpected closing brace")
                index += 1
                return tuple(result)
            key = tokens[index]
            if key in {"{", "="}:
                raise ParseError(f"unexpected token {key!r}")
            index += 1
            if index >= len(tokens) or tokens[index] != "=":
                raise ParseError(f"missing '=' after {key!r}")
            index += 1
            if index >= len(tokens):
                raise ParseError(f"missing value after {key!r}")
            if tokens[index] == "{":
                index += 1
                value: str | tuple[Assignment, ...] = parse_assignments(True)
            else:
                value = _unquote(tokens[index])
                index += 1
            result.append(Assignment(key, value))
        if stop_at_brace:
            raise ParseError("unclosed block")
        return tuple(result)

    return parse_assignments(False)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def _children(assignments: Iterable[Assignment], key: str) -> list[Assignment]:
    return [item for item in assignments if item.key == key]


def _scalar(assignments: Iterable[Assignment], key: str) -> str | None:
    for item in assignments:
        if item.key == key and isinstance(item.value, str):
            return item.value
    return None


def _walk(assignments: Iterable[Assignment]) -> Iterable[Assignment]:
    for item in assignments:
        yield item
        if item.block is not None:
            yield from _walk(item.block)


def _int(value: str | None) -> int | None:
    if value is None or not re.fullmatch(r"[0-9]+", value):
        return None
    return int(value)


def _parse_or_error(text: str, label: str, errors: list[str]) -> tuple[Assignment, ...]:
    try:
        return parse_script(text)
    except ParseError as exc:
        errors.append(f"{label}: Paradox 脚本结构无效：{exc}")
        return ()


def validate_land_oob(text: str, province_ids: set[int], label: str) -> list[str]:
    errors: list[str] = []
    document = _parse_or_error(text, label, errors)
    templates = _children(document, "division_template")
    template_names = {
        name
        for item in templates
        if item.block is not None
        and (name := _scalar(item.block, "name")) is not None
    }
    if not templates:
        errors.append(f"{label}: 缺少同文件 division_template")

    units_blocks = _children(document, "units")
    if len(units_blocks) != 1 or units_blocks[0].block is None:
        errors.append(f"{label}: 必须且只能有一个顶层 units 块")
        units = ()
    else:
        units = units_blocks[0].block
        if _children(units, "units"):
            errors.append(f"{label}: 禁止嵌套 units")

    divisions = [item for item in _walk(units) if item.key == "division" and item.block]
    if not divisions:
        errors.append(f"{label}: units 中缺少 division 部署")
    for index, division in enumerate(divisions, 1):
        assert division.block is not None
        template = _scalar(division.block, "division_template")
        if template not in template_names:
            errors.append(f"{label}: division[{index}] 引用未定义模板 {template!r}")
        location = _int(_scalar(division.block, "location"))
        if location not in province_ids:
            errors.append(f"{label}: division[{index}] location 非快照 province：{location}")

    for template in templates:
        if template.block is None:
            continue
        name = _scalar(template.block, "name") or "<unnamed>"
        for section_name in ("regiments", "support"):
            sections = _children(template.block, section_name)
            for section in sections:
                if section.block is None:
                    continue
                seen: set[tuple[int, int]] = set()
                for unit in section.block:
                    if unit.block is None:
                        errors.append(
                            f"{label}: 模板 {name} 的 {section_name}/{unit.key} 必须是坐标块"
                        )
                        continue
                    x = _int(_scalar(unit.block, "x"))
                    y = _int(_scalar(unit.block, "y"))
                    if x is None or y is None or not (0 <= x <= 4 and 0 <= y <= 4):
                        errors.append(
                            f"{label}: 模板 {name} 的 {section_name}/{unit.key} 坐标不在5x5：({x},{y})"
                        )
                        continue
                    if (x, y) in seen:
                        errors.append(
                            f"{label}: 模板 {name} 的 {section_name} 坐标重复：({x},{y})"
                        )
                    seen.add((x, y))
    return errors


def validate_naval_oob(text: str, province_ids: set[int], label: str) -> list[str]:
    errors: list[str] = []
    if re.search(r"\bnavy\s*=\s*\{", text):
        errors.append(f"{label}: 禁止 navy 伪层级，必须使用 fleet/task_force")
    document = _parse_or_error(text, label, errors)
    units_blocks = _children(document, "units")
    if len(units_blocks) != 1 or units_blocks[0].block is None:
        errors.append(f"{label}: 必须且只能有一个顶层 units 块")
        units = ()
    else:
        units = units_blocks[0].block
    fleets = _children(units, "fleet")
    if not fleets:
        errors.append(f"{label}: units 中缺少 fleet")
    for fleet_index, fleet in enumerate(fleets, 1):
        if fleet.block is None:
            continue
        naval_base = _int(_scalar(fleet.block, "naval_base"))
        if naval_base not in province_ids:
            errors.append(
                f"{label}: fleet[{fleet_index}] naval_base 非快照 province：{naval_base}"
            )
        task_forces = _children(fleet.block, "task_force")
        if not task_forces:
            errors.append(f"{label}: fleet[{fleet_index}] 缺 task_force")
        for task_index, task_force in enumerate(task_forces, 1):
            if task_force.block is None:
                continue
            location = _int(_scalar(task_force.block, "location"))
            if location not in province_ids:
                errors.append(
                    f"{label}: fleet[{fleet_index}]/task_force[{task_index}] "
                    f"location 非快照 province：{location}"
                )
            ships = _children(task_force.block, "ship")
            if not ships:
                errors.append(
                    f"{label}: fleet[{fleet_index}]/task_force[{task_index}] 缺 ship"
                )
            for ship_index, ship in enumerate(ships, 1):
                if ship.block is None:
                    continue
                equipment = _children(ship.block, "equipment")
                prefix = (
                    f"{label}: fleet[{fleet_index}]/task_force[{task_index}]/ship[{ship_index}]"
                )
                if not equipment or equipment[0].block is None:
                    errors.append(f"{prefix} 缺 equipment")
                    continue
                entries = [item for item in equipment[0].block if item.block is not None]
                if not entries:
                    errors.append(f"{prefix} equipment 缺装备类型")
                    continue
                for entry in entries:
                    assert entry.block is not None
                    amount = _int(_scalar(entry.block, "amount"))
                    owner = _scalar(entry.block, "owner")
                    if amount is None or amount < 1:
                        errors.append(f"{prefix} equipment/{entry.key} amount 无效")
                    if owner is None or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,}", owner):
                        errors.append(f"{prefix} equipment/{entry.key} owner 无效")
    return errors


def _province_ids(snapshot_path: Path) -> set[int]:
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    return {
        province
        for state in data.get("states", [])
        if isinstance(state, dict)
        for province in state.get("provinces", [])
        if type(province) is int
    }


def _top_history(text: str) -> str:
    match = DATE_BLOCK_RE.search(text)
    return text[: match.start()] if match else text


def validate_project_oobs(root: Path) -> list[str]:
    errors: list[str] = []
    snapshot_path = root / "协作/扫描快照/states.json"
    if not snapshot_path.is_file():
        return ["1910 OOB 校验缺少 states 快照"]
    try:
        province_ids = _province_ids(snapshot_path)
    except (OSError, ValueError, TypeError) as exc:
        return [f"1910 OOB 无法读取 states 快照：{exc}"]

    common_units = root / "mod/common/units"
    if common_units.is_dir():
        for path in sorted(common_units.glob("*.txt")):
            if re.search(r"\bdivision_template\s*=\s*\{", path.read_text(encoding="utf-8-sig")):
                errors.append(
                    f"{path.relative_to(root)}: division_template 不得放在 common/units，须放入对应 OOB"
                )

    land_refs: set[str] = set()
    naval_refs: set[str] = set()
    country_dir = root / "mod/history/countries"
    if country_dir.is_dir():
        for path in sorted(country_dir.glob("*.txt")):
            top = _top_history(path.read_text(encoding="utf-8-sig"))
            land_refs.update(stem for stem in LAND_REF_RE.findall(top) if "_1910" in stem)
            naval_refs.update(stem for stem in NAVAL_REF_RE.findall(top) if "_1910" in stem)

    units_dir = root / "mod/history/units"
    referenced = land_refs | naval_refs
    if units_dir.is_dir():
        for path in sorted(units_dir.glob("*_1910*.txt")):
            if path.stem not in referenced:
                errors.append(f"{path.relative_to(root)}: 1910 OOB 未被国家历史引用")

    for stem in sorted(land_refs):
        path = units_dir / f"{stem}.txt"
        label = str(path.relative_to(root))
        if not path.is_file():
            errors.append(f"{label}: 国家历史引用的陆军 OOB 不存在")
            continue
        errors.extend(validate_land_oob(path.read_text(encoding="utf-8-sig"), province_ids, label))
    for stem in sorted(naval_refs):
        path = units_dir / f"{stem}.txt"
        label = str(path.relative_to(root))
        if not path.is_file():
            errors.append(f"{label}: 国家历史引用的海军 OOB 不存在")
            continue
        errors.extend(validate_naval_oob(path.read_text(encoding="utf-8-sig"), province_ids, label))
    return errors
