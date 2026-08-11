import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scripts import workflow


class WorkflowTests(unittest.TestCase):
    def test_parse_state_and_snapshot_fingerprint_are_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "1-Test.txt"
            path.write_text(
                "state = {\n id = 1\n provinces = { 10 11 # comment\n 12 }\n}\n",
                encoding="utf-8",
            )
            parsed = workflow.parse_state(path)
            self.assertEqual(parsed["state_id"], 1)
            self.assertEqual(parsed["province_count"], 3)
            self.assertEqual(
                workflow.fingerprint_files([path]), workflow.fingerprint_files([path])
            )

    def test_environment_defaults_to_light_without_game_or_snapshot(self):
        with mock.patch.object(workflow, "SNAPSHOT_JSON", Path("/nonexistent/states.json")):
            result = workflow.derive_environment(
                {"machine_id": "C", "os": "ubuntu", "game_path": None}, []
            )
        self.assertEqual(result["profile"], "light")
        self.assertFalse(result["capabilities"]["snapshot_export"])
        self.assertFalse(result["capabilities"]["mod_execution"])
        self.assertTrue(result["capabilities"]["static_validation"])

    def test_render_tasks_escapes_markdown_cells(self):
        data = {
            "policy": {"lease_hours": 48},
            "tasks": [
                {
                    "id": "T-1",
                    "module": "A|B",
                    "status": "todo",
                    "lease_generation": 0,
                }
            ],
        }
        rendered = workflow.render_tasks(data)
        self.assertIn("A\\|B", rendered)
        self.assertIn("待办", rendered)

    def test_expired_lease_rejects_heartbeat(self):
        data = {
            "policy": {"lease_hours": 48},
            "tasks": [
                {
                    "id": "T-1",
                    "status": "in_progress",
                    "lease_generation": 2,
                    "lease_expires_at": "2026-08-01T00:00:00Z",
                }
            ],
        }
        args = type(
            "Args",
            (),
            {"id": "T-1", "generation": 2, "now": "2026-08-02T00:00:00Z"},
        )()
        with mock.patch.object(workflow, "load_tasks", return_value=data):
            with self.assertRaises(workflow.WorkflowError):
                workflow.task_heartbeat(args)

    def test_environment_snapshot_contains_no_local_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            game = root / "game"
            states = game / "history" / "states"
            states.mkdir(parents=True)
            (states / "1-Test.txt").write_text(
                "state={ id=1 provinces={ 1 } }", encoding="utf-8"
            )
            with mock.patch.object(workflow, "SNAPSHOT_JSON", root / "missing.json"):
                result = workflow.derive_environment(
                    {
                        "machine_id": "A",
                        "os": "windows",
                        "game_path": str(game),
                        "user_docs_path": None,
                    },
                    [],
                )
            payload = json.dumps(result)
            self.assertNotIn(str(root), payload)
            self.assertTrue(result["capabilities"]["snapshot_export"])

    def test_invalid_local_config_never_grants_external_path_capabilities(self):
        with tempfile.TemporaryDirectory() as directory:
            game = Path(directory) / "game"
            states = game / "history" / "states"
            states.mkdir(parents=True)
            (states / "1-Test.txt").write_text("state={ id=1 }", encoding="utf-8")
            with mock.patch.object(workflow, "SNAPSHOT_JSON", Path(directory) / "missing.json"):
                result = workflow.derive_environment(
                    {"machine_id": "bad id", "os": "ubuntu", "game_path": str(game)},
                    ["machine_id 无效"],
                )
        self.assertEqual(result["profile"], "light")
        self.assertFalse(result["capabilities"]["snapshot_export"])
        self.assertFalse(result["capabilities"]["load_test"])

    def test_subagent_environment_check_never_probes_external_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            game = Path(directory) / "game"
            states = game / "history" / "states"
            states.mkdir(parents=True)
            (states / "1-Test.txt").write_text("state={ id=1 }", encoding="utf-8")
            with mock.patch.object(workflow, "SNAPSHOT_JSON", Path(directory) / "missing.json"):
                with mock.patch.object(
                    workflow, "state_files", side_effect=AssertionError("不得探测本体")
                ):
                    result = workflow.derive_environment(
                        {"machine_id": "A", "os": "linux", "game_path": str(game)},
                        [],
                        probe_external=False,
                    )
        self.assertEqual(result["profile"], "light")
        self.assertFalse(result["capabilities"]["snapshot_export"])

    def test_malformed_snapshot_never_grants_mod_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "states.json"
            snapshot.write_text(
                json.dumps({"schema_version": 1, "source": {}}), encoding="utf-8"
            )
            with mock.patch.object(workflow, "SNAPSHOT_JSON", snapshot):
                result = workflow.derive_environment(
                    {"machine_id": "C", "os": "ubuntu", "game_path": None}, []
                )
        self.assertEqual(result["snapshot"]["status"], "missing")
        self.assertFalse(result["capabilities"]["mod_execution"])
        self.assertTrue(any("快照结构无效" in item for item in result["warnings"]))

    def test_snapshot_validation_checks_generated_summary(self):
        data = {
            "schema_version": 1,
            "generated_at": "2026-08-10T00:00:00Z",
            "generated_by_machine": "A",
            "game_version": "1.16.9",
            "source": {
                "relative_root": "history/states",
                "file_count": 1,
                "fingerprint": "a" * 64,
            },
            "states": [
                {
                    "state_id": 1,
                    "localisation_key": "STATE_1",
                    "relative_path": "history/states/1-Test.txt",
                    "province_count": 2,
                    "sha256": "b" * 64,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / "states.json"
            summary = root / "states-summary.md"
            snapshot.write_text(json.dumps(data), encoding="utf-8")
            summary.write_text("stale\n", encoding="utf-8")
            errors = []
            with mock.patch.object(workflow, "SNAPSHOT_JSON", snapshot):
                with mock.patch.object(workflow, "SNAPSHOT_MD", summary):
                    workflow.validate_snapshot(errors)
        self.assertEqual(
            errors,
            ["协作/扫描快照/states-summary.md 不是由当前 states.json 生成"],
        )

    def test_stale_snapshot_downgrades_profile_after_capability_gating(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            game = root / "game"
            states = game / "history" / "states"
            states.mkdir(parents=True)
            (states / "1-Test.txt").write_text("state={ id=1 }", encoding="utf-8")
            (game / "hoi4").write_text("", encoding="utf-8")
            docs = root / "docs"
            docs.mkdir()
            snapshot = root / "states.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "generated_at": "2026-08-10T00:00:00Z",
                        "generated_by_machine": "A",
                        "game_version": "test",
                        "source": {
                            "relative_root": "history/states",
                            "file_count": 1,
                            "fingerprint": "0" * 64,
                        },
                        "states": [
                            {
                                "state_id": 1,
                                "localisation_key": "STATE_1",
                                "relative_path": "history/states/1-Test.txt",
                                "province_count": 0,
                                "sha256": "1" * 64,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(workflow, "SNAPSHOT_JSON", snapshot):
                result = workflow.derive_environment(
                    {
                        "machine_id": "A",
                        "os": "linux",
                        "game_path": str(game),
                        "user_docs_path": str(docs),
                    },
                    [],
                )
        self.assertEqual(result["snapshot"]["status"], "stale")
        self.assertEqual(result["profile"], "partial")
        self.assertTrue(result["capabilities"]["snapshot_export"])
        self.assertFalse(result["capabilities"]["mod_execution"])
        self.assertFalse(result["capabilities"]["load_test"])

    def test_task_assign_rejects_incomplete_dependencies(self):
        data = {
            "policy": {"lease_hours": 48},
            "tasks": [
                {"id": "T-1", "status": "todo", "dependencies": ["T-0"]},
                {"id": "T-0", "status": "todo", "dependencies": []},
            ],
        }
        args = type("Args", (), {"id": "T-1", "owner": "C/codex", "now": None})()
        with mock.patch.object(workflow, "load_tasks", return_value=data):
            with self.assertRaisesRegex(workflow.WorkflowError, "依赖尚未完成"):
                workflow.task_assign(args)

    def test_task_registry_lifecycle_changes_are_not_policy_changes(self):
        before = {
            "schema_version": 1,
            "policy": {"lease_hours": 48},
            "tasks": [
                {
                    "id": "T-1",
                    "module": "test",
                    "status": "todo",
                    "owner": None,
                    "lease_generation": 0,
                    "dependencies": [],
                }
            ],
        }
        after = json.loads(json.dumps(before))
        after["tasks"][0].update(
            {
                "status": "in_progress",
                "owner": "C/codex",
                "branch": "task/T-1-g1",
                "lease_generation": 1,
                "base_commit": "a" * 40,
            }
        )
        self.assertEqual(
            workflow.normalized_task_registry(before),
            workflow.normalized_task_registry(after),
        )
        after["tasks"][0]["dependencies"] = ["T-0"]
        self.assertNotEqual(
            workflow.normalized_task_registry(before),
            workflow.normalized_task_registry(after),
        )

    def test_lifecycle_only_task_change_does_not_require_decision_record(self):
        errors = []
        with mock.patch.object(workflow, "changed_files", return_value={"协作/tasks.json"}):
            with mock.patch.object(workflow, "task_registry_policy_changed", return_value=False):
                workflow.validate_change_range("a" * 40, "b" * 40, errors)
        self.assertEqual(errors, [])

    def test_changed_files_preserves_unicode_paths(self):
        completed = type(
            "Completed",
            (),
            {
                "returncode": 0,
                "stdout": "协作/决策记录/D-20260810-001.json\n",
                "stderr": "",
            },
        )()
        with mock.patch.object(workflow, "run_git", return_value=completed) as run_git:
            files = workflow.changed_files("a" * 40, "b" * 40)
        self.assertEqual(files, {"协作/决策记录/D-20260810-001.json"})
        run_git.assert_called_once_with(
            "-c",
            "core.quotePath=false",
            "diff",
            "--name-only",
            f"{'a' * 40}..{'b' * 40}",
            check=False,
        )

    def test_validate_requires_complete_change_range(self):
        args = type("Args", (), {"base": "a" * 40, "head": None, "ci": False})()
        validators = (
            "validate_tasks",
            "validate_environment",
            "validate_snapshot",
            "validate_decisions",
            "validate_handoffs",
            "validate_static_files",
        )
        patches = [mock.patch.object(workflow, name) for name in validators]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.assertEqual(workflow.validate(args), 1)


if __name__ == "__main__":
    unittest.main()
