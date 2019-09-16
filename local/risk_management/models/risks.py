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
    _rec_name = 'short_name'

    risk_category_id = fields.Many2one(comodel_name='risk_management.risk.category', string='Category',
                                       ondelete='restrict', required=True)
    subcategory = fields.Char(translate=True, string='Sub-category')
    name = fields.Char(translate=True, index=True, copy=False, required=True, string='Name')
    short_name = fields.Char(translate=True, compute='_compute_short_name')
    description = fields.Html(translate=True, string='Description', required=True)
    cause = fields.Html(Translate=True, string='Cause', index=True)
    consequence = fields.Html(translate=True, string='Consequence', index=True)
    control = fields.Html(translate=True, string='Steering / Monitoring')
    action = fields.Html(translate=True, string='Actions / Hedging policy')
    dso_help = fields.Html(translate=True, string='Help with eval.')
    business_risk_ids = fields.One2many(comodel_name='risk_management.business_risk', inverse_name='risk_info_id',
                                        string='Occurrence(Business)')
    occurrences = fields.Integer(string='Occurrences', compute="_compute_occurrences")

    @api.depends('name')
    def _compute_short_name(self):
        for rec in self:
            if rec.name and len(rec.name) >= 64:
                rec.short_name = rec.name.strip()[:61] + '...'
            else:
                rec.short_name = rec.name

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        """Searches risk by name or description"""
        args = [] if args is None else args.copy()
        if not (name == '' and operator == 'ilike'):
            args += ['|', ('name', operator, name), ('description', operator, name)]
        return super(RiskInfo, self)._name_search(name='', args=args, operator='ilike', limit=limit,
                                                  name_get_uid=name_get_uid)

    @api.multi
    def _compute_occurrences(self):
        for risk in self:
            br = self.env['risk_management.business_risk'].search([('risk_info_id', '=', risk.id)])
            risk.occurrences = len(br)


