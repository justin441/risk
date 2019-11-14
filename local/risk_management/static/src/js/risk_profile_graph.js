odoo.define('risk_management.risk_profile_graph', function (require) {
    'use strict';
    require('web.dom_ready');
    let ajax = require('web.ajax');
    let ids = $(".page").data('ids');

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


    const pieOptions = {
        title: {
            display: true,
            text: 'Risk Management Stages',
            position: 'bottom'
        },
        responsive: true,
        legend: {
            position: 'right',
            display: true,
            align: 'start'
        },
        animation: {
            duration: 0
        },
        hover: {
            animationDuration: 0
        },
        responsiveAnimationDuration: 0
    };

    const renderDoughnutCategory = function (risks) {
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
                backgroundColor: cat_data.labels.map(function () {
                    return randomRGB();
                })
            }]
        };
        if(risks.length > 0){
            return new Chart(ctx, {
                type: 'pie',
                data: data,
                options: pieOptions
            });
        } else {
            ctx.parents(".row").remove();
        }

    };

    const renderDoughnutStage = function (risks) {
        /*
        Renders doughnut chart of risk management stages
         */
        let stage_data = getPieData(risks, 'stage');
        let ctx = $("#per-stage-pie");
        let data = {
            labels: stage_data.labels,
            label: 'Stages',
            datasets: [{
                data: stage_data.occurrences,
                backgroundColor: stage_data.labels.map(function () {
                    return randomRGB();
                })
            }]
        };

        if(risks.length > 0){
            return new Chart(ctx, {
                type: 'pie',
                data: data,
                options: pieOptions
            });
        } else {
            ctx.parents('.row').remove();
        }
    };

    const renderBarTreatment = function (tasks) {
        /*
        Renders bar chart of risk treatment tasks' progress
         */

        // parent tasks
        let treatmentTasks = tasks.filter(function (task) {
            return !task.parent_id;
        });

        // sub-tasks
        let treatmentSubTasks = tasks.filter(function (task) {
            return !!task.parent_id;
        });

        // add each sub-task to their corresponding parent task's `child_ids` array attribute
        treatmentTasks = treatmentTasks.map(function (task) {
            task.child_ids = [];
            treatmentSubTasks.forEach(function (tst) {
                if (tst.parent_id[0] === task.id) {
                    task.child_ids.push(tst);
                }
            });
            return task;
        });
        // filter out task whose child_ids attribute is an empy array
        treatmentTasks = treatmentTasks.filter(function(task){
            return task.child_ids.length > 0;
        });
        // bar chart labels
        let labels = treatmentTasks.map(function (task) {
            return task.business_risk_id[1];
        });

        let stageCounts = treatmentTasks.map(function (task) {
            return _.countBy(task.child_ids, function (child) {
                return child.stage_id[1];
            });
        });

        // bar chart datasets
        let datasets = [];

        // common attribute values for all datasets
        let baseDateset = {};

        // Build datasets
        stageCounts.forEach(function (counts, idx, arr) {
            let stages = Object.keys(counts);
            stages.forEach(function (stage) {
                let currentDataset = _.find(datasets, {'label': stage});
                if (currentDataset === undefined) {
                    // the dataset does not exist yet in the datasets array; Construct the new dataset and add it to datasets
                    let dataArr = new Array(arr.length).fill(0);
                    dataArr[idx] = counts[stage];
                    datasets.push(
                        Object.assign({label: stage, data: dataArr, backgroundColor: randomRGB()}, baseDateset)
                    );
                } else {

                    currentDataset.data[idx] = counts[stage];
                }
            })

        });

        let options = {
            title: {
                display: true,
                text: 'Risks Treatments Progress',
                position: 'bottom'
            },
            tooltips: {
                mode: 'index',
                intersect: false
            },
            responsive: true,
            scales: {
                xAxes: [{
                    stacked: true,
                }],
                yAxes: [{
                    stacked: true,
                    ticks: {
                        stepSize: 1,
                        suggestedMax: 10
                    }
                }]
            },
            animation: {
                duration: 0
            },
            hover: {
                animationDuration: 0
            },
            responsiveAnimationDuration: 0
        };

        let ctx = $("#treatment-task-bar");
        
        if(tasks.length > 0){
            return new Chart(ctx, {
                type: 'bar',
                data: {
                    datasets: datasets,
                    labels: labels
                },
                options: options
            });
        } else {
            ctx.parents('.row').remove();
        }
    };

    const renderGraphs = function (risks, tasks) {
        renderDoughnutCategory(risks);
        renderDoughnutStage(risks);
        renderBarTreatment(tasks)
    };

    return ajax.rpc('/web/dataset/call', {
        model: 'risk_management.business_risk',
        method: 'search_read',
        args: [
            [['id', 'in', ids]],
            ['name', 'risk_type', 'risk_info_category', 'stage', 'treatment_task_id']
        ]
    }).then(function (risk_data) {
        ajax.rpc('/web/dataset/call', {
            model: 'project.task',
            method: 'search_read',
            args: [
                ['|', ['business_risk_id', 'in', ids], ['parent_id.business_risk_id', 'in', ids]],
                ['id', 'business_risk_id', 'name', 'parent_id', 'child_ids', 'stage_id']
            ]
        }).then(function (task_data) {
            renderGraphs(risk_data, task_data);
        });
    })
});