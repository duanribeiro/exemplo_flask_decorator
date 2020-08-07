var quotingJson = {
    Spot: {All: false,},
    NDF: {All: false,},
}

var toggleSyncFlag = false

function parseButtonLogic(quotingIn) {
    var res = {}
    res.all = quotingIn.Spot.All && quotingIn.NDF.All
    res.spot = quotingIn.Spot.All
    res.ndf = quotingIn.NDF.All
    return res
}

function putHaltQuotingData(putData) {
    let url = '/fxsupplier/halt-quoting'
    let data = JSON.stringify({'Quoting': putData, })
    let errorMsg = 'ops...! An error has occurred on Halt Quoting PUT call!'
    submitData(url, data, errorMsg)
}

function haltAllHandler() {
    quotingJson.Spot.All = $(this).prop("checked")
    quotingJson.NDF.All = $(this).prop("checked")
    applyToggleLogic(parseButtonLogic(quotingJson))
    putHaltQuotingData(quotingJson)
}

function haltSPOTHandler() {
    var partialQuoting = {}
    partialQuoting.Spot = {}
    partialQuoting.Spot.All = $(this).prop("checked")
    jQuery.extend(quotingJson, partialQuoting)
    applyToggleLogic(parseButtonLogic(quotingJson))
    putHaltQuotingData(partialQuoting)
}

function haltNDFHandler() {
    var partialQuoting = {}
    partialQuoting.NDF = {}
    partialQuoting.NDF.All = $(this).prop("checked")
    jQuery.extend(quotingJson, partialQuoting)
    applyToggleLogic(parseButtonLogic(quotingJson))
    putHaltQuotingData(partialQuoting)
}

function applyBoolToToggle(toggleId, boolIn) {
    $(toggleId).bootstrapToggle( boolIn ? 'on' : 'off', true)
}

function applyToggleLogic(toggleLogic) {
    applyBoolToToggle('#halt-all', toggleLogic.all)
    applyBoolToToggle('#halt-spot', toggleLogic.spot)
    applyBoolToToggle('#halt-ndf', toggleLogic.ndf)
}

function handleHaltQuotingButtonText(halt_all) {
    halt_button_id = "#halt-quoting"
    if (halt_all){
        halt_button_text = "HALT QUOTING"
        $(halt_button_id).removeClass("btn-success").addClass("btn-danger")
        $(halt_button_id).html(halt_button_text)
    } else {
        halt_button_text = "RESUME QUOTING"
        $(halt_button_id).removeClass("btn-danger").addClass("btn-success")
        $(halt_button_id).html(halt_button_text)
    }
}

function handleFXProductStatus(fxproduct, status) {
    status_fxproduct_id = "#status_" + fxproduct
    if (fxproduct === "spot" || fxproduct === "ndf") {
        if (status) {
            $(status_fxproduct_id).removeClass("badge-danger").addClass("badge-success")
        } else {
            $(status_fxproduct_id).removeClass("badge-success").addClass("badge-danger")
        }
    } 
}

function handleFooterTradingStatus(spot_status, ndf_status) {
    handleFXProductStatus("spot", spot_status)
    handleFXProductStatus("ndf", ndf_status)
}


function refreshHaltData() {
    var startTime = new Date().getTime();
    $.get('/fxsupplier/halt-quoting', data => {
        if (toggleSyncFlag) {
            toggleSyncFlag = false
            return
        }
        quotingJson = data
        quotingJsonParsed = parseButtonLogic(quotingJson)
        halt_all = quotingJsonParsed.all
        spot_status = quotingJsonParsed.spot
        ndf_status = quotingJsonParsed.ndf
        applyToggleLogic(quotingJsonParsed)
        handleHaltQuotingButtonText(halt_all)
        handleFooterTradingStatus(spot_status, ndf_status)
    }).then(() => {
        var requestTime = new Date().getTime() - startTime
        var waitTime = requestTime > 1000 ? 1 : 1000 - requestTime
        setTimeout(refreshHaltData, waitTime)
    })
}

$(document).ready(function() {
    applyToggleLogic(parseButtonLogic(quotingJson))
    $("#halt-all").on('change', haltAllHandler)
    $("#halt-spot").on('change', haltSPOTHandler)
    $("#halt-ndf").on('change', haltNDFHandler)
})

refreshHaltData()