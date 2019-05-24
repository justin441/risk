from odoo import models, fields, api


class RiskClass(models.Model):
    _name = 'risk_management.risk_class'

    name = fields.Char(translate=True)
    risk_ids = fields.One2many(comodel_name='risk_management.risk', inverse_name='risk_class_id', string='Risks')


class Risk(models.Model):
    _name = 'risk_management.risk'

    risk_class_id = fields.Many2one(comodel_name='risk_management.risk_class', string='Category')
    short_name = fields.Char(translate=True)
    name = fields.Char(translate=True, index=True)
    description = fields.Html(translate=True, string='Description')
    cause = fields.Html(Translate=True, string='Cause')
    consequence = fields.Html(translate=True, )
    control = fields.Text(translate=True, string='Control / Monitoring')
    note = fields.Text(translate=True, string='Note')


class RiskCriteria(models.Model):
    _name ='risk_management.risk_criteria'

    DETECTABILTY_SELECTION = (
        (1, 'Continuous'),
        (2, 'High'),
        (3, 'Average'),
        (4, 'Low'),
        (5, 'Minimal')
    )
    OCCURRENCE_SELECTION = (
        (1, 'Almost impossible'),
        (2, 'Unlikely'),
        (3, 'Probable'),
        (4,'Very probable'),
        (5, 'Almost certain')
    )
    SEVERETY_SELECTION = (
        (1, 'Low'),
        (2, 'Average'),
        (3, 'High'),
        (4, 'Very High'),
        (5, 'Maximal')

    )
    detectability = fields.Selection(selection=DETECTABILTY_SELECTION, string='Detectability', default=2,
                                     help='What is the ability of the company to detect'
                                     ' a failure if it were to occur?')
    occurrence = fields.Selection(selection=OCCURRENCE_SELECTION, default=2, string='Occurrence',
                                  help='How likely is it for a particular failure to occur?')
    severity = fields.Selection(selection=SEVERETY_SELECTION, default=2, string='Severity',
                                help='If a failure were to occur, what effect would that failure have on company resources?')
    comment = fields.Html(string='Comments')
    value_threat = fields.Integer(string="Value if threat", compute='_compute_value_threat')
    value_opportunity = fields.Integer(string="Value if opportunity", compute='_compute_value_opportunity')

    @api.depends('detectability', 'occurrence', 'severity')
    def _compute_value_threat(self):
         """
        if the risk is a threat, return the product of the scores
        """
        for rec in self:
            rec.value_threat = rec.detectability * rec.occurrence * rec.severity
    
      @api.depends('detectability', 'occurrence', 'severity')
    def _compute_value_opportunity(self):
        """
        if the risk is an opportunity, invert the value of self.detectability before calculating the product of the scores
        """
        for rec in self:
            opp_detectability_selection = dict((x, y) for x, y in zip(range(1, len(self.DETECTABILTY_SELECTION) + 1), 
                                                                      range(len(self.DETECTABILTY_SELECTION), 0, -1)))
            detectability_opp = opp_detectability_selection.get(rec.detectability)
            rec.value_opportunity = rec.detectability * detectability_opp * rec.severity

    

