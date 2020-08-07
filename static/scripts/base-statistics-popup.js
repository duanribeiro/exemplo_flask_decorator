currency_formatter = Intl.NumberFormat('en-US',  {'minimumFractionDigits': 2, 'maximumFractionDigits': 2});

var processFloatNumber = function(num) {
    return currency_formatter.format(num);
}

$(document).ready(function() {
    var app = new Vue({
        el: '#vue_main_div',
        delimiters: ["[[", "]]"],
        data: {
            transact_date_info: TRANSACT_DATE_INFO,
        },
        methods: {
            processCurrency: function(num) {
                return processFloatNumber(num)
            }
        },
        computed: {
            transact_date() {
                return this.transact_date_info.transact_date
            },
            number_RFQs_total() {
                return this.transact_date_info.number_RFQs_total
            },
            number_RFQs_deal() {
                return this.transact_date_info.number_RFQs_deal
            },
            number_RFQs_rejected() {
                return this.transact_date_info.number_RFQs_rejected
            },
            number_RFQs_lost() {
                return this.transact_date_info.number_RFQs_lost
            },
            daily_revenue() {
                return this.transact_date_info.daily_revenue
            },
            USD_amount() {
                return this.transact_date_info.USD_amount
            },
            EUR_amount() {
                return this.transact_date_info.EUR_amount
            },
            JPY_amount() {
                return this.transact_date_info.JPY_amount
            },
            most_active_counterparts(){
                return this.transact_date_info.most_active_counterparts
            }
        }
    });

    var data = [{
        values: [app.number_RFQs_deal, app.number_RFQs_rejected, app.number_RFQs_lost],
        labels: ["deal", "rejected", "lost"],
        marker: {
            colors: ["green", "orange", "red"],
        },
        type: "pie",
    }];

    var layout = {
        legend: {
            font: {
                size: 14,
                color: 'orange',
            },
            x: 1,
            y: 0.5,
        },
        plot_bgcolor:"#222",
        paper_bgcolor:"#222",
        margin: {
            t: 30,
            l: 20,
            r: 20,
            b: 0
        }
    };
    
    Plotly.newPlot("stats_chart", data, layout, {responsive: true});
});