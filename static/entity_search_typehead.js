class SearchGroupOrCounterparty {
    constructor(component, group_or_counterparty, entities) {
        this.component = $(component)
        this.searching_groups = group_or_counterparty;
        this.entities = entities; // dict com grupos ou contrapartes
        this.search_map = {};
    }

    init() {
        this.search_map = {};

        // grupos e contrapartes possuem leiautes diferentes. Monta mapa de busca de acordo 
        // com cada uma.
        if (this.searching_groups) {
            $.each(this.entities, (key, value) => {
                let search_str = key + ' ' + value['NameHolding'];
                this.search_map[search_str] = key
            });
        }
        else {
            $.each(this.entities, (key, value) => {
                let search_str = key + ' ' + value['Alias'] + ' ' + value['CounterptyName'];
                this.search_map[search_str] = key
            });
        }

        // search engine abaixo garante que a busca seja feita por qualquer parte do texto.
        var search_engine = new Bloodhound({
            datumTokenizer: function (d) {
                var test = Bloodhound.tokenizers.whitespace(d);
                $.each(test, function (k, v) {
                    let i = 1; // start with 1 insted of 0 because test already contains 1st value
                    while (i < v.length - 1) {
                        test.push(v.substr(i, v.length));
                        i++;
                    }
                    $.unique(test); // removes duplicate values
                });
                return test;
            },
            queryTokenizer: Bloodhound.tokenizers.nonword,
            local: Object.keys(this.search_map),
        });

        this.component.typeahead('destroy');
        this.component.typeahead({
            hint: false,
            highlight: true,
            minLength: 1
        },
        {
            name: 'group_or_counterparty_typehead',
            source: search_engine,
            display: (data) => {
                return this.search_map[data];
            },
            templates: {
                empty: [
                    '<div class="m-1 pl-2"><p>',
                        'Unable to find any entity that match the current query',
                    '</p></div>'
                ].join('\n'),
                suggestion: (datastr) => {
                    let data = this.search_map[datastr];

                    if (this.searching_groups) {
                        return '<div><p><strong>' + data + '</strong></p><p>' + this.entities[data]['NameHolding'] + '</p></div>';
                    }

                    return '<div><p><strong>' + this.entities[data]['Alias'] + '</strong> – ' + data + '</p><p>' + this.entities[data]['CounterpartyName'] + '</p></div>';
                }
            }
        });
    }
}