class RiskCriteriaMixin(models.AbstractModel):
    _name = 'risk_management.risk_criteria.mixin'

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

    detectability = fields.Selection(selection=_get_detectability, string='Detectability',
                                     help='What is the ability of the company to detect'
                                          ' this failure (or gain) if it were to occur?')
    occurrence = fields.Selection(selection=_get_occurrence, string='Occurrence',
                                  help='How likely is it for this failure (or gain) to occur?')
    severity = fields.Selection(selection=_get_severity, string='Impact',
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
            if rec.detectability or rec.occurrence or rec.severity:
                rec.value_threat = (int(rec.detectability) or 1) * (int(rec.occurrence) or 1) * (int(rec.severity) or 1)
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
            if rec.detectability or rec.occurrence or rec.severity:
                detectability_opp = opp_detectability_dict.get(rec.detectability, 1)
                rec.value_opportunity = detectability_opp * (int(rec.occurrence) or 1) * (int(rec.severity) or 1)
            else:
                rec.value_opportunity = False


class RiskIdentificationMixin(models.AbstractModel):
    _name = 'risk_management.risk_identification.mixin'
    _inherit = ['risk_management.risk_criteria.mixin', 'mail.thread', 'mail.activity.mixin']
    _mail_post_access = 'read'
    _order = 'priority asc, report_date desc'

    def _compute_default_review_date(self):
        """By default the review date is RISK_REPORT_DEFAULT_MAX_AGE days ahead of the report date"""
        create_date = fields.Date.from_string(fields.Date.context_today(self))
        default_review_date = create_date + datetime.timedelta(days=RISK_REPORT_DEFAULT_MAX_AGE)
        return fields.Date.to_string(default_review_date)

    @api.model
    def _get_stage_select(self):
        return [
            ('1', 'Identification'),
            ('2', 'Id. done'),
            ('3', 'Evaluation'),
            ('4', 'Eval. done'),
            ('5', 'Treatment'),
            ('6', 'Done')
        ]

    uuid = fields.Char(default=lambda self: str(uuid.uuid4()), readonly=True, required=True)
    name = fields.Char(compute='_compute_name', index=True, readonly=True, store=True, rack_visibility="always")
    risk_type = fields.Selection(selection=(('T', 'Threat'), ('O', 'Opportunity')), string='Type', default='T',
                                 required=True, track_visibility="onchange",
                                 states={'4': [('readonly', True)], '5': [('readonly', True)],
                                         '6': [('readonly', True)]})
    risk_info_id = fields.Many2one(comodel_name='risk_management.risk.info', string='Risk', required=True,
                                   states={'2': [('readonly', True)], '3': [('readonly', True)],
                                           '4': [('readonly', True)], '5': [('readonly', True)],
                                           '6': [('readonly', True)]
                                           },
                                   )
    risk_info_name = fields.Char('Risk Title', related='risk_info_id.name', readonly=True, store=True)
    risk_info_category = fields.Char('Risk Category', related='risk_info_id.risk_category_id.name', readonly=True,
                                     store=True)
    risk_info_subcategory = fields.Char('Sub-category', related='risk_info_id.subcategory', readonly=True)
    risk_info_description = fields.Html('Description', related='risk_info_id.description', readonly=True)
    risk_info_cause = fields.Html('Cause', related='risk_info_id.cause', readonly=True)
    risk_info_consequence = fields.Html('Consequence', related='risk_info_id.consequence', readonly=True)
    risk_info_control = fields.Html('Monitoring', related='risk_info_id.control', readonly=True)
    risk_info_action = fields.Html('Hedging strategy', related='risk_info_id.action', readonly=True)
    risk_info_dso = fields.Html('DSO', related='risk_info_id.dso_help', readonly=True)
    report_date = fields.Date(string='Reported On', default=fields.Date.context_today, required=True)
    reported_by = fields.Many2one(comodel_name='res.users', string='Reported by', default=lambda self: self.env.user)
    is_confirmed = fields.Boolean('Confirmed', states={'3': [('readonly', True)], '4': [('readonly', True)],
                                                       '5': [('readonly', True)], '6': [('readonly', True)]},
                                  track_visibility="onchange")
    threshold_value = fields.Integer(compute='_compute_threshold_value', string='Risk threshold', store=True,
                                     track_visibility="onchange")
    latest_level_value = fields.Integer(compute='_compute_latest_eval', string='Risk Level', store=True,
                                        track_visibility="onchange")
    last_evaluator_id = fields.Many2one('res.users', compute='_compute_latest_eval', string='Evaluated by', store=True)
    max_level_value = fields.Integer(default=125, readonly=True, string='Max. Level')
    last_evaluate_date = fields.Date(compute='_compute_latest_eval', string='Last Evaluation Date', store=True)
    review_date = fields.Date(default=_compute_default_review_date, string="Review Date", track_visibility="onchange")
    owner = fields.Many2one(comodel_name='res.users', ondelete='set null', string='Assigned to', index=True,
                            track_visibility="onchange")
    active = fields.Boolean('Active', compute='_compute_active', inverse='_inverse_active', search='_search_active',
                            track_visibility="onchange")
    status = fields.Selection(selection=[('U', 'Unknown status'), ('A', 'Acceptable'), ('N', 'Unacceptable')],
                              compute='_compute_status', string='Status', search='_search_status',
                              track_visibility="onchange")
    state = fields.Selection(selection=_get_stage_select, compute='_compute_stage', string='Stage')
    stage = fields.Char(compute='_compute_stage_str', string='Stage', store=True, copy=False,
                        track_visibility="onchange", translate=True)
    priority = fields.Integer('Priority', compute='_compute_priority')
    treatment_project_id = fields.Many2one('project.project', default=lambda self: self.env.ref(
        'risk_management.risk_treatment_project'), readonly=True, required=True)
    treatment_task_id = fields.Many2one('project.task', string='Treatment Task', compute='_compute_treatment',
                                        inverse='_inverse_treatment', store=True)
    treatment_task_count = fields.Integer(related='treatment_task_id.subtask_count', string='Risk Treatment Tasks')

    @api.onchange('owner')
    def _onchange_owner(self):
        if self.treatment_task_id:
            self.treatment_task_id.user_id = self.owner

    @api.depends('latest_level_value', 'threshold_value')
    def _compute_priority(self):
        risks = self.env[self._name].with_context(active_test=False).search([]).sorted('create_date')
        sorted_risks = risks.sorted(lambda rec: rec.latest_level_value - rec.threshold_value, reverse=True).ids
        for risk in self:
            risk.priority = list(sorted_risks).index(risk.id) + 1

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
            if rec.id and rec.review_date and fields.Date.from_string(
                    fields.Date.context_today(self)) < fields.Date.from_string(rec.review_date):
                rec.active = True
            else:
                rec.active = False

    def _inverse_active(self):
        pass

    @api.multi
    def _search_active(self, operator, value):
        # active_test=False in context serves to prevent an infinite loop in the search function

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

    @api.depends('active', 'latest_level_value', 'threshold_value')
    def _compute_status(self):
        for rec in self:
            if rec.active and rec.latest_level_value and rec.threshold_value:
                if rec.risk_type == 'T':
                    if rec.latest_level_value <= rec.threshold_value:
                        rec.status = 'A'
                    else:
                        rec.status = 'N'
                elif rec.risk_type == 'O':
                    if rec.latest_level_value < rec.threshold_value:
                        rec.status = 'N'
                    else:
                        rec.status = 'A'
            else:
                rec.status = 'U'

    def _search_status(self, operator, value):
        recs = self.with_context(active_test=False)

        def acceptable(rec):
            # is the risk acceptable?
            if rec.risk_type == 'T':
                return rec.active and rec.latest_level_value and rec.threshold_value and \
                       rec.latest_level_value <= rec.threshold_value
            elif rec.risk_type == 'O':
                return rec.active and rec.latest_level_value and rec.threshold_value and \
                       rec.threshold_value <= rec.latest_level_value

        def unacceptable(rec):
            # is the risk unacceptable?
            if rec.risk_type == 'T':
                return rec.active and rec.latest_level_value and rec.threshold_value and \
                       rec.latest_level_value > rec.threshold_value
            elif rec.risk_type == 'O':
                return rec.active and rec.latest_level_value and rec.threshold_value and \
                       rec.threshold_value > rec.latest_level_value

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

    @api.depends('active', 'is_confirmed', 'treatment_task_id', 'treatment_task_count', 'evaluation_ids')
    def _compute_stage(self):
        for risk in self:
            # non-obsolete evaluations
            up_to_date_evals = risk.evaluation_ids and risk.evaluation_ids.filtered(
                lambda ev: not ev.is_obsolete)
            # validated non-obsolete evaluations
            valid_evals = up_to_date_evals and up_to_date_evals.filtered('is_valid')

            if not risk.active:
                risk.state = False
            elif not risk.is_confirmed:
                # risk has been reported but not confirmed
                risk.state = '1'  # still in identification stage

            elif not up_to_date_evals:
                # risk has been confirmed but does not have an non-obsolete evaluation
                risk.state = '2'  # risk identification completed

            elif not valid_evals:
                # there are evaluations of the risk but none has been validated
                risk.state = '3'  # still in evaluation stage

            elif not risk.treatment_task_id or not risk.treatment_task_id.child_ids:
                # there is at least one valid risk evaluation
                risk.state = '4'  # Risk evaluation completed

            elif risk.treatment_task_id.child_ids.filtered(lambda task: not task.stage_id.fold):
                # there is at least one ongoing risk treatment task
                risk.state = '5'  # ongoing risk treatment

            elif not risk.treatment_task_id.child_ids.filtered(lambda task: not task.stage_id.fold):
                # risk treatment done
                risk.state = '6'

    @api.depends('state')
    def _compute_stage_str(self):
        for risk_id in self:
            if not risk_id.state:
                risk_id.stage = 'New'
            elif risk_id.state == '1':
                risk_id.stage = 'Identification'
            elif risk_id.state == '2':
                risk_id.stage = 'Id. Done'
            elif risk_id.state == '3':
                risk_id.stage = 'Evaluation'
            elif risk_id.state == '4':
                risk_id.stage = 'Eval. Done'
            elif risk_id.state == '5':
                risk_id.stage = 'Treatment'
            elif risk_id.state == '6':
                risk_id.stage = 'Done'

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
                'default_project_id': self.treatment_project_id.id,
                'default_target_criterium': 'O'
            }
        }

    def assign_to_me(self):
        if self.status != 'N':
            pass
        else:
            self.sudo().write({'owner': self.env.user.id})

    @api.depends('evaluation_ids')
    def _compute_latest_eval(self):
        for rec in self:
            if not rec.evaluation_ids.exists():
                rec.latest_level_value = 0
                rec.last_evaluate_date = False
                rec.last_evaluator_id = False
            else:
                # get the latest evaluation
                latest_evaluation = rec.evaluation_ids.sorted().exists()[0]
                rec.last_evaluate_date = latest_evaluation.eval_date
                rec.last_evaluator_id = latest_evaluation.create_uid
                if latest_evaluation.is_obsolete:
                    rec.latest_level_value = 0
                elif rec.risk_type == 'T':
                    rec.latest_level_value = latest_evaluation.value_threat
                elif rec.risk_type == 'O':
                    rec.latest_level_value = latest_evaluation.value_opportunity

    @api.depends('treatment_task_ids')
    def _compute_treatment(self):
        for rec in self:
            if rec.treatment_task_ids:
                rec.treatment_task_id = rec.treatment_task_ids[0]

    def _inverse_treatment(self):
        for rec in self:
            if rec.treatment_task_ids:
                task = self.env['project.task'].browse(rec.treatment_task_ids[0].id)
                task.business_risk_id = False
            if rec.treatment_task_id:
                rec.treatment_task_id.business_risk_id = rec

    @api.multi
    def _notification_recipients(self, message, groups):
        groups = super(RiskIdentificationMixin, self)._notification_recipients(message, groups)

        for group_name, group_method, group_data in groups:
            group_data['has_button_access'] = True

        return groups

    @api.model
    def _message_get_auto_subscribe_fields(self, updated_fields, auto_follow_fields=None):
        user_field_lst = super(RiskIdentificationMixin, self)._message_get_auto_subscribe_fields(updated_fields,
                                                                                                 auto_follow_fields=None)
        user_field_lst.append('owner')
        return user_field_lst

    @api.constrains('report_date', 'review_date')
    def _check_review_after_report(self):
        for rec in self:
            if (rec.review_date and rec.report_date) and (rec.review_date < rec.report_date):
                raise exceptions.ValidationError(_('Review date must be after report date'))

    @api.multi
    def write(self, vals):
        if 'active' in vals:
            active = vals.pop('active')
            if active:
                # The risk is being activated
                new_report_date = fields.Date.context_today(self)
                review_date = fields.Date.from_string(new_report_date) + datetime.timedelta(
                    days=RISK_REPORT_DEFAULT_MAX_AGE)
                vals.update({'review_date': fields.Date.to_string(review_date),
                             'report_date': new_report_date,
                             'reported_by': self.env.user.id,
                             'is_confirmed': False,
                             'latest_level_value': False})
            else:
                # The risk is being archived

                # First, make the evaluations obsolete
                self.mapped('evaluation_ids').filtered(lambda ev: not ev.is_obsolete).write({
                    'review_date': fields.Date.context_today(self)
                })
                vals.update({
                    'review_date': fields.Date.context_today(self),
                    'owner': False
                })
                self.with_context(active_test=False).mapped('treatment_task_id').write({'active': active})

        res = super(RiskIdentificationMixin, self).write(vals)
        if res and (vals.get('detectability', False) or vals.get('occurrence', False) or vals.get('severity', False) or
                    vals.get('evaluation_ids', False)):
            self.invalidate_cache(ids=self.ids)
            updated_self = self.env[self._name].browse(self.ids)
            for rec in updated_self:
                if rec.status == 'N':
                    if not rec.treatment_task_id:
                        task = self.env['project.task'].create({
                            'name': 'Treatment for %s' % rec.name,
                            'description': """
                                <p>
                                    The purpose of this task is to select and implement measures to modify %s.
                                    These measures can include avoiding, optimizing, transferring or retaining risk.
                                </p>
                                        """ % rec.name,
                            'project_id': rec.treatment_project_id.id,
                            'priority': '1'
                        })
                        rec.write({
                            'treatment_task_id': task.id
                        })

                    elif not rec.treatment_task_id.active:
                        rec.treatment_task_id.active = True
                elif rec.treatment_task_id and rec.treatment_task_id.active:
                    rec.treatment_task_id.active = False

        activity = self.env['mail.activity']
        ir_model = self.env['ir.model']
        act_deadline_date = datetime.date.today() + datetime.timedelta(days=RISK_ACT_DELAY)
        act_deadline = fields.Date.to_string(act_deadline_date)
        act_type = self.env.ref('risk_management.risk_activity_todo')

        if vals.get('is_confirmed', False):
            # close preceding activities
            activity.search([
                ('res_id', 'in', self.ids),
                ('note', 'ilike', 'Check and confirm the existence of the risk'),
                ('summary', 'ilike', 'Next step in Risk Management:')
            ]).action_done()

            # add next activities
            for rec in self:
                rec.write({'activity_ids': [(0, False, {
                    'res_id': rec.id,
                    'res_model_id': ir_model._get_id(self._name),
                    'activity_type_id': act_type.id,
                    'summary': 'Next step in Risk Management: Evaluation',
                    'note': '<p>Assess the probability of risk occurring and its possible impact,'
                            'as well as the company\'s ability to detect it should it occur.</p>',
                    'date_deadline': act_deadline
                })]})

        return res


