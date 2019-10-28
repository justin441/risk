odoo.define('risk_management.timeline_graph', function (require) {
    'use strict';
    require('web.dom_ready');
    var ajax = require('web.ajax');

    // risks ids
    var risk_ids = $('#risk-ids').data('risk');
    console.log(risk_ids)


    var render_chart = function (risks) {
        Chart.defaults.global.elements.line.tension = 0;
        Chart.defaults.global.elements.line.fill = false;
        var getLabels = function (r) {
            var TICK_LENGTH = 10;
            var evalLength = r.evaluations.length;
            if (evalLength < TICK_LENGTH) {
                let timeGaps = r.evaluations.map(function (evaluation, index, evaluations) {
                    if (evaluation.length === 1) {
                        return 2592000000; // milliseconds in 30 days
                    } else if (index <= evaluations.length - 2) {
                        var date1 = new Date(evaluation.eval_date);
                        var date2 = new Date(evaluations[index + 1].eval_date);
                        return date1 - date2;
                    } else {
                        return 0;
                    }
                });
                let timeGapSum = timeGaps.reduce(function (acc, curr) {
                    return acc + curr;
                });

                var avgTimeGap = timeGapSum / evalLength < 172800000 ? 172800000 : timeGapSum / evalLength; // 172800000 == 48 hours

                var dates = r.evaluations.map(function (evaluation) {
                    return new Date(evaluation.eval_date);
                });
                var distance = TICK_LENGTH - evalLength;
                for (var i = distance; i > 0; i--) {
                    var lastEvalTime = Date.parse(dates[dates.length - 1]) + avgTimeGap;
                    dates.push(new Date(lastEvalTime));
                }
                return dates;
            } else {
                return r.evaluations.map(function (evaluation) {
                    return new Date(evaluation.eval_date);
                })
            }
        };

        var getEvalValues = function (evaluation) {
            return {
                x: new Date(evaluation.eval_date),
                y: evaluation.value
            };
        };

        var getCriteriaScores = function (evaluation) {
            return `D: ${evaluation.detectability}; S: ${evaluation.severity}; O: ${evaluation.occurrence}`;
        };

        var getThresholdValues = function (evaluation) {
            return {
                x: new Date(evaluation.eval_date),
                y: evaluation.threshold_value
            };
        };

        var getThresholdCriteriaScores = function (evaluation) {
            return `D: ${evaluation.threshold_detectability}; S: ${evaluation.threshold_severity}; O: ${evaluation.threshold_occurrence}`;
        };

        var getEvalData = function (evaluation) {
            return {x: evaluation.eval_date, y: evaluation.value};
        };

        var chartOptions = function (r) {
            var risk_name = r.name || 'Risk';
            var chart_label = risk_name + ' Timeline';
            return {
                devicePixelRatio: 2,
                aspectRatio: 2,
                hover: {
                    mode: "nearest",
                },
                tooltips: {
                    mode: 'index',
                    callbacks: {
                        afterLabel: function (tooltipItem, data) {
                            return data.datasets[tooltipItem.datasetIndex].criteriaScores[tooltipItem.index];
                        },
                        title: function (tooltipItem, data) {
                            var date = data.datasets[tooltipItem[0].datasetIndex].data[tooltipItem[0].index].x;
                            return moment().format('ll')
                        }
                    }
                },
                layout: {
                    padding: 10
                },
                legend: {
                    labels: {
                        padding: 40
                    }
                },
                title: {
                    display: true,
                    position: 'bottom',
                    text: chart_label ,
                    fontSize: 14
                },
                scales: {
                    xAxes: [{
                        id: 'time-axis',
                        type: 'time',
                        distribution: 'linear',
                        ticks: {
                            source: 'labels',
                        },
                        time: {
                            displayFormats: {
                                month: 'MMM YYYY'
                            },
                            unit: 'month'
                        }
                    }],
                    yAxes: [{
                        id: 'level-axis',
                        type: 'linear',
                        ticks: {
                            max: 125
                        }
                    }]

                }
            };
        };

        var chartData = function (r) {
            return {
                labels: getLabels(r),
                datasets: [{
                    data: getEvalData(r).map(getEvalValues),
                    label: 'Risk Level',
                    criteriaScores: getEvalData(r).map(getCriteriaScores),
                    borderColor: 'rgb(255, 99, 132)',
                    xAxesID: 'time-axis',
                    yAxesID: 'level-axis'
                },
                    {
                        label: 'Risk Threshold',
                        criteriaScores: getEvalData(r).map(getThresholdCriteriaScores),
                        borderColor: 'rgb(25, 255, 210)',
                        data: getEvalData(r).map(getThresholdValues)
                    }
                ]
            }

        };

        var makeChart = function (ctx, data, options) {
            return new Chart(ctx, {type: 'line', data: data, options: options})
        };

        console.log(risks)
    };
    // get validated evaluations for risks ids
    return ajax.rpc('/web/dataset/call', {
        model: 'risk_management.business_risk.evaluation',
        method: 'search_read',
        args: [
            ['&', ['business_risk_id', 'in', risk_ids], ['is_valid', '=', 1]],
            ['business_risk_id', 'eval_date', 'detectability', 'occurrence', 'severity', 'value',
                'threshold_detectability', 'threshold_occurrence', 'threshold_severity', 'threshold_value']
        ]
    }).then(function (eval_data) {
        /* groups evaluations by risk id and name
        built an array of risk objects implementing this interface:
        {id: risk_id, name: risk_name, evaluations: evaluationObjects[]}

         */
        var risk_data = [];
        risk_ids.forEach(function (risk_id) {
            var risk = {id: risk_id, name: "", evaluations: []};
            eval_data.forEach(function (evaluation) {
                evaluation.eval_date = new Date(evaluation.eval_date + "Z");
                if (evaluation.business_risk_id[0] === risk_id) {
                    risk.evaluations.push(evaluation);
                }
            });
            // Sort each risk evaluations from more recent to older
            risk.evaluations.sort(function (a, b) {
                return b.eval_date - a.eval_date
            });
            risk_data.push(risk);
        });
        // Draw charts
        render_chart(risk_data);

    });
});