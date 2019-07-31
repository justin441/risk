import datetime
import uuid
import logging

from odoo import models, fields, api, exceptions, _

RISK_REPORT_DEFAULT_MAX_AGE = 90
RISK_ACT_DELAY = 15
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
        for category in self:
            category.risk_count = len(category.risk_info_ids)


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
        for risk in self:
            risk.business_occurrences = len(risk.business_risk_ids)


class RiskCriteriaMixin(models.AbstractModel):
    _name = 'risk_management.risk_criteria.mixin'

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

    detectability = fields.Selection(selection=_get_detectability, string='Detectability', default='1', required=True,
                                     help='What is the ability of the company to detect'
                                          ' this failure (or gain) if it were to occur?')
    occurrence = fields.Selection(selection=_get_occurrence, default='1', string='Occurrence', required=True,
                                  help='How likely is it for this failure (or gain) to occur?')
    severity = fields.Selection(selection=_get_severity, default='1', string='Impact', required=True,
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
        threat case where the higher the ability to detect the threat occurrence the less the risk factor
        """
        inv_detectability_score = [str(x) for x in range(1, 6)]
        opp_detectability_dict = dict((x, y) for x, y in zip(inv_detectability_score, range(5, 0, -1)))
        for rec in self:
            if rec.detectability and rec.occurrence and rec.severity:
                detectability_opp = opp_detectability_dict.get(rec.detectability)
                rec.value_opportunity = detectability_opp * int(rec.occurrence) * int(rec.severity)
            else:
                rec.value_opportunity = False


class RiskIdentificationMixin(models.AbstractModel):
    _name = 'risk_management.risk_identification.mixin'
    _inherit = ['risk_management.risk_criteria.mixin', 'mail.thread', 'mail.activity.mixin']
    _mail_post_access = 'read'
    _order = 'priority desc, report_date desc'

    def _compute_default_review_date(self):

        """By default the review date is RISK_REPORT_DEFAULT_MAX_AGE days from the report date"""
        create_date = fields.Date.from_string(self.report_date or fields.Date.today())
        default_review_date = create_date + datetime.timedelta(days=RISK_REPORT_DEFAULT_MAX_AGE)
        return fields.Date.to_string(default_review_date)

    @api.model
    def _get_stage_select(self):
        return [
            ('1', 'Identification'),
            ('2', 'Id. done'),
            ('3', 'Evaluation'),
            ('4', 'Eval. done'),
            ('5', 'Ongoing treatment'),
            ('6', 'Done')
        ]

    uuid = fields.Char(default=lambda self: str(uuid.uuid4()), readonly=True, required=True)
    name = fields.Char(compute='_compute_name', index=True, readonly=True, store=True, rack_visibility="always")
    risk_type = fields.Selection(selection=(('T', 'Threat'), ('O', 'Opportunity')), string='Type', default='T',
                                 require=True, track_visibility="onchange", states={'A': 'readonly', 'N': 'readonly'})
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
    is_confirmed = fields.Boolean('Confirmed', states={'A': 'readonly', 'N': 'readonly'},
                                  groups=['risk_management.group_risk_manager'], track_visibility="onchange")
    threshold_value = fields.Integer(compute='_compute_threshold_value', string='Risk threshold', store=True,
                                     track_visibility="onchange")
    latest_level_value = fields.Integer(compute='_compute_latest_eval', string='Risk Level', store=True,
                                        track_visibility="onchange")
    last_evaluator_id = fields.Many2one('res.users', compute='_compute_latest_eval', string='Evaluated by')
    max_level_value = fields.Integer(default=125, readonly=True, string='Max. Level')
    last_evaluate_date = fields.Date(compute='_compute_latest_eval', string='Last Evaluation Date')
    review_date = fields.Date(default=_compute_default_review_date, string="Review Date", track_visibility="onchange")
    owner = fields.Many2one(comodel_name='res.users', ondelete='set null', string='Assigned to', index=True,
                            track_visibility="onchange")
    active = fields.Boolean(compute='_compute_active', inverse='_inverse_active', search='_search_active',
                            track_visibility="onchange")
    state = fields.Selection(selection=[('U', 'Unknown status'), ('A', 'Acceptable'), ('N', 'Unacceptable')],
                             compute='_compute_status', string='Status', search='_search_status',
                             track_visibility="onchange")
    mgt_stage = fields.Selection(selection=_get_stage_select, compute='_compute_stage', string='Stage',
                                 store=True, track_visibility="onchange")
    priority = fields.Char('Priority', compute='_compute_priority', store=True)

    @api.depends('latest_level_value')
    def _compute_priority(self):
        for risk in self:
            risks = self.search([]).sorted(lambda rec: rec.latest_level_value - rec.threshold_value, reverse=True)
            index = list(risks).index(risk) + 1
            risk.priority = '#' + str(index)

    @api.depends('uuid')
    def _compute_name(self):
        for rec in self:
            rec.name = _('risk ') + '#%s' % rec.uuid[:8]

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
            if rec.review_date and fields.Date.from_string(fields.Date.context_today(self)) < fields.Date.from_string(
                    rec.review_date):
                rec.active = True
            else:
                rec.active = False

    def _inverse_active(self):
        for rec in self.filtered('report_date'):
            rec.review_date = fields.Date.context_today(self)
            rec.is_confirmed = False

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

    @api.onchange('owner')
    def _onchange_owner(self):
        if self.treatment_task_id:
            self.treatment_task_id.user_id = self.owner

    @api.depends('active', 'is_confirmed', 'treatment_task_id', 'treatment_task_count', 'evaluation_ids')
    def _compute_stage(self):
        for risk in self:
            up_to_date_evals = risk.evaluation_ids.filtered(
                lambda ev: not ev.is_obsolete) if risk.evaluation_ids else False
            valid_evals = up_to_date_evals.filtered('is_valid')
            if not risk.active:
                risk.mgt_stage = False
            elif not risk.is_confirmed:
                # risk has been reported but not confirmed
                risk.mgt_stage = '1'  # still in identification stage

            elif not up_to_date_evals:
                # risk has been confirmed but has not yet been evaluated
                risk.mgt_stage = '2'  # risk identification completed

            elif not valid_evals:
                # there are evaluations of the risk but no valid one yet
                risk.mgt_stage = '3'  # still in evaluation stage

            elif not risk.treatment_task_id:
                # there is at least one valid risk evaluation
                risk.mgt_stage = '4'  # Risk evaluation completed

            elif risk.treatment_task_count:
                # there is at least one ongoing risk treatment task
                risk.mgt_stage = '5'  # ongoing risk treatment

            elif risk.treatment_task_id.child_ids and not risk.treatment_task_count:
                # risk treatment done
                risk.mgt_stage = '6'

    @api.onchange('mgt_stage')
    def _onchange_mgt_stage(self):
        activity = self.env['mail.activity']
        act_deadline_date = datetime.date.today() + datetime.timedelta(days=RISK_ACT_DELAY)
        act_deadline = fields.Date.to_string(act_deadline_date)

        for risk in self:
            if risk.mgt_stage == '1':
                act_confirm = activity.search([
                    ('res_id', '=', risk.id),
                    ('summary', 'like', 'Check and confirm the existence of the risk')
                ])
                if not act_confirm:
                    # next activity
                    risk.sudo().write({
                        "activity_ids": [(0, 0, {
                            'res_id': risk.id,
                            'res_model_id': self.env.ref(self._name),
                            'activity_type_id': self.env.ref('risk_management.risk_activity_todo'),
                            'summary': 'Check and confirm the existence of the risk',
                            'date_deadline': act_deadline
                        })]
                    })
            elif risk.mgt_stage == '2':
                # close preceding activity
                activity.search([
                    ('res_id', '=', risk.id),
                    ('summary', 'like', 'Check and confirm the existence of the risk')
                ]).action_feedback('<strong>Risk Confirmed</strong>')

                act_assess = activity.search(['&',
                                              ('res_id', '=', risk.id),
                                              ('summary', 'like',
                                               'Assess the probability of risk occurring and its possible impact,'
                                               'as well as the company\'s ability to detect it should it occur.'),
                                              ])
                if not act_assess:
                    # next activity
                    risk.write({
                        "activity_ids": [(0, 0, {
                            'res_id': risk.id,
                            'res_model_id': self.env.ref(self._name),
                            'activity_type_id': self.env.ref('risk_management.risk_activity_to_do'),
                            'summary': 'Assess the probability of risk occurring and its possible impact,'
                                       'as well as the company\'s ability to detect it should it occur.',
                            'date_deadline': act_deadline
                        })]
                    })
            elif risk.mgt_stage == '3':
                act_valid = activity.search(['&',
                                             ('res_id', '=', risk.id),
                                             ('summary', 'like', 'Validate the risk assessment')
                                             ])
                if not act_valid:
                    # next activity
                    risk.write({
                        "activity_ids": [(0, 0, {
                            'res_id': risk.id,
                            'res_model_id': self.env.ref(self._name),
                            'activity_type_id': self.env.ref('risk_management.risk_activity_to_do'),
                            'summary': 'Validate the risk assessment',
                            'date_deadline': act_deadline
                        })]
                    })
            elif risk.mgt_stage == '4':
                # close preceding activities
                activity.search(['&',
                                 ('res_id', '=', risk.id),
                                 '|',
                                 ('summary', 'like', 'Validate the risk assessment'),
                                 ('summary', 'like',
                                  'Assess the probability of risk occurring and its possible impact,'
                                  'as well as the company\'s ability to detect it should it occur.'),
                                 ]).action_feedback('<strong>Risk evaluation done</strong>')

                act_treat = activity.search([
                    ('res_id', '=', risk.id),
                    ('summary', 'like', 'Select and implement measures to modify risk')
                ])
                if not act_treat:
                    # next activity
                    if self.state == 'N':
                        risk.write({
                            "activity_ids": [(0, 0, {
                                'res_id': risk.id,
                                'res_model_id': self.env.ref(self._name),
                                'activity_type_id': self.env.ref('risk_management.risk_activity_to_do'),
                                'summary': 'Select and implement measures to modify risk',
                                'date_deadline': act_deadline
                            })]
                        })
            elif risk.mgt_stage == '6':
                # close preceding activities
                activity.search([
                    ('res_id', '=', risk.id),
                    ('summary', 'like', 'Select and implement measures to modify risk')
                ]).action_feedback('<strong>Risk Risk treatment done</strong>')

                act_reassess = activity.search([
                    ('res_id', '=', risk.id),
                    ('summary', 'like', 'Reassess the  risk to make sure that risk treatment has been effective')
                ])
                if not act_reassess:
                    risk.write({
                        "activity_ids": [(0, 0, {
                            'res_id': risk.id,
                            'res_model_id': self.env.ref(self._name),
                            'activity_type_id': self.env.ref('risk_management.risk_activity_to_do'),
                            'summary': 'Reassess the  risk to make sure that risk treatment has been effective',
                            'date_deadline': act_deadline
                        })]
                    })

    @api.multi
    def update_report(self, report_date=None, reporter=None):
        """Reactivate an old risk when it's re-reported"""
        self.ensure_one()
        if self.active:
            return
        new_report_date = report_date or fields.Date.context_today(self)
        new_reporter = reporter or self.env.user.id
        review_date = fields.Date.from_string(new_report_date) + datetime.timedelta(days=RISK_REPORT_DEFAULT_MAX_AGE)
        self.sudo().write({'review_date': fields.Date.to_string(review_date),
                           'report_date': new_report_date,
                           'reported_by': new_reporter,
                           'is_confirmed': False})

    @api.multi
    def toggle_active(self):
        for rec in self:
            if rec.active:
                rec._inverse_active()
            else:
                rec.update_report()

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
    def _compute_latest_eval(self):
        for rec in self:
            if not rec.evaluation_ids.exists():
                rec.latest_level_value = False
                rec.last_evaluate_date = False
                rec.last_evaluator_id = False
            else:
                # get the latest evaluation
                latest_evaluation = rec.evaluation_ids.sorted()[0]
                rec.last_evaluate_date = latest_evaluation.eval_date
                rec.last_evaluator_id = latest_evaluation.create_uid
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
    _inherit = ['risk_management.risk_identification.mixin']
    _sql_constraints = [
        (
            'unique_risk_process',
            'UNIQUE(risk_info_id, business_process_id, risk_type)',
            'This risk has already been reported.'
        )
    ]

    business_process_id = fields.Many2one(comodel_name='risk_management.business_process', string='Impacted Process',
                                          states={'A': 'readonly', 'N': 'readonly'})
    evaluation_ids = fields.One2many(comodel_name='risk_management.business_risk.evaluation',
                                     inverse_name='business_risk_id')
    treatment_task_id = fields.Many2one('project.task', compute='_compute_treatment_task_id', store=True)
    treatment_task_count = fields.Integer(related='treatment_task_id.subtask_count', string='Risk Treatment Tasks',
                                          store=True)

    @api.depends('state', 'mgt_stage')
    def _compute_treatment_task_id(self):
        """Adds a Task to treat the risk as soon as the risk level becomes unacceptable """
        for rec in self:
            if rec.mgt_stage >= '4' and rec.state == 'N':
                if not rec.treatment_task_id:
                    rec.treatment_task_id = self.env['project.task'].sudo().create({
                        'name': 'Treatment for %s' % rec.name,
                        'description': """
                                <p>
                                    The purpose of this task is to select and implement measures to modify the %s. 
                                    These measures can include avoiding, optimizing, transferring or retaining risk
                                </p>""" % rec.name,
                        'project_id': rec.business_process_id.risk_treatment_project_id.id,
                    })

    @api.multi
    def get_treatments_view(self):
        """returns the treatment tasks view.
        """
        self.ensure_one()
        return {
            'name': _('Treatment Tasks'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'views': [
                [False, "kanban"], [False, "form"], [False, "tree"],
                [False, "calendar"], [False, "pivot"], [False, "graph"]
            ],
            'context': {
                'search_default_parent_id': self.treatment_task_id.id,
                'default_parent_id': self.treatment_task_id.id,
                'default_business_risk_id': self.id,
                'default_project_id': self.business_process_id.risk_treatment_project_id.id,
                'default_target_criterium': 'O'
            }
        }

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'active' in init_values and self.active:
            return 'risk_management.mt_business_risk_new'
        elif 'report_date' in init_values and self.report_date == fields.Date.today():
            return 'risk_management.mt_business_risk_new'
        elif 'state' in init_values:
            return 'risk_management.mt_business_risk_status'
        elif 'mgt_stage' in init_values:
            return 'risk_management.mt_business_risk_stage'
        return super(BusinessRisk, self)._track_subtype(init_values)

    @api.multi
    def _notification_recipients(self, message, groups):
        groups = super(BusinessRisk, self)._notification_recipients(message, groups)

        for group_name, group_method, group_data in groups:
            group_data['has_button_access'] = True

        return groups

    @api.model
    def _message_get_auto_subscribe_fields(self, updated_fields, auto_follow_fields=None):
        user_field_lst = super(BusinessRisk, self)._message_get_auto_subscribe_fields(updated_fields,
                                                                                      auto_follow_fields=None)
        user_field_lst.append('owner')
        return user_field_lst

    @api.model
    def create(self, vals):
        # context: no_log, because subtype already handle this
        context = dict(self.env.context, mail_create_nolog=True)
        existing = self.env['risk_management.business_risk'].search(
            [('active', '=', True), ('risk_info_id', '=', vals.get('risk_info_id', False)),
             ('business_process_id', '=', vals.get('business_process_id', False)),
             ('risk_type', '=', vals.get('risk_type', False))])
        if existing:
            existing.exists()[0].update_report()
            return existing.exists()[0].id
        else:
            if vals.get('business_process_id') and not context.get('default_business_process_id'):
                context['default_business_process_id'] = vals.get('business_process_id')
        risk = super(BusinessRisk, self).create(vals)
        return risk


# -------------------------------------- Risk evaluation ----------------------------------


class RiskEvaluationMixin(models.AbstractModel):
    _name = 'risk_management.risk_evaluation.mixin'
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
    is_valid = fields.Boolean('Valid', groups=['risk_management.group_manager'])

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

    @api.depends('business_risk_id',
                 'detectability',
                 'occurrence',
                 'severity')
    def _compute_eval_value(self):
        for rec in self:
            if rec.risk_type == 'T':
                rec.value = rec.value_threat
            elif rec.risk_type == 'O':
                rec.value = rec.value_opportunity


class BusinessRiskEvaluation(models.Model):
    _name = 'risk_management.business_risk.evaluation'
    _description = 'Business risk evaluation'
    _inherit = ['risk_management.risk_evaluation.mixin']

    business_risk_id = fields.Many2one(comodel_name='risk_management.business_risk', string='Risk', required=True)
    risk_type = fields.Selection(related='business_risk_id.risk_type', readonly=True)
    threshold_value = fields.Integer(related='business_risk_id.threshold_value', store=True, readonly=True)
    value = fields.Integer('Risk Level', compute='_compute_eval_value', store=True)

    @api.model
    def create(self, vals):
        same_day = self.env['risk_management.business_risk.evaluation'].search([
            ('eval_date', '=', fields.Date.context_today(self)),
            ('business_risk_id', '=', vals['business_risk_id'])
        ])
        # if another estimation was created the same day, just update it
        if same_day:
            if len(same_day) > 1:
                # Hardly necessary, but you never know, there may be more than one record in `same_day`
                same_day[1:].unlink()
            same_day.exists().write(vals)
        else:
            return super(BusinessRiskEvaluation, self).create(vals)
