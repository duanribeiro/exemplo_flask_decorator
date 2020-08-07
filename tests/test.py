from flask import Blueprint, render_template, jsonify
from requests.auth import HTTPBasicAuth
from lib.libflask import login_required
import os
import zeep


test_bp = Blueprint('test_bp', __name__, url_prefix='/test')


@test_bp.route('/kyc_test1')
@login_required(roles=['ti'])
def kyc_test1():
    SFDC_LOGIN = os.getenv("RFX_SFDC_LOGIN")
    SFDC_PASSW = os.getenv("RFX_SFDC_PASS")
    log_client = zeep.Client(os.path.join(os.environ["ROBOTFXDIR"], "etc/wsdl/BV.wsdl"))
    kyc_client = zeep.Client(os.path.join(os.environ["ROBOTFXDIR"], "etc/wsdl/ServiceKYC.wsdl"))
    resp = log_client.service.login(SFDC_LOGIN, SFDC_PASSW)
    session_id = resp["sessionId"]
    header = {"SessionHeader": {"sessionId": session_id}}
    resp = kyc_client.service.getKycByCPFCNPJ('1234', _soapheaders=header)
    return jsonify({'status': 'success', 'msg': repr(resp)})


@test_bp.route('/kyc_test2')
@login_required(roles=['ti'])
def kyc_test2():
    SFDC_LOGIN = os.getenv("RFX_SFDC_LOGIN")
    SFDC_PASSW = os.getenv("RFX_SFDC_PASS")
    log_client = zeep.Client(os.path.join(os.environ["ROBOTFXDIR"], "etc/wsdl/BV.wsdl"))
    kyc_client = zeep.Client(os.path.join(os.environ["ROBOTFXDIR"], "etc/wsdl/ServiceKYC.wsdl"))
    kyc_client.transport.session.proxies = {
        'http': 'felipe.silva:acfb0420@proxy-corp.bvnet.bv:8080',
        'https': 'felipe.silva:acfb0420@proxy-corp.bvnet.bv:8080',
    }
    resp = log_client.service.login(SFDC_LOGIN, SFDC_PASSW)
    session_id = resp["sessionId"]
    header = {"SessionHeader": {"sessionId": session_id}}
    resp = kyc_client.service.getKycByCPFCNPJ('1234', _soapheaders=header)
    return jsonify({'status': 'success', 'msg': repr(resp)})


@test_bp.route('/kyc_test3')
@login_required(roles=['ti'])
def kyc_test3():
    SFDC_LOGIN = os.getenv("RFX_SFDC_LOGIN")
    SFDC_PASSW = os.getenv("RFX_SFDC_PASS")
    log_client = zeep.Client(os.path.join(os.environ["ROBOTFXDIR"], "etc/wsdl/BV.wsdl"))
    kyc_client = zeep.Client(os.path.join(os.environ["ROBOTFXDIR"], "etc/wsdl/ServiceKYC.wsdl"))
    kyc_client.transport.session.proxies = {
        'http': 'proxy-corp.bvnet.bv:8080',
        'https': 'proxy-corp.bvnet.bv:8080',
    }
    resp = log_client.service.login(SFDC_LOGIN, SFDC_PASSW)
    session_id = resp["sessionId"]
    header = {"SessionHeader": {"sessionId": session_id}}
    resp = kyc_client.service.getKycByCPFCNPJ('1234', _soapheaders=header)
    return jsonify({'status': 'success', 'msg': repr(resp)})


@test_bp.route('/kyc_test4')
@login_required(roles=['ti'])
def kyc_test4():
    SFDC_LOGIN = os.getenv("RFX_SFDC_LOGIN")
    SFDC_PASSW = os.getenv("RFX_SFDC_PASS")
    log_client = zeep.Client(os.path.join(os.environ["ROBOTFXDIR"], "etc/wsdl/BV.wsdl"))
    kyc_client = zeep.Client(os.path.join(os.environ["ROBOTFXDIR"], "etc/wsdl/ServiceKYC.wsdl"))
    kyc_client.transport.session.proxies = {
        'http': 'proxy-corp.bvnet.bv:8080',
        'https': 'proxy-corp.bvnet.bv:8080',
    }
    kyc_client.transport.session.auth = HTTPBasicAuth('felipe.silva', 'acfb0420')
    resp = log_client.service.login(SFDC_LOGIN, SFDC_PASSW)
    session_id = resp["sessionId"]
    header = {"SessionHeader": {"sessionId": session_id}}
    resp = kyc_client.service.getKycByCPFCNPJ('1234', _soapheaders=header)
    return jsonify({'status': 'success', 'msg': repr(resp)})


@test_bp.route('/test-style')
@login_required(roles=['ti'])
def test_style():
    return render_template('test.html')


@test_bp.route('/playground')
@login_required(roles=['ti'])
def playground():
    return render_template('playground.html')