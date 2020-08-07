import json
import copy
import csv
import os
import sys
import traceback
import subprocess
from decimal import Decimal
from flask import Blueprint
from flask import render_template
from flask import jsonify
from flask import request
from flask import abort
from flask import session
from flask import Response
from flask import send_from_directory
from lib.libflask import spread_transaction_getter
from lib.libflask import login_required
from lib.libflask import get_data_path
from lib.libflask import get_currencies_sorted_list
from lib.libflask import get_currencies_sorted
from lib.libflask import manage_spreads_tables
from lib.libflask import blotter_transactions
from lib.libflask import event_stream
from lib.libflask import get_username
from lib.libutils import get_local_time
from lib.libutils import get_validate_parameters
from lib.libutils import update_validate_rule
from lib.libtransactions import increase_cash_limits_spot
from lib.libtransactions import decrease_cash_limits_spot
from lib.libdatabus import databus
from lib.history.crud_transactions import get_day_trade_info
from lib.history.crud_transactions import get_daily_stats
from lib.history.crud_transactions import get_day_reject_info
from lib.history.crud_transactions import get_transactions_report
from datetime import datetime

# log_info = libep.log_info
fxspot_bp = Blueprint('fxspot_bp', __name__, url_prefix='/fxspot')


@fxspot_bp.route('/spreads_spot_counterparty_transactions')
@login_required(roles=['e-sales spot', 'fx-supplier'])
def spreads_spot_counterparty_transactions():
    return spread_transaction_getter(is_ndf=False, is_group=False)


@fxspot_bp.route('/spreads_spot_group_transactions')
@login_required(roles=['e-sales spot', 'fx-supplier'])
def spreads_spot_group_transactions():
    return spread_transaction_getter(is_ndf=False, is_group=True)


@fxspot_bp.route('/check_spot_limits_initialized')
def check_spot_limits_initialized():
    status = databus.get('System/Status/Trading/SPOT/Initialized')
    return json.dumps(status)


@fxspot_bp.route('/engine-parameters-spot-put', methods=['PUT'])
@login_required(roles=['e-sales spot'])
def engine_parameters_spot_put():
    try:
        engine_parameters = json.loads(request.data)
        with open(get_data_path('RobotFX_TradingParameters.json')) as json_file:
            old_obj = json.load(json_file)
            old_obj["Engine_Global_Parameters"]["FXSPOT"] = engine_parameters['engine_parameters']

        with open(get_data_path('RobotFX_TradingParameters.json'), "w") as json_file_out:
            json_file_out.write(json.dumps(old_obj, sort_keys=True, indent=4))

        databus.update_from_file(get_data_path('RobotFX_TradingParameters.json'), 'TradingParameters')

        return jsonify({'status': 'ok'})
    except json.decoder.JSONDecodeError:  # caso uso do comando: curl...
        return jsonify({'status': 'fail'})
    except Exception:
        return jsonify({'status': 'fail'})


@fxspot_bp.route('/blotter-spot-dealid-popup', methods=['GET'])
@login_required(roles=['e-sales spot'])
def getBlotterSpotPopup():
    deal_id = request.args.get('dealid', '')
    if not deal_id:
        abort(404, description="Resource not found")

    try:
        info = json.loads(databus.get('Blotter/{deal_id}'.format(deal_id=deal_id)))
    except TypeError:
        abort(404, description="Resource not found")

    return render_template('blotter-spot-dealid-popup.html', deal_id=json.dumps(deal_id), info=info)


@fxspot_bp.route('/trading-parameters-spot')
@login_required(roles=['e-sales spot'])
def trading_parameters_spot():
    cash_limits_initialized = databus.get('System/Status/Trading/SPOT/Initialized')
    trading_parameters = databus.get_dict('TradingParameters')
    engine_parameters = trading_parameters["Engine_Global_Parameters"]["FXSPOT"]
    currency_keys = trading_parameters["CurrencyKeys"]
    leg_entities = databus.get_dict('LegalEntities')
    if leg_entities is None:
        leg_entities = {}
    trad_counterparties = trading_parameters['CounterpartyKeys']
    common_cp_keys = tuple(k for k, v in leg_entities.items() if 'FXSPOT' in v['Products'])
    counterparty_list = []
    for cp_key in common_cp_keys:
        trad_value = trad_counterparties[cp_key]['FXSPOT']
        validate_kyc_rule = update_validate_rule(trad_value['ValidateKYC'], 'KYC', cp_key, False)
        counterparty_list.append(
            {
                'cter_prty_id': cp_key,
                'counterparty': leg_entities[cp_key]["CounterpartyName"],
                'automatic_flow': trad_value['AutoFlow'],
                'validate_kyc': validate_kyc_rule,
            }
        )
    json_sorted_currencies = get_currencies_sorted()
    cash_limits_logs = {}

    if cash_limits_initialized:
        cash_limits_logs = databus.get_dict('CashLimits/Logs')
        pre_trading_ini_bal = {}
        for currency, maturity_value in cash_limits_logs.items():
            pre_trading_ini_bal[currency] = {}
            for maturity, value in maturity_value.items():
                if isinstance(value, list) and len(value) > 0:
                    pre_trading_ini_bal[currency][maturity] = value[0]
    else:
        cash_limits_logs = {}
        pre_trading_ini_bal = trading_parameters['PreTradingInitialBalance']

    with open(get_data_path('RobotFX_Users.json')) as json_file:
        user_data = json.load(json_file)
        user_id = session.get("user_id", None)
        username = get_username(user_id)
        if username not in user_data:
            return render_template('404.html')

        response_data = user_data[username]
        allow_validate = response_data['allow_validate'].lower() == 'yes'

    validate_parameters = get_validate_parameters()

    return render_template(
        'trading-parameters-spot.html',
        engine_parameters=json.dumps(engine_parameters),
        currency_keys=json.dumps(currency_keys),
        pre_trading_ini_bal=json.dumps(pre_trading_ini_bal),
        counterparty_data=json.dumps(counterparty_list),
        sorted_currencies=json_sorted_currencies,
        spot_initialized=cash_limits_initialized,
        cash_limits_logs=cash_limits_logs,
        allow_validate=json.dumps(allow_validate),
        validate_parameters=json.dumps(validate_parameters),
    )


