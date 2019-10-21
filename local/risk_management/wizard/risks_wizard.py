import datetime
from odoo import models, fields, api, _
from ..models.risks import RISK_EVALUATION_DEFAULT_MAX_AGE


class BaseEvaluationWizard(models.AbstractModel):
    _name = 'risk_management.base_eval_wizard'

    @api.model
    def _get_detectability(self):
        levels = [_('Continuous'), _('High'), _('Average'), _('Low'), _('Minimal')]
        return [(str(x), y) for x, y in enumerate(levels, 1)]

    @api.model
    def _get_occurrence(self):
        levels = [_('Almost impossible'), _('Unlikely'), _('Probable'), _('Very probable'), _('Almost certain')]
        return [(str(x), y) for x, y in enumerate(levels, 1)]

    @api.model
    def _get_severity(self):
        levels = [_('Low'), _('Average'), _('High'), _('Very High'), _('Maximal')]
        return [(str(x), y) for x, y in enumerate(levels, 1)]

    def default_criteria(self):
        # returns a dict of containing the criteria values of the risk being evaluated
        risk_id = self.env.context.get('default_risk_id', False)
        risk_model = self.env.context.get('risk_model', False)
        if risk_id and risk_model:
            risk = self.env[risk_model].browse(risk_id)
            if risk.exists():
                return {'detectability': risk.detectability,
                        'occurrence': risk.occurrence,
                        'severity': risk.severity}
        return {}

    detectability = fields.Selection(selection=_get_detectability, string='Detectability',
                                     default=lambda self: self.default_criteria().get('detectability', False),
                                     help='What is the ability of the company to detect'
                                          ' this failure (or gain) if it were to occur?')
    occurrence = fields.Selection(selection=_get_occurrence, string='Occurrence',
                                  default=lambda self: self.default_criteria().get('occurrence', False),
                                  help='How likely is it for this failure (or gain) to occur?')
    severity = fields.Selection(selection=_get_severity, string='Impact',
                                default=lambda self: self.default_criteria().get('severity', False),
                                help='If this failure (or gain) were to occur, what is the level of the impact it '
                                     'would have on company assets?')

    @api.multi
    def set_value(self):
        for wizard in self:
            detectability = wizard.detectability
            occurrence = wizard.occurrence
            severity = wizard.severity
            comment = wizard.comment
            self.risk_id.write({
                'detectability': detectability,
                'occurrence': occurrence,
                'severity': severity,
                'comment': comment
            })

    @api.onchange('detectability', 'occurrence', 'severity')
    def _onchange_criteria(self):
        if self.risk_id.risk_type == 'T':
            self.threshold_value = int(self.detectability) * int(self.occurrence) * int(self.severity)
        elif self.risk_id.risk_type == 'O':
            inv_detectability_score = [str(x) for x in range(1, 6)]
            opp_detectability_dict = dict((x, y) for x, y in zip(inv_detectability_score, range(5, 0, -1)))
            detectability_opp = opp_detectability_dict.get(self.detectability, False)
            self.threshold_value = detectability_opp * int(self.occurrence) * int(self.severity)


