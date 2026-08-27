import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.dl.rules import validate_dl_rules
from modules.permit.rules import validate_permit_rules
from modules.decision.scorer import compute_score


class TestWave2Documents(unittest.TestCase):
    def test_valid_driving_licence(self):
        dl_fields = {
            "dl_number": "DL1420110012345",
            "name": "SHASHWAT KHANDELWAL",
            "dob": "12/05/1990",
            "issue_date": "10/10/2011",
            "expiry_date": "09/10/2035",
            "vehicle_classes": ["LMV", "MCWG"],
        }
        rules = validate_dl_rules(dl_fields)
        self.assertTrue(rules["valid"])
        self.assertTrue(rules["format_valid"])
        self.assertFalse(rules["expired"])
        self.assertTrue(rules["age_valid"])

        score_res = compute_score({"dl_rules": rules}, doc_type="DRIVING_LICENCE")
        self.assertEqual(score_res["status"], "CLEAR")
        self.assertEqual(score_res["overall_score"], 0.0)

    def test_expired_driving_licence(self):
        dl_fields = {
            "dl_number": "MH0220050012345",
            "name": "RAMESH KUMAR",
            "dob": "15/08/1980",
            "issue_date": "10/10/2005",
            "expiry_date": "01/01/2020",
            "vehicle_classes": ["LMV"],
        }
        rules = validate_dl_rules(dl_fields)
        self.assertFalse(rules["valid"])
        self.assertTrue(rules["expired"])

        score_res = compute_score({"dl_rules": rules, "expiry_valid": {"score": 0.0}}, doc_type="DRIVING_LICENCE")
        self.assertIn(score_res["status"], ("REVIEW", "FLAGGED"))
        self.assertGreaterEqual(score_res["overall_score"], 30.0)

    def test_valid_border_permit(self):
        permit_fields = {
            "permit_number": "ILP-2026-84920",
            "holder_name": "SHASHWAT KHANDELWAL",
            "border_gate": "POST_A",
            "valid_from": "01/01/2026",
            "valid_until": "01/01/2028",
            "associated_id": "L8406789",
        }
        rules = validate_permit_rules(permit_fields, presented_id="L8406789")
        self.assertTrue(rules["valid"])
        self.assertTrue(rules["bound"])

        score_res = compute_score({"permit_rules": rules}, doc_type="PERMIT")
        self.assertEqual(score_res["status"], "CLEAR")

    def test_mismatched_border_permit(self):
        permit_fields = {
            "permit_number": "ILP-2026-84920",
            "holder_name": "SHASHWAT KHANDELWAL",
            "border_gate": "POST_A",
            "valid_from": "01/01/2026",
            "valid_until": "01/01/2028",
            "associated_id": "L8406789",
        }
        rules = validate_permit_rules(permit_fields, presented_id="Z9999999")
        self.assertFalse(rules["valid"])
        self.assertFalse(rules["bound"])

        score_res = compute_score({"permit_rules": rules}, doc_type="PERMIT")
        self.assertEqual(score_res["status"], "FLAGGED")
        self.assertGreaterEqual(score_res["overall_score"], 70.0)


if __name__ == "__main__":
    unittest.main()
