from flask import Blueprint
from flask import render_template
from flask import session
from flask import request
from flask import redirect
from flask import url_for
from flask import jsonify
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash
from lib.libflask import login_required
from lib.libflask import get_data_path
from lib.libflask import get_user_role
from lib.libflask import get_username
from lib.libdatabus import databus
import json
import traceback
import sys
import uuid

auth_bp = Blueprint('auth_bp', __name__, url_prefix='/auth')
default_type_profiles = {}


def get_user_profile_option_list():
    global default_type_profiles
    if not default_type_profiles:
        with open(get_data_path('RobotFX_TypeProfiles.json')) as json_file:
            default_type_profiles = json.load(json_file)

    return [{'value': k, 'text': v} for k, v in default_type_profiles.items()]


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        req_data = request.form
        username = req_data.get('username', '').lower()
        if not username:
            session["login_error_msg"] = "Incorrect username or password."
            return redirect(url_for("auth_bp.login"))

        # hidden_login_code = req_data.get('hidden_login_code', '')
        # hidden_login_code_databus_key = "HiddenLoginCode"
        # hidden_login_code_in_databus = databus.get(hidden_login_code_databus_key)
        # if hidden_login_code != hidden_login_code_in_databus:
        #     session["login_error_msg"] = "Incorrect username or password."
        #     return redirect(url_for("auth_bp.login"))

        try:
            with open('/home/duanribeiro/PycharmProjects/exemplo_flask_decorator/data/RobotFX_Users.json') as json_file:
                file_dict = json.load(json_file)

                if username not in file_dict:
                    session["login_error_msg"] = "Incorrect username or password."
                    return redirect(url_for("auth_bp.login"))

                user_data = file_dict[username]

                hash_pwd = user_data['password']
                password = req_data.get('password', '')
                if not check_password_hash(hash_pwd, password):
                    session["login_error_msg"] = "Incorrect username or password."
                    return redirect(url_for("auth_bp.login"))

                redirct_url_dic = {
                    "e-sales ndf": "fxndf_bp.blotter_ndf",
                    "e-sales spot": "fxspot_bp.blotter_spot",
                    "ti": "log_bp.log",
                    "si": "auth_bp.user_management",
                    "fx-supplier": "fxsupplier_bp.supplier_control",
                    "supervisor": "fxspot_bp.statistics_spot",
                }

                user_id = str(uuid.uuid4())
                user_id_databus_key = f"ActiveUsers/{user_id}"
                databus.set(user_id_databus_key, user_id)
                session["user_id"] = user_id

                user_role = user_data["role"]
                user_role_databus_key = f"ActiveUsers/{user_id}/Role"
                databus.set(user_role_databus_key, user_role)
                session["role"] = user_role

                username_databus_key = f"ActiveUsers/{user_id}/Username"
                databus.set(username_databus_key, username)
                session["username"] = username

                # databus.delete(hidden_login_code_databus_key)
                # return redirect(url_for(redirct_url_dic[user_role]))
                return {"user_id": user_id}

        except Exception:
            session["login_error_msg"] = "Incorrect username or password."
            return redirect(url_for('auth_bp.login'))

    hidden_login_code = str(uuid.uuid4())
    # hidden_login_code = '123'
    # hidden_login_code_databus_key = "HiddenLoginCode"
    # databus.set(hidden_login_code_databus_key, hidden_login_code)
    login_error_msg = session.get('login_error_msg', None)
    session.pop('login_error_msg', None)
    return render_template('login.html', hidden_login_code=hidden_login_code, login_error_msg=login_error_msg)


@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('auth_bp.login'))


@auth_bp.route('/user_own_pwd_edit')
@login_required(roles=['e-sales ndf', 'e-sales spot', 'fx-supplier', 'ti', 'supervisor', 'si'])
def user_own_pwd_edit():
    try:
        user_id = session['user_id']
        user_role = get_user_role(user_id)
        username = get_username(user_id)
        return render_template('user_own_pwd_edit.html', username=username, oldpass='', user_role=user_role)
    except KeyError:
        return render_template('404.html')

    return render_template('404.html')


