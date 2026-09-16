from __future__ import annotations

import unittest
from pathlib import Path
from scripts.validate_vault import Document, check_dates


class DateContractTests(unittest.TestCase):
    def findings(self, fields, relative='06 实验/example.md', template_mode=False):
        document = Document(Path(relative), relative, [], fields, 0)
        findings = []
        check_dates({relative: document}, findings, template_mode)
        return {item.code for item in findings}

    def test_cross_quarter_plan_and_legacy_review_are_valid(self):
        self.assertEqual(self.findings({
            'as_of': '2030-09-25', 'scope_start': '2030-09-23',
            'scope_end': '2030-10-06', 'result_review_date': '2030-09-30',
            'started_on': '2030-09-24',
        }), set())

    def test_invalid_calendar_dates_and_reversed_ranges(self):
        for value in ['2030-02-29', '2030-13-01', 'tomorrow', '20300924']:
            with self.subTest(value=value):
                self.assertIn('DATE_INVALID', self.findings({'as_of': value}))
        self.assertIn('DATE_RANGE_REVERSED', self.findings({
            'scope_start': '2030-10-06', 'scope_end': '2030-09-23'}))

    def test_review_aliases_must_agree(self):
        self.assertEqual(self.findings({
            'review_due': '2030-09-30', 'result_review_date': '2030-09-30'}), set())
        self.assertIn('REVIEW_DATE_CONFLICT', self.findings({
            'review_due': '2030-09-30', 'result_review_date': '2030-10-01'}))

    def test_actual_start_cannot_be_a_future_plan(self):
        self.assertIn('START_AFTER_AS_OF', self.findings({
            'as_of': '2030-09-23', 'started_on': '2030-09-24'}))
        self.assertEqual(self.findings({'started_on': '', 'review_due': ''}), set())

    def test_placeholders_only_allowed_in_templates(self):
        self.assertEqual(self.findings({'as_of': '{{date:YYYY-MM-DD}}'},
                                       relative='90 模板/实验记录.md'), set())
        self.assertEqual(self.findings({'as_of': '__INIT_DATE__'}, template_mode=True), set())
        self.assertIn('DATE_INVALID', self.findings({'as_of': '__INIT_DATE__'}))
        self.assertIn('DATE_INVALID', self.findings({'as_of': '{{date:YYYY-MM-DD}}'}))


if __name__ == '__main__':
    unittest.main()
