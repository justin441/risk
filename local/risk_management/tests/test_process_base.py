from odoo.tests import common
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
        customer = self.env['res.partner.category'].browse(self.ref('risk_management.process_external_customer'))
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


class TestBusinessProcessIO(TestProcessIOCases):
    def setUp(self):
        super(TestBusinessProcessIO, self).setUp()
