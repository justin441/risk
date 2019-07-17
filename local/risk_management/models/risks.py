import datetime
import uuid
import logging

from odoo import models, fields, api, exceptions, _

RISK_REPORT_DEFAULT_MAX_AGE = 90
RISK_EVALUATION_DEFAULT_MAX_AGE = 30

_logger = logging.getLogger(__name__)


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
    control = fields.Html(translate=True, string='Steering / Monitoring', groups='risk_management.group_risk_manager')
    action = fields.Html(translate=True, string='Action / Hedging policy', groups='risk_management.group_risk_manager')
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
        return super(RiskInfo, self)._name_search(name='', args=args, operator='ilike', limit=limit,
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
    severity = fields.Selection(selection=_get_severity, default='3', string='Impact', required=True,
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
                rec.value_opportunity = detectability_opp * int(rec.occurrence) * int(rec.severity)
            else:
                rec.value_opportunity = False


class BaseRiskIdentification(models.AbstractModel):
    _name = 'risk_management.base_identification'
    _inherit = ['risk_management.base_criteria', 'mail.thread', 'mail.activity.mixin']
    _mail_post_access = 'read'
    _order = 'latest_level_value desc, report_date desc'

    def _compute_default_review_date(self):

        """By default the review date is RISK_REPORT_DEFAULT_MAX_AGE days from the report date"""
        create_date = fields.Date.from_string(self.report_date or fields.Date.today())
        default_review_date = create_date + datetime.timedelta(days=RISK_REPORT_DEFAULT_MAX_AGE)
        return fields.Date.to_string(default_review_date)

    uuid = fields.Char(default=lambda self: str(uuid.uuid4()), readonly=True, required=True)
    name = fields.Char(compute='_compute_name', index=True, readonly=True, store=True, rack_visibility="always")
    risk_type = fields.Selection(selection=(('T', 'Threat'), ('O', 'Opportunity')), string='Type', default='T',
                                 require=True, track_visibility="onchange")
    risk_info_id = fields.Many2one(comodel_name='risk_management.risk.info', string='Risk Name')
    risk_info_category = fields.Char('Risk Category', related='risk_info_id.risk_category_id.name', readonly=True,
                                     store=True)
    risk_info_subcategory = fields.Char('Sub-category', related='risk_info_id.subcategory', readonly=True)
    risk_info_description = fields.Html('Description', related='risk_info_id.description', readonly=True)
    risk_info_cause = fields.Html('Cause', related='risk_info_id.cause', readonly=True)
    risk_info_consequence = fields.Html('Consequence', related='risk_info_id.consequence', readonly=True)
    risk_info_control = fields.Html('Monitoring', related='risk_info_id.control', readonly=True, related_sudo=True)
    risk_info_action = fields.Html('Hedging strategy', related='risk_info_id.action', readonly=True, related_sudo=True)
    report_date = fields.Date(string='Reported On', default=lambda self: fields.Date.context_today(self))
    reported_by = fields.Many2one(comodel_name='res.users', string='Reported by', default=lambda self: self.env.user)
    threshold_value = fields.Integer(compute='_compute_threshold_value', string='Risk threshold', store=True,
                                     track_visibility="onchange")
    latest_level_value = fields.Integer(compute='_compute_latest_level_value', string='Risk Level', store=True,
                                        track_visibility="onchange")
    max_level_value = fields.Integer(default=125, readonly=True)
    last_evaluate_date = fields.Date(compute='_compute_last_evaluate_date')
    review_date = fields.Date(default=_compute_default_review_date, string="Review Date", track_visibility="onchange")
    owner = fields.Many2one(comodel_name='res.users', ondelete='set null', string='Assigned to', index=True,
                            track_visibility="onchange")
    active = fields.Boolean(compute='_compute_active', inverse='_inverse_active', search='_search_active',
                            track_visibility="onchange")
    state = fields.Selection(selection=[('U', 'Unknown status'), ('A', 'Acceptable'), ('N', 'Unacceptable')],
                             compute='_compute_status', string='Status', search='_search_status',
                             track_visibility="onchange")
    mgt_stage = fields.Selection([('1', 'Identification done'), ('2', 'Evaluation done'), ('3', 'Ongoing treatment')],
                                 compute='_compute_stage', string='Stage', store=True, track_visibility="onchange")

    @api.depends('uuid')
    def _compute_name(self):
        for rec in self:
            rec.name = _('risk') + '#%s' % rec.uuid[:8]

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
    def _compute_status(self):
        for rec in self:
            if rec.active and rec.latest_level_value and rec.threshold_value:
                if rec.risk_type == 'T':
                    if rec.latest_level_value <= rec.threshold_value:
                        rec.state = 'A'
                    else:
                        rec.state = 'N'
                elif rec.risk_type == 'O':
                    if rec.latest_level_value < rec.threshold_value:
                        rec.state = 'N'
                    else:
                        rec.state = 'A'
            else:
                rec.state = 'U'

    def _search_status(self, operator, value):
        recs = self.with_context(active_test=False)

        def acceptable(rec):
            # is the risk acceptable?
            if rec.risk_type == 'T':
                return rec.active and rec.latest_level_value and rec.threshold_value and rec.latest_level_value <= rec.threshold_value
            elif rec.risk_type == 'O':
                return rec.active and rec.latest_level_value and rec.threshold_value and rec.threshold_value <= rec.latest_level_value

        def unacceptable(rec):
            # is the risk unacceptable?
            if rec.risk_type == 'T':
                return rec.active and rec.latest_level_value and rec.threshold_value and rec.latest_level_value > rec.threshold_value
            elif rec.risk_type == 'O':
                return rec.active and rec.latest_level_value and rec.threshold_value and rec.threshold_value > rec.latest_level_value

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

    process_id = fields.Many2one(comodel_name='risk_management.business_process', string='Impacted Process')
    evaluation_ids = fields.One2many(comodel_name='risk_management.business_risk.evaluation', inverse_name='risk_id')
    treatment_ids = fields.One2many(comodel_name='project.project', inverse_name='risk_id')
    treatment_id = fields.Many2one(comodel_name='project.project', compute='_compute_treatment',
                                   inverse='_inverse_treatment', store=True)
    treatment_task_count = fields.Integer(compute='_compute_treatment_task_count', string='Risk Treatment Tasks')

    @api.onchange('owner')
    def _onchange_owner(self):
        if self.treatment_id:
            self.treatment_id.user_id = self.owner

    @api.depends('treatment_id')
    def _compute_treatment_task_count(self):
        for rec in self:
            if rec.treatment_id:
                rec.treatment_task_count = rec.treatment_id.task_count

    @api.depends('treatment_ids')
    def _compute_treatment(self):
        for rec in self:
            if rec.latest_level_value and rec.treatment_ids:
                rec.treatment_id = rec.treatment_ids.sorted('create_date', reverse=True)[0]

    @api.multi
    def _inverse_treatment(self):
        for rec in self:
            if rec.treatment_ids:
                # delete previous reference
                treatment = self.env['project.project'].browse(
                    rec.treatment_ids.sorted('create_date', reverse=True)[0].id)
                treatment.risk_id = False
                treatment.unlink()
            rec.treatment_id.risk_id = rec

    @api.depends('latest_level_value', 'treatment_id')
    def _compute_stage(self):
        for rec in self:
            if rec.active and not rec.latest_level_value:
                rec.mgt_stage = '1'
            elif rec.latest_level_value and not rec.treatment_id:
                rec.mgt_stage = '2'
            elif rec.treatment_id:
                rec.mgt_stage = '3'
            else:
                rec.mgt_stage = False

    @api.multi
    def get_treatment(self):
        """returns the treatment tasks view. If the risk treatment project does not exist, creates one. If there is no
        risk treatment process in the treatment project, also creates one.
        """
        project = self.env['project.project']
        self.ensure_one()
        if not self.latest_level_value:
            # No need to treat a risk if it's not yet evaluated
            raise exceptions.UserError('The risk is not yet evaluated')
        elif not self.treatment_id:
            if self.env.user != self.owner:
                raise exceptions.UserError('Only the risk owner can proceed with the risk treatment')
            else:
                t = project.sudo().create({
                    'risk_id': self.id,
                    'name': _('Risk Treatment #%s') % self.uuid[:8],
                    'user_id': self.owner.id if self.owner else False
                })
        else:
            t = self.treatment_ids.sorted('create_date', reverse=True)[0]
        process = t.get_or_add_risk_treatment_proc()
        return {
            'name': _('Treatment tasks'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'views': [
                [False, "kanban"], [False, "form"], [False, "tree"],
                [False, "calendar"], [False, "pivot"], [False, "graph"]
            ],
            'context': {
                'search_default_project_id': t.id,
                'search_default_user_id': self.env.user.id,
                'default_project_id': t.id,
                'default_process_id': process.id,
                'default_business_risk_id': self.id,
                'risk_model': self._name
            }
        }

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'active' in init_values and self.active:
            return 'risk_management.mt_business_risk_new'
        elif 'owner' in init_values and self.owner:
            return 'risk_management.mt_business_risk_new'
        elif 'state' in init_values:
            return 'risk_management.mt_business_risk_status'
        return super(BusinessRisk, self)._track_subtype(init_values)

    @api.multi
    def _notification_recipients(self, message, groups):
        groups = super(BusinessRisk, self)._notification_recipients(message, groups)

        for group_name, group_method, group_data in groups:
            group_data['has_button_access'] = True

        return groups


class ProjectRisk(models.Model):
    _name = 'risk_management.project_risk'
    _description = 'Project risk'
    _inherit = ['risk_management.base_identification']

    process_id = fields.Many2one(comodel_name='risk_management.project_process', string='Impacted Process')
    project_id = fields.Many2one(comodel_name='project.project', related='process_id.project_id', string='Project',
                                 readonly=True)
    evaluation_ids = fields.One2many(comodel_name='risk_management.project_risk.evaluation', inverse_name='risk_id',)
    treatment_ids = fields.One2many(comodel_name='project.task', inverse_name='project_risk_id',
                                    string='Treatment tasks',
                                    domain=lambda self: [('project_id', '=', self.project_id.id),
                                                         ('process_id', 'ilike', 'risk treatment')])
    treatment_task_count = fields.Integer(compute='_compute_treatment_count', string='Treatment tasks', store=True)

    @api.depends('latest_level_value', 'treatment_ids')
    def _compute_stage(self):
        for rec in self:
            if rec.active and not rec.latest_level_value:
                rec.mgt_stage = '1'
            elif rec.latest_level_value and not rec.treatment_ids:
                rec.mgt_stage = '2'
            elif rec.treatment_ids:
                rec.mgt_stage = '3'
            else:
                rec.mgt_stage = False

    @api.depends('treatment_ids')
    def _compute_treatment_count(self):
        for rec in self:
            rec.treatment_task_count = len(rec.treatment_ids)

    @api.multi
    def action_add_treatment_task(self):
        for rec in self:
            project = rec.project_id
            treatment_process = project.get_or_add_risk_treatment_proc()
            return {
                'name': _('Treatment tasks'),
                'type': 'ir.actions.act_window',
                'res_model': 'project.task',
                'views': [
                    [False, "kanban"], [False, "form"], [False, "tree"],
                    [False, "calendar"], [False, "pivot"], [False, "graph"]
                ],
                'context': {
                    'search_default_project_id': project.id,
                    'search_default_process_id': treatment_process.id,
                    'search_default_user_id': self.env.user.id,
                    'default_project_id': project.id,
                    'default_process_id': treatment_process.id,
                    'default_project_risk_id': rec.id,
                    'default_user_id': rec.owner.id if rec.owner else False,
                    'risk_model': rec._name
                }
            }

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'active' in init_values and self.active:
            return 'risk_management.mt_project_risk_new'
        elif 'owner' in init_values and self.owner:
            return 'risk_management.mt_project_risk_new'
        elif 'state' in init_values:
            return 'risk_management.mt_project_risk_status'
        return super(ProjectRisk, self)._track_subtype(init_values)

    @api.multi
    def _notification_recipients(self, message, groups):
        groups = super(ProjectRisk, self)._notification_recipients(message, groups)

        for group_name, group_method, group_data in groups:
            group_data['has_button_access'] = True

        return groups


# -------------------------------------- Risk evaluation ----------------------------------


class BaseEvaluation(models.AbstractModel):
    _name = 'risk_management.base_evaluation'
    _inherit = ['risk_management.base_criteria']
    _order = 'create_date desc'

    def _compute_default_review_date(self):
        date = fields.Date.from_string(fields.Date.context_today(self))
        default_review_date = date + datetime.timedelta(days=RISK_EVALUATION_DEFAULT_MAX_AGE)
        return fields.Date.to_string(default_review_date)

    review_date = fields.Date(string='Review Date', default=_compute_default_review_date)
    is_obsolete = fields.Boolean('Is Obsolete', compute='_compute_is_obsolete')
    eval_date = fields.Date(default=lambda self: fields.Date.context_today(self), string='Evaluated on',
                            readonly=True)

    @api.depends('review_date')
    def _compute_is_obsolete(self):
        for rec in self:
            if rec.review_date:
                review_date = fields.Date.from_string(rec.review_date)
                rec.is_obsolete = review_date < fields.Date.from_string(fields.Date.today())
            else:
                rec.is_obsolete = False

    def _search_is_obsolete(self, operator, value):
        if operator not in ('=', "!=") or value not in (0, 1):
            recs = self
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

    @api.depends('risk_id')
    def _compute_eval_value(self):
        for ev in self:
            if ev.risk_type == 'T':
                ev.value = ev.value_threat
            elif ev.risk_type == 'O':
                ev.value = ev.value_opportunity


class BusinessRiskEvaluation(models.Model):
    _name = 'risk_management.business_risk.evaluation'
    _description = 'Business risk evaluation'
    _inherit = ['risk_management.base_evaluation']

    risk_id = fields.Many2one(comodel_name='risk_management.business_risk', string='Risk', required=True)
    risk_type = fields.Selection(related='risk_id.risk_type', readonly=True)
    threshold_value = fields.Integer(related='risk_id.threshold_value', store=True, readonly=True)
    value = fields.Integer('Risk Level', compute='_compute_eval_value', store=True)

    @api.model
    def create(self, vals):
        same_day = self.env['risk_management.business_risk.evaluation'].search([
            ('eval_date', '=', fields.Date.context_today(self))
        ])
        # if another estimation was created the same day, just update it
        if same_day:
            if len(same_day) > 1:
                # Not strictly needed but you never know, there may be more than one record in `same_day`
                same_day[1:].unlink()
            same_day.exists().write(vals)
        else:
            return super(BusinessRiskEvaluation, self).create(vals)


class ProjectRiskEvaluation(models.Model):
    _name = 'risk_management.project_risk.evaluation'
    _description = 'Project risk evaluation'
    _inherit = ['risk_management.base_evaluation']

    risk_id = fields.Many2one(comodel_name='risk_management.project_risk', string='Risk', required=True)
    risk_type = fields.Selection(related='risk_id.risk_type', readonly=True)
    threshold_value = fields.Integer(related='risk_id.threshold_value', store=True, readonly=True)
    value = fields.Integer('Risk Level', compute='_compute_eval_value', store=True)

    @api.model
    def create(self, vals):
        same_day = self.env['risk_management.project_risk.evaluation'].search([
            ('eval_date', '=', fields.Date.context_today(self))
        ])
        # if another estimation was created the same day, just update it
        if same_day:
            if len(same_day) > 1:
                same_day[1:].unlink()
            same_day.exists().write(vals)
        else:
            return super(ProjectRiskEvaluation, self).create(vals)


# -------------------------------------- Risk Treatment -----------------------------------


class BusinessRiskTreatment(models.Model):
    _description = 'Business risk treatment'
    _inherit = ['project.project']

    risk_id = fields.Many2one(comodel_name='risk_management.business_risk', string='Risk')


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
