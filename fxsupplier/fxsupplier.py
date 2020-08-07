from flask import Blueprint
from flask import render_template
from flask import jsonify
from flask import request
from flask import Response
from flask import session
from lib.libflask import login_required
from lib.libflask import get_data_path
from lib.libflask import get_currencies_sorted
from lib.libflask import event_stream
from lib.libflask import blotter_transactions
from lib.libflask import get_user_role
from lib.libdatabus import databus
import json


fxsupplier_bp = Blueprint('fxsupplier_bp', __name__, url_prefix='/fxsupplier')


def is_positive_number(num, ge=False):
    """ Return whether num is greater than 0. If ge is True, checks whether num is  greater or equal than 0.
    """
    try:
        value = float(num)

        if ge:
            return value >= 0

        return value > 0
    except Exception:
        pass

    return False


@fxsupplier_bp.route('/supplier-control-limits-put', methods=['PUT'])
@login_required(roles=['fx-supplier'])
def supplier_control_limits_put():
    currencies_config = request.json['data']

    def is_brl_ok(config):
        return is_positive_number(config.get('SettlementRate', None))

    def is_ccy_ok(ccy, config):
        return (
            is_positive_number(config.get('SettlementRate', None))
            and is_positive_number(config.get('MaxQuantity', None))
            and is_positive_number(config.get('MarkupBUY', None), ge=True)
            and is_positive_number(config.get('MarkupSELL', None), ge=True)
        )

    ccy_valid = False
    system_currencies = databus.get('Currencies')
    if set(system_currencies) != set(currencies_config.keys()):
        return jsonify({'status': 'error - invalid_uploaded_data'})  # TODO: melhorar mensagem

    for ccy, config in currencies_config.items():
        if ccy.lower() == 'brl':
            ccy_valid = is_brl_ok(config)
        else:
            ccy_valid = is_ccy_ok(ccy, config)

        if not ccy_valid:
            return jsonify({'status': 'error - invalid_uploaded_data'})

    with open(get_data_path('RobotFX_FXSupplierControl.json'), 'w') as json_file_out:
        json_file_out.write(json.dumps(currencies_config, indent=2))

    databus.update_from_file(get_data_path('RobotFX_FXSupplierControl.json'), 'FXSupplierControl')
    return jsonify({'status': 'ok'})


@fxsupplier_bp.route('/fxsupplier-transactions')
@login_required(roles=['e-sales spot', 'e-sales ndf', 'fx-supplier'])
def fxsupplier_transactions():
    max_num_days_transaction = 3  # Constante de número total de dias de uma transação.
    accounting_status = databus.get_dict('Balance/SPOT')
    for currency, dict_value in accounting_status.items():
        del dict_value['TotalRevenue']
        accounting_status[currency] = dict_value['TotalAmount']
        accounting_status[currency]['BuyTotal'] = sum(
            accounting_status[currency]['BuyD' + str(i)] for i in range(max_num_days_transaction)
        )
        accounting_status[currency]['SellTotal'] = sum(
            accounting_status[currency]['SellD' + str(i)] for i in range(max_num_days_transaction)
        )
        accounting_status[currency]['Net'] = (
            accounting_status[currency]['BuyTotal'] - accounting_status[currency]['SellTotal']
        )

    return json.dumps(accounting_status)


@fxsupplier_bp.route('/supplier-blotter-spot')
@login_required(roles=['fx-supplier'])
def supplier_blotter_spot():
    return render_template(
        'supplier-blotter-spot.html', sorted_currencies=get_currencies_sorted(), halt="halt-quoting.html",
    )