@fxspot_bp.route('/counterparty-spot-put', methods=['PUT'])
@login_required(roles=['e-sales spot'])
def counterparty_spot_put():
    counterparty_spot = json.loads(request.data)['counterparty_data']
    with open(get_data_path('RobotFX_TradingParameters.json')) as json_file:
        old_obj = json.load(json_file)
        alt_obj = copy.deepcopy(old_obj)
        for cter_prty in counterparty_spot:
            autoflow = cter_prty['automatic_flow']
            validate_kyc = cter_prty['validate_kyc']
            validate_kyc = validate_kyc if validate_kyc != 'NO: GOOD-TODAY' else 'YES'
            fxndf_obj = old_obj["CounterpartyKeys"][cter_prty['cter_prty_id']]["FXSPOT"]
            fxndf_obj["AutoFlow"] = autoflow
            fxndf_obj["ValidateKYC"] = validate_kyc
            fxndf_obj2 = alt_obj["CounterpartyKeys"][cter_prty['cter_prty_id']]["FXSPOT"]
            fxndf_obj2["AutoFlow"] = autoflow
            fxndf_obj2["ValidateKYC"] = validate_kyc

    with open(get_data_path('RobotFX_TradingParameters.json'), "w") as json_file_out:
        json_file_out.write(json.dumps(old_obj, sort_keys=True, indent=4))

    databus.update_from_dict(alt_obj, 'TradingParameters')
    return jsonify({'status': 'ok'})


@fxspot_bp.route('/engine-control-spot')
@login_required(roles=['e-sales spot'])
def engine_control_spot():
    with open(get_data_path('RobotFX_TradingParameters.json')) as json_file:
        trading_parameters = json.load(json_file)
        engine_parameters = trading_parameters["Engine_Global_Parameters"]["FXSPOT"]

    with open(get_data_path('RobotFX_SpotConfig.json')) as json_file:
        spot_config = json.load(json_file)
        cutoff_times = spot_config['CutOffTimes']

    spot_timeout = databus.get('TradingParameters/Engine_Global_Parameters/FXSPOT/RFQ_Timeout')

    return render_template(
        'engine-control-spot.html',
        engine_parameters=json.dumps(engine_parameters),
        cutoff_times=json.dumps(cutoff_times),
        spot_timeout=json.dumps(spot_timeout),
    )


@fxspot_bp.route('/spreads-spot-get', methods=['GET'])
@login_required(roles=['e-sales spot'])
def spreads_spot_get():
    search_by_group = request.args.get('search_by', '').lower() == 'group'
    key = request.args.get('key', '').upper()

    sorted_currencies = json.loads(get_currencies_sorted())

    with open(get_data_path('RobotFX_Client_Spreads.json')) as json_file:
        all_spreads = json.load(json_file)
        all_spreads = all_spreads['GroupSpreads' if search_by_group else 'CounterpartySpreads']

        try:
            spreads = all_spreads[key]['FXSPOT']
        except KeyError:
            spreads = {currency: {'SELL': [None] * 3, 'BUY': [None] * 3} for currency in sorted_currencies}

    result = {'spreads': spreads, 'currencies': sorted_currencies}
    return jsonify(result)


@fxspot_bp.route('/spreads-spot-put', methods=['PUT'])
@login_required(roles=['e-sales spot'])
def spreads_spot_put():
    now = get_local_time()
    type_update = request.args.get('type', '').lower()
    update_group = type_update == 'group'
    key = request.args.get('key', '').upper()
    status = request.json['status']
    currency = status['currency']
    spotDay = status['spotday']
    side = status['side']
    spread = status['spread']
    if spread != '-':
        spread = int(Decimal(spread) * 10_000)  # Solucao de caso de spread igual a: 12, 24 ou 48.

    basic_key = 'SpreadRegistry/SPOT/' + type_update

    if databus.exists(basic_key):
        data_list = databus.get(basic_key)
    else:
        data_list = []
    user_id = session.get("user_id", None)
    username = get_username(user_id)
    element = {
        'target': key,
        'ts': now.strftime('%Y-%m-%d %H:%M:%S'),
        'user': str(username),
        'ccy': str(currency),
        'spotday': str(spotDay),
        'side': str(side),
        'spread': str(spread),
    }

    if not update_group:
        element['counterparty'] = databus.get('LegalEntities/{cnpj}/CounterpartyName'.format(cnpj=key))
        basic_group_key = 'LegalEntitiesRelationships/Groups_Spreads_'
        if databus.exists((basic_group_key + 'FX{type}_Memberships/{cnpj}').format(cnpj=key, type='SPOT')):
            element['group'] = databus.get(
                (basic_group_key + 'FX{type}_Memberships/{cnpj}').format(cnpj=key, type="SPOT")
            )
        else:
            element['group'] = '-'

    data_list.append(element)

    databus.set(basic_key, data_list)

    manage_spreads_tables(1, is_ndf=False)

    with open(get_data_path('RobotFX_Client_Spreads.json')) as json_file:
        all_spreads = json.load(json_file)
        entity_type = 'GroupSpreads' if update_group else 'CounterpartySpreads'
        if key not in all_spreads[entity_type]:
            all_spreads[entity_type][key] = {}

        all_spreads[entity_type][key]['FXSPOT'] = request.json['spreads']

    with open(get_data_path('RobotFX_Client_Spreads.json'), 'w') as json_file_out:
        json_file_out.write(json.dumps(all_spreads, indent=2))

    databus.update_from_file(get_data_path('RobotFX_Client_Spreads.json'), 'ClientSpreads')

    return jsonify({'status': 'ok'})


