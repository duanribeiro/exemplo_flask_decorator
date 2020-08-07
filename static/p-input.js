Vue.component('p_input', {
                props: ['value', 'multiplier', 'decimalplaces'],
                template: `<input
                  type="text" class="p_input_class"
                  v-bind:value="String(Math.round(value * multiplier * Math.pow(10, decimalplaces)) / Math.pow(10, decimalplaces))"
                  v-on:input="$emit('input', String($event.target.value / multiplier))"
                >`
            })
