import datetime
from odoo import models, fields, api
from ..models.risks import RISK_EVALUATION_DEFAULT_MAX_AGE


class BaseRiskWizard(models.AbstractModel):
    _name = 'risk_management.base_risk_wizard'

    risk_type = fields.Selection(selection=(('T', 'Threat'), ('O', 'Opportunity')), string='Type', default='T',
                                 require=True)
    risk_info_id = fields.Many2one('risk_management.risk.info', string='Name', required=True, ondelete='cascade')
    risk_info_description = fields.Html(string='Description', readonly=True, related='risk_info_id.description')
    risk_info_cause = fields.Html(string='Cause', readonly=True, related='risk_info_id.cause')
    risk_info_consequence = fields.Html(string='Consequence', readonly=True, related='risk_info_id.consequence')
    report_date = fields.Date(string='Reported On', default=fields.Date.today)
    reported_by = fields.Many2one(comodel_name='res.users', string='Reported by', default=lambda self: self.env.user)

    @api.multi
    def record_risk(self):
        risk_model = self.env[self.risk_model]
        for wizard in self:
            risk_type = wizard.risk_type
            risk_info = wizard.risk_info_id.id
            process_id = wizard.process_id.id
            report_date = wizard.report_date
            reporter = wizard.reported_by.id
            # Search the database for an old risk report with the same type, the same infos and on the same process as
            # this one.
            old_report = risk_model.search([('risk_type', '=', risk_type),
                                            ('risk_info_id', '=', risk_info),
                                            ('process_id', '=', process_id),
                                            ('active', '=', False)])
            if old_report:
                # old report is inactive
                old_report.update_id_info(report_date=report_date, reporter=reporter)
            else:
                risk_model.create({
                    'risk_type': risk_type,
                    'risk_info_id': risk_info,
                    'process_id': process_id,
                    'report_date': report_date,
                    'reported_by': reporter
                })
        # reload business risks list
        return {
            'type': 'ir.actions.client', 'tag': 'reload',
            'params': self.env.ref('risk_management.view_business_risk_list')
        }


