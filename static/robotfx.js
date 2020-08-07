

var doNothing = function() {

}

var submitData = function(the_url, the_data, error_msg = 'ops...!', reload = doNothing, dev=false, already_taken_msg="") {
    $.ajax({
        url: the_url,
        dataType: 'json',
        type: 'put',
        contentType: 'application/json',
        data: the_data,
        processData: false,
        success: (data, textStatus, jQxhr) => {
            let status = data['status'];
            let error = !status.includes('ok');
            if (!status.includes('ok')) {
                if (status.includes('duplicate')) {
                    alert('Duplicate data! A data with these values already exists!');
                } else if (status.includes('bad_old_pwd')) {
                    alert('The old password provided is incorrect!');
                } else if (status.includes('already_taken')) {
                    if (already_taken_msg) {
                        alert(already_taken_msg)
                    } else {
                        alert('Data already exists')
                    }

                    reload = doNothing
                } else {
                    toastr.error('The data updating was unsuccessful!');
                }
            }

            if (status.includes('ok - halted')) {
                toastr.error("Engine trading control time has passed.", 'Invalid operation...', {
                    "closeButton": false,
                    "timeOut": 5000
                  }) 
            }

            if (status == 'ok - Not a valid date.') {
                toastr.error("Not a valid date.", 'Invalid parameters')
            }

            console.log('Response: ' + status);

            if (dev && error) {
                console.log('error info: ' + data['exception']);
                return;
            }

            reload();
        },
        error: function(jqXhr, textStatus, errorThrown) {
            alert('Erro> event vale: ' + textStatus)
        }
    });
}
