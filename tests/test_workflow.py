import json
import subprocess
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

    @staticmethod
    def environment_snapshot(checked_at):
        return {
            "schema_version": 1,
            "machine_id": "C",
            "os": "ubuntu",
            "checked_at": checked_at,
            "profile": "light",
            "config_valid": True,
            "capabilities": {
                "dialog_development": True,
                "snapshot_export": False,
                "mod_execution": False,
                "static_validation": True,
                "load_test": False,
            },
            "snapshot": {
                "status": "missing",
                "game_version": None,
                "fingerprint": None,
            },
            "warnings": [],
        }

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

    def test_run_git_decodes_output_as_utf8_independent_of_locale(self):
        completed = subprocess.CompletedProcess(["git", "status"], 0, "", "")
        with mock.patch.object(
            workflow.subprocess, "run", return_value=completed
        ) as subprocess_run:
            workflow.run_git("status", check=False)
        subprocess_run.assert_called_once_with(
            ["git", "status"],
            cwd=workflow.ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
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
            if args[:5] == ("-c", "core.quotePath=false", "diff", "--cached", "--name-only"):
                return self.completed(
                    stdout="协作/tasks.json\n协作/任务台账.md\n协作/环境/C.json\n"
                )
            if args[0] in {"add", "commit", "branch"}:
                return self.completed()
            if args == ("rev-parse", "HEAD"):
                return self.completed(stdout=lease_commit + "\n")
            raise AssertionError(args)

        with mock.patch.object(workflow, "run_git", side_effect=fake_git) as run_git:
            result = workflow.commit_lease_and_create_branch(
                "T-003",
                1,
                "C/codex",
                "task/T-003-g1",
                workflow.ENV_DIR / "C.json",
            )
        self.assertEqual(result, lease_commit)
        run_git.assert_any_call("branch", "task/T-003-g1", lease_commit, check=False)

    def test_require_clean_main_allows_only_target_environment_snapshot(self):
        responses = iter(
            [
                self.completed(stdout="main\n"),
                self.completed(stdout=" M 协作/环境/C.json\n"),
                self.completed(stdout="a" * 40 + "\n"),
            ]
        )
        with mock.patch.object(workflow, "run_git", side_effect=lambda *a, **k: next(responses)):
            result = workflow.require_clean_main({"协作/环境/C.json"})
        self.assertEqual(result, "a" * 40)

    def test_owner_environment_snapshot_must_be_recent_and_not_future(self):
        task = {"required_capabilities": ["static_validation"]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env_dir = root / "协作" / "环境"
            env_dir.mkdir(parents=True)
            env_path = env_dir / "C.json"
            with mock.patch.object(workflow, "ROOT", root), mock.patch.object(
                workflow, "ENV_DIR", env_dir
            ):
                env_path.write_text(
                    json.dumps(self.environment_snapshot("2026-08-11T00:00:00Z")),
                    encoding="utf-8",
                )
                self.assertEqual(
                    workflow.assert_owner_capabilities(
                        task,
                        "C/codex",
                        workflow.parse_iso_z("2026-08-11T00:15:00Z"),
                    ),
                    env_path,
                )
                with self.assertRaisesRegex(workflow.WorkflowError, "超过 15 分钟"):
                    workflow.assert_owner_capabilities(
                        task,
                        "C/codex",
                        workflow.parse_iso_z("2026-08-11T00:16:00Z"),
                    )
                env_path.write_text(
                    json.dumps(self.environment_snapshot("2026-08-11T00:01:00Z")),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(workflow.WorkflowError, "来自未来"):
                    workflow.assert_owner_capabilities(
                        task,
                        "C/codex",
                        workflow.parse_iso_z("2026-08-11T00:00:00Z"),
                    )

    def test_task_assign_atomically_commits_fresh_environment_and_lease(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.run(
                    ["git", *args],
                    cwd=root,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )

            git("init", "-b", "main")
            git("config", "user.name", "Workflow Test")
            git("config", "user.email", "workflow@example.invalid")
            tasks_json = root / "协作" / "tasks.json"
            tasks_md = root / "协作" / "任务台账.md"
            env_dir = root / "协作" / "环境"
            env_dir.mkdir(parents=True)
            task_data = {
                "schema_version": 1,
                "policy": {"lease_hours": 48},
                "tasks": [
                    {
                        "id": "T-014",
                        "module": "test",
                        "status": "todo",
                        "owner": None,
                        "branch": None,
                        "lease_generation": 0,
                        "claimed_at": None,
                        "heartbeat_at": None,
                        "lease_expires_at": None,
                        "base_commit": None,
                        "head_commit": None,
                        "dependencies": [],
                        "required_capabilities": ["static_validation"],
                        "decision_ids": [],
                        "handoff": None,
                        "outputs": ["test"],
                        "blocker": None,
                    }
                ],
            }
            tasks_json.write_text(json.dumps(task_data), encoding="utf-8")
            tasks_md.write_text(workflow.render_tasks(task_data), encoding="utf-8")
            env_path = env_dir / "C.json"
            env_path.write_text(
                json.dumps(self.environment_snapshot("2026-08-11T02:00:00Z")),
                encoding="utf-8",
            )
            git("add", "--all")
            git("commit", "-m", "base")
            base = git("rev-parse", "HEAD").stdout.strip()
            env_path.write_text(
                json.dumps(self.environment_snapshot("2026-08-11T03:00:00Z")),
                encoding="utf-8",
            )
            args = type(
                "Args",
                (),
                {
                    "id": "T-014",
                    "owner": "C/codex",
                    "now": "2026-08-11T03:05:00Z",
                },
            )()
            with mock.patch.object(workflow, "ROOT", root):
                with mock.patch.object(workflow, "TASKS_JSON", tasks_json):
                    with mock.patch.object(workflow, "TASKS_MD", tasks_md):
                        with mock.patch.object(workflow, "ENV_DIR", env_dir):
                            self.assertEqual(workflow.task_assign(args), 0)
            head = git("rev-parse", "HEAD").stdout.strip()
            changed = set(
                git(
                    "-c",
                    "core.quotePath=false",
                    "show",
                    "--pretty=",
                    "--name-only",
                    "HEAD",
                ).stdout.splitlines()
            )
            self.assertEqual(
                changed,
                {"协作/tasks.json", "协作/任务台账.md", "协作/环境/C.json"},
            )
            self.assertEqual(git("rev-parse", "task/T-014-g1").stdout.strip(), head)
            self.assertEqual(git("status", "--porcelain").stdout, "")
            assigned = json.loads(tasks_json.read_text(encoding="utf-8"))["tasks"][0]
            self.assertEqual(assigned["base_commit"], base)

    def test_validation_result_atomically_commits_environment_report_and_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.run(
                    ["git", *args],
                    cwd=root,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )

            git("init", "-b", "main")
            git("config", "user.name", "Workflow Test")
            git("config", "user.email", "workflow@example.invalid")
            collaboration = root / "协作"
            env_dir = collaboration / "环境"
            review_dir = collaboration / "审查记录"
            env_dir.mkdir(parents=True)
            review_dir.mkdir()
            tasks_json = collaboration / "tasks.json"
            tasks_md = collaboration / "任务台账.md"
            task_data = {
                "schema_version": 1,
                "policy": {"lease_hours": 48},
                "tasks": [
                    {
                        "id": "T-015",
                        "status": "pending_validation",
                        "lease_generation": 1,
                        "blocker": None,
                    }
                ],
            }
            tasks_json.write_text(json.dumps(task_data), encoding="utf-8")
            tasks_md.write_text(workflow.render_tasks(task_data), encoding="utf-8")
            env_path = env_dir / "C.json"
            env_path.write_text(
                json.dumps(self.environment_snapshot("2026-08-11T03:00:00Z")),
                encoding="utf-8",
            )
            git("add", "--all")
            git("commit", "-m", "base")
            env_path.write_text(
                json.dumps(self.environment_snapshot("2026-08-11T03:05:00Z")),
                encoding="utf-8",
            )
            report = review_dir / "验证-T-015.md"
            report.write_text("# PASS\n", encoding="utf-8")
            args = type(
                "Args",
                (),
                {
                    "id": "T-015",
                    "generation": 1,
                    "result": "pass",
                    "report": "协作/审查记录/验证-T-015.md",
                    "requires_load_test": False,
                    "now": None,
                },
            )()
            with mock.patch.object(workflow, "ROOT", root), mock.patch.object(
                workflow, "TASKS_JSON", tasks_json
            ), mock.patch.object(workflow, "TASKS_MD", tasks_md), mock.patch.object(
                workflow, "ENV_DIR", env_dir
            ), mock.patch.object(
                workflow, "current_coordinator_environment_path", return_value=env_path
            ):
                self.assertEqual(workflow.task_validation_result(args), 0)
            changed = set(
                git(
                    "-c",
                    "core.quotePath=false",
                    "show",
                    "--pretty=",
                    "--name-only",
                    "HEAD",
                ).stdout.splitlines()
            )
            self.assertEqual(
                changed,
                {
                    "协作/tasks.json",
                    "协作/任务台账.md",
                    "协作/环境/C.json",
                    "协作/审查记录/验证-T-015.md",
                },
            )
            self.assertEqual(git("status", "--porcelain").stdout, "")
            updated = json.loads(tasks_json.read_text(encoding="utf-8"))["tasks"][0]
            self.assertEqual(updated["status"], "ready_to_merge")
            self.assertEqual(
                updated["validation_report"], "协作/审查记录/验证-T-015.md"
            )

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
        responses = iter([self.completed(), self.completed(), self.completed()])
        with mock.patch.object(
            workflow,
            "lifecycle_preflight",
            return_value=(workflow.ENV_DIR / "C.json", "d" * 40),
        ):
            with mock.patch.object(workflow, "load_tasks", return_value=data):
                with mock.patch.object(
                    workflow, "run_git", side_effect=lambda *a, **k: next(responses)
                ):
                    with mock.patch.object(
                        workflow, "resolve_task_branch_tip", return_value="c" * 40
                    ):
                        with self.assertRaisesRegex(
                            workflow.WorkflowError, "不是任务分支 tip"
                        ):
                            workflow.task_handoff(args)

    def test_task_branch_tip_accepts_fetched_remote_and_rejects_divergence(self):
        remote_tip = "b" * 40
        with mock.patch.object(
            workflow,
            "run_git",
            side_effect=[
                self.completed(returncode=1),
                self.completed(stdout=remote_tip + "\n"),
            ],
        ):
            self.assertEqual(
                workflow.resolve_task_branch_tip("task/T-003-g1"), remote_tip
            )
        with mock.patch.object(
            workflow,
            "run_git",
            side_effect=[
                self.completed(stdout="a" * 40 + "\n"),
                self.completed(stdout=remote_tip + "\n"),
            ],
        ):
            with self.assertRaisesRegex(workflow.WorkflowError, "tip 不一致"):
                workflow.resolve_task_branch_tip("task/T-003-g1")

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
        with mock.patch.object(
            workflow,
            "lifecycle_preflight",
            return_value=(workflow.ENV_DIR / "C.json", "a" * 40),
        ):
            with mock.patch.object(workflow, "load_tasks", return_value=data):
                with mock.patch.object(
                    workflow, "checked_report_path", return_value=args.report
                ):
                    with mock.patch.object(workflow, "write_json"):
                        with mock.patch.object(workflow, "TASKS_MD", tasks_md):
                            with mock.patch.object(workflow, "commit_task_state"):
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
        with mock.patch.object(
            workflow,
            "lifecycle_preflight",
            return_value=(workflow.ENV_DIR / "C.json", "a" * 40),
        ):
            with mock.patch.object(workflow, "load_tasks", return_value=data):
                with mock.patch.object(
                    workflow, "checked_report_path", return_value=args.report
                ):
                    with mock.patch.object(workflow, "write_json"):
                        with mock.patch.object(workflow, "TASKS_MD", mock.Mock()):
                            with mock.patch.object(workflow, "commit_task_state"):
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
        with mock.patch.object(
            workflow,
            "lifecycle_preflight",
            return_value=(workflow.ENV_DIR / "C.json", "b" * 40),
        ):
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

    def test_decision_schema_validates_resolved_pending_evidence(self):
        schema = workflow.read_json(workflow.SCHEMA_DIR / "decision.schema.json")
        decision = {
            "schema_version": 1,
            "decision_id": "D-20260811-009",
            "title": "test",
            "status": "confirmed",
            "confirmed_by": "user",
            "confirmed_at": "2026-08-11T00:00:00Z",
            "scope": ["pending_resolution"],
            "decisions": ["confirmed"],
            "affected_files": ["设定书/"],
            "resolved_pending": [
                {
                    "path": "设定书/06-军事.md",
                    "line_sha256": "a" * 64,
                    "occurrences": 1,
                    "resolution": "用户确认舰队规模",
                }
            ],
        }
        self.assertEqual(workflow.validate_schema_instance(decision, schema), [])
        decision["resolved_pending"][0]["occurrences"] = 0
        errors = workflow.validate_schema_instance(decision, schema)
        self.assertTrue(any("不得小于 1" in error for error in errors))

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
                        with mock.patch.object(
                            workflow, "pending_removals_for_git_diff", return_value=[]
                        ):
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
                        with mock.patch.object(
                            workflow, "pending_removals_for_git_diff", return_value=[]
                        ):
                            workflow.validate_commit_rules("a" * 40, "c" * 40, errors)
        self.assertEqual(
            errors,
            ["cccccccccccc: 设定层变更必须同 commit 更新00卷修订记录"],
        )

    def test_pending_marker_removal_requires_structured_resolution(self):
        diff = """diff --git a/设定书/06-军事.md b/设定书/06-军事.md
--- a/设定书/06-军事.md
+++ b/设定书/06-军事.md
@@ -1 +1 @@
-舰队规模待确认
+舰队规模确定为十艘
"""
        removals = workflow.pending_removals_from_diff(diff)
        self.assertEqual(len(removals), 1)
        removal = removals[0]
        errors = []
        workflow.validate_pending_resolutions(
            "deadbeef0000",
            removals,
            [{"decision_id": "D-1", "affected_files": ["设定书/"]}],
            errors,
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("resolved_pending", errors[0])

        decision = {
            "decision_id": "D-1",
            "affected_files": ["设定书/"],
            "resolved_pending": [
                {
                    "path": removal.path,
                    "line_sha256": removal.line_sha256,
                    "resolution": "用户确认舰队规模",
                }
            ],
        }
        errors = []
        workflow.validate_pending_resolutions(
            "deadbeef0000", removals, [decision], errors
        )
        self.assertEqual(errors, [])

        decision["affected_files"] = ["Settings/"]
        errors = []
        workflow.validate_pending_resolutions(
            "deadbeef0000", removals, [decision], errors
        )
        self.assertTrue(any("resolved_pending" in error for error in errors))

    def test_pending_marker_rewording_and_exact_move_are_not_resolutions(self):
        diff = """diff --git a/设定书/a.md b/设定书/a.md
--- a/设定书/a.md
+++ b/设定书/a.md
@@ -1 +1 @@
-规模待确认
+规模仍然待定
diff --git a/设定书/b.md b/设定书/b.md
--- a/设定书/b.md
+++ b/设定书/b.md
@@ -2 +1,0 @@
-边界待确认
diff --git a/设定书/c.md b/设定书/c.md
--- a/设定书/c.md
+++ b/设定书/c.md
@@ -0,0 +3 @@
+边界待确认
"""
        self.assertEqual(workflow.pending_removals_from_diff(diff), [])

    def test_pending_marker_synonym_heading_counts_as_one_annotation(self):
        self.assertEqual(workflow.pending_marker_count("待定/待确认事项"), 1)
        self.assertEqual(workflow.pending_marker_count("人口待定，舰队待确认"), 2)

    def test_pending_marker_staged_diff_reads_git_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.run(
                    ["git", *args],
                    cwd=root,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )

            git("init", "-b", "main")
            git("config", "user.name", "Workflow Test")
            git("config", "user.email", "workflow@example.invalid")
            setting_dir = root / "设定书"
            setting_dir.mkdir()
            setting = setting_dir / "06-军事.md"
            setting.write_text("舰队规模待确认\n", encoding="utf-8")
            git("add", "--all")
            git("commit", "-m", "base")
            setting.write_text("舰队规模确定为十艘\n", encoding="utf-8")
            git("add", "--all")
            with mock.patch.object(workflow, "ROOT", root):
                removals = workflow.pending_removals_for_git_diff("--cached")
            self.assertEqual(len(removals), 1)
            self.assertEqual(removals[0].path, "设定书/06-军事.md")
            self.assertEqual(
                removals[0].line_sha256,
                workflow.pending_line_sha256("舰队规模待确认"),
            )

    def test_pending_resolution_occurrences_cannot_be_underdeclared(self):
        diff = """diff --git a/Settings/example.md b/Settings/example.md
--- a/Settings/example.md
+++ b/Settings/example.md
@@ -1 +1 @@
-人口待定，舰队待确认
+人口与舰队均已确认
"""
        removals = workflow.pending_removals_from_diff(diff)
        self.assertEqual(len(removals), 2)
        decision = {
            "affected_files": ["Settings/"],
            "resolved_pending": [
                {
                    "path": removals[0].path,
                    "line_sha256": removals[0].line_sha256,
                    "occurrences": 1,
                    "resolution": "用户确认",
                }
            ]
        }
        errors = []
        workflow.validate_pending_resolutions("staged", removals, [decision], errors)
        self.assertEqual(len(errors), 1)
        self.assertIn("occurrences=1", errors[0])
        decision["resolved_pending"][0]["occurrences"] = 2
        errors = []
        workflow.validate_pending_resolutions("staged", removals, [decision], errors)
        self.assertEqual(errors, [])

    def test_staged_setting_change_uses_index_decision_and_pending_gate(self):
        removal = workflow.PendingRemoval(
            "设定书/06-军事.md", "a" * 64, "舰队规模待确认"
        )
        decision = {
            "decision_id": "D-20260811-009",
            "affected_files": ["设定书/"],
        }
        files = {
            "设定书/06-军事.md",
            "设定书/00-总览与索引.md",
            "协作/决策记录/D-20260811-009.json",
        }
        errors = []
        with mock.patch.object(workflow, "staged_files", return_value=files), mock.patch.object(
            workflow, "git_json_from_index", return_value=decision
        ), mock.patch.object(
            workflow, "pending_removals_for_git_diff", return_value=[removal]
        ), mock.patch.object(
            workflow,
            "added_staged_revision_rows",
            return_value=["2026-08-11 | 舰队 | D-20260811-009 | 06"],
        ):
            workflow.validate_staged_commit_rules(errors)
        self.assertTrue(any("resolved_pending" in error for error in errors))

        decision["resolved_pending"] = [
            {
                "path": removal.path,
                "line_sha256": removal.line_sha256,
                "resolution": "用户确认舰队规模",
            }
        ]
        errors = []
        with mock.patch.object(workflow, "staged_files", return_value=files), mock.patch.object(
            workflow, "git_json_from_index", return_value=decision
        ), mock.patch.object(
            workflow, "pending_removals_for_git_diff", return_value=[removal]
        ), mock.patch.object(
            workflow,
            "added_staged_revision_rows",
            return_value=["2026-08-11 | 舰队 | D-20260811-009 | 06"],
        ):
            workflow.validate_staged_commit_rules(errors)
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

    def test_interview_protocol_contains_all_restored_rules(self):
        protocol = (workflow.ROOT / "协作" / "决策协议.md").read_text(encoding="utf-8")
        adapter = (
            workflow.ROOT / ".opencode" / "skills" / "teg-interview-me" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(workflow.interview_protocol_errors(protocol, adapter), [])

    def test_interview_protocol_gate_detects_removed_rule_and_copied_adapter(self):
        protocol = "\n".join(workflow.INTERVIEW_PROTOCOL_MARKERS[:-1])
        adapter = "协作/决策协议.md\n必须完整读取并执行\n" + "\n" * 11
        errors = workflow.interview_protocol_errors(protocol, adapter)
        self.assertTrue(any("明确确认门槛" in error for error in errors))
        self.assertTrue(any("短适配器" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
