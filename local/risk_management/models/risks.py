import datetime
import uuid

from odoo import models, fields, api, exceptions

RISK_REPORT_DEFAULT_MAX_AGE = 90
RISK_EVALUATION_DEFAULT_MAX_AGE = 30


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
    control = fields.Text(translate=True, string='Steering / Monitoring', groups='risk_management.group_risk_manager')
    action = fields.Text(translate=True, string='Action / Hedging policy', groups='risk_management.group_risk_manager')
    business_risk_ids = fields.One2many(comodel_name='risk_management.business_risk', inverse_name='risk_info_id',
                                        string='Occurrence(Business)')
    project_risk_ids = fields.One2many(comodel_name='risk_management.project_risk', inverse_name='risk_info_id',
                                       string='Occurrence (Projects)')
    business_occurrences = fields.Integer(string='Occurrences', compute="_compute_business_occurrences")
    project_occurrences = fields.Integer(string="Occurrences in Projects", compute="_compute_project_occurrences")

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        """Searches risk by name or description"""
        args = [] if args is None else args.copy()
        if not (name == '' and operator == 'ilike'):
            args += ['|', ('name', operator, name), ('description', operator, name)]
        return super(RiskInfo, self)._name_search(name=name, args=args, operator='ilike', limit=limit,
                                                  name_get_uid=name_get_uid)

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
    _order = 'report_date desc'

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

    detectability = fields.Selection(selection=_get_detectability, string='Detectability', default='3', required=True,
                                     help='What is the ability of the company to detect'
                                          ' this failure (or gain) if it were to occur?')
    occurrence = fields.Selection(selection=_get_occurrence, default='3', string='Occurrence', required=True,
                                  help='How likely is it for this failure (or gain) to occur?')
    severity = fields.Selection(selection=_get_severity, default='3', string='Severity', required=True,
                                help='If this failure (or gain) were to occur, what is the level of the impact it '
                                     'would have on company assets?')

    comment = fields.Html(string='Comments', translate=True)
    value_threat = fields.Integer(compute='_compute_value_threat')
    value_opportunity = fields.Integer(compute='_compute_value_opportunity')

    @api.depends('detectability', 'occurrence', 'severity')
    def _compute_value_threat(self):
        """
       if the risk is a threat, return the product of the criteria score,
       """
        for rec in self:
            if rec.severity and rec.detectability and rec.occurrence:
                rec.value_threat = int(rec.detectability) * int(rec.occurrence) * int(rec.severity)
            else:
                rec.value_threat = False

    @api.depends('detectability', 'occurrence', 'severity')
    def _compute_value_opportunity(self):
        """
        if the risk is an opportunity, invert the value of self.detectability before computing the product of
        the scores; ie a `continuous` capacity to detect an opportunity corresponds to 5. This is the contrary of the
        threat case where the greater the ability to detect the threat occurrence the less the risk factor
        """
        inv_detectability_score = [str(x) for x in range(1, 6)]
        opp_detectability_dict = dict((x, y) for x, y in zip(inv_detectability_score, range(5, 0, -1)))
        for rec in self:
            if rec.detectability and rec.occurrence and rec.severity:
                detectability_opp = opp_detectability_dict.get(rec.detectability)
                rec.value_opportunity = int(rec.detectability) * detectability_opp * int(rec.severity)
            else:
                rec.value_opportunity = False