class BaseEvaluationWizard(models.AbstractModel):
    _name = 'risk_management.base_eval_wizard'

    @api.model
    def _get_detectability(self):
        levels = ['Continuous', 'High', 'Average', 'Low', 'Minimal']
        scores = [str(x) for x in range(1, 6)]
        return list(zip(scores, levels))

    @api.model
    def _get_occurrence(self):
        levels = ['Almost impossible', 'Unlikely', 'Probable', 'Very probable', 'Almost certain']
        scores = [str(x) for x in range(1, 6)]
        return list(zip(scores, levels))

    @api.model
    def _get_severity(self):
        levels = ['Low', 'Average', 'High', 'Very High', 'Maximal']
        scores = [str(x) for x in range(1, 6)]
        return list(zip(scores, levels))

    def _get_default_criteria(self):
        # return a dict of the risk criteria
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
                                     default=lambda self: self._get_default_criteria().get('detectability', '3'),
                                     required=True,
                                     help='What is the ability of the company to detect'
                                          ' this failure (or gain) if it were to occur?')
    occurrence = fields.Selection(selection=_get_occurrence, string='Occurrence',
                                  default=lambda self: self._get_default_criteria().get('occurrence', '3'),
                                  required=True,
                                  help='How likely is it for this failure (or gain) to occur?')
    severity = fields.Selection(selection=_get_severity, string='Impact',
                                default=lambda self: self._get_default_criteria().get('severity', '3'), required=True,
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
            detectability_opp = opp_detectability_dict.get(self.detectability)
            self.threshold_value = detectability_opp * int(self.occurrence) * int(self.severity)


class BaseRiskLevelWizard(models.AbstractModel):
    _name = 'risk_management.base_risk_level_wizard'
    _inherit = ['risk_management.base_eval_wizard']

    def _get_default_criteria(self):
        # returns a dict of the risk latest evaluation's criteria
        risk_id = self.env.context.get('default_risk_id', False)
        risk_model = self.env.context.get('risk_model', False)
        if risk_model and risk_id:
            risk = self.env[risk_model].browse(risk_id)
            if risk.exists() and risk.evaluation_ids.exists():
                latest_evaluation = risk.evaluation_ids.sorted()[0]
                return {
                    'detectability': latest_evaluation.detectability,
                    'occurrence': latest_evaluation.occurrence,
                    'severity': latest_evaluation.severity,
                }
        return {}

    def _compute_default_review_date(self):
        date = fields.Date.from_string(fields.Date.context_today(self))
        default_review_date = date + datetime.timedelta(days=RISK_EVALUATION_DEFAULT_MAX_AGE)
        return fields.Date.to_string(default_review_date)

    review_date = fields.Date(string='Review Date', default=_compute_default_review_date)

    @api.multi
    def set_value(self):
        risk_eval_model = self.env[self.risk_eval_model]
        for wizard in self:
            review_date = wizard.review_date
            detectability = wizard.detectability
            occurrence = wizard.occurrence
            severity = wizard.severity
            comment = wizard.comment
            risk_id = self.risk_id.id
            risk_eval_model.create({
                'review_date': review_date,
                'detectability': detectability,
                'occurrence': occurrence,
                'severity': severity,
                'comment': comment,
                'risk_id': risk_id
            })

    @api.onchange('detectability', 'occurrence', 'severity')
    def _onchange_criteria(self):
        if self.risk_id.risk_type == 'T':
            self.latest_level = int(self.detectability) * int(self.occurrence) * int(self.severity)
        elif self.risk_id.risk_type == 'O':
            inv_detectability_score = [str(x) for x in range(1, 6)]
            opp_detectability_dict = dict((x, y) for x, y in zip(inv_detectability_score, range(5, 0, -1)))
            detectability_opp = opp_detectability_dict.get(self.detectability)
            self.latest_level = detectability_opp * int(self.occurrence) * int(self.severity)

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


class ProjectRiskThresholdWizard(models.TransientModel):
    _name = 'risk_management.project_risk.set_threshold_wizard'
    _inherit = ['risk_management.base_eval_wizard']

    risk_id = fields.Many2one('risk_management.project_risk', string='Project Risk', required=True,
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
    risk_eval_model = fields.Char('Evaluation Model', default='risk_management.business_risk.evaluation', readonly=True)
    latest_level_date = fields.Date('Last evaluated on', related='risk_id.last_evaluate_date', readonly=True)
    comment = fields.Html(string='Comments', related='latest_eval.comment')


class ProjectRiskEvalWizard(models.TransientModel):
    _name = 'risk_management.project_risk.eval_wizard'
    _inherit = ['risk_management.base_risk_level_wizard']

    risk_id = fields.Many2one('risk_management.project_risk', string='Project Risk', required=True,
                              ondelete='cascade')
    latest_eval = fields.Many2one('risk_management.project_risk.evaluation', compute='_compute_latest_eval')
    threshold_value = fields.Integer('Current Threshold', related='risk_id.threshold_value')
    latest_level = fields.Integer('Current Level', related='risk_id.latest_level_value')
    risk_eval_model = fields.Char('Evaluation Model', default='risk_management.project_risk.evaluation', readonly=True)
    latest_level_date = fields.Date('Last evaluated on', related='risk_id.last_evaluate_date', readonly=True)
    comment = fields.Html(string='Comments', related='latest_eval.comment')


class BusinessRiskWizard(models.TransientModel):
    _name = 'risk_management.business_risk.wizard'
    _inherit = ['risk_management.base_risk_wizard']

    def _get_default_process(self):
        process_id = self.env.context.get('default_process_id')
        return self.env['risk_management.business_process'].browse(process_id).exists()

    process_id = fields.Many2one('risk_management.business_process', string='Process', ondelete='cascade',
                                 default=_get_default_process, required=True)
    risk_model = fields.Char(default='risk_management.business_risk', readonly=True)


class ProjectRiskWizard(models.TransientModel):
    _name = 'risk_management.project_risk.wizard'
    _inherit = ['risk_management.base_risk_wizard']

    process_id = fields.Many2one('risk_management.project_process', string='Process', ondelete='cascade')
    project_id = fields.Many2one('project.project', string='Project', ondelete='cascade', required=True,
                                 related='process_id.project_id')
    risk_model = fields.Char(default='risk_management.project_risk', readonly=True)


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
    risk_info_action = fields.Html(translate=True, string='Action / Hedging policy', related='risk_info_id.action')

    @api.multi
    def write_changes(self):
        for wizard in self:
            control = wizard.risk_info_control
            action = wizard.risk_info_action
            wizard.risk_info_id.write({
                'control': control,
                'action': action
            })
