from .common import TestRiskReportCases
from odoo import exceptions
import logging

_logger = logging.getLogger(__name__)


class TestBusinessRisk(TestRiskReportCases):
    def setUp(self):
        super(TestBusinessRisk, self).setUp()

    def test_compute_priority(self):
        """Tests the determination of the priority of the risk"""
        br = self.env['risk_management.business_risk']
        risk = br.create({
            'risk_info_id': self.risk_info3.id
        })
        risks = br.search([]).sorted('create_date')
        sorted_risks = risks.sorted(lambda rec: rec.latest_level_value - rec.threshold_value)
        self.assertEqual(list(risks).index(self.business_risk1), 0)
        self.assertEqual(list(risks).index(self.business_risk2), 1)
        self.assertEqual(list(risks).index(risk), 2)
        self.assertEqual(list(sorted_risks).index(self.business_risk1), 0)
        self.assertEqual(list(sorted_risks).index(self.business_risk2), 1)
        self.assertEqual(list(sorted_risks).index(risk), 2)
        self.assertEqual(risk.priority, 3)
        self.assertEqual(self.business_risk1.priority, 1)
        self.assertEqual(self.business_risk2.priority, 2)
        self.business_risk1.write({
            'detectability': '3',
            'occurrence': '4',
            'severity': '3'
        })
        self.assertEqual(self.business_risk1.priority, 3)
        self.assertEqual(self.business_risk2.priority, 1)
        self.assertEqual(risk.priority, 2)

    def test_compute_stage(self):
        """Tests the evolution of the risk through the different stages of risk management"""
        self.assertEqual(self.business_risk1.state, '1')
        self.business_risk1.is_confirmed = True
        self.assertEqual(self.business_risk1.state, '2')
        self.business_risk1.write({
            'detectability': '3',
            'occurrence': '4',
            'severity': '3'
        })
        self.business_risk1.write({
            'evaluation_ids': [(0, False, {
                'detectability': '3',
                'occurrence': '3',
                'severity': '2'
            })]
        })
        self.assertEqual(self.business_risk1.state, '3')
        self.business_risk1.evaluation_ids[0].is_valid = True
        self.assertEqual(self.business_risk1.state, '4')
        self.business_risk1.write({
            'evaluation_ids': [(0, False, {
                'detectability': '3',
                'occurrence': '3',
                'severity': '5'
            })]
        })
        self.business_risk1.evaluation_ids[0].is_valid = True
        self.assertEqual(self.business_risk1.latest_level_value, 45)
        self.assertTrue(bool(self.business_risk1.treatment_task_id))

        task1 = self.env['project.task'].create({
            'name': 'Treatment task 1',
            'project_id': self.business_risk1.treatment_project_id.id,
            'parent_id': self.business_risk1.treatment_task_id.id
        })
        self.assertEqual(self.business_risk1.state, '5')
        task1.stage_id = self.ref('risk_management.risk_treatment_stage_3')
        self.assertEqual(self.business_risk1.state, '6')

    def test_compute_status(self):
        """Tests the determination of the risk status"""
        self.assertEqual(self.business_risk1.status, 'U')
        self.business_risk1.write({
            'detectability': '3',
            'occurrence': '4',
            'severity': '3'
        })
        self.business_risk1.write({
            'evaluation_ids': [(0, False, {
                'detectability': '3',
                'occurrence': '3',
                'severity': '2'
            })]
        })
        self.assertEqual(self.business_risk1.status, 'A')
        self.business_risk1.write({
            'evaluation_ids': [(0, False, {
                'detectability': '3',
                'occurrence': '3',
                'severity': '5'
            })]
        })
        self.assertEqual(self.business_risk1.status, 'N')
        treatment_task = self.business_risk1.treatment_task_id
        self.assertTrue(bool(treatment_task))
        self.business_risk1.write({
            'detectability': '5',
            'occurrence': '4',
            'severity': '3'
        })
        self.assertEqual(self.business_risk1.status, 'A')
        self.assertFalse(self.business_risk1.treatment_task_id.active)

    def test_compute_latest_eval(self):
        self.business_risk1.write({
            'evaluation_ids': [(0, False, {
                'detectability': '1',
                'occurrence': '3',
                'severity': '5'
            })]
        })

        self.business_risk2.write({
            'evaluation_ids': [(0, False, {
                'detectability': '1',
                'occurrence': '3',
                'severity': '5'
            })]
        })
        # risk level of a threat
        self.assertEqual(self.business_risk1.latest_level_value, 15)
        # risk level of an opportunity
        self.assertEqual(self.business_risk2.latest_level_value, 75)

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