class BaseRiskIdentification(models.AbstractModel):
    _name = 'risk_management.base_identification'
    _inherit = ['risk_management.base_criteria']
    _order = 'report_date desc'

    def _compute_default_review_date(self):

        """By default the review date is RISK_REPORT_DEFAULT_MAX_AGE days from the report date"""
        create_date = fields.Date.from_string(self.report_date or fields.Date.today())
        default_review_date = create_date + datetime.timedelta(days=RISK_REPORT_DEFAULT_MAX_AGE)
        return fields.Date.to_string(default_review_date)

    uuid = fields.Char(default=lambda self: str(uuid.uuid4()), readonly=True, required=True)
    name = fields.Char(compute='_compute_name', index=True, readonly=True, store=True)
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
    report_date = fields.Date(string='Reported On', default=lambda self: fields.Date.context_today(self))
    reported_by = fields.Many2one(comodel_name='res.users', string='Reported by', default=lambda self: self.env.user)
    threshold_value = fields.Integer(compute='_compute_threshold_value', string='Risk threshold', store=True)
    latest_level_value = fields.Integer(compute='_compute_latest_level_value', string='Risk Level', store=True)
    last_evaluate_date = fields.Date(compute='_compute_last_evaluate_date')
    review_date = fields.Date(default=_compute_default_review_date, string="Review Date")
    owner = fields.Many2one(comodel_name='res.users', ondelete='set null', string='Assigned to', index=True)
    active = fields.Boolean(compute='_compute_active', inverse='_inverse_active', search='_search_active')
    status = fields.Selection(selection=[('U', 'Unknown'), ('A', 'Acceptable'), ('N', 'Unacceptable')],
                              compute='_compute_acceptable', string='Status', search='_search_acceptable')
    mgt_stage = fields.Selection([('I', 'Identification'), ('E', 'Evaluation'), ('T', 'Treatment')],
                                 compute='_compute_stage', store=True)

    @api.depends('uuid')
    def _compute_name(self):
        for rec in self:
            rec.name = 'risk #%s' % rec.uuid[:8]

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
            else:
                last_evaluation = rec.evaluation_ids.sorted()[0]
                rec.last_evaluate_date = last_evaluation.create_date

    @api.depends('review_date')
    def _compute_active(self):
        for rec in self:
            if rec.review_date and fields.Date.from_string(fields.Date.context_today(self)) < fields.Date.from_string(
                    rec.review_date):
                rec.active = True
            else:
                rec.active = False

    def _inverse_active(self):
        for rec in self.filtered('report_date'):
            rec.review_date = fields.Date.context_today(self)

    @api.multi
    def _search_active(self, operator, value):
        # active_test=False in context prevent infinite loop in the search function
        recs = self.with_context(active_test=False)
        today = fields.Date.context_today(self)
        if operator not in ('=', '!=') or value not in (1, 0):
            recs = recs.search([])
        elif value:
            if operator == '=':
                recs = recs.search([('review_date', '>', today)])
            elif operator == '!=':
                recs = recs.search([('review_date', '<=', today)])
        else:
            if operator == '=':
                recs = recs.search([('review_date', '<=', today)])
            elif operator == '!=':
                recs = recs.search([('review_date', '>', today)])
        return [('id', 'in', [rec.id for rec in recs])]

    @api.constrains('report_date', 'review_date')
    def _check_review_after_report(self):
        for rec in self:
            if (rec.review_date and rec.report_date) and (rec.review_date < rec.report_date):
                raise exceptions.ValidationError('Review date must be after report date')

    @api.constrains('report_date', 'create_date')
    def _check_report_date_post_create_date(self):
        for rec in self:
            if rec.report_date and rec.create_date < rec.report_date:
                raise exceptions.ValidationError('Report date must post or same as create date')

    @api.depends('evaluation_ids')
    def _compute_latest_level_value(self):
        for rec in self:
            if not rec.evaluation_ids.exists():
                rec.latest_level_value = False
            else:
                # get the latest evaluation
                latest_evaluation = rec.evaluation_ids.sorted()[0]
                if latest_evaluation.is_obsolete:
                    rec.latest_level_value = False
                elif rec.risk_type == 'T':
                    rec.latest_level_value = latest_evaluation.value_threat
                elif rec.risk_type == 'O':
                    rec.latest_level_value = latest_evaluation.value_opportunity

    @api.multi
    def update_id_info(self, report_date=None, reporter=None):
        """Reactivate an old risk when it's re-reported"""
        self.ensure_one()
        if self.active:
            return
        new_report_date = report_date or fields.Date.context_today(self)
        new_reporter = reporter or self.env.user.id
        review_date = fields.Date.from_string(new_report_date) + datetime.timedelta(days=RISK_REPORT_DEFAULT_MAX_AGE)
        self.sudo().write({'review_date': fields.Date.to_string(review_date),
                           'report_date': new_report_date,
                           'reported_by': new_reporter})

    @api.multi
    def toggle_active(self):
        for rec in self:
            if rec.active:
                rec._inverse_active()
            else:
                rec.update_id_info()

    @api.depends('active', 'latest_level_value', 'threshold_value')
    def _compute_acceptable(self):
        for rec in self:
            if rec.active and rec.latest_level_value and rec.threshold_value:
                if rec.latest_level_value <= rec.threshold_value:
                    rec.status = 'A'
                else:
                    rec.status = 'N'
            else:
                rec.status = 'U'

    def _search_acceptable(self, operator, value):
        recs = self.with_context(active_test=False)

        def acceptable(rec):
            # is the risk acceptable?
            return rec.active and rec.latest_level_value and rec.threshold_value and rec.latest_level_value <= rec.threshold_value

        def unacceptable(rec):
            # is the risk unacceptable?
            return rec.active and rec.latest_level_value and rec.threshold_value and rec.latest_level_value > rec.threshold_value

        def unknown_status(rec):
            # is the risk status unknown?
            return not rec.active or not rec.latest_level_value or not rec.threshold_value

        if operator not in ('=', '!=') or value not in ('A', 'N', 'U'):
            recs = recs.search([])
        else:
            if operator == '=':
                if value == 'A':
                    recs = recs.filtered(acceptable)
                elif value == 'N':
                    recs = recs.filtered(unacceptable)
                elif value == 'U':
                    recs = recs.filtered(unknown_status)
            if operator == '!=':
                if value == 'A':
                    recs = recs.filtered(unacceptable) | recs.filtered(unknown_status)
                elif value == 'N':
                    recs = recs.filtered(acceptable) | recs.filtered(unknown_status)
                elif value == 'U':
                    recs = recs.filtered(acceptable) | recs.filtered(unacceptable)

        return [('id', 'in', [rec.id for rec in recs])]

    def assign_to_me(self):
        self.sudo().write({'owner': self.env.user.id})


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
            if rec.latest_level_value and rec.treatment_ids:
                rec.treatment_id = rec.treatment_ids[0]

    @api.multi
    def _inverse_treatment(self):
        for rec in self:
            if rec.treatment_ids:
                # delete previous reference
                treatment = self.env['project.project'].browse(rec.treatment_ids[0].id)
                treatment.risk_id = False
            rec.treatment_id.risk_id = rec

    @api.depends('latest_level_value', 'treatment_id')
    def _compute_stage(self):
        for rec in self:
            if rec.active and not rec.latest_level_value:
                rec.mgt_stage = 'I'
            elif rec.latest_level_value and not rec.treatment_id:
                rec.mgt_stage = 'E'
            elif rec.treatment_id:
                rec.mgt_stage = 'T'
            else:
                rec.mgt_stage = False


