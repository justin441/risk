from odoo import _


def add_risk_activity(env, risk, note, deadline, act_to_close=None, summary=None):
    """
    Create the next activity to be done in the risk management process
    :param env: odoo environment
    :param risk: record: an object representing the risk to which the activity is being added
    :param note: string: Activity note
    :param deadline: string: the deadline of the activity
    :param act_to_close: record: an object representing an activity to close before adding the new one
    :param summary: string: Activity summary
    :return: None
    """
    activity = env['mail.activity']
    res_model_id = env['ir.model']._get_id('risk_management.business_risk')

    # close any preceding activities on business risk
    if act_to_close:
        act_to_close.action_done()
    else:
        activity.search([
            ('res_id', '=', risk.id),
            ('res_model_id', '=', res_model_id),
        ]).action_done()

    # Add a new activity
    risk.write({
        'activity_ids': [(0, False, {
            'res_id': risk.id,
            'res_model_id': res_model_id,
            'activity_type_id': env.ref('risk_management.risk_activity_todo').id,
            'summary': summary,
            'note': '<p>%s</p>' % note,
            'date_deadline': deadline
        })]
    })