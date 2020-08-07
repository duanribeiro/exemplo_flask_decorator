import json
import datetime
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
from flask import send_from_directory
from flask import abort
from flask import session
from flask import Response
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
from lib.libdatabus import databus
from lib.history.crud_transactions import get_day_trade_info
from lib.history.crud_transactions import get_daily_stats
from lib.history.crud_transactions import get_day_reject_info
from lib.history.crud_transactions import get_transactions_report

fxndf_bp = Blueprint('fxndf_bp', __name__, url_prefix='/fxndf')


@fxndf_bp.route('/spreads_ndf_counterparty_transactions')
@login_required(roles=['e-sales ndf', 'fx-supplier'])
def spreads_ndf_counterparty_transactions():
    return spread_transaction_getter(is_ndf=True, is_group=False)


@fxndf_bp.route('/spreads_ndf_group_transactions')
@login_required(roles=['e-sales ndf', 'fx-supplier'])
def spreads_ndf_group_transactions():
    return spread_transaction_getter(is_ndf=True, is_group=True)


@fxndf_bp.route('/engine-parameters-ndf-put', methods=['PUT'])
@login_required(roles=['e-sales ndf'])
def engine_parameters_ndf_put():
    engine_parameters = json.loads(request.data)
    status = 'ok'
    try:
        datetime.datetime.strptime(engine_parameters['engine_parameters']['EngineOnlineEndTime'], "%H:%M")
    except ValueError:
        status = 'ok - Not a valid date.'

    if status == 'ok':
        with open(get_data_path('RobotFX_TradingParameters.json')) as json_file:
            old_obj = json.load(json_file)
            old_obj["Engine_Global_Parameters"]["FXNDF"] = engine_parameters['engine_parameters']

        with open(get_data_path('RobotFX_TradingParameters.json'), "w") as json_file_out:
            json_file_out.write(json.dumps(old_obj, sort_keys=True, indent=4))

        databus.update_from_file(get_data_path('RobotFX_TradingParameters.json'), 'TradingParameters')

    return jsonify({'status': status})


@fxndf_bp.route('/blotter-ndf-dealid-popup', methods=['GET'])
@login_required(roles=['e-sales ndf'])
def getBlotterNdfPopup():
    deal_id = request.args.get('dealid', '')
    if not deal_id:
        abort(404, description="Resource not found")

    try:
        info = json.loads(databus.get('Blotter/{deal_id}'.format(deal_id=deal_id)))
    except TypeError:
        abort(404, description="Resource not found")

    return render_template('blotter-ndf-dealid-popup.html', deal_id=json.dumps(deal_id), info=info)


@fxndf_bp.route('/trading-parameters-ndf')
@login_required(roles=['e-sales ndf'])
def trading_parameters_ndf():
    trading_parameters = databus.get_dict('TradingParameters')
    engine_parameters = json.dumps(trading_parameters["Engine_Global_Parameters"]["FXNDF"])
    currency_keys = json.dumps(trading_parameters["CurrencyKeys"])
    counterparty_list = []
    leg_entities = databus.get_dict('LegalEntities')
    if leg_entities is None:
        leg_entities = {}
    trad_counterparties = trading_parameters['CounterpartyKeys']
    common_cp_keys = tuple(k for k, v in leg_entities.items() if 'FXNDF' in v['Products'])
    for cp_key in common_cp_keys:
        trad_value = trad_counterparties[cp_key]['FXNDF']
        validate_kyc_rule = update_validate_rule(trad_value['ValidateKYC'], 'KYC', cp_key, True)
        validate_isda_rule = update_validate_rule(trad_value['ValidateISDA'], 'ISDA', cp_key, True)
        counterparty_list.append(
            {
                'cter_prty_id': cp_key,
                'counterparty': leg_entities[cp_key]["CounterpartyName"],
                'upper_limit_dc': trad_value['UpperLimitDays2Maturity'],
                'automatic_flow': trad_value['AutoFlow'],
                'validate_kyc': validate_kyc_rule,
                'validate_isda': validate_isda_rule,
            }
        )

    with open(get_data_path('RobotFX_Users.json')) as json_file:
        user_data = json.load(json_file)
        user_id = session.get("user_id", None)
        username = get_username(user_id)
        if username not in user_data:
            return render_template('404.html')

        response_data = user_data[username]
        allow_validate = response_data['allow_validate'].lower() == 'yes'

    validate_parameters = get_validate_parameters()

    json_sorted_currencies = get_currencies_sorted()
    return render_template(
        'trading-parameters-ndf.html',
        engine_parameters=engine_parameters,
        currency_keys=currency_keys,
        counterparty_data=json.dumps(counterparty_list),
        sorted_currencies=json_sorted_currencies,
        allow_validate=json.dumps(allow_validate),
        validate_parameters=json.dumps(validate_parameters),
    )


