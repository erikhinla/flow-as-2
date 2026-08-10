import importlib.util
import json
import os
import pathlib
import tempfile
import unittest


os.environ["INTAKE_DIR"] = tempfile.mkdtemp(prefix="flow-diagnostic-test-")
APP_PATH = pathlib.Path(__file__).with_name("app.py")
SPEC = importlib.util.spec_from_file_location("flow_gateway_app", APP_PATH)
APP = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(APP)


class DiagnosticCopyTests(unittest.TestCase):
    def make_subject(self, diagnostic_type: str):
        dimensions = (
            ["clarity", "attention", "folders", "markdowns"]
            if diagnostic_type == "tbtx"
            else ["offer", "audience", "capture", "qualification"]
        )
        return APP.DiagnosticSub(
            name="Test Person",
            email="test@example.com",
            company="Test Company",
            industry="Consulting / Professional Services",
            diagnostic_type=diagnostic_type,
            answers=[
                APP.DiagnosticAnswer(
                    question_id=f"question-{index}",
                    answer_value=3,
                    dimension=dimension,
                )
                for index, dimension in enumerate(dimensions)
            ],
        )

    def report_for(self, diagnostic_type: str):
        subject = self.make_subject(diagnostic_type)
        scores = APP.score_dimensions(subject.answers, diagnostic_type)
        return APP.build_report(subject, "Stalled", scores)

    def test_personal_and_business_routes_are_distinct(self):
        personal = APP.get_config("tbtx")
        business = APP.get_config("bizbuilders")

        self.assertEqual(personal["cta"], "Get the Fog-Lift Kit")
        self.assertIn("foglift", personal["route_to"])
        self.assertEqual(business["cta"], "Get My BizBuilders Roadmap")
        self.assertIn("bizbuilders.ai/roadmap", business["route_to"])
        self.assertNotIn("bizbot", business["route_to"].lower())

    def test_public_results_do_not_expose_internal_language(self):
        public_copy = json.dumps(
            {
                "personal_config": APP.get_config("tbtx"),
                "business_config": APP.get_config("bizbuilders"),
                "personal_report": self.report_for("tbtx"),
                "business_report": self.report_for("bizbuilders"),
            }
        ).lower()
        forbidden = (
            "highest leverage",
            "execution system",
            "quad-keystone",
            "quad keystone",
            "recommended infrastructure",
            "phased plan",
            "next cta",
            "operational readiness",
        )

        for phrase in forbidden:
            self.assertNotIn(phrase, public_copy)

    def test_results_have_different_language_and_actions(self):
        personal = self.report_for("tbtx")
        business = self.report_for("bizbuilders")

        self.assertNotEqual(personal["headline"], business["headline"])
        self.assertNotEqual(personal["first_moves"], business["first_moves"])
        self.assertNotEqual(personal["action_plan"], business["action_plan"])
        self.assertIn("Fog-Lift", personal["next_step"])
        self.assertIn("BizBuilders", business["next_step"])


if __name__ == "__main__":
    unittest.main()
