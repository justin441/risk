odoo.define('risk_management.risk_profile_graph', function (require) {
    'use strict';
    require('web.dom_ready');
    let ajax = require('web.ajax');
    let ids = $(".page").data('ids');
    console.log(ids);

    return ajax.rpc('/web/dataset/call', {
        model: 'risk_management.business_risk',
        method: 'search_read',
        args: [
            [['id', 'in', ids]],
            ['id', 'name', 'risk_type', 'risk_info_category', 'status', 'stage', 'treatment_task_id']
        ]
    }).then(function (data) {
        let treatment_tasks = [];
        console.log(data);
    })
 });