@fxndf_bp.route('/currency-keys-ndf-put', methods=['PUT'])
@login_required(roles=['e-sales ndf'])
def currency_keys_ndf_put():
    currency_keys = json.loads(request.data)
    with open(get_data_path('RobotFX_TradingParameters.json')) as json_file:
        old_obj = json.load(json_file)
        old_obj["CurrencyKeys"] = currency_keys['currency_keys']

    with open(get_data_path('RobotFX_TradingParameters.json'), "w") as json_file_out:
        json_file_out.write(json.dumps(old_obj, sort_keys=True, indent=4))

    databus.update_from_file(get_data_path('RobotFX_TradingParameters.json'), 'TradingParameters')

    return jsonify({'status': 'ok'})


@fxndf_bp.route('/counterparty-ndf-put', methods=['PUT'])
@login_required(roles=['e-sales ndf'])
def counterparty_ndf_put():
    counterparty_ndf = json.loads(request.data)['counterparty_data']
    with open(get_data_path('RobotFX_TradingParameters.json')) as json_file:
        old_obj = json.load(json_file)
        alt_obj = copy.deepcopy(old_obj)
        for cter_prty in counterparty_ndf:
            autoflow = cter_prty['automatic_flow']
            upper_limmit_dc = cter_prty['upper_limit_dc']
            validate_kyc = cter_prty['validate_kyc']
            validate_kyc = validate_kyc if validate_kyc != 'NO: GOOD-TODAY' else 'YES'
            validate_isda = cter_prty['validate_isda']
            validate_isda = validate_isda if validate_isda != 'NO: GOOD-TODAY' else 'YES'
            fxndf_obj = old_obj["CounterpartyKeys"][cter_prty['cter_prty_id']]["FXNDF"]
            fxndf_obj["AutoFlow"] = autoflow
            fxndf_obj["UpperLimitDays2Maturity"] = upper_limmit_dc
            fxndf_obj["ValidateKYC"] = validate_kyc
            fxndf_obj["ValidateISDA"] = validate_isda
            fxndf_obj2 = alt_obj["CounterpartyKeys"][cter_prty['cter_prty_id']]["FXNDF"]
            fxndf_obj2["AutoFlow"] = autoflow
            fxndf_obj2["UpperLimitDays2Maturity"] = upper_limmit_dc
            fxndf_obj2["ValidateKYC"] = validate_kyc
            fxndf_obj2["ValidateISDA"] = validate_isda

    with open(get_data_path('RobotFX_TradingParameters.json'), "w") as json_file_out:
        json_file_out.write(json.dumps(old_obj, sort_keys=True, indent=4))

    databus.update_from_dict(alt_obj, 'TradingParameters')
    return jsonify({'status': 'ok'})


@fxndf_bp.route('/engine-control-ndf')
@login_required(roles=['e-sales ndf'])
def engine_control_ndf():
    with open(get_data_path('RobotFX_TradingParameters.json')) as json_file:
        trading_parameters = json.load(json_file)
        engine_parameters = trading_parameters["Engine_Global_Parameters"]["FXNDF"]

        return render_template('engine-control-ndf.html', engine_parameters=json.dumps(engine_parameters))


