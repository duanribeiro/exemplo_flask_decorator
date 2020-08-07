Vue.component('number_input', {
    props: {
        value: {
            required: true,
            validator: prop => typeof prop === 'number' || prop === null
        },
        thousandseparator: {
            type: Boolean,
            default: false
        },
        multiplier: {
            type: Number,
            default: 1
        },
        decimalplaces: {
            type: Number,
            default: 2
        }
    },
    data: function() {
        return {
            'Value': (this.value !== null && this.value * this.multiplier) || null,
            'DecimalPlacesValueRaw': this.decimalplaces,
            'withFocus': false,
            'Intl': Intl.NumberFormat('en-US', {
                'minimumFractionDigits': this.decimalplaces,
                'maximumFractionDigits': this.decimalplaces,
                'useGrouping': true})
        }
    },
    created: function() {
        var p = this.multiplier;
        while (p >= 10) {
            p = p / 10;
            this.DecimalPlacesValueRaw += 1;
        }

        if (this.value != null)
            this.Value = this.Intl.format(this.value * this.multiplier)
        else
            this.Value = null;
    },
    watch: {
        value: function(val) {
            if (this.withFocus)
                return;

            if (val !== null) {
                this.Value = val * this.multiplier;
            } else {
                this.Value = null
            }

            this.onBlur();
        }
    },
    computed:{
        myValue: {
            get() {
                return this.Value;
            },
            set(v) {
                if (this.withFocus) {
                    if (v != '-') {
                        this.Value = v;
                        this.$emit("input", v / this.multiplier);
                    }
                    else {
                        this.Value = null;
                        this.$emit("input", null);
                    }
                }
            }
        }
    },
    methods: {
        onFocus : function() {
            this.withFocus = true;
        },
        focusOut: function() {
            this.$refs.myinput.blur();
        },
        onBlur: function(){
            var value_clean = String(this.Value).replace(/[^\d.-]/g,'');

            if (value_clean) {
                if (Object.is(value_clean, '-')) {
                    this.$emit("input", null)
                } else {
                    this.Value = this.Intl.format(value_clean);
                    raw_value = (parseFloat(value_clean) / this.multiplier).toFixed(this.DecimalPlacesValueRaw);
                    this.$emit("input", raw_value)
                }
            }
            else {
                this.$emit("input", null)
            }
            
            this.withFocus = false;
        }   
    },
    template: `
        <input type="text"
            v-model="myValue"
            v-on:blur="onBlur()"
            v-on:focus="onFocus()"
            @keyup.enter="focusOut()"
            ref="myinput"
        >`
})