@auth_bp.route('/user_own_pwd_save', methods=['PUT'])
@login_required(roles=['e-sales ndf', 'e-sales spot', 'fx-supplier', 'ti', 'supervisor', 'si'])
def user_own_pwd_save():
    try:
        with open(get_data_path('RobotFX_Users.json')) as json_file:
            users = json.load(json_file)
            user_pwd = request.json['data']
            username = user_pwd['username']

            old_pwd = user_pwd['old_pwd']
            old_hash_pwd = users[username]['password']
            if not check_password_hash(old_hash_pwd, old_pwd):
                return jsonify({'status': 'bad_old_pwd'})

            new_password = user_pwd['password']
            users[username]['password'] = generate_password_hash(new_password)

        with open(get_data_path('RobotFX_Users.json'), 'w') as json_file_out:
            json_file_out.write(json.dumps(users))

        return jsonify({'status': 'ok'})
    except Exception:
        exc_info = sys.exc_info()
        return jsonify(
            {
                'status': 'error',
                'exception': ''.join(
                    [
                        ''.join(traceback.format_exception(*exc_info)),
                        ' e o request foi: ',
                        json.dumps(request.json['data'], indent=2),
                    ]
                ),
            }
        )


@auth_bp.route('/user_pwd_edit', methods=['POST'])
@login_required(roles=['si'])
def user_pwd_edit():
    try:
        with open(get_data_path('RobotFX_Users.json')) as json_file:
            user_data = json.load(json_file)
            username = request.form['username']
            password = request.form['password']
            if username in user_data:
                hash_password = user_data[username]['password']
                if hash_password == password:
                    return render_template('user_pwd_edit.html', username=username)
    except KeyError:
        return render_template('404.html')

    return render_template('404.html')


@auth_bp.route('/save_new_user', methods=['PUT'])
@login_required(roles=['si'])
def save_new_user():
    try:
        with open(get_data_path('RobotFX_Users.json')) as json_file:
            users = json.load(json_file)

        user_dict = request.json['data']
        username = user_dict['username'].lower()
        del user_dict['username']
        if username in users:
            return jsonify({'status': 'duplicate'})

        user_dict['password'] = generate_password_hash(user_dict['password'])
        del user_dict['confirm_password']

        if 'errors' in user_dict:
            del user_dict['errors']

        if user_dict['role'] in ('e-sales ndf', 'e-sales spot'):
            user_dict['allow_validate'] = 'Yes' if user_dict['allow_validate'] else 'No'
        else:
            user_dict['allow_validate'] = 'N/A'

        users[username] = user_dict

        with open(get_data_path('RobotFX_Users.json'), 'w') as json_file_out:
            json_file_out.write(json.dumps(users, indent=2))

        return jsonify({'status': 'ok'})
    except Exception:
        exc_info = sys.exc_info()
        return jsonify(
            {
                'status': 'error',
                'exception': ''.join(
                    [
                        ''.join(traceback.format_exception(*exc_info)),
                        ' e o request foi: ',
                        json.dumps(request.json['data'], indent=2),
                    ]
                ),
            }
        )


@auth_bp.route('/save_old_user', methods=['PUT'])
@login_required(roles=['si'])
def save_old_user():
    try:
        with open(get_data_path('RobotFX_Users.json')) as json_file:
            users = json.load(json_file)

        user_dict = request.json['data']
        username = user_dict['username'].lower()
        if username not in users:
            return jsonify({'status': 'error'})
        del user_dict['username']

        for key in ("confirm_password", 'errors'):
            if key in user_dict:
                del user_dict[key]

        user_dict['allow_validate'] = 'Yes' if user_dict['allow_validate'] else 'No'

        users[username] = user_dict

        with open(get_data_path('RobotFX_Users.json'), 'w') as json_file_out:
            json_file_out.write(json.dumps(users, indent=2))

        return jsonify({'status': 'ok'})
    except Exception:
        exc_info = sys.exc_info()
        return jsonify(
            {
                'status': 'error',
                'exception': ''.join(
                    [
                        ''.join(traceback.format_exception(*exc_info)),
                        ' e o request foi: ',
                        json.dumps(request.json['data'], indent=2),
                    ]
                ),
            }
        )