class ProjectRisk(models.Model):
    _name = 'risk_management.project_risk'
    _description = 'Project risk'
    _inherit = ['risk_management.base_identification']

    process_id = fields.Many2one(comodel_name='risk_management.project_process', string='Process')
    evaluation_ids = fields.One2many(comodel_name='risk_management.project_risk.evaluation', inverse_name='risk_id',
                                     string='Evaluations')
    treatment_ids = fields.One2many(comodel_name='risk_management.project_risk.treatment_task', inverse_name='risk_id',
                                    string='Treatment tasks')

    @api.depends('latest_level_value', 'treatment_ids')
    def _compute_stage(self):
        for rec in self:
            if rec.active and not rec.latest_level_value:
                rec.mgt_stage = 'I'
            elif rec.latest_level_value and not rec.treatment_ids:
                rec.mgt_stage = 'E'
            elif rec.treatment_ids:
                rec.mgt_stage = 'T'
            else:
                rec.mgt_stage = False


# -------------------------------------- Risk evaluation ----------------------------------


class BaseEvaluation(models.AbstractModel):
    _name = 'risk_management.base_evaluation'
    _inherit = ['risk_management.base_criteria']
    _order = 'write_date desc'

    def _compute_default_review_date(self):
        date = fields.Date.from_string(fields.Date.today())
        default_review_date = date + datetime.timedelta(days=RISK_EVALUATION_DEFAULT_MAX_AGE)
        return fields.Date.to_string(default_review_date)

    review_date = fields.Date(string='Review Date', default=_compute_default_review_date)
    is_obsolete = fields.Boolean('Is Obsolete', compute='_compute_is_obsolete')  # TODO: search method

    @api.depends('review_date')
    def _compute_is_obsolete(self):
        for rec in self:
            if rec.review_date:
                review_date = fields.Date.from_string(rec.review_date)
                rec.is_obsolete = review_date < fields.Date.from_string(fields.Date.today())
            else:
                rec.is_obsolete = False

    def _search_is_obsolete(self, operator, value):
        if operator not in('=', "!=") or value not in (0, 1):
            recs = self.search([])
        elif operator == '=':
            if value:
                recs = self.search(['review_date', '<', fields.Date.today()])
            else:
                recs = self.search(['review_date', '>=', fields.Date.today()])
        else:
            if value:
                recs = self.search(['review_date', '>=', fields.Date.today()])
            else:
                recs = self.search(['review_date', '<', fields.Date.today()])
        return [('id', 'in', [rec.id for rec in recs])]


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
        # return the risk to use as default in risk_id field
        default_risk_id = self.env.context.get('default_risk_id', False)

        if default_risk_id:
            risk = self.env['risk_management.business_risk'].browse(default_risk_id)
            if risk:
                return risk.exists()

    risk_id = fields.Many2one(comodel_name='risk_management.business_risk', string='Risk',
                              default=_get_default_risk, required=True)
    name = fields.Char(compute='_compute_name', store=True)

    @api.depends('risk_id')
    def _compute_name(self):
        for rec in self:
            rec.name = "%s: Treatment" % self.risk_id.name