@fxspot_bp.route('/market-data-spot')
@login_required(roles=['e-sales spot'])
def market_data_spot():
    return render_template('market-data-spot.html', sec_type='SPOT')


@fxspot_bp.route("/statistics-spot")
@login_required(roles=["e-sales spot", "supervisor"])
def statistics_spot():
    fx_product = "SPOT"
    session = SessionMaker()
    currencies = get_currencies_sorted_list()
    daily_stats_dict = get_daily_stats(session, fx_product, currencies)
    session.close()
    daily_stats_json = json.dumps(daily_stats_dict)
    sorted_currencies = get_currencies_sorted()

    return render_template("statistics-spot.html", daily_stats=daily_stats_json, sorted_currencies=sorted_currencies)


@fxspot_bp.route("/statistics-spot-day-popup", methods=["GET"])
@login_required(roles=["e-sales spot", "supervisor"])
def getStatisticsSpotPopup():
    transact_date = request.args.get("day", "")
    if not transact_date:
        abort(404, description="Resource not found")

    fx_product = "SPOT"
    session = SessionMaker()
    currencies = get_currencies_sorted_list()
    day_trade_info_dict = get_day_trade_info(session, fx_product, transact_date, currencies)
    session.close()
    day_trade_info_json = json.dumps(day_trade_info_dict)

    session = SessionMaker()
    get_day_reject_info(session, fx_product, transact_date)
    session.close()

    return render_template(
        "statistics-spot-day-popup.html", transact_date=transact_date, transact_date_info=day_trade_info_json,
    )


@fxspot_bp.route("/statistics-spot-day-reject-popup", methods=["GET"])
@login_required(roles=["e-sales spot", "supervisor"])
def getStatisticsSpotRejectPopup():
    transact_date = request.args.get("day", "")
    if not transact_date:
        abort(404, description="Resource not found")

    fx_product = "SPOT"
    session = SessionMaker()
    day_reject_info_list = get_day_reject_info(session, fx_product, transact_date)
    session.close()
    day_reject_info_json = json.dumps(day_reject_info_list)

    return render_template(
        "statistics-day-reject-popup.html", transact_date=transact_date, day_reject_info_json=day_reject_info_json,
    )


@fxspot_bp.route("/statistics-report", methods=["GET"])
@login_required(roles=["e-sales spot", "supervisor"])
def statisticsReport():
    startDate = request.args.get("startDate")
    endDate = request.args.get("endDate")

    if not startDate or not endDate:
        abort(404, description="Dates must be defined to export CSV report")

    fx_product = "SPOT"
    startDate = datetime.strptime(startDate, "%Y-%m-%d").date()
    endDate = datetime.strptime(endDate, "%Y-%m-%d").date()

    session = SessionMaker()
    column_names, transaction_report = get_transactions_report(session, fx_product, startDate, endDate)
    session.close()

    reports_dir = os.getenv("RFX_HISTORY_DIR")
    filename = f"{fx_product}_report_{startDate}_{endDate}.csv"
    filepath = f"{reports_dir}/{filename}"
    try:
        with open(filepath, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=column_names)
            writer.writeheader()
            for transaction in transaction_report:
                writer.writerow(transaction)
    except IOError:
        print("I/O error")

    return send_from_directory(
        directory=reports_dir, filename=filename, as_attachment=True, attachment_filename=filename
    )


@fxspot_bp.route('/balance_spot')
@login_required(roles=['e-sales spot'])
def balance_spot():
    data = databus.get_dict('Balance')['SPOT']
    return json.dumps(data)


@fxspot_bp.route('/blotter-spot')
@login_required(roles=['e-sales spot'])
def blotter_spot():
    json_sorted_currencies = get_currencies_sorted()
    return render_template('blotter-spot.html', sorted_currencies=json_sorted_currencies)


@fxspot_bp.route('/spreads-spot')
@login_required(roles=['e-sales spot'])
def spreads_spot():
    legal_entities = {}

    with open(get_data_path('RobotFX_LegalEntitiesRelationships.json')) as rel_leg_ent_json:
        rel_leg_ents = json.load(rel_leg_ent_json)
        wgrp = rel_leg_ents['Groups_Spreads']['FXSPOT']
        groups = {elem: {'NameHolding': name['Name']} for elem, name in wgrp.items()}

    with open(get_data_path('RobotFX_LegalEntities.json')) as json_file:
        counterparties = json.load(json_file)
        counterparties = {k: v for k, v in counterparties.items() if 'FXSPOT' in v['Products']}
        legal_entities = {'Groups': groups, 'Counterparties': counterparties}

    return render_template('spreads-spot.html', legal_entities=json.dumps(legal_entities))


