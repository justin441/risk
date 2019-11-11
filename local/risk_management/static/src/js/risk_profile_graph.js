odoo.define('risk_management.risk_profile_graph', function (require) {
    'use strict';
    require('web.dom_ready');
    let ajax = require('web.ajax');
    let ids = $(".page").data('ids');

    const getPieData = function (risks, field) {
        let fieldLabelCount = _.countBy(risks, function (risk) {
            return risk[field];
        });
        let labelNumPairs = Object.entries(fieldLabelCount);
        return {
            labels: labelNumPairs.map(function (pair) {
                return pair[0];
            }),
            occurrences: labelNumPairs.map(function (pair) {
                return pair[1]
            })
        }

    };

    const randomNum = function () {
        return Math.floor(Math.random() * 256);
    };

    // Returns an array of 3 values for rgb
    const randomRGB = function () {
        let red = randomNum();
        let green = randomNum();
        let blue = randomNum();
        return `rgb(${red}, ${green}, ${blue})`;
    };

    const pieOptions = {
        title: {
            display: true,
            text: 'Risk Management Stages'
        },
        legend: {
            position: 'right',
            display: true,
            align: 'start'
        }
    };

    const render_doughnut_category = function (risks) {
        let cat_data = getPieData(risks, 'risk_info_category');
        let ctx = $("#per-category-pie");
        let data = {
            labels: cat_data.labels,
            label: "Risk Category",
            datasets: [{
                data: cat_data.occurrences,
                backgroundColor: cat_data.labels.map(function (label) {
                    return randomRGB();
                })
            }]
        };

        return new Chart(ctx, {
            type: 'pie',
            data: data,
            options: pieOptions
        });

    };
    const render_doughnut_stage = function (risks) {
        let stage_data = getPieData(risks, 'stage');
        let ctx = $("#per-stage-pie");
        console.log(stage_data.labels.map(function (label) {
            return randomRGB();
        }));
        let data = {
            labels: stage_data.labels,
            label: 'Stages',
            datasets: [{
                data: stage_data.occurrences,
                backgroundColor: stage_data.labels.map(function (label) {
                    return randomRGB();
                })
            }]
        };

        return new Chart(ctx, {
            type: 'pie',
            data: data,
            options: pieOptions
        });
    };

    const render_bar_treatment = function (risks) {

    };

    const render_graphs = function (risks) {
        console.log(getPieData(risks, 'risk_info_category'));
        console.log(getPieData(risks, 'stage'));
        render_doughnut_category(risks);
        render_doughnut_stage(risks);
    };

    return ajax.rpc('/web/dataset/call', {
        model: 'risk_management.business_risk',
        method: 'search_read',
        args: [
            [['id', 'in', ids]],
            ['id', 'name', 'risk_type', 'risk_info_category', 'stage', 'treatment_task_id']
        ]
    }).then(function (data) {
        let treatment_tasks = [];
        render_graphs(data)
    })
});