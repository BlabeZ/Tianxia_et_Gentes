#!/usr/bin/env python3
"""Deterministically build the CHI 1910 land and naval OOB candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "协作" / "扫描快照" / "states.json"
OUTPUT_DIR = ROOT / "mod" / "history" / "units"

GUARD_STATES = (608, 1035, 596, 592, 715, 743)
FIELD_STATES = (
    600,
    602,
    603,
    605,
    606,
    607,
    608,
    615,
    620,
    622,
    744,
    748,
    749,
    750,
    524,
    591,
    592,
    593,
    595,
    596,
    715,
    743,
    1035,
)
CAVALRY_STATES = (715, 615, 622, 744, 607, 608)
LAND_STATE_IDS = tuple(sorted(set(GUARD_STATES + FIELD_STATES + CAVALRY_STATES)))

# Candidate coastal provinces. T-052 must confirm a built naval base at each one.
NAVAL_STATE_PROVINCES = {
    743: 10000,  # Qingdao / 东海舰队
    592: 1047,   # Guangzhou / 南洋舰队
    591: 994,    # Hainan / 印度洋舰队
    524: 1091,   # Taiwan / 新瀛舰队前进基地
    595: 1006,   # Fujian / 北美远征舰队前进基地
}

FLEETS = (
    ("东海舰队", 743),
    ("南洋舰队", 592),
    ("印度洋舰队", 591),
    ("新瀛舰队", 524),
    ("北美远征舰队", 595),
)

SHIP_CLASSES = {
    "dinghai": ("定海", "battleship", "ship_hull_heavy_1", "battleship_1"),
    "zhenyang": ("镇洋", "battleship", "ship_hull_heavy_1", "battleship_1"),
    "feihong": ("飞鸿", "heavy_cruiser", "ship_hull_cruiser_1", "heavy_cruiser_1"),
    "haisun": ("海隼", "light_cruiser", "ship_hull_cruiser_1", "light_cruiser_1"),
    "leizhen": ("雷震", "destroyer", "ship_hull_light_1", "destroyer_1"),
    "qianlong": ("潜龙", "submarine", "ship_hull_submarine_1", "submarine_1"),
}

# East / South / Indian / Xinying / North-American-expedition; each class sum is fixed.
NAVAL_ALLOCATION = {
    "dinghai": (1, 1, 0, 0, 0),
    "zhenyang": (3, 2, 2, 2, 1),
    "feihong": (2, 3, 3, 3, 1),
    "haisun": (4, 4, 3, 4, 1),
    "leizhen": (12, 12, 12, 10, 4),
    "qianlong": (2, 3, 3, 3, 1),
}


def _state_provinces(snapshot: dict[str, Any]) -> dict[int, tuple[int, ...]]:
    result: dict[int, tuple[int, ...]] = {}
    for state in snapshot.get("states", []):
        if not isinstance(state, dict) or type(state.get("state_id")) is not int:
            continue
        provinces = state.get("provinces", [])
        if isinstance(provinces, list) and all(type(item) is int for item in provinces):
            result[state["state_id"]] = tuple(provinces)
    return result


def _locations(snapshot: dict[str, Any]) -> tuple[dict[int, int], dict[int, int]]:
    states = _state_provinces(snapshot)
    required = set(LAND_STATE_IDS) | set(NAVAL_STATE_PROVINCES)
    missing = sorted(required - states.keys())
    if missing:
        raise ValueError(f"states 快照缺少 OOB 州：{missing}")
    land = {state_id: states[state_id][0] for state_id in LAND_STATE_IDS}
    naval: dict[int, int] = {}
    for state_id, province_id in NAVAL_STATE_PROVINCES.items():
        if province_id not in states[state_id]:
            raise ValueError(
                f"海军候选 province {province_id} 不属于 state {state_id}"
            )
        naval[state_id] = province_id
    return land, naval


def _template(name: str, line_units: list[tuple[str, int, int]]) -> list[str]:
    lines = ["division_template = {", f'\tname = "{name}"', "\tregiments = {"]
    lines.extend(
        f"\t\t{token} = {{ x = {x} y = {y} }}" for token, x, y in line_units
    )
    lines.extend(
        [
            "\t}",
            "\tsupport = {",
            "\t\tengineer = { x = 0 y = 0 }",
            "\t\trecon = { x = 1 y = 0 }",
            "\t}",
            "}",
            "",
        ]
    )
    return lines


def _infantry_layout() -> list[tuple[str, int, int]]:
    infantry = [("infantry", 0, y) for y in range(5)]
    infantry.extend(("infantry", 1, y) for y in range(4))
    artillery = [("artillery", 2, y) for y in range(3)]
    return infantry + artillery


def _cavalry_layout() -> list[tuple[str, int, int]]:
    cavalry = [("cavalry", 0, y) for y in range(5)]
    cavalry.append(("cavalry", 1, 0))
    return cavalry


def _division(
    name: str, template: str, location: int, experience: str
) -> list[str]:
    return [
        "\tdivision = {",
        f'\t\tname = "{name}"',
        f"\t\tlocation = {location}",
        f'\t\tdivision_template = "{template}"',
        f"\t\tstart_experience_factor = {experience}",
        "\t}",
    ]


def build_land_oob(land_locations: dict[int, int]) -> str:
    lines = [
        "# 大顺陆军 1910 开局部署（R-006 T-051；D-20260817-008/D-20260819-001）",
        "# 45师：禁卫6 + 野战33 + 良家子骑兵6；location 均为受控快照 province ID。",
        "",
    ]
    lines.extend(_template("CHI_1910_Guard_Infantry", _infantry_layout()))
    lines.extend(_template("CHI_1910_Field_Infantry", _infantry_layout()))
    lines.extend(_template("CHI_1910_Cavalry", _cavalry_layout()))
    lines.append("units = {")
    for index, state_id in enumerate(GUARD_STATES, 1):
        lines.extend(
            _division(
                f"禁卫第{index}师",
                "CHI_1910_Guard_Infantry",
                land_locations[state_id],
                "0.7",
            )
        )
    for index in range(33):
        state_id = FIELD_STATES[index % len(FIELD_STATES)]
        lines.extend(
            _division(
                f"野战第{index + 1}师",
                "CHI_1910_Field_Infantry",
                land_locations[state_id],
                "0.5",
            )
        )
    for index, state_id in enumerate(CAVALRY_STATES, 1):
        lines.extend(
            _division(
                f"良家子骑兵第{index}师",
                "CHI_1910_Cavalry",
                land_locations[state_id],
                "0.5",
            )
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def _ship(
    name: str, definition: str, equipment_type: str
) -> list[str]:
    return [
        "\t\tship = {",
        f'\t\t\tname = "{name}"',
        f"\t\t\tdefinition = {definition}",
        "\t\t\tequipment = {",
        f"\t\t\t\t{equipment_type} = {{",
        "\t\t\t\t\tamount = 1",
        "\t\t\t\t\towner = CHI",
        "\t\t\t\t}",
        "\t\t\t}",
        "\t\t\tstart_experience_factor = 0.3",
        "\t\t}",
    ]


def build_naval_oob(naval_locations: dict[int, int], mtg: bool) -> str:
    suffix = "MTG hull" if mtg else "legacy equipment"
    lines = [
        f"# 大顺海军 1910 开局部署（R-006 T-051；{suffix}）",
        "# 第8号表：定海2+镇洋10+飞鸿12+海隼16+雷震50+潜龙12=102。",
        "units = {",
    ]
    class_counters = {key: 0 for key in SHIP_CLASSES}
    for fleet_index, (fleet_name, state_id) in enumerate(FLEETS):
        location = naval_locations[state_id]
        lines.extend(
            [
                "\tfleet = {",
                f'\t\tname = "{fleet_name}"',
                f"\t\tnaval_base = {location}",
                "\t\ttask_force = {",
                f'\t\t\tname = "{fleet_name}主力队"',
                f"\t\t\tlocation = {location}",
            ]
        )
        for class_key, allocations in NAVAL_ALLOCATION.items():
            display, definition, mtg_type, legacy_type = SHIP_CLASSES[class_key]
            equipment_type = mtg_type if mtg else legacy_type
            for _ in range(allocations[fleet_index]):
                class_counters[class_key] += 1
                lines.extend(
                    _ship(
                        f"{display}{class_counters[class_key]}",
                        definition,
                        equipment_type,
                    )
                )
        lines.extend(["\t\t}", "\t}"])
    lines.append("}")
    return "\n".join(lines) + "\n"


def build_chi_oobs(snapshot: dict[str, Any]) -> dict[str, str]:
    land_locations, naval_locations = _locations(snapshot)
    return {
        "CHI_1910.txt": build_land_oob(land_locations),
        "CHI_1910_naval_mtg.txt": build_naval_oob(naval_locations, mtg=True),
        "CHI_1910_naval_legacy.txt": build_naval_oob(naval_locations, mtg=False),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write generated OOB files")
    parser.add_argument("--check", action="store_true", help="check committed files are current")
    args = parser.parse_args(argv)
    if args.write == args.check:
        parser.error("choose exactly one of --write or --check")
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    outputs = build_chi_oobs(snapshot)
    if args.write:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for name, text in outputs.items():
            (OUTPUT_DIR / name).write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {OUTPUT_DIR / name}")
        return 0
    errors = []
    for name, expected in outputs.items():
        path = OUTPUT_DIR / name
        if not path.is_file():
            errors.append(f"missing {path}")
        elif path.read_text(encoding="utf-8") != expected:
            errors.append(f"stale {path}")
    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        return 1
    print("CHI 1910 OOB files are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