@fxndf_bp.route('/spreads-ndf-get', methods=['GET'])
@login_required(roles=['e-sales ndf'])
def spreads_ndf_get():
    search_by_group = request.args.get('search_by', '').lower() == 'group'
    key = request.args.get('key', '').upper()

    sorted_currencies = json.loads(get_currencies_sorted())

    with open(get_data_path('RobotFX_Client_Spreads.json')) as json_file:
        all_spreads = json.load(json_file)

        try:
            if search_by_group:
                all_spreads = all_spreads['GroupSpreads']
            else:
                all_spreads = all_spreads['CounterpartySpreads']

            spreads_by_product = all_spreads[key]
            spreads = spreads_by_product['FXNDF']
        except KeyError:
            spreads = {'Spreads': {}}
            with open(get_data_path('RobotFX_NDFTimeBuckets.json')) as json_file:
                buckets_l = json.load(json_file).get('TimeBuckets')
                buckets = [value['EndDay'] for value in buckets_l]
                spreads['Buckets'] = buckets
            for ccy in sorted_currencies:
                spreads['Spreads'][ccy] = {'BUYSELL': [None] * len(buckets)}

    result = {'spreads_catalog': spreads, 'currencies': sorted_currencies}
    return jsonify(result)


@fxndf_bp.route('/spreads-ndf-put', methods=['PUT'])
@login_required(roles=['e-sales ndf'])
def spreads_ndf_put():
    now = get_local_time()
    print('ndf put.....')
    type_update = request.args.get('type', '').lower()
    update_group = type_update == 'group'
    key = request.args.get('key', '').upper()
    if 'status' not in request.json:
        return jsonify({'status': 'error', 'exception': 'Status data is not in Request\'s JSON\'s Content.'})

    status = request.json['status']
    if ('currency' in status) and ('bucket' in status) and ('spread' in status):
        currency = status['currency']
        bucket = status['bucket']
        spread = status['spread']
        if spread is None:
            spread = '-'

        if spread != '-':
            spread = int(Decimal(spread) * 10_000)  # Solucao de caso de spread igual a: 12, 24 ou 48.

        basic_key = 'SpreadRegistry/NDF/' + type_update

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
            'bucket': str(bucket),
            'spread': str(spread),
        }

        if not update_group:
            element['counterparty'] = databus.get('LegalEntities/{cnpj}/CounterpartyName'.format(cnpj=key))
            basic_group_key = 'LegalEntitiesRelationships/Groups_Spreads_'
            if databus.exists((basic_group_key + 'FX{type}_Memberships/{cnpj}').format(cnpj=key, type='NDF')):
                element['group'] = databus.get(
                    (basic_group_key + 'FX{type}_Memberships/{cnpj}').format(cnpj=key, type="NDF")
                )
            else:
                element['group'] = '-'

        data_list.append(element)

        databus.set(basic_key, data_list)

        manage_spreads_tables(1, is_ndf=True)

    with open(get_data_path('RobotFX_Client_Spreads.json')) as json_file:
        all_spreads = json.load(json_file)
        entity_type = 'GroupSpreads' if update_group else 'CounterpartySpreads'
        if key not in all_spreads[entity_type]:
            all_spreads[entity_type][key] = {}

        all_spreads[entity_type][key]['FXNDF'] = request.json['spreads_catalog']

    with open(get_data_path('RobotFX_Client_Spreads.json'), 'w') as json_file_out:
        json_file_out.write(json.dumps(all_spreads, indent=2))

    databus.update_from_file(get_data_path('RobotFX_Client_Spreads.json'), 'ClientSpreads')

    return jsonify({'status': 'ok'})


@fxndf_bp.route('/market-data-ndf')
@login_required(roles=['e-sales ndf'])
def market_data_ndf():
    return render_template('market-data-ndf.html', sec_type='NDF')


@fxndf_bp.route("/statistics-ndf")
@login_required(roles=["e-sales ndf", "supervisor"])
def statistics_ndf():
    fx_product = "NDF"
    session = SessionMaker()
    currencies = get_currencies_sorted_list()
    daily_stats_dict = get_daily_stats(session, fx_product, currencies)
    session.close()
    daily_stats_json = json.dumps(daily_stats_dict)
    sorted_currencies = get_currencies_sorted()

    return render_template("statistics-ndf.html", daily_stats=daily_stats_json, sorted_currencies=sorted_currencies)


