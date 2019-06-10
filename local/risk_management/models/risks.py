import datetime

from odoo import models, fields, api, exceptions

REPORT_MAX_AGE = 30


# -------------------------------------- Risk identification ----------------------------------


class RiskCategory(models.Model):
    _name = 'risk_management.risk.category'
    _description = 'Risk Category'
    _order = 'name asc'

    _sql_constraints = [
        (
            'category_name_unique',
            'UNIQUE(name)',
            'Risk category name must be unique.'
        )
    ]

    name = fields.Char(translate=True, required=True)
    risk_info_ids = fields.One2many(comodel_name='risk_management.risk.info', inverse_name='risk_category_id',
                                    string='Risks')
    risk_count = fields.Integer(compute='_compute_risk_count', string='Risks')

    @api.multi
    def _compute_risk_count(self):
        for rec in self:
            rec.risk_count = len(rec.risk_info_ids)


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
    subcategory = fields.Char(translate=True, string='Sub-category')
    name = fields.Char(translate=True, index=True, copy=False, required=True)
    description = fields.Html(translate=True, string='Description', required=True)
    cause = fields.Html(Translate=True, string='Cause', index=True)
    consequence = fields.Html(translate=True, string='Consequence', index=True)
    control = fields.Text(translate=True, string='Monitoring', groups='risk_management.group_risk_manager')
    action = fields.Text(translate=True, string='Hedging policy', groups='risk_management.group_risk_manager')
    business_risk_ids = fields.One2many(comodel_name='risk_management.business_risk', inverse_name='risk_info_id',
                                        string='Occurrence(Business)')
    project_risk_ids = fields.One2many(comodel_name='risk_management.project_risk', inverse_name='risk_info_id',
                                       string='Occurrence (Projects)')
    business_occurrences = fields.Integer(string='Occurrences', compute="_compute_business_occurrences")
    project_occurrences = fields.Integer(string="Occurrences in Projects", compute="_compute_project_occurrences")

    @api.multi
    def _compute_business_occurrences(self):
        for rec in self:
            rec.business_occurrences = len(rec.business_risk_ids)

    @api.multi
    def _compute_project_occurrences(self):
        for rec in self:
            rec.project_occurrences = len(rec.project_risk_ids)


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
        if not self.last_evaluate_date:
            return False
        last_evaluate_date = fields.Date.from_string(self.last_evaluate_date)
        default_review_date = last_evaluate_date + datetime.timedelta(days=REPORT_MAX_AGE)
        return fields.Date.to_string(default_review_date)

    risk_type = fields.Selection(selection=(('T', 'Threat'), ('O', 'Opportunity')), string='Type', default='T',
                                 require=True)
    risk_info_id = fields.Many2one(comodel_name='risk_management.risk.info', string='Risk')
    risk_info_category = fields.Char('Risk Category', related='risk_info_id.risk_category_id.name', readonly=True)
    risk_info_subcategory = fields.Char('Sub-category', related='risk_info_id.subcategory', readonly=True)
    risk_info_description = fields.Html('Description', related='risk_info_id.description', readonly=True)
    risk_info_cause = fields.Html('Cause', related='risk_info_id.cause', readonly=True)
    risk_info_consequence = fields.Html('Consequence', related='risk_info_id.consequence', readonly=True)
    risk_info_control = fields.Text('Monitoring', related='risk_info_id.control', readonly=True, related_sudo=True)
    risk_info_action = fields.Text('Hedging strategy', related='risk_info_id.action', readonly=True, related_sudo=True)
    report_date = fields.Date(string='Reported On', default=fields.Date.today)
    reported_by = fields.Many2one(comodel_name='res.users', string='Reported by', default=lambda self: self.env.user)
    threshold_value = fields.Integer(compute='_compute_threshold_value', string='Risk threshold', store=True)
    latest_level_value = fields.Integer(compute='_compute_latest_level_value', string='Risk Level', store=True)
    last_evaluate_date = fields.Date(compute='_compute_last_evaluate_date')
    review_date = fields.Date(default=_compute_default_review_date, string="Review on")
    owner = fields.Many2one(comodel_name='res.users', ondelete='set null', string='Risk Owner', index=True)
    active = fields.Boolean(compute='_compute_active', store=True)  # FIXME: inverse active field

    @api.depends('risk_type', 'detectability', 'occurrence', 'severity')
    def _compute_threshold_value(self):
        for rec in self:
            if rec.risk_type == 'T':
                rec.threshold_value = rec.value_threat
            elif rec.risk_type == 'O':
                rec.threshold_value = rec.value_opportunity

    @api.depends('evaluation_ids')
    def _compute_last_evaluate_date(self):
        for rec in self:
            if not rec.evaluation_ids:
                rec.last_evaluate_date = False
            last_evaluation = rec.evaluation_ids.sorted()[0]
            rec.last_evaluate_date = last_evaluation.create_date

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

    @api.multi
    def update_info(self, report_date=None, reporter=None):
        self.ensure_one()
        if self.active:
            return
        report_date = report_date or fields.Date.today()
        reporter = reporter or self.env.user
        review_date = fields.Date.from_string(report_date) + datetime.timedelta(REPORT_MAX_AGE)
        self.sudo().write({'review_date': fields.Date.to_string(review_date),
                           'report_date': report_date,
                           'reported_by': reporter})


