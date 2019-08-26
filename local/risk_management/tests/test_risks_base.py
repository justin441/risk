
from .common import TestRiskReportCases
from odoo import exceptions


class TestBusinessRisk(TestRiskReportCases):
    def setUp(self):
        super(TestBusinessRisk, self).setUp()

    def test_compute_priority(self):
        br = self.env['risk_management.business_risk']
        risk = br.create({
            'risk_info_id': self.risk_info3.id
        })
        self.assertEqual(risk.priority, 3)
        self.assertEqual(self.business_risk2.priority, 2)
        self.assertEqual(self.business_risk1.priority, 1)
        self.business_risk1.write({
            'detectability': '3',
            'occurrence': '4',
            'severity': '3'
        })
        self.assertEqual(self.business_risk1.priority, 3)

    def test_compute_stage(self):
        pass

    def test_compute_status(self):
        pass

    def test_compute_latest_eval(self):
        pass

    def test_create(self):
        pass

    def test_write(self):
        pass


class TestRiskEvaluation(TestRiskReportCases):
    def setUp(self):
        super(TestRiskEvaluation, self).setUp()

    def test_create(self):
        pass

    def test_write(self):
        pass