@fxndf_bp.route("/statistics-ndf-day-popup", methods=["GET"])
@login_required(roles=["e-sales ndf", "supervisor"])
def getStatisticsNDFPopup():
    transact_date = request.args.get("day", "")
    if not transact_date:
        abort(404, description="Resource not found")

    fx_product = "NDF"
    session = SessionMaker()
    currencies = get_currencies_sorted_list()
    day_trade_info_dict = get_day_trade_info(session, fx_product, transact_date, currencies)
    session.close()
    day_trade_info_json = json.dumps(day_trade_info_dict)

    return render_template("statistics-ndf-day-popup.html", transact_date_info=day_trade_info_json)


@fxndf_bp.route("/statistics-ndf-day-reject-popup", methods=["GET"])
@login_required(roles=["e-sales ndf", "supervisor"])
def getStatisticsNDFRejectPopup():
    transact_date = request.args.get("day", "")
    if not transact_date:
        abort(404, description="Resource not found")

    fx_product = "NDF"
    session = SessionMaker()
    day_reject_info_list = get_day_reject_info(session, fx_product, transact_date)
    session.close()
    day_reject_info_json = json.dumps(day_reject_info_list)

    return render_template(
        "statistics-day-reject-popup.html", transact_date=transact_date, day_reject_info_json=day_reject_info_json,
    )


@fxndf_bp.route("/statistics-report", methods=["GET"])
@login_required(roles=["e-sales ndf", "supervisor"])
def statisticsReport():
    startDate = request.args.get("startDate")
    endDate = request.args.get("endDate")

    if not startDate or not endDate:
        abort(404, description="Dates must be defined to export CSV report")

    fx_product = "NDF"
    startDate = datetime.datetime.strptime(startDate, "%Y-%m-%d").date()
    endDate = datetime.datetime.strptime(endDate, "%Y-%m-%d").date()

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


@fxndf_bp.route('/balance_ndf')
@login_required(roles=['e-sales ndf', 'fx-supplier'])
def balance_ndf():
    data = databus.get_dict('Balance/NDF')
    return json.dumps(data)


@fxndf_bp.route('/blotter-ndf')
@login_required(roles=['e-sales ndf'])
def blotter_ndf():
    json_sorted_currencies = get_currencies_sorted()
    return render_template('blotter-ndf.html', sorted_currencies=json_sorted_currencies)


@fxndf_bp.route('/spreads-ndf')
@login_required(roles=['e-sales ndf'])
def spreads_ndf():
    legal_entities = {}

    with open(get_data_path('RobotFX_LegalEntitiesRelationships.json')) as rel_leg_ent_json:
        rel_leg_ents = json.load(rel_leg_ent_json)
        wgrp = rel_leg_ents['Groups_Spreads']['FXNDF']
        groups = {elem: {'NameHolding': name['Name']} for elem, name in wgrp.items()}

    with open(get_data_path('RobotFX_LegalEntities.json')) as json_file:
        counterparties = json.load(json_file)
        counterparties = {k: v for k, v in counterparties.items() if 'FXNDF' in v['Products']}
        legal_entities = {'Groups': groups, 'Counterparties': counterparties}

    return render_template('spreads-ndf.html', legal_entities=json.dumps(legal_entities))


@fxndf_bp.route('/halt-ndf', methods=['GET', 'PUT'])
@login_required(roles=['e-sales ndf'])
def halt_ndf():
    if request.method == 'GET':
        status_trading_ndf = databus.get_dict('System/Status/Trading/NDF')
        status_supplier = databus.get_dict('System/Status/Quoting')
        status_trading_ndf.update(status_supplier)
        return jsonify(status_trading_ndf)
    if request.method == 'PUT':
        ndf_key = databus.get_dict('System/Status/General/NDF')
        if ndf_key:
            databus.update_from_dict(json.loads(request.data), "System/Status/Trading")
            return jsonify({'status': 'ok'})
        else:
            return jsonify({'status': 'ok - halted'})


