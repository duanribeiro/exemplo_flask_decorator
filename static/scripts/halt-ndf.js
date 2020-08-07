var ndfJson = {
    All: false,
}
var toggleSyncFlag = false

function putHaltNDFData(putData) {
    let url = '/fxndf/halt-ndf'
    let data = JSON.stringify({'NDF': putData, })
    let errorMsg = 'ops...! An error has occurred on Halt NDF PUT call!'
    submitData(url, data, errorMsg)
}

function haltAllHandler() {
    toggleSyncFlag = true
    ndfJson.All = $(this).prop("checked")
    putHaltNDFData(ndfJson)
}

function applyToggleLogic(toggleLogic) {
    $('#halt-all').bootstrapToggle( toggleLogic.All? 'on' : 'off', true)
}

function handleHaltButtonText(halt_all) {
    halt_button_id = "#halt-button"
    if (halt_all){
        halt_button_text = "HALT TRADING"
        $(halt_button_id).removeClass("btn-success").addClass("btn-danger")
        $(halt_button_id).html(halt_button_text)
    } else {
        halt_button_text = "RESUME TRADING"
        $(halt_button_id).removeClass("btn-danger").addClass("btn-success")
        $(halt_button_id).html(halt_button_text)
    }
}

function handleSupplierStatus(quoting_ndf) {
    status_supplier_id = "#status_supplier"
    if (quoting_ndf) {
        $(status_supplier_id).removeClass("badge-danger").addClass("badge-success")
    } else {
        $(status_supplier_id).removeClass("badge-success").addClass("badge-danger")
    }
}

function handleFooterTradingStatus(ndf_status) {
    status_ndf_id = "#status_ndf"
    if (ndf_status) {
        $(status_ndf_id).removeClass("badge-danger").addClass("badge-success")
    } else {
        $(status_ndf_id).removeClass("badge-success").addClass("badge-danger")
    }
}

function refreshHaltData() {
    var startTime = new Date().getTime();
    $.get('/fxndf/halt-ndf', data => {
        if (toggleSyncFlag) {
            toggleSyncFlag = false
            return
        }
        ndfJson = data
        applyToggleLogic(ndfJson)
        halt_all = ndfJson.All
        handleHaltButtonText(halt_all)
        handleFooterTradingStatus(halt_all)

        quoting_ndf = data.NDF.All
        handleSupplierStatus(quoting_ndf)
        
    }).then(() => {
        var requestTime = new Date().getTime() - startTime
        var waitTime = requestTime > 1000 ? 1 : 1000 - requestTime
        setTimeout(refreshHaltData, waitTime)
    })
}


$(document).ready(function() {
    applyToggleLogic(ndfJson)
    $("#halt-all").on('change', haltAllHandler)
})

refreshHaltData()