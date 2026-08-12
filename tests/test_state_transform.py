import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import state_transform, workflow


SOURCE = """# source comment must survive
state = {
	id = 1
	name = STATE_1
	manpower = 100
	state_category = rural
	resources = {
		steel = 2
	}
	history = {
		owner = GER
		add_core_of = GER
		add_core_of = FRA
		buildings = {
			infrastructure = 3
			10 = { naval_base = 1 }
		}
	}
	provinces = { 10 11 }
}
"""


def override(**changes):
    data = {
        "state_id": 1,
        "source_relative_path": "history/states/1-Test.txt",
        "source_sha256": "a" * 64,
    }
    data.update(changes)
    return data


def document(item, fingerprint="b" * 64):
    return {
        "schema_version": 1,
        "decision_id": "D-20260811-004",
        "source_fingerprint": fingerprint,
        "overrides": [item],
    }


class StateTransformTests(unittest.TestCase):
    def test_transform_preserves_unmentioned_content_and_changes_supported_fields(self):
        result = state_transform.transform_state(
            SOURCE,
            override(
                owner="CHI",
                controller="CHI",
                add_core_of=["CHI"],
                add_claim_by=["JAP"],
                manpower=123456,
                state_category="large_city",
                resources={"steel": 5, "oil": 2},
                buildings={"infrastructure": 4, "arms_factory": 3},
            ),
        )
        self.assertIn("# source comment must survive", result)
        self.assertIn("manpower = 123456", result)
        self.assertIn("state_category = large_city", result)
        self.assertIn("owner = CHI", result)
        self.assertIn("controller = CHI", result)
        self.assertEqual(result.count("add_core_of = CHI"), 1)
        self.assertNotIn("add_core_of = GER", result)
        self.assertNotIn("add_core_of = FRA", result)
        self.assertIn("add_claim_by = JAP", result)
        self.assertIn("steel = 5", result)
        self.assertIn("oil = 2", result)
        self.assertIn("infrastructure = 4", result)
        self.assertIn("arms_factory = 3", result)
        self.assertIn("10 = { naval_base = 1 }", result)
        self.assertIn("provinces = { 10 11 }", result)

    def test_transform_can_remove_declared_scalar_and_repeated_values(self):
        source = SOURCE.replace("\t\towner = GER\n", "\t\towner = GER\n\t\tcontroller = GER\n")
        result = state_transform.transform_state(
            source,
            override(controller=None, add_core_of=[]),
        )
        self.assertNotIn("controller =", result)
        self.assertNotIn("add_core_of =", result)
        self.assertIn("owner = GER", result)

    def test_transform_rejects_state_id_mismatch(self):
        with self.assertRaisesRegex(state_transform.StateTransformError, "state ID 不匹配"):
            state_transform.transform_state(SOURCE, {**override(owner="CHI"), "state_id": 2})

    def test_transform_rejects_ambiguous_unique_field(self):
        source = SOURCE.replace("\t\towner = GER\n", "\t\towner = GER\n\t\towner = FRA\n")
        with self.assertRaisesRegex(state_transform.StateTransformError, "owner 重复"):
            state_transform.transform_state(source, override(owner="CHI"))

    def test_transform_rejects_inline_block_when_insertion_is_required(self):
        source = "state = { id = 1 history = { owner = GER } }"
        with self.assertRaisesRegex(state_transform.StateTransformError, "不是多行格式"):
            state_transform.transform_state(source, override(add_core_of=["CHI"]))

    def test_transform_can_add_missing_resources_and_buildings_blocks(self):
        source = """state = {
	id = 1
	history = {
		owner = GER
	}
	provinces = { 1 }
}
"""
        result = state_transform.transform_state(
            source,
            override(resources={"steel": 3}, buildings={"infrastructure": 2}),
        )
        self.assertIn("resources = {", result)
        self.assertIn("steel = 3", result)
        self.assertIn("buildings = {", result)
        self.assertIn("infrastructure = 2", result)

    def test_override_validation_rejects_duplicate_state_and_empty_patch(self):
        item = {
            "state_id": 1,
            "source_relative_path": "history/states/1-Test.txt",
            "source_sha256": "a" * 64,
        }
        data = document(item)
        data["overrides"].append(dict(item))
        errors = state_transform.validate_override_document(data)
        self.assertTrue(any("至少声明一个改写字段" in error for error in errors))
        self.assertTrue(any("state_id 重复" in error for error in errors))

    def test_schema_rejects_unknown_override_fields(self):
        schema = json.loads(
            (workflow.SCHEMA_DIR / "state-overrides.schema.json").read_text(encoding="utf-8")
        )
        data = document(override(owner="CHI", invented_field=1))
        errors = workflow.validate_schema_instance(data, schema)
        self.assertTrue(any("不允许额外字段 invented_field" in error for error in errors))

    def test_build_verifies_each_source_and_emits_unchanged_states_too(self):
        with tempfile.TemporaryDirectory() as directory:
            game = Path(directory) / "game"
            states = game / "history" / "states"
            states.mkdir(parents=True)
            first = states / "1-Test.txt"
            second = states / "2-Untouched.txt"
            first.write_text(SOURCE, encoding="utf-8")
            untouched = SOURCE.replace("id = 1", "id = 2").replace("STATE_1", "STATE_2")
            second.write_text(untouched, encoding="utf-8")
            first_sha = state_transform.sha256_path(first)
            second_sha = state_transform.sha256_path(second)
            fingerprint = "c" * 64
            snapshot = {
                "source": {"fingerprint": fingerprint},
                "states": [
                    {
                        "state_id": 1,
                        "relative_path": "history/states/1-Test.txt",
                        "sha256": first_sha,
                    },
                    {
                        "state_id": 2,
                        "relative_path": "history/states/2-Untouched.txt",
                        "sha256": second_sha,
                    },
                ],
            }
            item = override(owner="CHI")
            item["source_sha256"] = first_sha
            outputs = state_transform.build_state_outputs(
                game, snapshot, [document(item, fingerprint)]
            )
        self.assertEqual(len(outputs), 2)
        self.assertIn("owner = CHI", outputs[0].text)
        self.assertEqual(outputs[1].text, untouched)

    def test_build_rejects_overrides_bound_to_another_snapshot(self):
        with self.assertRaisesRegex(state_transform.StateTransformError, "source_fingerprint"):
            state_transform.merge_override_documents(
                [document(override(owner="CHI"), "a" * 64)], "b" * 64
            )

    def test_merge_rejects_two_documents_overlapping_same_field(self):
        first = document(override(owner="CHI"))
        second = document(override(owner="ENG"))
        with self.assertRaisesRegex(state_transform.StateTransformError, "同时修改 state 1 的字段"):
            state_transform.merge_override_documents([first, second], "b" * 64)

    def test_merge_allows_disjoint_fields_across_documents(self):
        first = document(override(owner="CHI", add_core_of=["CHI"]))
        second = document(override(buildings={"civilian_factory": 3}))
        merged = state_transform.merge_override_documents([first, second], "b" * 64)
        self.assertIn(1, merged)
        self.assertEqual(merged[1]["owner"], "CHI")
        self.assertEqual(merged[1]["buildings"], {"civilian_factory": 3})

    def test_writer_refuses_unexpected_existing_state_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "states"
            output.mkdir()
            (output / "999-Stale.txt").write_text("state = {}", encoding="utf-8")
            with self.assertRaisesRegex(state_transform.StateTransformError, "快照之外"):
                state_transform.write_state_outputs(
                    [state_transform.BuiltState("history/states/1-Test.txt", SOURCE)],
                    output,
                )

    def test_state_build_gate_rejects_light_machine_before_reading_sources(self):
        args = type("Args", (), {"override": ["协作/state-overrides/test.json"]})()
        with mock.patch.object(workflow, "load_local_config", return_value=({}, [])):
            with mock.patch.object(
                workflow,
                "derive_environment",
                return_value={
                    "capabilities": {"snapshot_export": False, "mod_execution": False},
                    "snapshot": {"status": "missing"},
                },
            ):
                with self.assertRaisesRegex(workflow.WorkflowError, "snapshot_export"):
                    workflow.state_build(args)

    def test_state_build_integration_uses_current_snapshot_and_fixed_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            game = root / "game"
            state_dir = game / "history" / "states"
            state_dir.mkdir(parents=True)
            source = state_dir / "1-Test.txt"
            source.write_text(SOURCE, encoding="utf-8")
            source_sha = state_transform.sha256_path(source)
            fingerprint = workflow.fingerprint_files([source])
            snapshot = {
                "schema_version": 2,
                "generated_at": "2026-08-11T00:00:00Z",
                "generated_by_machine": "A",
                "game_version": "test",
                "source": {
                    "relative_root": "history/states",
                    "file_count": 1,
                    "fingerprint": fingerprint,
                },
                "states": [
                    {
                        "state_id": 1,
                        "localisation_key": "STATE_1",
                        "relative_path": "history/states/1-Test.txt",
                        "province_count": 2,
                        "provinces": [10, 11],
                        "sha256": source_sha,
                    }
                ],
            }
            snapshot_path = root / "协作" / "扫描快照" / "states.json"
            snapshot_path.parent.mkdir(parents=True)
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
            override_dir = root / "协作" / "state-overrides"
            override_dir.mkdir(parents=True)
            item = override(owner="CHI")
            item["source_sha256"] = source_sha
            override_path = override_dir / "test.json"
            override_path.write_text(json.dumps(document(item, fingerprint)), encoding="utf-8")
            decision_dir = root / "协作" / "决策记录"
            decision_dir.mkdir(parents=True)
            (decision_dir / "D-20260811-004.json").write_text("{}", encoding="utf-8")
            output_dir = root / "mod" / "history" / "states"
            args = type("Args", (), {"override": ["协作/state-overrides/test.json"]})()
            with mock.patch.object(workflow, "ROOT", root):
                with mock.patch.object(workflow, "STATE_OVERRIDE_DIR", override_dir):
                    with mock.patch.object(workflow, "SNAPSHOT_JSON", snapshot_path):
                        with mock.patch.object(workflow, "DECISION_DIR", decision_dir):
                            with mock.patch.object(workflow, "MOD_STATES_DIR", output_dir):
                                with mock.patch.object(
                                    workflow,
                                    "load_local_config",
                                    return_value=({"game_path": str(game)}, []),
                                ):
                                    with mock.patch.object(
                                        workflow,
                                        "derive_environment",
                                        return_value={
                                            "capabilities": {
                                                "snapshot_export": True,
                                                "mod_execution": True,
                                            },
                                            "snapshot": {"status": "current"},
                                        },
                                    ):
                                        self.assertEqual(workflow.state_build(args), 0)
            result = (output_dir / "1-Test.txt").read_text(encoding="utf-8")
            self.assertIn("owner = CHI", result)


if __name__ == "__main__":
    unittest.main()
