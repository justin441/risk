from .common import TestProcessCases, TestProcessIOCases
from odoo import exceptions


class TestBusinessProcess(TestProcessCases):
    def setUp(self):
        super(TestBusinessProcess, self).setUp()

    def test_check_output_not_in_input(self):

        with self.assertRaises(exceptions.ValidationError) as cm:
            self.sales.write({
                'input_data_ids': [(4, self.ref('risk_management.customer_invoice_io'))]
            })
        self.assertIsInstance(cm.exception, exceptions.ValidationError)

    def test_get_provider_processes(self):
        self.assertIn(self.delivery, self.sales.get_provider_processes())
        self.assertIn(self.accounting, self.sales.get_provider_processes())
        self.assertNotIn(self.fin, self.accounting.get_provider_processes())

    def test_get_customers(self):
        customer = self.env['res.partner.category'].browse(self.ref('risk_management.process_partner_cat_customer'))
        self.assertIn(customer, self.sales.get_customers()['external'])
        self.assertIn(self.sales, self.delivery.get_customers()['internal'])
        self.assertIn(self.delivery, self.accounting.get_customers()['internal'])
        self.assertNotIn(self.accounting, self.fin.get_customers()['internal'])

    def test_compute_is_core(self):
        self.assertTrue(self.sales.is_core)
        self.assertTrue(self.delivery.is_core)
        self.assertTrue(self.accounting.is_core)
        self.assertFalse(self.fin.is_core)
        sales_journal_id = self.ref('risk_management.sales_journal_io')
        # remove the sales journal from the accounting process output data
        self.accounting.write({
            'output_data_ids': [(2, sales_journal_id)]
        })
        self.assertFalse(self.accounting.is_core)

    def test_compute_sequence(self):
        self.assertEqual(self.sales.sequence, 10)
        self.assertEqual(self.delivery.sequence, 11)
        self.assertEqual(self.accounting.sequence, 11)
        self.assertEqual(self.hiring.sequence, 100)
        self.assertEqual(self.fin.sequence, 250)
        self.env['risk_management.business_process.input_output'].create({
            'name': 'Balance Sheet',
            'description': '''
            <p>reports on a company's assets, liabilities, and ownership equity at a given point in time.</p>
            ''',
            'business_process_id': self.accounting.id,
            'user_process_ids': [(4, self.fin.id)]
        })
        self.assertEqual(self.accounting.sequence, 11)
        # add 2 output to finance management process
        self.env['risk_management.business_process.input_output'].create({
            'name': 'Reconciled Budget Statement',
            'description': '''
                   <p>Reconciled budget of all the company's division.</p>
                   ''',
            'business_process_id': self.fin.id})
        self.env['risk_management.business_process.input_output'].create({
            'name': 'Tax Declaration',
            'description': '''
                           <p>Tax Declaration.</p>
                           ''',
            'business_process_id': self.fin.id,
            'dest_partner_ids': [(4, self.ref('risk_management.process_partner_cat_gov'))]
        })
        self.assertEqual(self.fin.sequence, 150)

        # a project management process with 1 output
        pmp = self.env['risk_management.business_process'].browse(self.ref(
            'risk_management.project_charter_dev_process'))
        self.assertEqual(pmp.sequence, 1100)

    def test_write_color(self):
        """When a process color is changed, every process with the same type has their color changed to the same
        color. """
        self.sales.write({'color': 6})
        self.assertEqual(self.hiring.color, 6)
        # if one or more processes color is the same as the color being written, these processes color is changed to
        # a random color
        self.assertEqual(self.fin.color, 5)  # default color code for processes of type management: 5
        self.hiring.write({'color': 5})  # set a operational process' color code to 5
        self.assertNotEqual(self.fin.color, 5)

    def test_create_color(self):
        """On creation process should get the same color code as processes of the same type"""
        self.assertEqual(self.fin.color, 5)
        self.assertEqual(self.sales.color, 1)
        self.fin.write({'color': 6})  # all management processes color code set to 6
        self.sales.write({'color': 3})  # all operations color code set to 3
        proc = self.env['risk_management.business_process']
        procurement_mgt_proc = proc.create({
            'name': 'Procurement Management',
            'process_type': 'M',
        })
        procurement_proc = proc.create({'name': 'Purchasing process'})

        self.assertEqual(procurement_mgt_proc.color, 6)
        self.assertEqual(procurement_proc.color, 3)


class TestBusinessProcessIO(TestProcessIOCases):
    def setUp(self):
        super(TestBusinessProcessIO, self).setUp()

    def test_compute_origin(self):
        partner_cat = self.env['res.partner.category']
        proc = self.env['risk_management.business_process']
        self.assertEqual(self.quote_request.origin_id, partner_cat.browse(
            self.ref('risk_management.process_partner_cat_customer')))
        self.assertEqual(self.customer_invoice.origin_id, self.sales)
        self.assertEqual(self.delivery_note.origin_id, self.delivery)
        self.assertEqual(self.project_charter.origin_id, proc.browse(
            self.ref('risk_management.project_charter_dev_process')))

    def test_compute_is_customer_voice(self):
        self.assertTrue(self.quote_request.is_customer_voice)
        self.assertTrue(self.customer_invoice.is_customer_voice)
        self.assertTrue(self.delivery_note.is_customer_voice)
        self.assertFalse(self.project_charter.is_customer_voice)

    def test_constraints(self):
        with self.assertRaises(exceptions.ValidationError) as cm:
            self.quote_request.write({'ref_input_ids': [(4, self.customer_invoice.id)]})
        self.assertIsInstance(cm.exception, exceptions.ValidationError)

        with self.assertRaises(exceptions.ValidationError) as cm:
            self.quote_request.write({'dest_partner_ids': [(4, self.ref('risk_management.process_partner_cat_gov'))]})
        self.assertIsInstance(cm.exception, exceptions.ValidationError)

        with self.assertRaises(exceptions.ValidationError) as cm:
            self.delivery_note.write({'user_process_ids': [(4, self.sales.id)]})
        self.assertIsInstance(cm.exception, exceptions.ValidationError)

