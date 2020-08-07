from flask import Blueprint
from flask import render_template
from flask import jsonify
from flask import request
from flask import send_file
from lib.libflask import login_required
from lib.libflask import get_username
from lib.libflask import session
from datetime import datetime
import os
import json
import logging
from ansi2html import Ansi2HTMLConverter
from zipfile import ZipFile
import subprocess

log_bp = Blueprint('log_bp', __name__, url_prefix='/log')


location = '/var/log'


def log_base():
    if suppressed_logging:
        ignore_list = ['rfx-flask_website.log', 'rfx-fixserver.log', 'rfx-legacy_mocks.log']
    else:
        ignore_list = []

    def format_log(filename, msg):
        with open(os.path.join(location, filename), 'r') as f:
            conv = Ansi2HTMLConverter()
            html = conv.convert(f.read(), full=False)
            msg = f"{html}"
        return msg

    logs_msg = {}

    for filename in sorted(os.listdir(location)):
        if filename.startswith('rfx-') and filename not in ignore_list:
            logs_msg[filename] = ''  # format_log(filename, str_msg)
    return render_template('log.html', logs_msg=logs_msg)


config = {}
config_path = os.path.join(os.environ["ROBOTFXDIR"], "etc/rfxconfig.json")
with open(config_path) as json_config_file:
    config = json.load(json_config_file)
suppressed_logging = config["suppressed_logging"]

if suppressed_logging:
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)


@log_bp.route('/log')
@login_required(roles=['ti'])
def log():
    return log_base()


# Zip the files from given directory that matches the filter
def zipFilesInDir(dirName, zipFileName, filter):
    # create a ZipFile object
    with ZipFile(zipFileName, 'w') as zipObj:
        # Iterate over all the files in directory
        for folderName, subfolders, filenames in os.walk(dirName):
            for filename in filenames:
                if filter(filename):
                    # create complete filepath of file in directory
                    filePath = os.path.join(folderName, filename)
                    # Add file to zip
                    zipObj.write(filePath, os.path.basename(filePath))


@log_bp.route('/download')
@login_required(roles=['ti'])
def download():
    filename = request.args.get('filename')
    if filename:
        path = os.path.join(location, filename)
        return send_file(path, as_attachment=True)
    else:

        def filterfile(filename):
            return filename.startswith('rfx-') and filename.endswith('.log')

        dt = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        outputfile = f'/tmp/robotfx_logs{dt}.zip'
        zipFilesInDir('/var/log/', outputfile, filterfile)
        return send_file(outputfile, as_attachment=True)


@log_bp.route('/log-update')
@login_required(roles=['ti'])
def log_update():
    filename = request.args.get('filename')
    numlines = int(request.args.get('numlines', None))
    msg = 'invalid'

    try:
        with open(os.path.join(location, filename), 'r') as f:
            conv = Ansi2HTMLConverter()
            lines = f.readlines()
            if numlines is not None:
                lines = lines[-numlines:]

            contents = '\n'.join(lines)
            html = conv.convert(contents, full=False)
            msg = f"{html}"
    except Exception as e:
        return str(e)

    return msg


@log_bp.route('/log-clear')
@login_required(roles=['ti'])
def log_clear():
    filename = request.args.get('filename')

    with open(os.path.join(location, filename), 'w') as f:
        f.truncate(0)  # need '0' when using r+
        return jsonify({'status': True})

    return jsonify({'status': False})


@log_bp.route('/restart-service', methods=['POST'])
@login_required(roles=['ti'])
def restart_service():
    service = request.get_json().get('service')
    service_path = os.path.join(os.getenv('ROBOTFXDIR'), 'etc', 'init', service)
    output = subprocess.run([service_path, 'restart'], stdout=subprocess.PIPE)
    conv = Ansi2HTMLConverter()
    html = conv.convert(output.stdout.decode("utf-8"), full=False)

    return jsonify({'output': html})


@log_bp.route('/erase_log')
@login_required(roles=['ti'])
def erase_log():
    ping_ip1 = subprocess.run(
        f"cd /var/log && truncate -s 0 rfx-*",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        encoding="utf-8",
    )
    user_id = session.get("user_id", None)
    username = get_username(user_id)
    print(f"Log erased by: {username}", flush=True)
    stderr_msg = ping_ip1.stderr
    if not stderr_msg:
        return jsonify({'status': 'success', 'msg': 'Log erased'})
    else:
        return jsonify({'status': 'error', 'msg': 'Error: ' + stderr_msg})
