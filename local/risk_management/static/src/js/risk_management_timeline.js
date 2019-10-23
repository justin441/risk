odoo.define('risk_management.timeline_graph', function (require) {
    'use strict';
    require('web.dom_ready');
    var ajax = require('web.ajax');
    var risk_ids = $('#risk_ids').data('risk');

    var render_chart = function (risks) {
        console.log(risks);
    }
    return ajax.rpc('/web/dataset/call', {
        model: 'risk_management.business_risk.evaluation',
        method: 'search_read',
        args: [
            ['&', ['business_risk_id', 'in', risk_ids], ['is_valid', '=', 1]],
            ['business_risk_id', 'eval_date', 'detectability', 'occurrence', 'severity', 'value',
                'threshold_detectability', 'threshold_occurrence', 'threshold_severity', 'threshold_value']
        ]
    }).then(function (eval_data) {
        var risk_data = [];
        risk_ids.forEach(function (risk_id) {
            var risk = {id: risk_id, evaluations: []};
            eval_data.forEach(function (evaluation) {
                evaluation.eval_date = new Date(evaluation.eval_date + "Z");
                if (evaluation.business_risk_id[0] === risk_id) {
                    risk.evaluations.push(evaluation);
                }
            });
            risk_data.push(risk);
        });
        render_chart(risk_data);

    });
});