class BusinessRisk(models.Model):
    _name = 'risk_management.business_risk'
    _description = 'Business risk'
    _inherit = ['risk_management.risk_identification.mixin']

    company_id = fields.Many2one('res.company', string='Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id,
                                 help="Company affected by the risk")
    ref_asset_id = fields.Reference(selection='_ref_models', string='Affected Asset')
    asset = fields.Char(compute='_compute_asset', store=True)
    asset_desc = fields.Char(compute='_compute_asset', string='Asset Type')
    evaluation_ids = fields.One2many(comodel_name='risk_management.business_risk.evaluation',
                                     inverse_name='business_risk_id')
    treatment_task_ids = fields.One2many('project.task', inverse_name='business_risk_id')

    @api.depends('ref_asset_id')
    def _compute_asset(self):
        """This field is used to search risk on `ref_asset_id`"""
        for rec in self:
            if rec.ref_asset_id:
                rec.asset_desc = rec.ref_asset_id._description
                rec.asset = rec.ref_asset_id._name + ',' + str(rec.ref_asset_id.id)

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'active' in init_values and self.active:
            return 'risk_management.mt_business_risk_new'
        elif 'active' in init_values and not self.active:
            return 'risk_management.mt_business_risk_obsolete'
        elif 'report_date' in init_values and self.report_date == fields.Date.today():
            return 'risk_management.mt_business_risk_new'
        elif 'status' in init_values:
            return 'risk_management.mt_business_risk_status'
        elif 'stage' in init_values:
            return 'risk_management.mt_business_risk_stage'
        return super(BusinessRisk, self)._track_subtype(init_values)

    @api.model
    def _ref_models(self):
        m = self.env['res.request.link'].search([('object', '!=', 'risk_management.business_risk')])
        return [(x.object, x.name) for x in m]

    @api.model
    def create(self, vals):
        # context: no_log, because subtype already handle this
        context = dict(self.env.context, mail_create_nolog=True)
        existing = self.env[self._name].with_context(active_test=False).search(
            [('risk_info_id', '=', vals.get('risk_info_id')),
             ('risk_type', '=', vals.get('risk_type', 'T')),
             ('ref_asset_id', '=', vals.get('ref_asset_id', False)),
             ('company_id', '=', vals.get('company_id', self.env.user.company_id.id))])
        act_deadline_date = datetime.date.today() + datetime.timedelta(days=RISK_ACT_DELAY)
        act_deadline = fields.Date.to_string(act_deadline_date)
        ir_model = self.env['ir.model']
        act_type = self.env.ref('risk_management.risk_activity_todo')

        if existing:
            existing = existing.exists()[0]  # if by chance there is more than one existing, which should not be!
            if not existing.active:
                # the risk was already submitted but is inactive, just reactivate it
                vals.update({'active': True})
                existing.write(vals)
                # add an activity to verify the risk
                self.env['mail.activity'].create({
                    'res_id': existing.id,
                    'res_model_id': ir_model._get_id(self._name),
                    'activity_type_id': act_type.id,
                    'note': '<p>Check and confirm the existence of the risk.</p>',
                    'summary': 'Next step in Risk Management: Confirm',
                    'date_deadline': act_deadline
                })
                return existing
            else:
                raise exceptions.UserError(_("This risk has already been reported."))

        if vals.get('company_id') and not context.get('default_company_id'):
            context['default_company_id'] = vals.get('company_id')

        risk = super(BusinessRisk, self).create(vals)

        # Next activity
        self.env['mail.activity'].create({
            'res_id': risk,
            'res_model_id': ir_model._get_id(self._name),
            'activity_type_id': act_type.id,
            'note': '<p>Check and confirm the existence of the risk.</p>',
            'summary': 'Next step in Risk Management: Confirm',
            'date_deadline': act_deadline
        })

        # add risk channel as follower
        obsolete = self.env.ref('risk_management.mt_business_risk_obsolete')
        status = self.env.ref('risk_management.mt_business_risk_status')
        self.env['mail.followers'].create({
            'res_model': self._name,
            'res_id': risk.id,
            'channel_id': self.env.ref('risk_management.mail_channel_risk_management_risk').id,
            'subtype_ids': [(6, False, [obsolete.id, status.id])]
        })

        return risk


