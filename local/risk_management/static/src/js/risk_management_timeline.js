odoo.define('risk_management.timeline', function (require) {
   'use strict';
   require('web.dom_ready');
   var ajax = require('web.ajax');
   ajax.jsonRpc('/web/dataset/call', 'call', {
                model:  'risk_management.business_risk',
                method: 'read',
                args: [[1, 2]]
            }).then(function (data) {
         console.log(data)
   });
});