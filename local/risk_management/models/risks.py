import datetime

from odoo import models, fields, api, exceptions

REPORT_OBSOLETE_AFTER_DAYS = 30


# -------------------------------------- Risk identification ----------------------------------


class RiskCategory(models.Model):
    _name = 'risk_management.risk.category'
    _description = 'Risk Category'

    _sql_constraints = [
        (
            'category_name_unique',
            'UNIQUE(name)',
            'Risk category name must be unique.'
        )
    ]

    name = fields.Char(translate=True)
    risk_info_ids = fields.One2many(comodel_name='risk_management.risk.info', inverse_name='risk_category_id',
                                    string='Risks')


class RiskInfo(models.Model):
    _name = 'risk_management.risk.info'
    _description = 'Information on risk'
    _sql_constraints = [
        (
            'unique_name_category',
            'UNIQUE(risk_category_id, subcategory, name)',
            'Name must be unique per category'
        )
    ]

    risk_category_id = fields.Many2one(comodel_name='risk_management.risk.category', string='Category',
                                       ondelete='restrict')
    subcategory = fields.Char(translate=True)
    name = fields.Char(translate=True, index=True, copy=False)
    description = fields.Html(translate=True, string='Description')
    cause = fields.Html(Translate=True, string='Cause')
    consequence = fields.Html(translate=True, )
    control = fields.Text(translate=True, string='Control / Monitoring')
    note = fields.Text(translate=True, string='Note')
    business_risk_ids = fields.One2many(comodel_name='risk_management.business_risk', inverse_name='risk_info_id',
                                        string='Occurrence(Business)')
    project_risk_ids = fields.One2many(comodel_name='risk_management.project_risk', inverse_name='risk_info_id',
                                       string='Occurrence (Projects)')


class BaseRiskCriteria(models.AbstractModel):
    _name = 'risk_management.base_criteria'

    DETECTABILITY_SELECTION = (
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
        (4, 'Very probable'),
        (5, 'Almost certain')
    )
    SEVERITY_SELECTION = (
        (1, 'Low'),
        (2, 'Average'),
        (3, 'High'),
        (4, 'Very High'),
        (5, 'Maximal')

    )
    detectability = fields.Selection(selection=DETECTABILITY_SELECTION, string='Detectability', default=2,
                                     help='What is the ability of the company to detect'
                                          ' a failure if it were to occur?')
    occurrence = fields.Selection(selection=OCCURRENCE_SELECTION, default=2, string='Occurrence',
                                  help='How likely is it for a particular failure to occur?')
    severity = fields.Selection(selection=SEVERITY_SELECTION, default=2, string='Severity',
                                help='If a failure were to occur, what effect would that failure '
                                     'have on company assets?')
    comment = fields.Html(string='Comments', translate=True)
    value_threat = fields.Integer(compute='_compute_value_threat')
    value_opportunity = fields.Integer(compute='_compute_value_opportunity')

    @api.depends('detectability', 'occurrence', 'severity')
    def _compute_value_threat(self):
        """
       if the risk is a threat, return the product of the scores,
       """
        for rec in self:
            rec.value_threat = rec.detectability * rec.occurrence * rec.severity

    @api.depends('detectability', 'occurrence', 'severity')
    def _compute_value_opportunity(self):
        """
        if the risk is an opportunity, invert the value of self.detectability before calculating the product of
        the scores; ie a `continuous` capacity to detect an opportunity corresponds to 5. This is the contrary of the
        threat case where the greater the ability to detect the threat occurrence the less the risk factor
        """
        opp_detectability_selection = dict((x, y) for x, y in zip(range(1, len(self.DETECTABILTY_SELECTION) + 1),
                                                                  range(len(self.DETECTABILTY_SELECTION), 0, -1)))
        for rec in self:
            detectability_opp = opp_detectability_selection.get(rec.detectability)
            rec.value_opportunity = self.detectability * detectability_opp * rec.severity


