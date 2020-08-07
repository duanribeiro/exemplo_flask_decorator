// define a global mixin for all Vue instances on RobotFX software!
Vue.mixin({
    methods: {
        enableApplyConfig: function() {
            $("#idApplyChanges").prop("disabled", false)
            $("#idApplyChanges").removeClass("elemento_borrado")
            $("#idApplyChanges").addClass("blinking")
        },
        disableApplyConfig: function() {
            $("#idApplyChanges").prop("disabled", true)
            $("#idApplyChanges").addClass("elemento_borrado")
            $("#idApplyChanges").removeClass("blinking")
       	}
    },
    filters: {
        numberformat: function(value) {
            let currency_formatter = Intl.NumberFormat('en-US',  {'minimumFractionDigits': 2, 'maximumFractionDigits': 2})
            return currency_formatter.format(value)
        },
        currency: function(value) {
            let currency_formatter = Intl.NumberFormat('en-US',  {'minimumFractionDigits': 2, 'maximumFractionDigits': 2})
            return currency_formatter.format(value)
        },
        formatCNPJ: function(cnpj) {
            return cnpj.substr(0, 2) + '.' + cnpj.substr(2, 3) + '.' + cnpj.substr(5, 3) + '/' + cnpj.substr(8, 4) + '-' + cnpj.substr(12)
        }
    }
})


var SimpleApplyConfig = Vue.extend({
    data: function() {
        return {
            modified: false
        }
    },
    watch: {
        modified: function (newModified, oldModified) {
            if (newModified) {
                window.addEventListener("beforeunload", this.handleAreYouSure);
            } else {
                window.removeEventListener("beforeunload", this.handleAreYouSure);
            }
        },
    },
    methods: {
        handleAreYouSure: function(event) {
            event.preventDefault();
            event.returnValue = "";
        },

        enableSimpleApplyConfig: function() {
            this.onchange_value(null)
        },
        disableSimpleApplyConfig: function() {
            this.reset()
            this.disableApplyConfig()
        },
        onchange_value: function(event) {
            if (this.modified) {
                return
            }

            this.modified = true
            this.enableApplyConfig()
        },
        reset: function() {
            if (!this.modified) {
                return
            }

            this.modified = false
        },
        save: function() {
            this.modified && (this.submit() || this.reset() || this.disableApplyConfig())
        },
        validated_string_input: function(str_input) {
             if (typeof(str_input) == 'undefined') {
                return false
             }

             if (typeof(str_input) == 'string' && !str_input) {
                return false
             }

             if (str_input == null) {
                return false
             }

             return true
        },
        fix_time_hhmm_input: function(time_input) {
            // this function fixes a string in formats: 'h:m', 'hh:m', or 'h:mm', which represents
            // a hour:minute time expression!
            let x = time_input.split(':')
            
            if (x[0].length == 1) {
                x[0] = '0' + x[0]
            }

            if (x[1].length == 1) {
                x[1] = '0' + x[1]
            }

            return x[0] + ':' + x[1]
        },
        validated_time_hhmm_input: function(time_input) {
            // this function validate a string in format: 'hh:mm', which represents
            // a hour:minute time expression!
            let x = time_input.split(':')

            if (x.length != 2) {
                return false
            }

            let hours = Number(x[0])

            if (Number.isNaN(hours) || !Number.isInteger(hours)) {
                return false
            }

            if (hours < 0 || hours > 23) {
                return false
            }

            let minutes = Number(x[1])

            if (Number.isNaN(minutes) || !Number.isInteger(minutes)) {
                return false
            }

            if (minutes < 0 || minutes > 59) {
                return false
            }

            return true
        }
    }
})
