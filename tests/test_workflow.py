import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scripts import workflow


class WorkflowTests(unittest.TestCase):
    @staticmethod
    def completed(returncode=0, stdout="", stderr=""):
        return type(
            "Completed",
            (),
            {"returncode": returncode, "stdout": stdout, "stderr": stderr},
        )()

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

    def test_task_assign_requires_clean_main(self):
        calls = iter(
            [
                self.completed(stdout="main\n"),
                self.completed(stdout=" M file.txt\n"),
            ]
        )
        with mock.patch.object(workflow, "run_git", side_effect=lambda *a, **k: next(calls)):
            with self.assertRaisesRegex(workflow.WorkflowError, "要求干净工作区"):
                workflow.require_clean_main()

    def test_assignment_commits_lease_and_creates_local_branch(self):
        lease_commit = "c" * 40

        def fake_git(*args, **kwargs):
            if args[:3] == ("show-ref", "--verify", "--quiet"):
                return self.completed(returncode=1)
            if args[0] in {"add", "commit", "branch"}:
                return self.completed()
            if args == ("rev-parse", "HEAD"):
                return self.completed(stdout=lease_commit + "\n")
            raise AssertionError(args)

        with mock.patch.object(workflow, "run_git", side_effect=fake_git) as run_git:
            result = workflow.commit_lease_and_create_branch(
                "T-003", 1, "C/codex", "task/T-003-g1"
            )
        self.assertEqual(result, lease_commit)
        run_git.assert_any_call("branch", "task/T-003-g1", lease_commit, check=False)

    def test_handoff_rejects_head_that_is_not_task_branch_tip(self):
        data = {
            "tasks": [
                {
                    "id": "T-003",
                    "status": "in_progress",
                    "lease_generation": 1,
                    "lease_expires_at": "2099-01-01T00:00:00Z",
                    "base_commit": "a" * 40,
                    "branch": "task/T-003-g1",
                    "decision_ids": [],
                }
            ]
        }
        args = type(
            "Args",
            (),
            {
                "id": "T-003",
                "generation": 1,
                "head": "b" * 40,
                "changed_file": [],
                "notes": "",
            },
        )()
        responses = iter(
            [
                self.completed(),
                self.completed(),
                self.completed(),
                self.completed(stdout="c" * 40 + "\n"),
            ]
        )
        with mock.patch.object(workflow, "load_tasks", return_value=data):
            with mock.patch.object(workflow, "run_git", side_effect=lambda *a, **k: next(responses)):
                with self.assertRaisesRegex(workflow.WorkflowError, "不是任务分支 tip"):
                    workflow.task_handoff(args)

    def test_validation_pass_moves_task_to_ready_to_merge(self):
        data = {
            "policy": {"lease_hours": 48},
            "tasks": [
                {
                    "id": "T-003",
                    "status": "pending_validation",
                    "lease_generation": 1,
                    "blocker": None,
                }
            ],
        }
        args = type(
            "Args",
            (),
            {
                "id": "T-003",
                "generation": 1,
                "result": "pass",
                "report": "协作/审查记录/验证-T-003.md",
                "requires_load_test": False,
                "now": None,
            },
        )()
        tasks_md = mock.Mock()
        with mock.patch.object(workflow, "require_clean_main"):
            with mock.patch.object(workflow, "load_tasks", return_value=data):
                with mock.patch.object(
                    workflow, "checked_report_path", return_value=args.report
                ):
                    with mock.patch.object(workflow, "write_json"):
                        with mock.patch.object(workflow, "TASKS_MD", tasks_md):
                            workflow.task_validation_result(args)
        task = data["tasks"][0]
        self.assertEqual(task["status"], "ready_to_merge")
        self.assertEqual(task["validation_report"], args.report)
        tasks_md.write_text.assert_called_once()

    def test_validation_failure_reopens_same_generation_lease(self):
        data = {
            "policy": {"lease_hours": 48},
            "tasks": [
                {
                    "id": "T-003",
                    "status": "pending_validation",
                    "lease_generation": 4,
                    "head_commit": "a" * 40,
                    "handoff": "协作/交接单/T-003-g4.json",
                }
            ],
        }
        args = type(
            "Args",
            (),
            {
                "id": "T-003",
                "generation": 4,
                "result": "fail",
                "report": "协作/审查记录/验证-T-003.md",
                "requires_load_test": False,
                "now": "2026-08-11T00:00:00Z",
            },
        )()
        with mock.patch.object(workflow, "require_clean_main"):
            with mock.patch.object(workflow, "load_tasks", return_value=data):
                with mock.patch.object(
                    workflow, "checked_report_path", return_value=args.report
                ):
                    with mock.patch.object(workflow, "write_json"):
                        with mock.patch.object(workflow, "TASKS_MD", mock.Mock()):
                            workflow.task_validation_result(args)
        task = data["tasks"][0]
        self.assertEqual(task["status"], "in_progress")
        self.assertEqual(task["lease_generation"], 4)
        self.assertEqual(task["lease_expires_at"], "2026-08-13T00:00:00Z")
        self.assertIsNone(task["head_commit"])
        self.assertIsNone(task["handoff"])

    def test_complete_rejects_unmerged_task_head(self):
        data = {
            "tasks": [
                {
                    "id": "T-003",
                    "status": "ready_to_merge",
                    "lease_generation": 1,
                    "head_commit": "a" * 40,
                }
            ]
        }
        args = type("Args", (), {"id": "T-003", "generation": 1})()
        with mock.patch.object(workflow, "require_clean_main", return_value="b" * 40):
            with mock.patch.object(workflow, "load_tasks", return_value=data):
                with mock.patch.object(
                    workflow, "run_git", return_value=self.completed(returncode=1)
                ):
                    with self.assertRaisesRegex(workflow.WorkflowError, "尚未进入 main"):
                        workflow.task_complete(args)

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
                with mock.patch.object(workflow, "validate_commit_rules"):
                    workflow.validate_change_range("a" * 40, "b" * 40, errors)
        self.assertEqual(errors, [])

    def test_executable_schema_rejects_missing_required_and_extra_fields(self):
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string", "minLength": 1}},
            "additionalProperties": False,
        }
        self.assertEqual(
            workflow.validate_schema_instance({"extra": True}, schema),
            ["$: 缺少必填字段 name", "$: 不允许额外字段 extra"],
        )

    def test_absolute_path_detection_covers_posix_windows_and_unc(self):
        samples = (
            "/tmp/secret",
            "/mnt/c/secret",
            "C:/secret",
            r"C:\\secret",
            r"\\server\share",
            "错误路径：/opt/game/history/states",
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(workflow.string_contains_absolute_path(sample))
        self.assertFalse(workflow.string_contains_absolute_path("history/states/1-Test.txt"))
        self.assertFalse(workflow.string_contains_absolute_path("https://example.com/path"))

    def test_decision_must_apply_to_changed_core_paths(self):
        errors = []
        decision = {
            "decision_id": "D-20260811-001",
            "affected_files": ["AGENTS.md"],
        }
        with mock.patch.object(workflow, "commits_in_range", return_value=["c" * 40]):
            with mock.patch.object(workflow, "first_parent", return_value="b" * 40):
                with mock.patch.object(
                    workflow,
                    "changed_files",
                    return_value={"scripts/workflow.py", "协作/决策记录/D-20260811-001.json"},
                ):
                    with mock.patch.object(workflow, "git_json_at", return_value=decision):
                        workflow.validate_commit_rules("a" * 40, "c" * 40, errors)
        self.assertEqual(
            errors,
            ["cccccccccccc: 决策 affected_files 与当前设定/核心变更无匹配"],
        )

    def test_setting_change_requires_same_commit_index_update(self):
        errors = []
        decision = {
            "decision_id": "D-20260811-001",
            "affected_files": ["Settings/"],
        }
        with mock.patch.object(workflow, "commits_in_range", return_value=["c" * 40]):
            with mock.patch.object(workflow, "first_parent", return_value="b" * 40):
                with mock.patch.object(
                    workflow,
                    "changed_files",
                    return_value={"Settings/example.md", "协作/决策记录/D-20260811-001.json"},
                ):
                    with mock.patch.object(workflow, "git_json_at", return_value=decision):
                        workflow.validate_commit_rules("a" * 40, "c" * 40, errors)
        self.assertEqual(
            errors,
            ["cccccccccccc: 设定层变更必须同 commit 更新00卷修订记录"],
        )

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
