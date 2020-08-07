var spotJson = {
    D0: false,
    D1: false,
    D2: false,
}
var toggleSyncFlag = false

function parseButtonLogic(tradingSPOT) {
    var res = {}
    res.all = tradingSPOT.D0 && tradingSPOT.D1 && tradingSPOT.D2
    res.d0 = tradingSPOT.D0
    res.d1 = tradingSPOT.D1
    res.d2 = tradingSPOT.D2
    return res
}

function putHaltSpotData(putData) {
    let url = '/fxspot/halt-spot'
    let data = JSON.stringify({'SPOT': putData, })
    let errorMsg = 'ops...! An error has occurred on Halt SPOT PUT call!'
    submitData(url, data, errorMsg)
}

function isCashLimiitsInitialized(callback) {
    $.getJSON( "/fxspot/check_spot_limits_initialized", function(data) {
        callback(Boolean(data));
    });
};

function haltChangeState(elem, spotJson, partialSpot) {
    function change_state() {
        applyToggleLogic(parseButtonLogic(spotJson))
        putHaltSpotData(partialSpot)
    }

    // se usuário estiver tentando dar um resume, checa se cash limits já foi 
    // inicializado, caso contrario não deixa.
    if ($(elem).is(':checked')) {
        isCashLimiitsInitialized(function(is_ready) {
            if (is_ready)
                change_state(spotJson, spotJson);
            else
                $('#spot_limits_alert').modal('show');
        });
    }
    else
        change_state(spotJson, spotJson);
}

function haltAllHandler() {
    toggleSyncFlag = true;
    spotJson.D0 = $(this).prop("checked")
    spotJson.D1 = $(this).prop("checked")
    spotJson.D2 = $(this).prop("checked")
    haltChangeState(this, spotJson, spotJson);
}

function haltD0Handler() {
    toggleSyncFlag = true;
    var partialSpot = {}
    partialSpot.D0 = $(this).prop("checked")
    jQuery.extend(spotJson, partialSpot)
    haltChangeState(this, spotJson, partialSpot)
}

function haltD1Handler() {
    toggleSyncFlag = true;
    var partialSpot = {}
    partialSpot.D1 = $(this).prop("checked")
    jQuery.extend(spotJson, partialSpot)
    haltChangeState(this, spotJson, partialSpot)
}

function haltD2Handler() {
    toggleSyncFlag = true;
    var partialSpot = {}
    partialSpot.D2 = $(this).prop("checked")
    jQuery.extend(spotJson, partialSpot)
    haltChangeState(this, spotJson, partialSpot)
}

function applyBoolToToggle(toggleId, boolIn) {
    $(toggleId).bootstrapToggle( boolIn ? 'on' : 'off', true)
}

function applyToggleLogic(toggleLogic) {
    applyBoolToToggle('#halt-all', toggleLogic.all)
    applyBoolToToggle('#halt-d0', toggleLogic.d0)
    applyBoolToToggle('#halt-d1', toggleLogic.d1)
    applyBoolToToggle('#halt-d2', toggleLogic.d2)
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

function handleSpotDnStatus(n, spot_dn) {
    status_dn_id = "#status_d" + n
    if (spot_dn) {
        $(status_dn_id).removeClass("badge-danger").addClass("badge-success")
    } else {
        $(status_dn_id).removeClass("badge-success").addClass("badge-danger")
    }
}

function handleSupplierStatus(quoting_spot) {
    status_supplier_id = "#status_supplier"
    if (quoting_spot) {
        $(status_supplier_id).removeClass("badge-danger").addClass("badge-success")
    } else {
        $(status_supplier_id).removeClass("badge-success").addClass("badge-danger")
    }
}

function handleFooterTradingStatus(spot_d0, spot_d1, spot_d2) {
    handleSpotDnStatus(0, spot_d0)
    handleSpotDnStatus(1, spot_d1)
    handleSpotDnStatus(2, spot_d2)
}

function refreshHaltData() {
    var startTime = new Date().getTime();
    $.get('/fxspot/halt-spot', data => {
        if (toggleSyncFlag) {
            toggleSyncFlag = false
            return
        }
        spotJson = data
        spotJsonParsed = parseButtonLogic(spotJson)
        applyToggleLogic(spotJsonParsed)
        halt_all = spotJsonParsed.all
        spot_d0 = spotJsonParsed.d0
        spot_d1 = spotJsonParsed.d1
        spot_d2 = spotJsonParsed.d2
        handleHaltButtonText(halt_all)
        handleFooterTradingStatus(spot_d0, spot_d1, spot_d2)

        quoting_spot = data.Spot.All
        handleSupplierStatus(quoting_spot)
        
    }).then(() => {
        var requestTime = new Date().getTime() - startTime
        var waitTime = requestTime > 1000 ? 1 : 1000 - requestTime
        setTimeout(refreshHaltData, waitTime)
    })
}

$(document).ready(function() {
    $("#halt-all").on('change', haltAllHandler)
    $("#halt-d0").on('change', haltD0Handler)
    $("#halt-d1").on('change', haltD1Handler)
    $("#halt-d2").on('change', haltD2Handler)
})

refreshHaltData()