@fxsupplier_bp.route('/supplier-control-data')
@login_required(roles=['fx-supplier', 'e-sales spot'])
def supplier_control_data():
    data_json = {}

    currencies = databus.get('Currencies')
    for currency in currencies:
        ccy_info = {}
        base = 'FXSupplierControl/{ccy}/'.format(ccy=currency)
        ccy_info['SettlementRate'] = databus.get(base + 'SettlementRate')

        if currency.upper() != 'BRL':
            ccy_info['SettlementRateCurveConvention'] = databus.get(base + 'SettlementRateCurveConvention')
            ccy_info['MaxQuantity'] = databus.get(base + 'MaxQuantity')
            ccy_info['MarkupSELL'] = databus.get(base + 'MarkupSELL')
            ccy_info['MarkupBUY'] = databus.get(base + 'MarkupBUY')

            precision = databus.get('Currencies/{ccy}/Precision'.format(ccy=currency))
            value_buy = databus.get('FXSupplierData/SPOT/{ccy}BRL/Bid'.format(ccy=currency))
            value_sell = databus.get('FXSupplierData/SPOT/{ccy}BRL/Ask'.format(ccy=currency))

            if value_buy is None or value_sell is None:
                ccy_info['Buy'] = "Fail"
                ccy_info['Sell'] = "Fail"
            else:
                ccy_info['Buy'] = round(value_buy, precision)
                ccy_info['Sell'] = round(value_sell, precision)

            ccy_info['CashLimitsD0'] = databus.get('CashLimits/SPOT/{ccy}/d0'.format(ccy=currency))
            ccy_info['CashLimitsD1'] = databus.get('CashLimits/SPOT/{ccy}/d1'.format(ccy=currency))
        else:
            ccy_info['Buy'] = '-'
            ccy_info['Sell'] = '-'

        data_json[currency] = ccy_info

    return jsonify(data_json)


@fxsupplier_bp.route('/supplier-blotter-ndf')
@login_required(roles=['fx-supplier'])
def supplier_blotter_ndf():
    json_sorted_currencies = get_currencies_sorted()
    return render_template(
        'supplier-blotter-ndf.html', sorted_currencies=json_sorted_currencies, halt="halt-quoting.html",
    )


@fxsupplier_bp.route('/fxsupplier-stream')
@login_required(roles=['e-sales spot', 'e-sales ndf', 'fx-supplier'])
def fxsupplier_stream():
    return Response(
        event_stream('blotter_fxsupplier'),
        mimetype="text/event-stream",
        headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'},
    )


@fxsupplier_bp.route('/halt-quoting', methods=['GET', 'PUT'])
@login_required(roles=['fx-supplier'])
def halt_quoting():
    if request.method == 'GET':
        return jsonify(databus.get_dict('System/Status/Quoting'))
    if request.method == 'PUT':
        spot_key = databus.get_dict('System/Status/General/Spot')
        ndf_key = databus.get_dict('System/Status/General/NDF')
        data = (json.loads(request.data))['Quoting']
        allow_clicking_NDF = 'Spot' not in data and 'NDF' in data and ndf_key
        allow_clicking_Spot = 'Spot' in data and 'NDF' not in data and spot_key
        allow_clicking_All = 'Spot' in data and 'NDF' in data and spot_key and ndf_key
        if allow_clicking_NDF or allow_clicking_Spot or allow_clicking_All:
            databus.update_from_dict(json.loads(request.data), "System/Status")
            return jsonify({'status': 'ok'})
        else:
            return jsonify({'status': 'ok - halted'})


