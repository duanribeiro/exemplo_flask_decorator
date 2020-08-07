init_market_data_panel = function(marketdata_url) {
    app_market_data = new Vue({
        el: '#panel_quotes',
        delimiters: ["<%","%>"],
        data: {
            currency_pairs: null,
            market_base: null,
            market_casado: null
        },
        methods: {
            pooling: function() {
                var startTime = new Date().getTime();
                var self = this
                $.get(marketdata_url, _data => {
                    this.currency_pairs = _data['CurrencyPairs'];
                    this.market_base = _data['Futures'];
                    this.market_casado = _data['Casado'];
                }).fail(function() {
                    // TODO: Fail treatment
                    setTimeout(() => { app_market_data.pooling() }, 3000)
                }).then(() => {
                    var requestTime = new Date().getTime() - startTime
                    var waitTime = requestTime > 1000 ? 1 : 1000 - requestTime
                    setTimeout(() => { this.pooling() }, waitTime)
                })
            },
            sortCurrencies() {
                var sortable = [];
                for (var ccy_pair in this.currency_pairs) {
                    // console.log(this.currency_pairs[ccy_pair]);
                    sortable.push([ccy_pair, this.currency_pairs[ccy_pair].ViewPriority]);
                }

                sortable.sort(function(ccy_a, ccy_b) {
                    return ccy_a[1] - ccy_b[1];
                });

                return sortable;
            }
        },
        beforeMount() {
            this.pooling();
        },
    });
};