@fxspot_bp.route('/halt-spot', methods=['GET', 'PUT'])
@login_required(roles=['e-sales spot'])
def halt_spot():
    if request.method == 'GET':
        status_trading_spot = databus.get_dict('System/Status/Trading/SPOT')
        status_supplier = databus.get_dict('System/Status/Quoting')
        status_trading_spot.update(status_supplier)
        return jsonify(status_trading_spot)
    if request.method == 'PUT':
        spot_key = databus.get_dict('System/Status/General/Spot')
        if spot_key:
            databus.update_from_dict(json.loads(request.data), "System/Status/Trading")
            return jsonify({'status': 'ok'})
        else:
            return jsonify({'status': 'ok - halted'})


@fxspot_bp.route('/pre-trading-balance-update', methods=['PUT'])
@login_required(roles=['e-sales spot'])
def pre_trading_balance_update():
    """
@login_required(roles=['e-sales spot'])
    atualiza o CashLimits adicionando ou removendo + dinheiro.
    """
    balance_update = json.loads(request.data)
    balance_update = balance_update.get('balance_update', None)

    if balance_update is not None:
        for ccy, limits in balance_update.items():
            for maturity, value in limits.items():
                if value is None:
                    continue

                value = float(value)
                n = int(maturity[1])

                if n not in [0, 1]:
                    continue

                if databus.get(f'CashLimits/SPOT/{ccy}/{maturity}') is None:
                    databus.set(f'CashLimits/SPOT/{ccy}/{maturity}', 0.0)

                if value > 0:
                    success, error_msg = increase_cash_limits_spot(ccy, value, n)
                else:
                    success, error_msg = decrease_cash_limits_spot(ccy, value, n, reset=True)

                ccy_logs = databus.get(f'CashLimits/Logs/{ccy}/{maturity}')
                if isinstance(ccy_logs, list):
                    ccy_logs.append(value)
                    databus.set(f'CashLimits/Logs/{ccy}/{maturity}', ccy_logs)

                if not success:
                    return jsonify({'status': 'fail', 'reason': error_msg})

    return jsonify({'status': 'ok'})


@fxspot_bp.route('/pre-trading-ini-bal-put', methods=['PUT'])
@login_required(roles=['e-sales spot'])
def pre_trading_ini_bal_spot_put():
    pre_trading_ini_bal_spot = json.loads(request.data)['pre_trading_ini_bal']

    initialized = False
    log = {}

    for ccy, maturity_balance in pre_trading_ini_bal_spot.items():
        log[ccy] = {}
        for maturity, value in maturity_balance.items():
            log[ccy][maturity] = [value]
            if value is not None:
                initialized = True

    databus.update_from_dict(pre_trading_ini_bal_spot, 'CashLimits/SPOT')
    databus.update_from_dict(log, 'CashLimits/Logs')
    databus.set('System/Status/Trading/SPOT/Initialized', initialized)

    return jsonify({'status': 'ok'})


@fxspot_bp.route('/stream')
@login_required(roles=['e-sales spot'])
def stream():
    return Response(
        event_stream(), mimetype="text/event-stream", headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'}
    )


@fxspot_bp.route('/currency-keys-spot-put', methods=['PUT'])
@login_required(roles=['e-sales spot'])
def currency_keys_spot_put():
    currency_keys = json.loads(request.data)
    with open(get_data_path('RobotFX_TradingParameters.json')) as json_file:
        old_obj = json.load(json_file)
        old_obj["CurrencyKeys"] = currency_keys['currency_keys']

    with open(get_data_path('RobotFX_TradingParameters.json'), "w") as json_file_out:
        json_file_out.write(json.dumps(old_obj, sort_keys=True, indent=4))

    databus.update_from_file(get_data_path('RobotFX_TradingParameters.json'), 'TradingParameters')

    return jsonify({'status': 'ok'})


@fxspot_bp.route('/transactions')
@login_required(roles=['e-sales spot'])
def transactions():
    return json.dumps(blotter_transactions())


@fxspot_bp.route('/cutoff-times-put', methods=['PUT'])
@login_required(roles=['e-sales spot'])
def cutoff_times_spot_put():
    json_data = json.loads(request.data)
    cutoff_times_spot = json_data['cutoff_times']
    with open(get_data_path('RobotFX_SpotConfig.json')) as json_file:
        old_obj = json.load(json_file)
        old_obj["CutOffTimes"] = cutoff_times_spot

    with open(get_data_path('RobotFX_SpotConfig.json'), "w") as json_file_out:
        json_file_out.write(json.dumps(old_obj, indent=2))

    databus.update_from_file(get_data_path('RobotFX_SpotConfig.json'), 'SpotConfig')

    return jsonify({'status': 'ok'})


# O código abaixo está "duplicado"
# O mesmo se encontra nas blueprints fxndf, fxspot, e fxconfig.
# TODO: Estudar solução mais eficiente futuramente.


