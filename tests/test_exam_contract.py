"""Regression tests for the public exam-generator contract."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hoeren import blueprint, telegram  # noqa: E402
from hoeren.validate import check_part  # noqa: E402


class ExamContractTest(unittest.TestCase):
    def setUp(self):
        self.exam_dir = ROOT / "exams" / "2026-09-21-264053"
        self.exam = json.loads((self.exam_dir / "exam.json").read_text())

    def test_fixture_satisfies_its_blueprint(self):
        for part in self.exam["parts"].values():
            errors, _warnings = check_part(part, self.exam["blueprint"])
            self.assertEqual([], errors, f"Teil {part['part']}")

    def test_manifest_has_one_delivery_post_per_part(self):
        manifest = telegram.build(self.exam, self.exam_dir)
        self.assertEqual(self.exam["id"], manifest["exam_id"])
        self.assertEqual(["teil1", "teil2", "teil3", "teil4"],
                         [post["id"] for post in manifest["posts"]])
        self.assertEqual(["sendMediaGroup", "sendAudio", "sendAudio", "sendAudio"],
                         [post["method"] for post in manifest["posts"]])

    def test_blueprint_is_repeatable_for_a_seed(self):
        self.assertEqual(blueprint.make(741852), blueprint.make(741852))


if __name__ == "__main__":
    unittest.main()
