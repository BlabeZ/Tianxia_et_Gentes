import os
import tempfile
import unittest
from unittest import mock

import scripts.game_test as gt


class ScanTextTests(unittest.TestCase):
    def test_fatal_priority_over_ignore(self):
        rules = gt.compile_rules(
            [
                {"rule_id": "fatal_map", "kind": "fatal", "pattern": "MAP_ERROR"},
                {"rule_id": "noise", "kind": "ignore", "pattern": "MAP_ERROR"},
            ]
        )
        hits, _ = gt.scan_text("something MAP_ERROR here\n", rules, "logs/game.log")
        kinds = [h.kind for h in hits]
        self.assertIn("fatal", kinds)

    def test_required_marker_capture_and_count(self):
        rules = gt.compile_rules(
            [
                {
                    "rule_id": "mod_loaded",
                    "kind": "required_marker",
                    "pattern": r"Mod loaded: (\S+)",
                    "capture_group": 1,
                }
            ]
        )
        hits, markers = gt.scan_text(
            "Mod loaded: txg\nMod loaded: txg\n", rules, "logs/game.log"
        )
        self.assertEqual(len(hits), 0)
        self.assertEqual(markers["mod_loaded"].count, 2)
        self.assertEqual(markers["mod_loaded"].capture, "txg")

    def test_rule_log_scope(self):
        rules = gt.compile_rules(
            [{"rule_id": "e", "kind": "fatal", "pattern": "boom", "log": "logs/error.log"}]
        )
        hits, _ = gt.scan_text("boom\n", rules, "logs/game.log")
        self.assertEqual(hits, [])
        hits, _ = gt.scan_text("boom\n", rules, "logs/error.log")
        self.assertEqual(len(hits), 1)

    def test_unknown_rule_kind_rejected(self):
        with self.assertRaises(ValueError):
            gt.compile_rules([{"rule_id": "x", "kind": "nope", "pattern": "x"}])


class EvaluateTests(unittest.TestCase):
    def test_pass_full_evidence(self):
        markers = {"mod_loaded": gt.MarkerEvidence("mod_loaded", "logs/game.log", 0, "txg", 1)}
        result = gt.evaluate(
            markers=markers,
            fatal_hits=[],
            invalidating_hits=[],
            crash_evidence=[],
            any_new_evidence=True,
            all_logs_consistent=True,
            ready_reached=True,
            survived_after_ready=True,
            required_marker_ids=["mod_loaded"],
        )
        self.assertEqual(result.verdict, "PASS")

    def test_fail_on_fatal(self):
        fatal = [gt.RuleHit("fatal_map", "fatal", "logs/game.log", 3, "MAP_ERROR")]
        result = gt.evaluate(
            markers={},
            fatal_hits=fatal,
            invalidating_hits=[],
            crash_evidence=[],
            any_new_evidence=True,
            all_logs_consistent=True,
            ready_reached=True,
            survived_after_ready=True,
            required_marker_ids=[],
        )
        self.assertEqual(result.verdict, "FAIL")

    def test_fail_on_crash_evidence(self):
        result = gt.evaluate(
            markers={},
            fatal_hits=[],
            invalidating_hits=[],
            crash_evidence=["crashes/hoi4_20260813_1/"],
            any_new_evidence=True,
            all_logs_consistent=True,
            ready_reached=True,
            survived_after_ready=True,
            required_marker_ids=[],
        )
        self.assertEqual(result.verdict, "FAIL")

    def test_inconclusive_no_new_evidence(self):
        result = gt.evaluate(
            markers={},
            fatal_hits=[],
            invalidating_hits=[],
            crash_evidence=[],
            any_new_evidence=False,
            all_logs_consistent=True,
            ready_reached=False,
            survived_after_ready=False,
            required_marker_ids=[],
        )
        self.assertEqual(result.verdict, "INCONCLUSIVE")

    def test_inconclusive_missing_markers(self):
        result = gt.evaluate(
            markers={},
            fatal_hits=[],
            invalidating_hits=[],
            crash_evidence=[],
            any_new_evidence=True,
            all_logs_consistent=True,
            ready_reached=True,
            survived_after_ready=True,
            required_marker_ids=["mod_loaded"],
        )
        self.assertEqual(result.verdict, "INCONCLUSIVE")
        self.assertTrue(any("缺失" in r for r in result.reasons))

    def test_inconclusive_ready_timeout_without_fatal(self):
        result = gt.evaluate(
            markers={},
            fatal_hits=[],
            invalidating_hits=[],
            crash_evidence=[],
            any_new_evidence=True,
            all_logs_consistent=True,
            ready_reached=False,
            survived_after_ready=False,
            required_marker_ids=[],
        )
        self.assertEqual(result.verdict, "INCONCLUSIVE")

    def test_fail_on_invalidating_after_ready(self):
        inv = [gt.RuleHit("menu_closed", "invalidating", "logs/game.log", 9, "menu closed")]
        result = gt.evaluate(
            markers={"mod_loaded": gt.MarkerEvidence("mod_loaded", "logs/game.log", 0, "txg", 1)},
            fatal_hits=[],
            invalidating_hits=inv,
            crash_evidence=[],
            any_new_evidence=True,
            all_logs_consistent=True,
            ready_reached=True,
            survived_after_ready=True,
            required_marker_ids=["mod_loaded"],
        )
        self.assertEqual(result.verdict, "FAIL")

    def test_inconclusive_on_log_rotation(self):
        result = gt.evaluate(
            markers={},
            fatal_hits=[],
            invalidating_hits=[],
            crash_evidence=[],
            any_new_evidence=True,
            all_logs_consistent=False,
            ready_reached=True,
            survived_after_ready=True,
            required_marker_ids=[],
        )
        self.assertEqual(result.verdict, "INCONCLUSIVE")