@fxspot_bp.route('/config')
@login_required(roles=['e-sales spot'])
def config():
    with open(get_data_path('RobotFX_SpotConfig.json')) as json_file:
        spot_config = json.load(json_file)
        cutoff_times = spot_config['CutOffTimes']

        with open(get_data_path('RobotFX_Currencies.json')) as currencies_json_file:
            cur_data = json.load(currencies_json_file)
            for cur in cutoff_times['Primary']:
                cutoff_times['Primary'][cur]['ViewPriority'] = cur_data[cur]['ViewPriority']

    with open(get_data_path('RobotFX_NDFTimeBuckets.json')) as json_file:
        time_buckets_data = json.load(json_file)
        time_buckets = time_buckets_data['TimeBuckets']

    counterparties = []
    with open(get_data_path('RobotFX_LegalEntities.json')) as json_file:
        legal_entities_data = json.load(json_file)
        for (key, obj) in legal_entities_data.items():
            counterparties.append(
                {
                    'Id': len(counterparties) + 1,
                    'Alias': obj['Alias'],
                    'Counterparty': obj['CounterpartyName'],
                    'Cnpj': key,
                    'MarketType': obj['FXMarketType'],
                    'DefaultTransaction': obj['DefaultFXTransaction'],
                    'Products': obj['Products'],
                }
            )

    counterparties = sorted(counterparties, key=lambda cparty: cparty['Alias'])

    # groups = []
    with open(get_data_path('RobotFX_LegalEntitiesRelationships.json')) as json_file:
        groups_data = json.load(json_file)
        groups_data = groups_data.get('Groups_Spreads', {})
        spot_groups = groups_data.get('FXSPOT', {})
        ndf_groups = groups_data.get('FXNDF', {})

    spot_timeout = databus.get('TradingParameters/Engine_Global_Parameters/FXSPOT/RFQ_Timeout')
    ndf_timeout = databus.get('TradingParameters/Engine_Global_Parameters/FXNDF/RFQ_Timeout')

    json_sorted_currencies = get_currencies_sorted()
    return render_template(
        'config-main-spot.html',
        cutoff_times=json.dumps(cutoff_times),
        time_buckets=json.dumps(time_buckets),
        counterparties=json.dumps(counterparties),
        spot_groups=json.dumps(spot_groups),
        ndf_groups=json.dumps(ndf_groups),
        currencies=json.dumps(cur_data),
        spot_timeout=json.dumps(spot_timeout),
        ndf_timeout=json.dumps(ndf_timeout),
        sorted_currencies=json_sorted_currencies,
    )


@fxspot_bp.route('/time-buckets-put', methods=['PUT'])
@login_required(roles=['e-sales spot'])
def put_time_buckets():
    time_buckets = request.json['time_buckets']
    with open(get_data_path('RobotFX_NDFTimeBuckets.json')) as json_file:
        time_buckets_data = json.load(json_file)
        time_buckets_data['TimeBuckets'] = time_buckets

    with open(get_data_path('RobotFX_NDFTimeBuckets.json'), 'w') as json_file_out:
        json_file_out.write(json.dumps(time_buckets_data, indent=2))

    databus.update_from_file(get_data_path('RobotFX_NDFTimeBuckets.json'), 'NDFTimeBuckets')

    return jsonify({'status': 'ok'})


@fxspot_bp.route('/counterparty-delete', methods=['PUT'])
@login_required(roles=['e-sales spot'])
def counterparty_delete():
    try:
        counterparty_set = set(request.json['counterparty'])

        with open(get_data_path('RobotFX_LegalEntities.json')) as json_file:
            legal_entities_data = json.load(json_file)

        with open(get_data_path('RobotFX_TradingParameters.json')) as json_file:
            trading_parameters_file_data = json.load(json_file)

        trading_parameters_data = trading_parameters_file_data['CounterpartyKeys']

        for dict_data in (legal_entities_data, trading_parameters_data):
            keys_to_remove = counterparty_set.intersection(set(dict_data.keys()))
            for key in keys_to_remove:
                del dict_data[key]

        with open(get_data_path('RobotFX_LegalEntities.json'), 'w') as json_file_out:
            json_file_out.write(json.dumps(legal_entities_data, indent=2))

        databus.overwrite_from_file(get_data_path('RobotFX_LegalEntities.json'), 'LegalEntities')

        with open(get_data_path('RobotFX_TradingParameters.json'), 'w') as json_file_out:
            json_file_out.write(json.dumps(trading_parameters_file_data, indent=2))

        databus.overwrite_from_file(get_data_path('RobotFX_TradingParameters.json'), 'TradingParameters')

        with open(get_data_path('RobotFX_Client_Spreads.json')) as json_file:
            client_spreads_data = json.load(json_file)

        counterparty_spreads_data = client_spreads_data['CounterpartySpreads']

        with open(get_data_path('RobotFX_LegalEntitiesRelationships.json')) as json_file:
            old_groups_data = json.load(json_file)

        ndf_old_groups_data = old_groups_data['Groups_Spreads_FXNDF_Memberships']
        spot_old_groups_data = old_groups_data['Groups_Spreads_FXSPOT_Memberships']

        keys_to_remove_spreads = counterparty_set.intersection(set(counterparty_spreads_data.keys()))
        keys_to_remove_ndf_old_groups = counterparty_set.intersection(ndf_old_groups_data.keys())
        keys_to_remove_spot_old_groups = counterparty_set.intersection(spot_old_groups_data.keys())
        update_group_data = any(keys_to_remove_ndf_old_groups) or any(keys_to_remove_spot_old_groups)

        for key in keys_to_remove_spreads:
            del counterparty_spreads_data[key]

        for key in keys_to_remove_spot_old_groups:
            del spot_old_groups_data[key]

        for key in keys_to_remove_ndf_old_groups:
            del ndf_old_groups_data[key]

        if update_group_data:
            with open(get_data_path('RobotFX_LegalEntitiesRelationships.json'), 'w') as json_file_out:
                json_file_out.write(json.dumps(old_groups_data, indent=2))

            databus.overwrite_from_file(
                get_data_path('RobotFX_LegalEntitiesRelationships.json'), 'LegalEntitiesRelationships'
            )

            with open(get_data_path('RobotFX_Client_Spreads.json'), 'w') as json_file_out:
                json_file_out.write(json.dumps(client_spreads_data, indent=2))

            databus.overwrite_from_file(get_data_path('RobotFX_Client_Spreads.json'), 'ClientSpreads')

        return jsonify({'status': 'ok'})
    except KeyError:
        # The exceptions are serialized here like at:
        # https://stackoverflow.com/questions/45240549/how-to-serialize-an-exception
        exc_info = sys.exc_info()
        return jsonify({'status': 'error', 'exception': ''.join(traceback.format_exception(*exc_info))})


