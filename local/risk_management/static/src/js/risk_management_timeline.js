odoo.define('risk_management.timeline_graph', function (require) {
   'use strict';
   require('web.dom_ready');
   var ajax = require('web.ajax');
   var risk_ids = $('#risk_ids').data('risk');
   return ajax.rpc('/web/dataset/call', {
                model:  'risk_management.business_risk.evaluation',
                method: 'search_read',
                args: [['&', ['business_risk_id', 'in', risk_ids], ['is_valid', '=', 1]]]
            }).then(function (data) {     
            console.log(data);
            console.log(d3.time.format('%x')(new Date(1251691200000)));
            });
});