@auth_bp.route('/user_pwd_save', methods=['PUT'])
@login_required(roles=['si'])
def user_pwd_save():
    try:
        with open(get_data_path('RobotFX_Users.json')) as json_file:
            users = json.load(json_file)
            user_pwd = request.json['data']
            username = user_pwd['username']

            new_password = user_pwd['password']
            new_password = user_pwd['password']
            users[username]['password'] = generate_password_hash(new_password)

        with open(get_data_path('RobotFX_Users.json'), 'w') as json_file_out:
            json_file_out.write(json.dumps(users))

        return jsonify({'status': 'ok'})
    except Exception:
        exc_info = sys.exc_info()
        return jsonify(
            {
                'status': 'error',
                'exception': ''.join(
                    [
                        ''.join(traceback.format_exception(*exc_info)),
                        ' e o request foi: ',
                        json.dumps(request.json['data'], indent=2),
                    ]
                ),
            }
        )


@auth_bp.route('/user_management')
@login_required(roles=['si'])
def user_management():
    try:
        with open(get_data_path('RobotFX_Users.json')) as json_file:
            file_dict = json.load(json_file)
            user_list = []
            for key, single_user_data in file_dict.items():
                single_user_data['username'] = key
                single_user_data['role'] = single_user_data['role'].upper()
                single_user_data['allow_validate'] = json.dumps(single_user_data['allow_validate'])
                user_list.append(single_user_data)

            return render_template('user_management.html', user_data=user_list, exception=json.dumps(''))
    except KeyError:
        exc_info = sys.exc_info()
        return render_template(
            'user_management.html',
            user_data=[],
            exception=json.dumps(''.join(traceback.format_exception(*exc_info)), indent=2),
        )


@auth_bp.route('/user_addition')
@login_required(roles=['si'])
def user_addition():
    role_options = get_user_profile_option_list()
    insert_case = json.dumps(True)
    delete_disabled = json.dumps(True)
    override_enabled = json.dumps(True)
    change_pwd_enabled = json.dumps(False)

    return render_template(
        'user_insert_edit.html',
        user_data={},
        role_data=role_options,
        insert_case=insert_case,
        delete_disabled=delete_disabled,
        override_enabled=override_enabled,
        change_pwd_enabled=change_pwd_enabled,
        title_contents="Add User",
    )


@auth_bp.route('/user_editing/<username>')
@login_required(roles=['si'])
def user_editing(username):
    role_options = get_user_profile_option_list()
    insert_case = json.dumps(False)
    user_id = session.get("user_id", None)
    username_databus = get_username(user_id)
    delete_disabled = json.dumps(username == username_databus)

    try:
        with open(get_data_path('RobotFX_Users.json')) as json_file:
            user_data = json.load(json_file)
            if username not in user_data:
                return render_template('404.html')

            response_data = user_data[username]
            response_data['allow_validate'] = json.dumps(response_data['allow_validate'])
            response_data['username'] = username
            override_enabled = json.dumps(user_data[username]['role'] in ('e-sales ndf', 'e-sales spot'))
            change_pwd_enabled = json.dumps(True)

            return render_template(
                'user_insert_edit.html',
                user_data=response_data,
                role_data=role_options,
                insert_case=insert_case,
                delete_disabled=delete_disabled,
                override_enabled=override_enabled,
                change_pwd_enabled=change_pwd_enabled,
                title_contents="Edit User",
            )
    except Exception:
        raise
        return render_template('404.html')


@auth_bp.route('/user_delete/<user_name>', methods=['PUT'])
@login_required(roles=['si'])
def user_delete(user_name):
    user_id = session.get("user_id", None)
    username_databus = get_username(user_id)
    try:
        if user_name == username_databus:
            return jsonify({'status': 'error', 'exception': 'Trying to delete the same user...!'})

        with open(get_data_path('RobotFX_Users.json')) as json_file:
            users = json.load(json_file)
            if user_name in users:
                del users[user_name]
            else:
                raise Exception('User: ' + user_name + ' not in json file!')

        with open(get_data_path('RobotFX_Users.json'), 'w') as json_file_out:
            json_file_out.write(json.dumps(users))

        return jsonify({'status': 'ok'})
    except Exception:
        exc_info = sys.exc_info()
        return jsonify({'status': 'error', 'exception': ''.join(traceback.format_exception(*exc_info))})


@auth_bp.route('/user_check/<user_name>')
@login_required(roles=['si'])
def user_check(user_name):
    try:
        with open(get_data_path('RobotFX_Users.json')) as json_file:
            users = json.load(json_file)
            result = user_name in users

        return jsonify({'status': str(result)})
    except Exception:
        exc_info = sys.exc_info()
        return jsonify({'status': 'error', 'exception': ''.join(traceback.format_exception(*exc_info))})
