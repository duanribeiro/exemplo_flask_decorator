from flask import Blueprint
from flask import render_template
from flask import jsonify
from flask import request
from lib.libflask import login_required
from lib.libflask import get_data_path
from lib.libflask import get_currencies_sorted
from lib.libflask import get_username
from lib.libflask import session
from lib.libdatabus import databus
import traceback
import json
import sys
import os
import csv
import datetime
import subprocess


fxconfig_bp = Blueprint('fxconfig_bp', __name__, url_prefix='/fxconfig')


@fxconfig_bp.route('/config')
@login_required(roles=['ti', 'si'])
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
        'config-main.html',
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


@fxconfig_bp.route('/time-buckets-put', methods=['PUT'])
@login_required(roles=['e-sales ndf', 'ti'])
def put_time_buckets():
    time_buckets = request.json['time_buckets']
    with open(get_data_path('RobotFX_NDFTimeBuckets.json')) as json_file:
        time_buckets_data = json.load(json_file)
        time_buckets_data['TimeBuckets'] = time_buckets

    with open(get_data_path('RobotFX_NDFTimeBuckets.json'), 'w') as json_file_out:
        json_file_out.write(json.dumps(time_buckets_data, indent=2))

    databus.update_from_file(get_data_path('RobotFX_NDFTimeBuckets.json'), 'NDFTimeBuckets')

    return jsonify({'status': 'ok'})


@fxconfig_bp.route('/counterparty-delete', methods=['PUT'])
@login_required(roles=['ti'])
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


@fxconfig_bp.route('/counterparty-data-add')
@login_required(roles=['ti'])
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
        alias_spot = list(spot_groups.keys())
        alias_spot.insert(0, '')
        ndf_groups = spreads_data.get('FXNDF', {})
        alias_ndf = list(ndf_groups.keys())
        alias_ndf.insert(0, '')

        selected_spot = ''
        selected_ndf = ''

    return render_template(
        'counterparty-edit.html',
        counterparty=json.dumps(counterparty),
        alias_ndf=json.dumps(alias_ndf),
        alias_spot=json.dumps(alias_spot),
        selected_ndf=json.dumps(selected_ndf),
        selected_spot=json.dumps(selected_spot),
        read_only=json.dumps(read_only),
    )


@fxconfig_bp.route('/counterparty-config-put', methods=['PUT'])
@login_required(roles=['ti'])
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


@fxconfig_bp.route('/group-delete/<fxtype>', methods=['PUT'])
@login_required(roles=['ti'])
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


@fxconfig_bp.route('/group-edit/<fxtype>/<alias>')
@login_required(roles=['ti'])
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


@fxconfig_bp.route('/group-add/<fxtype>')
@login_required(roles=['ti'])
def group_add(fxtype):
    group = {'Alias': '', 'Name': ''}
    upper_fxtype = fxtype.upper()
    if upper_fxtype in ('SPOT', 'NDF'):
        group['Type'] = upper_fxtype
    else:
        group['Type'] = 'undefined'
    read_only = False
    return render_template('group-edit.html', group=group, members=[], read_only=json.dumps(read_only))


@fxconfig_bp.route('/currencies-put', methods=['PUT'])
@login_required(roles=['ti'])
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


@fxconfig_bp.route('/bpipe_log_level', methods=['PUT'])
@login_required(roles=['ti'])
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


@fxconfig_bp.route('/currency-calendar-view/<cur>')
@login_required(roles=['ti'])
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


@fxconfig_bp.route('/group-put', methods=['PUT'])
@login_required(roles=['ti'])
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


@fxconfig_bp.route('/counterparty-data-edit/<cnpj>')
@login_required(roles=['ti'])
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
        'counterparty-edit.html',
        counterparty=json.dumps(counterparty),
        alias_ndf=json.dumps(alias_ndf),
        alias_spot=json.dumps(alias_spot),
        selected_ndf=json.dumps(selected_ndf),
        selected_spot=json.dumps(selected_spot),
        read_only=json.dumps(read_only),
    )


@fxconfig_bp.route('/calendar-cur-post/<cur>', methods=['POST'])
@login_required(roles=['ti'])
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


@fxconfig_bp.route('/system_reboot')
@login_required(roles=['ti'])
def reboot():
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
        return jsonify({'status': 'success', 'msg': stdout_msg})
    else:
        return jsonify({'status': 'error', 'msg': stderr_msg})
