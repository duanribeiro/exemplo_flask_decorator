$(document).ready(function() {
    currency_formatter = Intl.NumberFormat('en-US',  {'minimumFractionDigits': 2, 'maximumFractionDigits': 2});
    
    var processFloatNumber = function(num) { return currency_formatter.format(num); }

    var app = new Vue({
        el: '#table_daily_stats',
        delimiters: ["[[", "]]"],
        data: {
            daily_stats_thead: [
                "Date",
                "Number RFQs",
                "Number Deal",
                "Number Rejected",
                "Number Lost",
                "Daily Revenue (BRL)"
            ],
            sorted_currencies: SORTED_CURRENCIES,
            daily_stats: DAILY_STATS,
        },
        computed: {
            daily_stats_data_to_plot() {
                var data_to_plot = {
                    dates: ["2020-01-01"], 
                    number_RFQs_total: [0],
                    number_RFQs_deal: [0],
                    number_RFQs_rejected: [0],
                    number_RFQs_lost: [0],
                }
                if (this.daily_stats.daily_trade_info.length > 0) {
                    data_to_plot = {
                        dates: [], 
                        number_RFQs_total: [],
                        number_RFQs_deal: [],
                        number_RFQs_rejected: [],
                        number_RFQs_lost: [],
                    }
                    for(var i = 0; i < this.daily_stats.daily_trade_info.length; i++){
                        data_to_plot["dates"].push(this.daily_stats.daily_trade_info[i].transact_date)
                        data_to_plot["number_RFQs_total"].push(this.daily_stats.daily_trade_info[i].number_RFQs_total)
                        data_to_plot["number_RFQs_deal"].push(this.daily_stats.daily_trade_info[i].number_RFQs_deal)
                        data_to_plot["number_RFQs_rejected"].push(this.daily_stats.daily_trade_info[i].number_RFQs_rejected)
                        data_to_plot["number_RFQs_lost"].push(this.daily_stats.daily_trade_info[i].number_RFQs_lost)
                    }
                }
                return data_to_plot
            },
        },
        methods:{
            open_transact_info_popup(op_day) {
                window.open('/fxndf/statistics-ndf-day-popup?day=' + op_day, "", "width=800,height=640");
            },
            processCurrency(num) {
                return processFloatNumber(num)
            },
            open_reject_info_popup(op_day) {
                window.open('/fxndf/statistics-ndf-day-reject-popup?day=' + op_day, "", "width=800,height=640");
            },
        },
        beforeMount() {},
    });
    
    var trace_number_RFQ_total = {
        x: app.daily_stats_data_to_plot["dates"],
        y: app.daily_stats_data_to_plot["number_RFQs_total"],
        type: "scatter",
        name: "total", 
        marker: {
            color: "blue"
        }
    };

    var trace_number_RFQ_deal = {
        x: app.daily_stats_data_to_plot["dates"],
        y: app.daily_stats_data_to_plot["number_RFQs_deal"],
        type: "scatter",
        name: "deal",
        marker: {
            color: "green"
        }
    };

    var trace_number_RFQ_rejected = {
        x: app.daily_stats_data_to_plot["dates"],
        y: app.daily_stats_data_to_plot["number_RFQs_rejected"],
        type: "scatter",
        name: "rejected",
        marker: {
            color: "red"
        }
    };

    var trace_number_RFQ_lost = {
        x: app.daily_stats_data_to_plot["dates"],
        y: app.daily_stats_data_to_plot["number_RFQs_lost"],
        type: "scatter",
        name: "lost",
        marker: {
            color: "orange"
        }
    };
    
    var data = [
        trace_number_RFQ_rejected,
        trace_number_RFQ_lost,
        trace_number_RFQ_deal,
        trace_number_RFQ_total, 
    ];

    var tickfont_size = 12;

    var layout = {
        // barmode: "stack",
        yaxis: {
            showgrid: true,
            zeroline: true,
            showline: true,
            mirror: 'ticks',
            gridcolor: '#bdbdbd',
            gridwidth: 1,
            zerolinecolor: '#969696',
            zerolinewidth: 2,
            linecolor: '#636363',
            linewidth: 3,
            tickfont: {
                size: tickfont_size,
                color: 'orange'
            },
        },
        xaxis: {
            tickmode: "array",
            type: 'date',
            tickfont: {
                size: tickfont_size,
                color: 'orange',
            },
            tickformat: "%Y-%m-%d", // "%d %b, %Y", 
            tickangle: 0
        },
        legend: {
            font: {
                size: 14,
                color: 'orange',
            },
        },
        plot_bgcolor:"#222",
        paper_bgcolor:"#222",
        margin: {
            t: 50,
            l: 30,
            r: 30,
            b: 50
        }
    }

    var config = {
        scrollZoom: true,
        displaylogo: false,
        responsive: true,
    }
    
    Plotly.newPlot("stats_chart", data, layout, config);
});