import os
import json
import redis
from lib.libdatabus import databus
from functools import wraps
from flask import request, redirect, url_for, session
# from lib.history.tables import connect_to_transactions_db


red = redis.StrictRedis(charset="utf-8", decode_responses=True)


# SessionMaker = connect_to_transactions_db()


def event_stream(tag_subscription='blotter'):
    pubsub = red.pubsub()
    pubsub.subscribe(tag_subscription)

    for message in pubsub.listen():
        if type(message['data']) != str:
            continue

        data = json.loads(message['data'])
        if type(data) != str:
            continue

        yield 'data: {}\n\n'.format(data)


def get_data_path(filename, subdirs=[]):
    datadir = os.getenv('ROBOTFX_DATADIR')
    if subdirs:
        datadir = os.path.join(datadir, *subdirs)
    return os.path.join(datadir, filename)


def get_user_role(user_id):
    user_role_databus_key = f"ActiveUsers/{user_id}/Role"
    user_role = databus.get(user_role_databus_key)
    return user_role if user_role else None


def get_username(user_id):
    username_databus_key = f"ActiveUsers/{user_id}/Username"
    username = databus.get(username_databus_key)
    return username if username else None


def login_required(roles=[]):
    default_url = 'auth_bp.logout'
    def redirect_to_logout():
        session['login_error_msg'] = (
            'Access Denied. You don\'t have' + ' permission to access \'' + request.path + '\' on this server.'
        )
        return redirect(url_for(default_url))

    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            # user_id = session.get("user_id", None)
            user_id = kwargs["user_id"]
            username_databus_key = f"ActiveUsers/{user_id}"
            # user_id = databus.get(username_databus_key)

            if not username_databus_key:
                return redirect_to_logout()

            username = get_username(user_id)
            if not username:
                return redirect_to_logout()

            with open('/home/duanribeiro/PycharmProjects/exemplo_flask_decorator/data/RobotFX_Users.json') as json_file:
                file_dict = json.load(json_file)

                if username not in file_dict:
                    return redirect_to_logout()

                user_data = file_dict[username]
                role = user_data['role']
                if role not in roles:
                    return redirect_to_logout()

                user_role = get_user_role(user_id)
                if user_role != role:
                    return redirect_to_logout()

            if 'login_error_msg' in session:
                del session['login_error_msg']

            return fn(*args, **kwargs)

        return decorated_view

    return wrapper


def manage_spreads_tables(data, is_ndf=True):
    if is_ndf:
        qname = 'spreads-table-ndf'
    else:
        qname = 'spreads-table-spot'

    red.publish(qname, data)


def spread_transaction_getter(is_ndf, is_group):
    basic_key = 'SpreadRegistry/' + ('NDF' if is_ndf else 'SPOT') + '/' + ('group' if is_group else 'counterparty')

    if databus.exists(basic_key):
        transactions = databus.get(basic_key)
        transactions = sorted(transactions, key=lambda x: x['ts'], reverse=True)
    else:
        transactions = []

    return json.dumps(transactions)


def get_currencies_sorted():
    dic = databus.get_dict('Currencies')
    result = sorted(dic.keys(), key=lambda x: dic[x]['ViewPriority'])
    try:
        result.remove('BRL')
    except ValueError:
        pass
    return json.dumps(result)


def get_currencies_sorted_list():
    currencies = databus.get_dict('Currencies')
    currencies_sorted = sorted(currencies.keys(), key=lambda x: currencies[x]['ViewPriority'])
    try:
        currencies_sorted.remove('BRL')
    except ValueError:
        pass
    return currencies_sorted


def blotter_transactions():
    blotter_msgs = databus.get('Blotter')
    l_messages = []
    if blotter_msgs:
        for t in blotter_msgs:
            msg = databus.get('Blotter/{}'.format(t))
            l_messages.append(json.loads(msg))
        l_messages = sorted(l_messages, key=lambda x: x['quote_req_id'])
    return l_messages