class ProjectRiskTreatmentTask(models.Model):
    _name = 'risk_management.project_risk.treatment_task'
    _inherit = ['project.task']

    def _get_default_risk(self):
        default_risk_id = self.env.context.get('default_risk_id', False)
        if default_risk_id:
            return default_risk_id.exists()

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
        else:
            return {}

    detectability = fields.Selection(selection=_get_detectability, string='Detectability',
                                     default=lambda self: self._get_default_criteria().get('detectability', '3'),
                                     required=True,
                                     help='What is the ability of the company to detect'
                                          ' this failure (or gain) if it were to occur?')
    occurrence = fields.Selection(selection=_get_occurrence, string='Occurrence',
                                  default=lambda self: self._get_default_criteria().get('occurrence', '3'), required=True,
                                  help='How likely is it for this failure (or gain) to occur?')
    severity = fields.Selection(selection=_get_severity, string='Severity',
                                default=lambda self: self._get_default_criteria().get('severity', '3'), required=True,
                                help='If this failure (or gain) were to occur, what is the level of the impact it '
                                     'would have on company assets?')
    comment = fields.Html(string='Comments', translate=True)

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
        else:
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


class BusinessRiskThresholdWizard(models.TransientModel):
    _name = 'risk_management.business_risk.set_threshold_wizard'
    _inherit = ['risk_management.base_eval_wizard']

    risk_id = fields.Many2one('risk_management.business_risk', string='Business Risk', required=True,
                              ondelete='cascade')


class ProjectRiskThresholdWizard(models.TransientModel):
    _name = 'risk_management.project_risk.set_threshold_wizard'
    _inherit = ['risk_management.base_eval_wizard']

    risk_id = fields.Many2one('risk_management.project_risk', string='Project Risk', required=True,
                              ondelete='cascade')


class BusinessRiskEvalWizard(models.TransientModel):
    _name = 'risk_management.business_risk.eval_wizard'
    _inherit = ['risk_management.base_risk_level_wizard']

    risk_id = fields.Many2one('risk_management.business_risk', string='Business Risk', required=True,
                              ondelete='cascade')
    risk_eval_model = fields.Char('Evaluation Model', default='risk_management.business_risk.evaluation', readonly=True)


class ProjectRiskEvalWizard(models.TransientModel):
    _name = 'risk_management.project_risk.eval_wizard'

    risk_id = fields.Many2one('risk_management.project_risk', string='Project Risk', required=True,
                              ondelete='cascade')
    risk_eval_model = fields.Char('Evaluation Model', default='risk_management.project_risk.evaluation', required=True)


class BusinessRiskWizard(models.TransientModel):
    _name = 'risk_management.business_risk.wizard'
    _inherit = ['risk_management.base_risk_wizard']

    def get_default_process_id(self):
        process_id = self.env.context.get('default_process_id', False)
        if process_id:
            process = self.env['risk_management.business_process'].browse(process_id)
            return process.exists()

    process_id = fields.Many2one('risk_management.business_process', string='Process', ondelete='cascade',
                                 default=get_default_process_id)
    risk_model = fields.Char(default='risk_management.business_risk', readonly=True)


class ProjectRiskWizard(models.TransientModel):
    _name = 'risk_management.project_risk.wizard'
    _inherit = ['risk_management.base_risk_wizard']

    process_id = fields.Many2one('risk_management.project_process', string='Process', ondelete='cascade')
    risk_model = fields.Char(default='risk_management.project_risk', readonly=True)


class RiskHelpWizard(models.TransientModel):
    _name = 'risk_management.risk.help_wizard'

    def _get_default_risk_info(self):
        risk_info_id = self.env.context.get('default_risk_info_id', False)
        if risk_info_id:
            risk_info = self.env['risk_management.risk.info'].browse(risk_info_id)
            return risk_info.exists()

    risk_info_id = fields.Many2one('risk_management.risk.info', default=_get_default_risk_info, required=True,
                                   ondelete='cascade')
    risk_info_control = fields.Text(translate=True, string='Steering / Monitoring', related='risk_info_id.control')
    risk_info_action = fields.Text(translate=True, string='Action / Hedging policy', related='risk_info_id.action')

    @api.multi
    def write_changes(self):
        for wizard in self:
            control = wizard.risk_info_control
            action = wizard.risk_info_action
            wizard.risk_info_id.write({
                'control': control,
                'action': action
            })


