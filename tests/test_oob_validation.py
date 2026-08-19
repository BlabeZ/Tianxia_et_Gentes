import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import oob_build, oob_validation, workflow


VALID_LAND = '''
division_template = {
    name = "CHI_1910_Field_Infantry"
    regiments = {
        infantry = { x = 0 y = 0 }
        infantry = { x = 0 y = 1 }
        artillery = { x = 1 y = 0 }
    }
    support = {
        engineer = { x = 0 y = 0 }
    }
}
units = {
    division = {
        name = "野战第一师"
        location = 100
        division_template = "CHI_1910_Field_Infantry"
        start_experience_factor = 0.5
    }
}
'''


VALID_NAVAL = '''
units = {
    fleet = {
        name = "东海舰队"
        naval_base = 100
        task_force = {
            name = "东海主力队"
            location = 100
            ship = {
                name = "定海"
                definition = battleship
                equipment = {
                    ship_hull_heavy_1 = {
                        amount = 1
                        owner = CHI
                    }
                }
            }
        }
    }
}
'''


class OobValidationTests(unittest.TestCase):
    def test_chi_builder_emits_valid_45_division_and_102_ship_oobs(self):
        state_ids = sorted(
            set(oob_build.LAND_STATE_IDS) | set(oob_build.NAVAL_STATE_PROVINCES)
        )
        snapshot = {
            "states": [
                {
                    "state_id": state_id,
                    "provinces": [
                        oob_build.NAVAL_STATE_PROVINCES.get(state_id, state_id + 10000)
                    ],
                }
                for state_id in state_ids
            ]
        }
        outputs = oob_build.build_chi_oobs(snapshot)
        province_ids = {
            province
            for state in snapshot["states"]
            for province in state["provinces"]
        }
        self.assertEqual(
            oob_validation.validate_land_oob(
                outputs["CHI_1910.txt"], province_ids, "CHI_1910.txt"
            ),
            [],
        )
        for name in ("CHI_1910_naval_mtg.txt", "CHI_1910_naval_legacy.txt"):
            self.assertEqual(
                oob_validation.validate_naval_oob(outputs[name], province_ids, name),
                [],
            )
        self.assertEqual(outputs["CHI_1910.txt"].count("division = {"), 45)
        self.assertEqual(outputs["CHI_1910_naval_mtg.txt"].count("ship = {"), 102)
        self.assertEqual(outputs["CHI_1910_naval_legacy.txt"].count("ship = {"), 102)

    def test_valid_land_oob_accepts_local_template_and_province_location(self):
        self.assertEqual(
            oob_validation.validate_land_oob(VALID_LAND, {100}, "CHI_1910.txt"),
            [],
        )

    def test_land_oob_rejects_nested_units_missing_template_and_state_location(self):
        text = '''
units = {
    units = {
        division = {
            name = "Bad"
            location = 608
            division_template = "Missing"
        }
    }
}
'''
        errors = oob_validation.validate_land_oob(text, {100}, "bad-land.txt")
        self.assertTrue(any("嵌套 units" in item for item in errors), errors)
        self.assertTrue(any("未定义模板" in item for item in errors), errors)
        self.assertTrue(any("非快照 province" in item for item in errors), errors)

    def test_land_oob_rejects_template_grid_outside_five_by_five(self):
        text = VALID_LAND.replace("x = 0 y = 1", "x = 0 y = 5")
        errors = oob_validation.validate_land_oob(text, {100}, "bad-grid.txt")
        self.assertTrue(any("5x5" in item for item in errors), errors)

    def test_valid_naval_oob_accepts_fleet_task_force_and_equipment(self):
        self.assertEqual(
            oob_validation.validate_naval_oob(VALID_NAVAL, {100}, "CHI_naval.txt"),
            [],
        )

    def test_naval_oob_rejects_navy_pseudo_layer_and_missing_equipment(self):
        text = '''
units = {
    navy = {
        ship = {
            name = "Bad"
            definition = battleship
        }
    }
}
'''
        errors = oob_validation.validate_naval_oob(text, {100}, "bad-naval.txt")
        self.assertTrue(any("navy 伪层级" in item for item in errors), errors)
        self.assertTrue(any("fleet" in item for item in errors), errors)

    def test_naval_oob_rejects_state_location_and_ship_without_equipment(self):
        text = VALID_NAVAL.replace("naval_base = 100", "naval_base = 608")
        text = text.replace("location = 100", "location = 608")
        start = text.index("                equipment = {")
        end = text.index("            }\n        }\n    }", start)
        text = text[:start] + text[end:]
        errors = oob_validation.validate_naval_oob(text, {100}, "bad-ship.txt")
        self.assertTrue(any("naval_base 非快照 province" in item for item in errors), errors)
        self.assertTrue(any("task_force[1] location 非快照 province" in item for item in errors), errors)
        self.assertTrue(any("缺 equipment" in item for item in errors), errors)

    def test_project_validator_rejects_common_template_and_unreferenced_1910_oob(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mod/common/units").mkdir(parents=True)
            (root / "mod/history/countries").mkdir(parents=True)
            (root / "mod/history/units").mkdir(parents=True)
            (root / "协作/扫描快照").mkdir(parents=True)
            (root / "mod/common/units/bad.txt").write_text(
                'division_template = { name = "Bad" }\n', encoding="utf-8"
            )
            (root / "mod/history/units/ENG_1910.txt").write_text(
                VALID_LAND, encoding="utf-8"
            )
            (root / "协作/扫描快照/states.json").write_text(
                json.dumps({"states": [{"state_id": 1, "provinces": [100]}]}),
                encoding="utf-8",
            )
            errors = oob_validation.validate_project_oobs(root)
            self.assertTrue(any("common/units" in item for item in errors), errors)
            self.assertTrue(any("未被国家历史引用" in item for item in errors), errors)

    def test_project_validator_accepts_referenced_land_and_dlc_naval_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mod/history/countries").mkdir(parents=True)
            (root / "mod/history/units").mkdir(parents=True)
            (root / "协作/扫描快照").mkdir(parents=True)
            (root / "mod/history/countries/CHI - China.txt").write_text(
                '''
set_oob = "CHI_1910"
if = {
    limit = { has_dlc = "Man the Guns" }
    set_naval_oob = "CHI_1910_naval_mtg"
    else = { set_naval_oob = "CHI_1910_naval_legacy" }
}
1939.1.1 = { set_oob = "CHI_1939" }
''',
                encoding="utf-8",
            )
            (root / "mod/history/units/CHI_1910.txt").write_text(
                VALID_LAND, encoding="utf-8"
            )
            (root / "mod/history/units/CHI_1910_naval_mtg.txt").write_text(
                VALID_NAVAL, encoding="utf-8"
            )
            (root / "mod/history/units/CHI_1910_naval_legacy.txt").write_text(
                VALID_NAVAL.replace("ship_hull_heavy_1", "battleship_1"),
                encoding="utf-8",
            )
            (root / "协作/扫描快照/states.json").write_text(
                json.dumps({"states": [{"state_id": 1, "provinces": [100]}]}),
                encoding="utf-8",
            )
            self.assertEqual(oob_validation.validate_project_oobs(root), [])

    def test_workflow_gate_includes_project_oob_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mod/history/countries").mkdir(parents=True)
            (root / "mod/history/units").mkdir(parents=True)
            (root / "协作/扫描快照").mkdir(parents=True)
            (root / "mod/history/countries/CHI - China.txt").write_text(
                'set_oob = "CHI_1910"\n', encoding="utf-8"
            )
            (root / "mod/history/units/CHI_1910.txt").write_text(
                'units = { units = { } }\n', encoding="utf-8"
            )
            (root / "协作/扫描快照/states.json").write_text(
                json.dumps({"states": [{"state_id": 1, "provinces": [100]}]}),
                encoding="utf-8",
            )
            errors = []
            with mock.patch.object(workflow, "ROOT", root):
                workflow.validate_1910_oobs(errors)
            self.assertTrue(any("CHI_1910.txt" in item for item in errors), errors)


if __name__ == "__main__":
    unittest.main()