@fxsupplier_bp.route('/supplier_data/<security_type>')
@login_required(roles=['e-sales ndf', 'e-sales spot', 'fx-supplier'])
def supplier_data(security_type):

    data = {}
    if security_type not in ('SPOT', 'NDF'):
        raise Exception('error: security type not found!')

    user_id = session.get("user_id", None)
    role = get_user_role(user_id)
    if role == 'fx-supplier':
        quoting_not_halted = True
    elif security_type == 'SPOT':
        quoting_not_halted = databus.get('System/Status/Quoting/Spot/All')
    elif security_type == 'NDF':
        quoting_not_halted = databus.get('System/Status/Quoting/NDF/All')

    if quoting_not_halted:
        casado = databus.get('FXSupplierCasado/Price')
    else:
        casado = '-'
    data['Casado'] = {'Price': casado}
    data['CurrencyPairs'] = {}
    currency_pairs = databus.get('FXSupplierData/{security}'.format(security=security_type))
    if currency_pairs is None:
        currency_pairs = {}
    for ccy_pair in currency_pairs:
        ccy = ccy_pair[0:3]
        precision = databus.get('Currencies/{ccy}/Precision'.format(ccy=ccy))
        if quoting_not_halted:
            bid = databus.get(
                'FXSupplierData/{security}/{ccy_pair}/Bid'.format(security=security_type, ccy_pair=ccy_pair)
            )
            ask = databus.get(
                'FXSupplierData/{security}/{ccy_pair}/Ask'.format(security=security_type, ccy_pair=ccy_pair)
            )

            if bid is None or ask is None:
                bid = "Fail"
                ask = "Fail"
            else:
                bid = round(bid, precision)
                ask = round(ask, precision)
        else:
            bid = '-'
            ask = '-'

        view_priority = databus.get('Currencies/{ccy}/ViewPriority'.format(ccy=ccy))
        data['CurrencyPairs'][ccy_pair] = {'Bid': bid, 'Ask': ask, 'ViewPriority': view_priority}

    if quoting_not_halted:
        fut_usdbrl_bid = databus.get('MarketData/Futures/USDBRL/Active/Bid')
        fut_usdbrl_ask = databus.get('MarketData/Futures/USDBRL/Active/Ask')

        if fut_usdbrl_bid is None or fut_usdbrl_ask is None:
            fut_usdbrl_bid = "Fail"
            fut_usdbrl_ask = "Fail"
    else:
        fut_usdbrl_bid = "-"
        fut_usdbrl_ask = "-"

    data['Futures'] = {"USDBRL": {'Active': {'Bid': fut_usdbrl_bid, 'Ask': fut_usdbrl_ask}}}

    return jsonify(data)


@fxsupplier_bp.route('/casado-data-put', methods=['PUT'])
@login_required(roles=['fx-supplier'])
def casado_data_put():
    casado_config = request.json['data']

    if not casado_config or not is_positive_number(casado_config):
        return jsonify({'status': 'error - invalid_uploaded_data'})

    with open(get_data_path('RobotFX_FXSupplierCasado.json')) as json_file:
        casado_data = json.load(json_file)

        try:
            casado_data['Price'] = float(casado_config)
        except ValueError:
            return jsonify({'status': "error: casado price's data is invalid!"})

    with open(get_data_path('RobotFX_FXSupplierCasado.json'), 'w') as json_file_out:
        json_file_out.write(json.dumps(casado_data, indent=2))

    databus.update_from_file(get_data_path('RobotFX_FXSupplierCasado.json'), 'FXSupplierCasado')

    return jsonify({'status': 'ok'})


@fxsupplier_bp.route('/casado-data')
@login_required(roles=['fx-supplier'])
def casado_data():
    data_json = {}
    data_json['CasadoBuy'] = databus.get('FXSupplierCasado/Price')

    return jsonify(data_json)


@fxsupplier_bp.route('/supplier-control')
@login_required(roles=['fx-supplier', 'e-sales spot'])
def supplier_control():
    with open(get_data_path('RobotFX_FXSupplierControl.json')) as json_file:
        currencies_config = json.load(json_file)

    json_sorted_currencies = get_currencies_sorted()
    return render_template(
        'supplier-control.html',
        currencies_config=json.dumps(currencies_config),
        sorted_currencies=json_sorted_currencies,
    )


@fxsupplier_bp.route('/risk_data/<string:user_id>')
@login_required(roles=['e-sales ndf', 'e-sales spot', 'fx-supplier'])
def risk_data(user_id):
    risk_dict = databus.get_dict('RiskData/CURVE')

    def sort(elem):
        return elem[1]['ViewPriority']

    sorted_dict = {k: v for k, v in sorted(risk_dict.items(), key=sort)}

    return json.dumps(sorted_dict)


@fxsupplier_bp.route('/market-data/details/<curve_code>')
@login_required(roles=['e-sales ndf', 'e-sales spot', 'fx-supplier'])
def market_data_details(curve_code):
    return render_template('market-data-details.html', curve_code=curve_code)


@fxsupplier_bp.route('/market_data')
@login_required(roles=['e-sales ndf', 'e-sales spot', 'fx-supplier'])
def market_data():
    return json.dumps(databus.get_dict('MarketData/Curves'))


@fxsupplier_bp.route('/transactions')
@login_required(roles=['fx-supplier'])
def transactions():
    return json.dumps(blotter_transactions())