class BaseRiskLevelWizard(models.AbstractModel):
    _name = 'risk_management.base_risk_level_wizard'
    _inherit = ['risk_management.base_eval_wizard']

    def _compute_default_review_date(self):
        date = fields.Date.from_string(fields.Date.context_today(self))
        default_review_date = date + datetime.timedelta(days=RISK_EVALUATION_DEFAULT_MAX_AGE)
        return fields.Date.to_string(default_review_date)

    def default_criteria(self):
        # returns a dict of the  latest evaluation's criteria of the risk being evaluated
        risk_id = self.env.context.get('default_risk_id', False)
        risk_model = self.env.context.get('risk_model', False)
        if risk_id and risk_model:
            risk = self.env[risk_model].browse(risk_id)
            if risk.exists() and risk.evaluation_ids.exists():
                latest_evaluation = risk.evaluation_ids.sorted()[0]
                return {
                    'detectability': latest_evaluation.detectability,
                    'occurrence': latest_evaluation.occurrence,
                    'severity': latest_evaluation.severity,
                }
        return {}

    review_date = fields.Date(string='Review Date', default=_compute_default_review_date)

    @api.multi
    def set_value(self):
        # Get risk evaluation model
        for wizard in self:
            review_date = wizard.review_date
            detectability = wizard.detectability
            occurrence = wizard.occurrence
            severity = wizard.severity
            comment = wizard.comment
            self.risk_id.write({
                'evaluation_ids': [(0, 0, {
                    'review_date': review_date,
                    'detectability': detectability,
                    'occurrence': occurrence,
                    'severity': severity,
                    'comment': comment,
                })]
            })

    @api.onchange('detectability', 'occurrence', 'severity')
    def _onchange_criteria(self):
        if self.risk_id.risk_type == 'T':
            self.latest_level = (int(self.detectability) or 1) * (int(self.occurrence) or 1) * (int(self.severity) or 1)
        elif self.risk_id.risk_type == 'O':
            inv_detectability_score = [str(x) for x in range(1, 6)]
            opp_detectability_dict = dict((x, y) for x, y in zip(inv_detectability_score, range(5, 0, -1)))
            detectability_opp = opp_detectability_dict.get(self.detectability, False)
            self.latest_level = detectability_opp * (int(self.occurrence) or 1) * (int(self.severity) or 1)

    @api.depends('risk_id')
    def _compute_latest_eval(self):
        for wizard in self:
            if wizard.risk_id.evaluation_ids:
                wizard.latest_eval = wizard.risk_id.evaluation_ids.sorted().exists()[0]


class BusinessRiskThresholdWizard(models.TransientModel):
    _name = 'risk_management.business_risk.set_threshold_wizard'
    _inherit = ['risk_management.base_eval_wizard']

    risk_id = fields.Many2one('risk_management.business_risk', string='Business Risk', required=True,
                              ondelete='cascade')
    threshold_value = fields.Integer('Current Threshold', related='risk_id.threshold_value')
    latest_level = fields.Integer('Current Level', related='risk_id.latest_level_value')
    comment = fields.Html(string='Comments', related='risk_id.comment')


class BusinessRiskEvalWizard(models.TransientModel):
    _name = 'risk_management.business_risk.eval_wizard'
    _inherit = ['risk_management.base_risk_level_wizard']

    risk_id = fields.Many2one('risk_management.business_risk', string='Business Risk', required=True,
                              ondelete='cascade')
    latest_eval = fields.Many2one('risk_management.business_risk.evaluation', compute='_compute_latest_eval')
    threshold_value = fields.Integer('Current Threshold', related='risk_id.threshold_value')
    latest_level = fields.Integer('Current Level', related='risk_id.latest_level_value')
    latest_level_date = fields.Date('Last evaluated on', related='risk_id.last_evaluate_date', readonly=True)
    comment = fields.Html(string='Comments', related='latest_eval.comment')


class RiskHelpWizard(models.TransientModel):
    _name = 'risk_management.risk.help_wizard'

    def _get_default_risk_info(self):
        risk_info_id = self.env.context.get('default_risk_info_id')
        if risk_info_id:
            risk_info = self.env['risk_management.risk.info'].browse(risk_info_id)
            return risk_info.exists()

    risk_info_id = fields.Many2one('risk_management.risk.info', default=_get_default_risk_info, required=True,
                                   ondelete='cascade')
    risk_info_control = fields.Html(translate=True, string='Steering / Monitoring', related='risk_info_id.control')
    risk_info_action = fields.Html(translate=True, string='Actions / Hedging policy', related='risk_info_id.action')

    @api.multi
    def write_changes(self):
        for wizard in self:
            control = wizard.risk_info_control
            action = wizard.risk_info_action
            wizard.risk_info_id.write({
                'control': control,
                'action': action
            })