class BusinessRisk(models.Model):
    _name = 'risk_management.business_risk'
    _description = 'Business risk'
    _inherit = ['risk_management.base_identification']
    _sql_constraints = [
        (
            'unique_risk_process',
            'UNIQUE(risk_info_id, process_id, risk_type)',
            'This risk has already been reported.'
        )
    ]

    process_id = fields.Many2one(comodel_name='risk_management.business_process', string='Process')
    evaluation_ids = fields.One2many(comodel_name='risk_management.business_risk.evaluation', inverse_name='risk_id')
    treatment_ids = fields.One2many(comodel_name='risk_management.business_risk.treatment', inverse_name='risk_id')
    treatment_id = fields.Many2one(comodel_name='risk_management.business_risk.treatment', compute='_compute_treatment',
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
    evaluation_ids = fields.One2many(comodel_name='risk_management.project_risk.evaluation', inverse_name='risk_id',
                                     string='Evaluations')
    treatment_ids = fields.One2many(comodel_name='risk_management.project_risk.treatment_task', inverse_name='risk_id',
                                    string='Treatment tasks')


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

    risk_id = fields.Many2one(comodel_name='risk_management.business_risk', string='Risk', required=True)


class ProjectRiskEvaluation(models.Model):
    _name = 'risk_management.project_risk.evaluation'
    _description = 'Project risk evaluation'
    _inherit = ['risk_management.base_evaluation']

    risk_id = fields.Many2one(comodel_name='risk_management.project_risk', string='Risk', required=True)


# -------------------------------------- Risk Treatment -----------------------------------


class BusinessRiskTreatment(models.Model):
    _name = 'risk_management.business_risk.treatment'
    _description = 'Business risk treatment'
    _inherit = ['project.project']

    def _get_default_risk(self):
        default_risk_id = self.env.context.get('default_risk_id')
        if default_risk_id:
            return default_risk_id.exists()
        else:
            return False

    risk_id = fields.Many2one(comodel_name='risk_management.business_risk', string='Risk',
                              default=_get_default_risk, required=True)
    name = fields.Char(compute='_compute_name', store=True)

    @api.depends('risk_id')
    def _compute_name(self):
        for rec in self:
            rec.name = "%s: Treatment" % self.risk_id.risk_info_id.name


class ProjectRiskTreatmentTask(models.Model):
    _name = 'risk_management.project_risk.treatment_task'
    _inherit = ['project.task']

    def _get_default_risk(self):
        default_risk_id = self.env.context.get('default_risk_id')
        if default_risk_id:
            return default_risk_id.exists()
        else:
            return False

    risk_id = fields.Many2one(comodel_name='risk_management.project_risk', string='Risk', default=_get_default_risk,
                              required=True)
    project_id = fields.Many2one('project.project', string='Project', index=True, track_visibility='onchange',
                                 change_default=True, compute='_compute_project_id', store=True, default=False)

    @api.depends('risk_id')
    def _compute_project_id(self):
        for rec in self:
            if rec.risk_id:
                rec.project_id = rec.risk_id.process_id.project_id
            else:
                rec.project_id = False


# -------------------------------------- Wizards -------------------------------------------

class BaseRiskWizard(models.AbstractModel):
    _name = 'risk_management.base_risk_wizard'

    risk_type = fields.Selection(selection=(('T', 'Threat'), ('O', 'Opportunity')), string='Type', default='T',
                                 require=True)
    risk_info_id = fields.Many2one('risk_management.risk.info', string='Name', required=True)
    risk_info_description = fields.Html(string='Description', readonly=True)
    risk_info_cause = fields.Html(string='Cause', readonly=True)
    risk_info_consequence = fields.Html(string='Consequence', readonly=True)
    report_date = fields.Date(string='Reported On', default=fields.Date.today)
    reported_by = fields.Many2one(comodel_name='res.users', string='Reported by', default=lambda self: self.env.user)

    @api.multi
    def record_risk(self):
        business_risk = self.env['risk_management.business_risk']
        for wizard in self:
            risk_type = wizard.risk_type
            risk_info = wizard.risk_info_id
            process_id = wizard.process_id
            report_date = wizard.report_date
            reporter = wizard.reported_by
            # Search the database for an old risk report with the same type, the same infos and on the same process as
            # this one.
            old_report = business_risk.search([('risk_type', '=', risk_type),
                                               ('risk_info_id', '=', risk_info),
                                               ('process_id', '=', process_id),
                                               ('active', '=', False)])
            if old_report:
                # old report is inactive
                old_report.update_info(report_date=report_date, reporter=reporter)
            else:
                business_risk.create({
                    'risk_type': risk_type,
                    'risk_info': risk_info,
                    'process_id': process_id,
                    'report_date': report_date,
                    'reported_by': reporter
                })



class BusinessRiskWizard(models.TransientModel):
    _name = 'risk_management.business_risk.wizard'
    _inherit = ['risk_management.base_risk_wizard']

    process_id = fields.Many2one('risk_management.business_process', string='Process')
