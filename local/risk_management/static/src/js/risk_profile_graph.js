odoo.define('risk_management.risk_profile_graph', function (require) {
    'use strict';
    require('web.dom_ready');
    let ajax = require('web.ajax');
    let ids = $(".page").data('ids');

    const getPieData = function (risks, field) {
        // Returns an object containing the field labels and number of occurrences for each field

        /* An  array of objects containing the count for each value of field param;
        interface [{fieldName: count}, ...];
        example for stage field [{"id. done": 3}, ...]
         */
        let fieldLabelCount = _.countBy(risks, function (risk) {
            return risk[field];
        });
        /*
        An array of arrays [[fieldName, count], ...]
         */
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
        /*
        Returns a random integer between 0 and 255
         */
        return Math.floor(Math.random() * 256);
    };

    const randomRGB = function () {
        /*
        Returns an array of 3 values for rgb
         */
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
        /*
        Renders doughnut chart of risk categories
         */
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
        /*
        Renders doughnut chart of risk management stages
         */
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

    const render_bar_treatment = function (task) {
        /*
        Renders bar chart of risk treatment tasks and their progress
         */
         console.log(data);
    };

    const render_graphs = function (risks) {
        render_doughnut_category(risks);
        render_doughnut_stage(risks);
    };

    return ajax.rpc('/web/dataset/call', {
        model: 'risk_management.business_risk',
        method: 'search_read',
        args: [
            [['id', 'in', ids]],
            ['name', 'risk_type', 'risk_info_category', 'stage', 'treatment_task_id']
        ]
    }).then(function (data) {
        ajax.rpc('/web/dataset/call', {
            model: 'project.task',
            method: 'search_read',
            args: [
                ['|', ['business_risk_id', 'in', ids], ['parent_id.business_risk_id', 'in', ids]],
                ['id', 'name', 'parent_id', 'child_ids', 'stage_id']
            ]
        }).then(function (data) {
            render_bar_treatment(data);
            render_graphs(data);
        });
    })
});