class BaseRiskIdentification(models.AbstractModel):
    _name = 'risk_management.base_identification'
    _inherit = ['risk_management.base_criteria']

    def _compute_default_review_date(self):
        if not self.report_date:
            return False
        report_date = fields.Date.from_string(self.report_date)
        default_review_date = report_date + datetime.timedelta(days=REPORT_OBSOLETE_AFTER_DAYS)
        return fields.Date.to_string(default_review_date)

    risk_type = fields.Selection(selection=(('T', 'Threat'), ('O', 'Opportunity')), string='Type', default='T',
                                 require=True)
    risk_info_id = fields.Many2one(comodel_name='risk_management.risk.info', string='Risk')
    report_date = fields.Date(string='Reported On', default=fields.Date.today)
    reported_by = fields.Many2one(comodel_name='res.users', string='Reported_by', default=lambda self: self.env.user)
    threshold_value = fields.Integer(compute='_compute_threshold_value', string='Risk threshold', store=True)
    latest_level_value = fields.Integer(compute='_compute_latest_level_value', string='Risk Level', store=True)
    review_date = fields.Date(default=_compute_default_review_date, string="Review on")
    owner = fields.Many2one(comodel_name='res.users', ondelete='set null', string='Risk Owner', index=True)
    active = fields.Boolean(compute='_compute_active')

    @api.depends('risk_type', 'detectability', 'occurrence', 'severity')
    def _compute_threshold_value(self):
        for rec in self:
            if rec.risk_type == 'T':
                rec.threshold_value = rec.value_threat
            elif rec.risk_type == 'O':
                rec.threshold_value = rec.value_opportunity

    @api.depends('review_date')
    def _compute_active(self):
        for rec in self:
            if rec.review_date and fields.Date.from_string(fields.Date.today()) < fields.Date.from_string(
                    rec.review_date):
                rec.active = True
            else:
                rec.active = False

    @api.constrains('report_date', 'review_date')
    def _check_review_after_report(self):
        for rec in self:
            if (rec.review_date and rec.report_date) and (rec.review_date < rec.report_date):
                raise exceptions.ValidationError('Review date must be after report date')

    @api.constrains('report_date', 'create_date')
    def _check_report_date_post_create_date(self):
        for rec in self:
            if rec.report_date and rec.create_date < rec.report_date:
                raise exceptions.ValidationError('Report date must prior to or same as create date')

    @api.depends('evaluation_ids')
    def _compute_latest_level_value(self):
        for rec in self:
            if not rec.active or not rec.evaluation_ids:
                rec.latest_level_value = False
            # get the latest evaluation
            latest_evaluation = rec.evaluation_ids.sorted()[0]
            if rec.risk_type == 'T':
                rec.latest_level_value = latest_evaluation.value_threat
            elif rec.risk_type == 'O':
                rec.latest_level_value = latest_evaluation.value_opportunity


class BusinessRisk(models.Model):
    _name = 'risk_management.business_risk'
    _description = 'Business risk'
    _inherit = ['risk_management.base_identification']

    process_id = fields.Many2one(comodel_name='risk_management.business_process', string='Process')
    evaluation_ids = fields.One2many(comodel_name='risk_management.business_risk.evaluation', inverse_name='risk_id')
    treatment_ids = fields.One2many(comodel_name='project.project', inverse_name='risk_id')
    treatment_id = fields.Many2one(comodel_name='project.project', compute='_compute_treatment',
                                   inverse='_inverse_treatment')

    @api.depends('treatment_ids')
    def _compute_treatment(self):
        for rec in self:
            if rec.treatment_ids:
                rec.treatment_id = rec.treatment_ids[0]

    @api.multi
    def _inverse_treatment(self):
        for rec in self:
            if rec.treatment_ids:
                # delete previous reference
                treatment = self.env['project.project'].browse(rec.treatment_ids[0].id)
                treatment.risk_id = False
            rec.treatment_id.risk_id = rec


class ProjectRisk(models.Model):
    _name = 'risk_management.project_risk'
    _description = 'Project risk'
    _inherit = ['risk_management.base_identification']

    process_id = fields.Many2one(comodel_name='risk_management.project_process', string='Process')
    evaluation_ids = fields.One2many(comodel_name='risk_management.project_risk.evaluation', inverse_name='risk_id')


# -------------------------------------- Risk evaluation ----------------------------------


class BaseEvaluation(models.AbstractModel):
    _name = 'risk_management.base_evaluation'
    _inherit = ['risk_management.base_criteria']
    _order = 'date desc'

    date = fields.Date(string='Estimated On', default=lambda self: self.create_date)


class BusinessRiskEvaluation(models.Model):
    _name = 'risk_management.business_risk.evaluation'
    _description = 'Business risk evaluation'
    _inherit = ['risk_management.base_evaluation']

    risk_id = fields.Many2one(comodel_name='risk_management.business_risk', string='Risk')


class ProjectRiskEvaluation(models.Model):
    _name = 'risk_management.project_risk.evaluation'
    _description = 'Project risk evaluation'
    _inherit = ['risk_management.base_evaluation']

    risk_id = fields.Many2one(comodel_name='risk_management.project_process')
