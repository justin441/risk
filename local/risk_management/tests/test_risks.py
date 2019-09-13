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
        """- If a risk that already exist in the database is reported, two things: if it is active, return an error,
        otherwise reactivate the risk
           - on risk creation or reactivation add a risk verification activity to do
        """

        self.assertTrue(self.business_risk1.active)
        with self.assertRaises(exceptions.UserError) as cm:
            self.env['risk_management.business_risk'].create({
                'risk_info_id': self.business_risk1.risk_info_id.id,
            })
        self.assertIsInstance(cm.exception, exceptions.UserError)

        self.business_risk1.active = False
        self.assertFalse(self.business_risk1.active)

        self.env['risk_management.business_risk'].create({
            'risk_info_id': self.risk_info1.id
        })
        self.assertTrue(self.business_risk1.active)
        self.assertTrue(bool(self.business_risk1.activity_ids))

    def test_write(self):
        pass


class TestSecurity(TestRiskReportCases):
    def setUp(self):
        super(TestSecurity, self).setUp()

    def test_report_risks_rights(self):
        br_risk_usr = self.env['risk_management.business_risk'].sudo(self.risk_user_2)
        risk_info_usr = self.env['risk_management.risk.info'].sudo(self.risk_user_1)

        # every employee can report risk
        self.assertTrue(bool(risk_info_usr.create({'risk_category_id': self.ref('risk_management.risk_cat_1'),
                                                   'name': 'Risk of rain',
                                                   'description': 'It might rain this week'})))
        self.assertTrue(bool(br_risk_usr.create({'risk_info_id': self.risk_info3.id})))

    def test_write_unlink_risk(self):

        # risk info creation
        risk_info_usr = self.env['risk_management.risk.info'].sudo(self.risk_user_1)
        risk_info_1 = risk_info_usr.create({'risk_category_id': self.ref('risk_management.risk_cat_1'),
                                            'name': 'Risk of rain',
                                            'description': 'It might rain this week'})
        risk_info_2 = risk_info_usr.create({'risk_category_id': self.ref('risk_management.risk_cat_1'),
                                            'name': 'Risk of Fraud',
                                            'description': 'Some one might steal a company asset'})

        # business risks creation
        br_risk_usr = self.env['risk_management.business_risk'].sudo(self.risk_user_2)
        risk1 = br_risk_usr.create({'risk_info_id': risk_info_1.id})
        risk2 = br_risk_usr.create({'risk_info_id': self.risk_info3.id, 'risk_type': 'O'})

        # users can modify or unlink the risks they have reported as long as it has not been confirmed
        self.assertTrue(risk1.sudo(self.risk_user_2).write({'risk_type': 'O'}))
        self.assertTrue(risk_info_1.sudo(self.risk_user_1).write({'description': 'It might rain today'}))
        self.assertTrue(risk1.sudo(self.risk_user_2).unlink())
        self.assertTrue(risk_info_1.sudo(self.risk_user_1).unlink())

        # users can only delete modify or delete the risk the have submitted
        with self.assertRaises(exceptions.AccessError):
            risk_info_2.sudo(self.risk_user_2).unlink()

        with self.assertRaises(exceptions.AccessError):
            risk2.sudo(self.risk_user_1).unlink()

        # if a risk is confirmed or a risk info is modified the user who created them can no longer modify them
        risk2.sudo(self.risk_manager).write({'is_confirmed': True})
        risk_info_2.sudo(self.risk_manager).write({'description': 'Some one might defraud the company'})

        with self.assertRaises(exceptions.AccessError):
            risk2.sudo(self.risk_user_2).unlink()
            risk_info_2.sudo(self.risk_user_1).unlink()