@fxspot_bp.route('/counterparty-data-add')
@login_required(roles=['e-sales spot'])
def counterparty_data_add():
    counterparty = {}
    counterparty['Cnpj'] = ''
    counterparty['Alias'] = ''
    counterparty['CounterpartyName'] = ''
    counterparty['Products'] = []

    read_only = False

    alias_ndf = []
    alias_spot = []
    with open(get_data_path('RobotFX_LegalEntitiesRelationships.json')) as json_file:
        groups_data = json.load(json_file)

        spreads_data = groups_data.get('Groups_Spreads', {})
        spot_groups = spreads_data.get('FXSPOT', {})
        if spot_groups is None:
            spot_groups = {}
        alias_spot = list(spot_groups.keys())
        alias_spot.insert(0, '')
        ndf_groups = spreads_data.get('FXNDF', {})
        if ndf_groups is None:
            spot_groups = {}
        alias_ndf = list(ndf_groups.keys())
        alias_ndf.insert(0, '')

        selected_spot = ''
        selected_ndf = ''

    return render_template(
        'counterparty-edit-spot.html',
        counterparty=json.dumps(counterparty),
        alias_ndf=json.dumps(alias_ndf),
        alias_spot=json.dumps(alias_spot),
        selected_ndf=json.dumps(selected_ndf),
        selected_spot=json.dumps(selected_spot),
        read_only=json.dumps(read_only),
    )


@fxspot_bp.route('/counterparty-config-put', methods=['PUT'])
@login_required(roles=['e-sales spot'])
def counterparty_config_put():
    try:
        cp = json.loads(request.data)['counterparty']
        cnpj = cp['Cnpj']
        del cp['Cnpj']
        sel_spot = json.loads(request.data)['selected_spot']
        sel_ndf = json.loads(request.data)['selected_ndf']
        update_case = json.loads(request.data)['update_case']

        if "FXSPOT" not in cp['Products']:
            cp['FXMarketType'] = 1
            cp['DefaultFXTransaction'] = ''
            sel_spot = ''

        if "FXNDF" not in cp['Products']:
            sel_ndf = ''

        with open(get_data_path('RobotFX_LegalEntities.json')) as json_file:
            old_obj = json.load(json_file)
            if not update_case and cnpj in old_obj:
                return jsonify({'status': 'already_taken'})

            old_obj[cnpj] = cp

        with open(get_data_path('RobotFX_LegalEntities.json'), "w") as json_file_out:
            json_file_out.write(json.dumps(old_obj, indent=2))

        databus.update_from_file(get_data_path('RobotFX_LegalEntities.json'), 'LegalEntities')

        with open(get_data_path('RobotFX_TradingParameters.json')) as json_file:
            old_obj = json.load(json_file)
            cp = old_obj['CounterpartyKeys']

        with open(get_data_path('RobotFX_TradingParameters.json'), "w") as json_file_out:
            new_counterparty_default = {
                cnpj: {
                    "FXSPOT": {"ValidateKYC": "YES", "AutoFlow": "ENABLED"},
                    "FXNDF": {
                        "UpperLimitDays2Maturity": 720,
                        "AutoFlow": "ENABLED",
                        "ValidateKYC": "YES",
                        "ValidateISDA": "YES",
                    },
                }
            }
            cp.update(new_counterparty_default)
            old_obj['CounterpartyKeys'] = cp
            json_file_out.write(json.dumps(old_obj, sort_keys=True, indent=4))

        databus.update_from_file(get_data_path('RobotFX_TradingParameters.json'), 'TradingParameters')

        currencies = list(databus.get_dict('Currencies').keys())
        currencies.remove('BRL')

        time_buckets = []
        with open(get_data_path('RobotFX_NDFTimeBuckets.json')) as json_file:
            old_obj = json.load(json_file)
            tb = old_obj['TimeBuckets']
            for elem in tb:
                time_buckets.append(elem['EndDay'])

        with open(get_data_path('RobotFX_Client_Spreads.json')) as json_file:
            old_client_spreads = json.load(json_file)
            old_client_spreads['CounterpartySpreads'][cnpj] = {
                'FXSPOT': {},
                'FXNDF': {'Buckets': time_buckets, 'Spreads': {}},
            }
            for cur in currencies:
                old_client_spreads['CounterpartySpreads'][cnpj]['FXSPOT'][cur] = {'BUY': [None] * 3, 'SELL': [None] * 3}
                old_client_spreads['CounterpartySpreads'][cnpj]['FXNDF']['Spreads'][cur] = {
                    'BUYSELL': [None] * len(time_buckets)
                }

        with open(get_data_path('RobotFX_Client_Spreads.json'), 'w') as json_file_out:
            json_file_out.write(json.dumps(old_client_spreads, indent=2))

        databus.update_from_file(get_data_path('RobotFX_Client_Spreads.json'), 'ClientSpreads')

        with open(get_data_path('RobotFX_LegalEntitiesRelationships.json')) as json_file:
            groups_data = json.load(json_file)
            groups_data["Groups_Spreads_FXSPOT_Memberships"][cnpj] = sel_spot
            groups_data["Groups_Spreads_FXNDF_Memberships"][cnpj] = sel_ndf

        with open(get_data_path('RobotFX_LegalEntitiesRelationships.json'), "w") as json_file_out:
            json_file_out.write(json.dumps(groups_data, indent=2))

        databus.update_from_file(get_data_path('RobotFX_LegalEntitiesRelationships.json'), 'LegalEntitiesRelationships')

        return jsonify({'status': 'ok'})
    except KeyError:
        exc_info = sys.exc_info()
        return jsonify({'status': 'error', 'exception': ''.join(traceback.format_exception(*exc_info))})
    except json.decoder.JSONDecodeError:
        return jsonify({'status': 'fail because JSONDecoderError!'})


