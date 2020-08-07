function collectionToCSV(keys = []) {
    return (collection = []) => {
        const headers = keys.map((key) => `"${key}"`).join(",");
        const extractKeyValues = (record) => keys.map((key) => `"${record[key]}"`);

        return collection.reduce((csv, record) => {
            return `${csv}\n${extractKeyValues(record)}`.trim();
        }, headers);
    };
}

const exportFieldsSPOT = [
    "quote_req_id",
    "customer_id",
    "customer_str",
    "customer_deal_code",
    "currency",
    "ord_qty",
    "status",
    "fx_product",
    "revenue_brl",
    "symbol",
    "buy",
    "sell",
    "spread",
    "s_cost",
    "validate_kyc",
    "reject_text",
    "settlement_ccy",
    "settlement_brl",
    "settlement_ccy_dn",
    "settlement_brl_dn",
];

const exportFieldsNDF = [
    "quote_req_id",
    "customer_id",
    "customer_str",
    "customer_deal_code",
    "currency",
    "ord_qty",
    "status",
    "fx_product",
    "revenue_brl",
    "symbol",
    "buy",
    "sell",
    "spread",
    "s_cost",
    "validate_kyc",
    "reject_text",
    "maturity",
    "dc",
    "du",
    "pre_brl",
    "cupom_ccy",
    "brl_risk",
    "spread_risk",
    "spread_notional",
    "f_cost",
    "fwd_points",
    "y_ccy",
    "y_ccy_client",
    "f_pfe",
    "validate_isda",
    "adj_maturity",
    "present_value_ccy",
];


function fetchSPOTReport() {
    $.get("/fxspot/statistics-report?startDate=2020-07-06&endDate=2020-07-07", (data) => {
        console.log(data);
        console.log(collectionToCSV(exportFieldsSPOT)(data))
        csvReport = collectionToCSV(exportFieldsSPOT)(data)
    });
}

function fetchNDFReport() {
    $.get("/fxndf/statistics-report", (data) => {
        console.log(data);
        console.log(collectionToCSV(exportFieldsNDF)(data))
    });
}

const fs = require('fs')

let data = "Learning how to write in a file."
  
// Write data in 'Output.txt' . 
fs.writeFile('Output.txt', data, (err) => { 
      
    // In case of a error throw err. 
    if (err) throw err; 
}) 