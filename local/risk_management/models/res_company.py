from odoo import models, api


class Company(models.Model):
    _inherit = 'res.company'

    @api.model
    def create(self, vals):
        company = super(Company, self).create(vals)
        business_process = self.env['risk_management.business_process']
        business_process.create(
            {
                'name': 'Business Process Zero',
                'description': """
                <p>This process represents the overall process of the company's business, to be used for activities, 
                methods or risks in the absence of more specific processes.</p>
                """,
                'company_id': company.id
            }
        )
        return company
