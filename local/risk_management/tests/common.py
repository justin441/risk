from odoo.tests import common


class TestProcessCases(common.TransactionCase):
    def Setup(self):
        super(TestProcessCases, self).setUp()

        # Create users
        self.proc_manager = self.env['res.users'].create({
            'company_id': self.env.ref("base.main_company").id,
            'name': "Process Manager",
            'login': "pmgr",
            'email': "proc.manager@yourcompany.com",
            'groups_id': [(6, 0, [self.ref('risk_management.manager')])]
        })
        self.risk_manager = self.env['res.users'].create({
            'company_id': self.env.ref("base.main_company").id,
            'name': "Risk Manager",
            'login': "rmgr",
            'email': "risk.manager@yourcompany.com",
            'groups_id': [(6, 0, [self.env.ref('risk_management.group_risk_manager').id])]
        })
        self.risk_user_1 = self.env['res.users'].create({
            'company_id': self.env.ref("base.main_company").id,
            'name': "Risk User 1",
            'login': "r_user1",
            'email': "risk.user1@yourcompany.com",
            'groups_id': [(6, 0, [self.env.ref('risk_management.group_risk_user').id])]
        })
        self.risk_manager = self.env['res.users'].create({
            'company_id': self.env.ref("base.main_company").id,
            'name': "Risk User 2",
            'login': "r_user2",
            'email': "risk.user2@yourcompany.com",
            'groups_id': [(6, 0, [self.env.ref('risk_management.group_risk_user').id])]
        })

        # get business processes
        self.sales_process = self.ref('risk_management.sales_process')
        self.delivery_process = self.ref('risk_management.delivery_process')
        self.hiring_process = self.ref('risk_management.hiring_process')
        self.accounting_process = self.ref('risk_management.accounting_process')
        self.finance_management = self.ref('risk_management.finance_management_process')


class TestProcessIOCases(TestProcessCases):
    def Setup(self):
        super(TestProcessIOCases, self).setUp()

        # get process IO
        self.quote_request = self.ref('risk_management.quote_req_io')
        self.purchase_order = self.ref('risk_management.purchase_order_io')
        self.customer_invoice = self.ref('risk_management.customer_invoice_io')
        self.delivery_note = self.ref('risk_management.delivery_form_io')
