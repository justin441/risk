from odoo import models, fields, api


class RiskClass(models.Model):
    _name = 'risk_management.risk_class'

    name = fields.Char(translate=True)


class BaseRisk(models.AbstractModel):
    _name = 'risk_management.base_risk'

    short_name = fields.Char(translate=True)
    name = fields.Char(translate=True, index=True)
