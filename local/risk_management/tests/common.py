from odoo.tests import common
import logging

_logger = logging.getLogger(__name__)


class TestProcessCases(common.TransactionCase):
    def setUp(self):
        super(TestProcessCases, self).setUp()

        # Create users
        self.proc_manager = self.env['res.users'].create({
            'company_id': self.env.ref("base.main_company").id,
            'name': "Process Manager",
            'login': "proc_mgr",
            'email': "proc.manager@yourcompany.com",
            'groups_id': [(6, 0, [self.ref('risk_management.group_manager')])]
        })
        self.risk_manager = self.env['res.users'].create({
            'company_id': self.env.ref("base.main_company").id,
            'name': "Risk Manager",
            'login': "risk_mgr",
            'email': "risk.manager@yourcompany.com",
            'groups_id': [(6, 0, [self.env.ref('risk_management.group_risk_manager').id])]
        })
        self.risk_user_1 = self.env['res.users'].create({
            'company_id': self.env.ref("base.main_company").id,
            'name': "Risk User 1",
            'login': "risk_user1",
            'email': "risk.user1@yourcompany.com",
            'groups_id': [(6, 0, [self.env.ref('risk_management.group_risk_user').id])]
        })
        self.risk_manager = self.env['res.users'].create({
            'company_id': self.env.ref("base.main_company").id,
            'name': "Risk User 2",
            'login': "risk_user2",
            'email': "risk.user2@yourcompany.com",
            'groups_id': [(6, 0, [self.env.ref('risk_management.group_risk_user').id])]
        })

        # get business processes
        proc = self.env['risk_management.business_process']
        self.sales = proc.browse(self.ref('risk_management.sales_process'))
        self.delivery = proc.browse(self.ref('risk_management.delivery_process'))
        self.hiring = proc.browse(self.ref('risk_management.hiring_process'))
        self.accounting = proc.browse(self.ref('risk_management.accounting_process'))
        self.fin = proc.browse(self.ref('risk_management.finance_management_process'))


class TestProcessIOCases(TestProcessCases):
    def setUp(self):
        super(TestProcessIOCases, self).setUp()

        # get process IO
        self.quote_request_id = self.ref('risk_management.quote_req_io')
        self.purchase_order_id = self.ref('risk_management.purchase_order_io')
        self.customer_invoice_id = self.ref('risk_management.customer_invoice_io')
        self.delivery_note_id = self.ref('risk_management.delivery_form_io')