@fxndf_bp.route('/stream')
@login_required(roles=['e-sales ndf'])
def stream():
    return Response(
        event_stream(), mimetype="text/event-stream", headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'}
    )


@fxndf_bp.route('/transactions')
@login_required(roles=['e-sales ndf'])
def transactions():
    return json.dumps(blotter_transactions())


# O código abaixo está "duplicado"
# O mesmo se encontra nas blueprints fxndf, fxspot, e fxconfig.
# TODO: Estudar solução mais eficiente futuramente.


@fxndf_bp.route('/config')
@login_required(roles=['e-sales ndf'])
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
        'config-main-ndf.html',
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


@fxndf_bp.route('/time-buckets-put', methods=['PUT'])
@login_required(roles=['e-sales ndf'])
def put_time_buckets():
    time_buckets = request.json['time_buckets']
    with open(get_data_path('RobotFX_NDFTimeBuckets.json')) as json_file:
        time_buckets_data = json.load(json_file)
        time_buckets_data['TimeBuckets'] = time_buckets

    with open(get_data_path('RobotFX_NDFTimeBuckets.json'), 'w') as json_file_out:
        json_file_out.write(json.dumps(time_buckets_data, indent=2))

    databus.update_from_file(get_data_path('RobotFX_NDFTimeBuckets.json'), 'NDFTimeBuckets')

    return jsonify({'status': 'ok'})


@fxndf_bp.route('/counterparty-delete', methods=['PUT'])
@login_required(roles=['e-sales ndf'])
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


@fxndf_bp.route('/counterparty-data-add')
@login_required(roles=['e-sales ndf'])
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
        'counterparty-edit-ndf.html',
        counterparty=json.dumps(counterparty),
        alias_ndf=json.dumps(alias_ndf),
        alias_spot=json.dumps(alias_spot),
        selected_ndf=json.dumps(selected_ndf),
        selected_spot=json.dumps(selected_spot),
        read_only=json.dumps(read_only),
    )


@fxndf_bp.route('/counterparty-config-put', methods=['PUT'])
@login_required(roles=['e-sales ndf'])
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


@fxndf_bp.route('/group-delete/<fxtype>', methods=['PUT'])
@login_required(roles=['e-sales ndf'])
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


@fxndf_bp.route('/group-edit/<fxtype>/<alias>')
@login_required(roles=['e-sales ndf'])
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


@fxndf_bp.route('/group-add/<fxtype>')
@login_required(roles=['e-sales ndf'])
def group_add(fxtype):
    group = {'Alias': '', 'Name': ''}
    upper_fxtype = fxtype.upper()
    if upper_fxtype in ('SPOT', 'NDF'):
        group['Type'] = upper_fxtype
    else:
        group['Type'] = 'undefined'
    read_only = False
    return render_template('group-edit.html', group=group, members=[], read_only=json.dumps(read_only))


@fxndf_bp.route('/currencies-put', methods=['PUT'])
@login_required(roles=['e-sales ndf'])
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


@fxndf_bp.route('/bpipe_log_level', methods=['PUT'])
@login_required(roles=['e-sales ndf'])
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


@fxndf_bp.route('/currency-calendar-view/<cur>')
@login_required(roles=['e-sales ndf'])
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


@fxndf_bp.route('/group-put', methods=['PUT'])
@login_required(roles=['e-sales ndf'])
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


@fxndf_bp.route('/counterparty-data-edit/<cnpj>')
@login_required(roles=['e-sales ndf'])
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
        'counterparty-edit-ndf.html',
        counterparty=json.dumps(counterparty),
        alias_ndf=json.dumps(alias_ndf),
        alias_spot=json.dumps(alias_spot),
        selected_ndf=json.dumps(selected_ndf),
        selected_spot=json.dumps(selected_spot),
        read_only=json.dumps(read_only),
    )


@fxndf_bp.route('/calendar-cur-post/<cur>', methods=['POST'])
@login_required(roles=['e-sales ndf'])
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