class RedactTests(unittest.TestCase):
    def test_redact_absolute_paths_and_credentials(self):
        text = "loaded C:\\Users\\alice\\Docs\\mods\\x.mod token=abc123 76561198000000001 /home/user/x"
        redacted = gt.redact_text(text)
        self.assertNotIn("C:\\Users\\alice", redacted)
        self.assertNotIn("abc123", redacted)
        self.assertNotIn("76561198000000001", redacted)
        self.assertNotIn("/home/user", redacted)

    def test_report_has_no_absolute_path(self):
        report = gt.build_report(
            session_id="txg-" + "a" * 16,
            task_id="T-028",
            generation=1,
            profile="map-load",
            game_version="1.19.2",
            executable_sha256="a" * 64,
            baseline_contract_id=None,
            mod_descriptor_sha256="b" * 64,
            mod_tree_sha256="c" * 64,
            git_head="d" * 40,
            git_dirty=False,
            runner_commit="e" * 40,
            profile_hash="f" * 64,
            rules_hash="g" * 64,
            started_at="2026-08-13T00:00:00Z",
            ended_at="2026-08-13T00:05:00Z",
            durations={"startup": 10.0},
            executable_basename="hoi4.exe",
            sanitized_argv=["hoi4.exe", "-debug"],
            markers=[gt.MarkerEvidence("mod_loaded", "logs/game.log", 1000, "txg", 1)],
            exit_code=0,
            terminated_by_runner=True,
            log_diffs=[gt.LogDiff(path="logs/game.log", baseline_size=0, new_size=10, appended_bytes=10)],
            result=gt.SessionResult(
                verdict="PASS",
                reasons=["ok"],
                hits=[gt.RuleHit("r", "ignore", "logs/game.log", 1, "C:\\Users\\bob\\x")],
            ),
            registrable=True,
        )
        self.assertFalse(gt.contains_absolute_path(report))

    def test_markdown_renders_repeatably(self):
        report = gt.build_report(
            session_id="txg-" + "a" * 16,
            task_id="T-028",
            generation=1,
            profile="map-load",
            game_version=None,
            executable_sha256=None,
            baseline_contract_id=None,
            mod_descriptor_sha256=None,
            mod_tree_sha256=None,
            git_head="d" * 40,
            git_dirty=False,
            runner_commit="e" * 40,
            profile_hash="f" * 64,
            rules_hash="g" * 64,
            started_at="s",
            ended_at="e",
            durations={},
            executable_basename=None,
            sanitized_argv=[],
            markers=[],
            exit_code=None,
            terminated_by_runner=False,
            log_diffs=[],
            result=gt.SessionResult(verdict="INCONCLUSIVE", reasons=["无证据"]),
            registrable=False,
        )
        md = gt.render_markdown(report)
        self.assertEqual(gt.render_markdown(report), md)
        self.assertEqual(gt.report_files_valid(report, md), [])

    def test_registrable_gate_on_smoke_profile(self):
        report = gt.build_report(
            session_id="txg-" + "a" * 16,
            task_id="T-042",
            generation=1,
            profile="process-smoke",
            game_version=None,
            executable_sha256=None,
            baseline_contract_id=None,
            mod_descriptor_sha256=None,
            mod_tree_sha256=None,
            git_head="d" * 40,
            git_dirty=False,
            runner_commit="e" * 40,
            profile_hash="f" * 64,
            rules_hash="g" * 64,
            started_at="s",
            ended_at="e",
            durations={},
            executable_basename=None,
            sanitized_argv=[],
            markers=[],
            exit_code=None,
            terminated_by_runner=False,
            log_diffs=[],
            result=gt.SessionResult(verdict="PASS", reasons=[]),
            registrable=True,
        )
        self.assertTrue(gt.report_files_valid(report, gt.render_markdown(report)))


if __name__ == "__main__":
    unittest.main()