# -------------------------------------- Risk evaluation ----------------------------------


class RiskEvaluationMixin(models.AbstractModel):
    _name = 'risk_management.risk_evaluation.mixin'
    _inherit = ['risk_management.risk_criteria.mixin']
    _order = 'create_date desc'

    def _compute_default_review_date(self):
        date = fields.Date.from_string(fields.Date.context_today(self))
        default_review_date = date + datetime.timedelta(days=RISK_EVALUATION_DEFAULT_MAX_AGE)
        return fields.Date.to_string(default_review_date)

    review_date = fields.Date(string='Review Date', default=_compute_default_review_date)
    is_obsolete = fields.Boolean('Is Obsolete', compute='_compute_is_obsolete')
    eval_date = fields.Date(default=lambda self: fields.Date.context_today(self), string='Evaluated on',
                            readonly=True)
    is_valid = fields.Boolean('Validated')

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


class BusinessRiskEvaluation(models.Model):
    _name = 'risk_management.business_risk.evaluation'
    _description = 'Business risk evaluation'
    _inherit = ['risk_management.risk_evaluation.mixin']

    business_risk_id = fields.Many2one(comodel_name='risk_management.business_risk', string='Risk', required=True,
                                       ondelete='cascade')
    risk_type = fields.Selection(related='business_risk_id.risk_type', readonly=True)
    threshold_value = fields.Integer(related='business_risk_id.threshold_value', store=True, readonly=True)
    value = fields.Integer('Risk Level', compute='_compute_eval_value', store=True)

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

    @api.model
    def create(self, vals):
        same_day_eval = self.env['risk_management.business_risk.evaluation'].search([
            ('eval_date', '=', fields.Date.context_today(self)),
            ('business_risk_id', '=', vals['business_risk_id'])
        ])
        # if another estimation was created the same day, just update it
        if same_day_eval.exists():
            vals.update({'is_valid': False})
            if len(same_day_eval.exists()) > 1:
                # Hardly necessary, but you never know, there may be more than one record in `same_day_eval`
                same_day_eval.exists()[1:].unlink()
            same_day_eval = same_day_eval.exists()
            same_day_eval.write(vals)
            evaluation = same_day_eval.id

        else:
            evaluation = super(BusinessRiskEvaluation, self).create(vals)
            act_deadline_date = datetime.date.today() + datetime.timedelta(days=RISK_ACT_DELAY)
            # add an activity to validate the risk evaluation.
            self.env['mail.activity'].create({
                'res_id': vals.get('business_risk_id'),
                'res_model_id': self.env['ir.model']._get_id('risk_management.business_risk'),
                'activity_type_id': self.env.ref('risk_management.risk_activity_todo').id,
                'summary': 'Next step in Risk Management: Validate Evaluation',
                'note': '<p>Validate the risk assessment.</p>',
                'date_deadline': fields.Date.to_string(act_deadline_date)
            })
        return evaluation

    @api.multi
    def write(self, vals):
        res = super(BusinessRiskEvaluation, self).write(vals)
        if res and vals.get('is_valid', False):
            res_model_id = self.env['ir.model']._get_id('risk_management.business_risk')
            act_deadline_date = datetime.date.today() + datetime.timedelta(days=RISK_ACT_DELAY)
            for rec in self:
                # mark previous activities as done
                self.env['mail.activity'].search(['&', '&', ('res_id', '=', rec.business_risk_id.id),
                                                  ('res_model_id', '=', res_model_id),
                                                  '|',
                                                  ('note', 'ilike', 'Validate the risk assessment'),
                                                  ('note', 'ilike',
                                                   'Assess the probability of risk occurring and its possible impact,'
                                                   'as well as the company\'s ability to detect it should it occur.')
                                                  ]).action_done()
                if rec.value > rec.threshold_value:
                    # add an activity to treat the risk
                    self.env['mail.activity'].create({
                        'res_id': rec.business_risk_id.id,
                        'res_model_id': res_model_id,
                        'activity_type_id': self.env.ref('risk_management.risk_activity_todo').id,
                        'summary': 'Next step in Risk Management: Treat risk',
                        'note': '<p>Select and implement measures to modify risk.</p>',
                        'date_deadline': fields.Date.to_string(act_deadline_date)
                    })

                    if not rec.business_risk_id.treatment_task_id:
                        # create a risk treatment task for the risk being evaluated
                        self.env['project.task'].create({
                            'name': 'Treatment for %s' % rec.business_risk_id.name,
                            'description': """
                                <p>
                                    Select and implement options for modifying %s, and/or improve risk control for
                                    this risk.
                                </p>
                            """ % rec.business_risk_id.name,
                            'priority': '1',
                            'project_id': self.env.ref('risk_management.risk_treatment_project').id,
                            'business_risk_id': rec.business_risk_id.id,
                            'user_id': rec.business_risk_id.owner.id if rec.business_risk_id.owner else False
                        })
        return res