@fxspot_bp.route('/group-delete/<fxtype>', methods=['PUT'])
@login_required(roles=['e-sales spot'])
def group_delete(fxtype):
    try:
        group_data = request.json['group']
        upper_fxtype = fxtype.upper()
        if upper_fxtype in ('SPOT', 'NDF'):
            for gr in group_data:
                databus.delete('LegalEntitiesRelationships/Groups_Spreads/FX' + upper_fxtype + '/' + gr)
                databus.delete('ClientSpreads/GroupSpreads/' + gr + '/FX' + upper_fxtype)

            with open(get_data_path('RobotFX_LegalEntitiesRelationships.json'), 'w') as json_file_out:
                json_file_out.write(json.dumps(databus.get_dict('LegalEntitiesRelationships'), indent=2))

            with open(get_data_path('RobotFX_Client_Spreads.json'), 'w') as json_file_out:
                json_file_out.write(json.dumps(databus.get_dict('ClientSpreads'), indent=2))

            return jsonify({'status': 'ok - group - ' + fxtype.lower() + ' - delete'})
        else:
            raise KeyError()
    except KeyError:
        exc_info = sys.exc_info()
        return jsonify(
            {
                'status': 'error - group - ' + fxtype.lower() + ' - delete',
                'exception': ''.join(traceback.format_exception(*exc_info)),
            }
        )


@fxspot_bp.route('/group-edit/<fxtype>/<alias>')
@login_required(roles=['e-sales spot'])
def group_edit(fxtype, alias):
    try:
        with open(get_data_path('RobotFX_LegalEntitiesRelationships.json')) as json_file:
            old_groups_data = json.load(json_file)
            upper_fxtype = fxtype.upper()
            if upper_fxtype in ('SPOT', 'NDF'):
                sub_old_groups_data = old_groups_data["Groups_Spreads"]["FX" + upper_fxtype]
                group = sub_old_groups_data[alias]
                group['Alias'] = alias
                group['Type'] = upper_fxtype
                members_data = old_groups_data['Groups_Spreads_FX' + upper_fxtype + '_Memberships']
                members = tuple(k for k, v in members_data.items() if v == alias)
                with open(get_data_path('RobotFX_LegalEntities.json')) as json_file:
                    legal_entities_data = json.load(json_file)
                    list_members = []
                    for m in members:
                        alias = legal_entities_data[m]["Alias"]
                        name = legal_entities_data[m]['CounterpartyName']
                        list_members.append({'Alias': alias, 'Name': name, 'Cnpj': m})
            else:
                raise KeyError()
        read_only = True
        return render_template(
            'group-edit.html',
            group=json.dumps(group),
            members=json.dumps(list_members),
            read_only=json.dumps(read_only),
        )
    except KeyError:
        exc_info = sys.exc_info()
        return jsonify({'status': 'error', 'exception': ''.join(traceback.format_exception(*exc_info))})


@fxspot_bp.route('/group-add/<fxtype>')
@login_required(roles=['e-sales spot'])
def group_add(fxtype):
    group = {'Alias': '', 'Name': ''}
    upper_fxtype = fxtype.upper()
    if upper_fxtype in ('SPOT', 'NDF'):
        group['Type'] = upper_fxtype
    else:
        group['Type'] = 'undefined'
    read_only = False
    return render_template('group-edit.html', group=group, members=[], read_only=json.dumps(read_only))


@fxspot_bp.route('/currencies-put', methods=['PUT'])
@login_required(roles=['e-sales spot'])
def currencies_put():
    try:
        currencies = json.loads(request.data)['currencies']

        with open(get_data_path('RobotFX_Currencies.json'), "w") as json_file_out:
            json_file_out.write(json.dumps(currencies, indent=2))

        databus.update_from_file(get_data_path('RobotFX_Currencies.json'), 'Currencies')

        return jsonify({'status': 'ok'})
    except KeyError:
        exc_info = sys.exc_info()
        return jsonify({'status': 'error', 'exception': ''.join(traceback.format_exception(*exc_info))})
    except json.decoder.JSONDecodeError:
        return jsonify({'status': 'fail'})


