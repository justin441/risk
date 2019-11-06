odoo.define('risk_management.timeline_graph', function (require) {
    'use strict';

    require('web.dom_ready');
    let ajax = require('web.ajax');

    // wkhtmltopdf 0.12.5 crash fix.
    // https://github.com/wkhtmltopdf/wkhtmltopdf/issues/3242#issuecomment-518099192
    (function (setLineDash) {
        CanvasRenderingContext2D.prototype.setLineDash = function () {
            if (!arguments[0].length) {
                arguments[0] = [1, 0];
            }
            // Now, call the original method
            return setLineDash.apply(this, arguments);
        };
    })(CanvasRenderingContext2D.prototype.setLineDash);
    Function.prototype.bind = Function.prototype.bind || function (thisp) {
        var fn = this;
        return function () {
            return fn.apply(thisp, arguments);
        };
    };

    // risks ids
    let risk_ids = $('#risk-ids').data('risk');

    const render_chart = function (risks) {
        Chart.defaults.global.elements.line.fill = false;

        const getEvalData = function (risk) {
            // get risk's evaluations
            return risk.evaluations;
        };

        const getEvalValues = function (evaluation) {
            return {
                x: evaluation.eval_date,
                y: evaluation.value
            };
        };

        const getCriteriaScores = function (evaluation) {
            return `D: ${evaluation.detectability}; S: ${evaluation.severity}; O: ${evaluation.occurrence}`;
        };

        const getThresholdValues = function (evaluation) {
            return {
                x: evaluation.eval_date,
                y: evaluation.threshold_value
            };
        };

        const getThresholdCriteriaScores = function (evaluation) {
            return `D: ${evaluation.threshold_detectability}; S: ${evaluation.threshold_severity}; O: ${evaluation.threshold_occurrence}`;
        };

        const getLabels = function (r) {
            /*
            returns an array of dates label for the chart
             */
            let TICK_LENGTH = 10;
            let evalLength = r.evaluations.length;
            if (evalLength < TICK_LENGTH) {
                // The risk has less than less than 10 evaluations; make the label array have 10 dates nevertheless
                let timeGaps = r.evaluations.map(function (evaluation, index, evaluations) {
                    if (evaluation.length === 1) {
                        return 2592000000; // milliseconds in 30 days
                    } else if (index <= evaluations.length - 2) {
                        let date1 = evaluation.eval_date;
                        let date2 = evaluations[index + 1].eval_date;
                        return date1 - date2;
                    } else {
                        return 0;
                    }
                });
                let timeGapSum = timeGaps.reduce(function (acc, curr) {
                    return acc + curr;
                });

                // Average gap between evaluation dates
                let avgTimeGap = (timeGapSum / evalLength) < (3600000 * 48) ? (3600000 * 48) : timeGapSum / evalLength; // 3600000 * 48 ms == 48 hours

                let dates = r.evaluations.map(function (evaluation) {
                    return evaluation.eval_date;
                });
                let distance = TICK_LENGTH - evalLength;
                for (let i = distance; i > 0; i--) {
                    let lastEvalTime = Date.parse(dates[dates.length - 1]) + avgTimeGap;
                    dates.push(new Date(lastEvalTime));
                }
                return dates;
            } else {
                return r.evaluations.map(function (evaluation) {
                    return evaluation.eval_date;
                });
            }
        };

        const chartOptions = function (r) {
            let risk_name = r.name || 'Risk';
            let chart_label = risk_name + ' Timeline';
            return {
                elements: {
                    line: {
                        tension: 0 // disables bezier curves
                    }
                },
                animation: {
                    onComplete: function (animation) {
                        let image = new Image();
                        // let chartCanvas =  $("#risk-" + r.id + "-chart");
                        // image.src = animation.chart.canvas.toDataURL();
                        // $(image).attr("style", $(this).attr("style"));
                        // $(image).attr("style", "position: absolute;");
                        // $(image).attr("width", 950);
                        // $(image).attr("height", 480);
                        //
                        // // Replace the canvas object with its corresponding img-tag
                        // chartCanvas.replaceWith($(image));
                    }
                },
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
                            return moment(date).format('ll')
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
                    text: chart_label,
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
                                week: 'll'
                            },
                            unit: 'week'
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

        const chartData = function (r) {
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

        const chartRisk = function (risk) {
            let ctx = $("#risk-" + risk.id + "-chart");
            return new Chart(ctx, {reponsive: false, type: 'line', data: chartData(risk), options: chartOptions(risk)});
        };

        risks.forEach(function (risk) {

            if (risk.evaluations.length === 0) {
            } else {
                chartRisk(risk);
            }
        })
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
    }).then(function (data) {
        /* groups evaluations by risk's id and name
        built an array of risk objects implementing this interface:
        {id: risk_id, name: risk_name, evaluations: evaluationObjects[]}

         */
        // Firefox 68 - 70 does not seem to be able to parse eval_date into a Date object
        let evalDataStr = JSON.stringify(data);
        let evalData = JSON.parse(evalDataStr);
        let risk_data = [];
        risk_ids.forEach(function (risk_id) {
            let risk = {id: risk_id, name: "", evaluations: []};
            evalData.forEach(function (evaluation) {
                evaluation.eval_date = new Date(evaluation.eval_date);
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