@fxspot_bp.route('/bpipe_log_level', methods=['PUT'])
@login_required(roles=['e-sales spot'])
def bpipe_log_level():
    if request.json:
        os.environ['BLPAPI_LOGLEVEL'] = request.json['log_level']
        user_id = session.get("user_id", None)
        username = get_username(user_id)
        print(f"REBOOTING by: {username}", flush=True)
        ping_ip1 = subprocess.run(
            f"""sh /opt/robotfx/etc/robotfx.sh restart 'rfx-flask_website
                                                        rfx-legacy_mocks
                                                        rfx-frontend
                                                        rfx-fixserver'""",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            encoding="utf-8",
        )
        stdout_msg = ping_ip1.stdout
        stderr_msg = ping_ip1.stderr
        if not stderr_msg:
            return jsonify({'status': 'ok', 'msg': stdout_msg})
        else:
            return jsonify({'status': 'error', 'msg': stderr_msg})


@fxspot_bp.route('/currency-calendar-view/<cur>')
@login_required(roles=['e-sales spot'])
def currency_calendar_view(cur):
    try:
        holidays = []
        date_index = 0
        name_index = 1
        with open(
            get_data_path('Holydays_' + cur + '.csv', subdirs=['calendars']), newline='', encoding='utf-8'
        ) as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                if row:
                    holidays.append({'date': row[date_index], 'name': row[name_index]})

        return render_template('currency-calendar-view.html', currency=json.dumps(cur), holidays=json.dumps(holidays))
    except FileNotFoundError:
        return render_template('currency-calendar-view.html', currency=json.dumps(cur), holidays=json.dumps([]))


@fxspot_bp.route('/group-put', methods=['PUT'])
@login_required(roles=['e-sales spot'])
def group_put():
    try:
        json_req_data = json.loads(request.data)
        group = json_req_data['group']
        alias = json_req_data['alias']

        with open(get_data_path('RobotFX_LegalEntitiesRelationships.json')) as json_file:
            groups_data = json.load(json_file)
            work_data = groups_data["Groups_Spreads"]['FX' + group['Type']]

            # Se for o update de um grupo existente
            if group['Alias'] == alias:
                work_data[alias]["Name"] = group["Name"]
            else:
                alias = group['Alias']
                work_data[alias] = {'Name': group['Name']}

            groups_data["Groups_Spreads"]['FX' + group['Type']] = work_data

        with open(get_data_path('RobotFX_LegalEntitiesRelationships.json'), "w") as json_file_out:
            json_file_out.write(json.dumps(groups_data, indent=2))

        databus.update_from_file(get_data_path('RobotFX_LegalEntitiesRelationships.json'), 'LegalEntitiesRelationships')

        return jsonify({'status': 'ok'})
    except KeyError:
        exc_info = sys.exc_info()
        return jsonify({'status': 'error', 'exception': ''.join(traceback.format_exception(*exc_info))})


@fxspot_bp.route('/counterparty-data-edit/<cnpj>')
@login_required(roles=['e-sales spot'])
def counterparty_data_edit(cnpj):
    with open(get_data_path('RobotFX_LegalEntities.json')) as json_file:
        legal_entities_data = json.load(json_file)
        counterparty = legal_entities_data[cnpj]
        counterparty['Cnpj'] = cnpj

    read_only = True

    alias_ndf = []
    alias_spot = []
    with open(get_data_path('RobotFX_LegalEntitiesRelationships.json')) as json_file:
        groups_data = json.load(json_file)

        spreads_data = groups_data.get('Groups_Spreads', {})
        spot_groups = spreads_data.get('FXSPOT', {})
        alias_spot = list(spot_groups.keys())
        alias_spot.insert(0, '')
        ndf_groups = spreads_data.get('FXNDF', {})
        alias_ndf = list(ndf_groups.keys())
        alias_ndf.insert(0, '')

        spot_members_data = groups_data.get("Groups_Spreads_FXSPOT_Memberships", {})
        selected_spot = spot_members_data.get(cnpj, None)
        ndf_members_data = groups_data.get("Groups_Spreads_FXNDF_Memberships", {})
        selected_ndf = ndf_members_data.get(cnpj, None)

    return render_template(
        'counterparty-edit-spot.html',
        counterparty=json.dumps(counterparty),
        alias_ndf=json.dumps(alias_ndf),
        alias_spot=json.dumps(alias_spot),
        selected_ndf=json.dumps(selected_ndf),
        selected_spot=json.dumps(selected_spot),
        read_only=json.dumps(read_only),
    )


@fxspot_bp.route('/calendar-cur-post/<cur>', methods=['POST'])
@login_required(roles=['e-sales spot'])
def calendar_cur_post(cur):
    try:
        if '0' not in request.files:
            return jsonify({'status': 'fail'})

        x = request.files['0']

        path = get_data_path('Holydays_{currency}.csv'.format(currency=cur), subdirs=['calendars'])
        x.save(path)

        date_index = 0
        name_index = 1
        with open(path, 'r') as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                try:
                    if row:
                        datetime.datetime.strptime(row[date_index], "%Y-%m-%d")
                        if not row[name_index]:
                            raise Exception('Invalid file contents!')
                except ValueError:
                    raise Exception('Invalid file contents!')

        return jsonify({'status': 'ok'})
    except (KeyError, Exception):
        exc_info = sys.exc_info()
        return jsonify({'status': 'error', 'exception': ''.join(traceback.format_exception(*exc_info))})
