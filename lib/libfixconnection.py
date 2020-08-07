import base64
import os
import shutil
import tempfile
import subprocess
from uuid import uuid1

from libep import log_info

"""Quickfix para python não fornece recursos para manipulação de certas funcionalidades/recursos,
   como por exemplo conexões SSL. Para que continue sendo possível utilizar o Quickfix em Python
   foram desenvolvidos recursos para:
        -> Abrir o arquivo de configuração das sessões FIX
        -> Executar modificações nessas configurações
        -> Gerar um arquivo de saída que será utilizado pelo quickfix
        -> Gerar um arquivo de saída para o stunnel para gerenciamento das conexões seguras.
        -> Inicializar o stunnel quando serviço for inicializado.
        -> Interromper o stunnel quando serviço for desligado.

  As seguintes variáveis devem ser definidas para o funcionamento do sistema:
    RFX_FIXCONFIG_FILE=/opt/robotfx/etc/fxgo/config.txt
    RFX_FIXSESSION_{session_name}_ENABLED=Y/N
    RFX_FIXCONFIG_{session_name}_SERVER="200.123.11.1:88"
    RFX_FIXCONFIG_{session_name}_KEY=/opt/robotfx/etc/fxgo/key.key
    RFX_FIXCONFIG_{session_name}_CERTIFICATE=/opt/robotfx/etc/fxgo/cert.cert
"""

FIX_CONFIG_DIR='/var/tmp/quickfix-config/'


def rm_directory(path):
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass


def create_directory(path):
    try:
        os.mkdir(path)
    except FileExistsError:
        pass


def decode_and_save(encoded_value, outputfile):
    #content = base64.b64decode(encoded_value)
    with open(outputfile, 'w') as f_output:
        f_output.write(encoded_value)


class QuickfixConfig(object):
    class Session(object):
        def __init__(self, session_type):
            self.session_type = session_type
            self.enabled = True
            self.lines = list()

        def get_property(self, key):
            for line in self.lines:
                if line.startswith(key):
                    return line.split('=')[1]

            return None

    def __init__(self):
        self.sessions = list()

    def load_file(self, inputfile):
        """Loads file contents into Session data structure"""
        session = None

        with open(inputfile) as f_input:
            for line in f_input:
                line = line.strip()
                if line.startswith('[DEFAULT]') or line.startswith('[SESSION]'):
                    session = QuickfixConfig.Session(line)
                    self.sessions.append(session)  # muttable object, mantains reference

                if session:
                    session.lines.append(line)

    def save_file(self, outputfile):
        """Writes Session data structure into a file"""
        with open(outputfile, 'w') as f_output:
            for session in self.sessions:
                if not session.enabled:
                    continue

                f_output.write('\n'.join(session.lines) + '\n')


def update_sessions_disabled(quickfix_config):
    """Check for disabled FIX sessions, via environment variables or directly in the configuration"""
    disable_flags = ['false', '0', 'f', 'n', 'no']

    for session in quickfix_config.sessions:
        session_name = session.get_property('SessionName')
        if session_name:
            status = os.getenv(f'RFX_FIXSESSION_{session_name}_ENABLED', 'True')
            if status.lower() in disable_flags:
                session.enabled = False
                log_info(f'quickfix session {session_name} disabled (env)')
                continue

        status = session.get_property('Enabled')
        if status and status.lower() in disable_flags:
            session.enabled = False
            log_info(f'quickfix session {session_name} disabled')


def create_stunnel_config(quickfix_config, stunnel_config_file):
    """Check for FIX Sessions that need a SSL connection and generates stunnel config file"""
    ssl_connections = []

    for session in quickfix_config.sessions:
        session_name = session.get_property('SessionName')

        if session_name:
            connection_host = session.get_property('SocketConnectHost')
            connection_port = session.get_property('SocketConnectPort')

            # these 3 env variables must me defined to create a SSL connection.
            remote_host = os.getenv(f'RFX_FIXCONFIG_{session_name}_SERVER', None)
            ssl_key    = os.getenv(f'RFX_FIXCONFIG_{session_name}_KEY', None)
            ssl_certificate = os.getenv(f'RFX_FIXCONFIG_{session_name}_CERTIFICATE', None)

            if None in [remote_host, ssl_key, ssl_certificate]:
                log_info(f'quickfix session {session_name} not configured to use stunnel')
                log_info(f'{remote_host}, bool({ssl_key}), bool({ssl_certificate})')
                continue

            log_info(f'quickfix session {session_name} remote host {remote_host}')
            log_info(f'quickfix session {session_name} local host {connection_host}:{connection_port}')

            cert_file = os.path.join(FIX_CONFIG_DIR, f'rfx-{session_name}.cert')
            key_file = os.path.join(FIX_CONFIG_DIR, f'rfx-{session_name}.key')

            decode_and_save(ssl_key, key_file)
            decode_and_save(ssl_certificate, cert_file)

            ssl_connection = f'[{session_name}]\n'
            ssl_connection += f'client = yes\n'
            ssl_connection += f'accept = {connection_host}:{connection_port}\n'
            ssl_connection += f'connect = {remote_host}\n'
            ssl_connection += f'cert = {cert_file}\n'
            ssl_connection += f'key = {key_file}\n'

            ssl_connections.append(ssl_connection)

    if ssl_connections:
        with open(stunnel_config_file, 'w') as f_output:
            header =  'debug = 7\n'  # TODO: 7 é apenas para quando se quer debugar.
            header += 'output = /var/log/rfx-stunnel.log\n'
            header += 'foreground = no\n'

            f_output.write(header + '\n')

            for connection in ssl_connections:
                f_output.write(connection + '\n')


def quickfix_setup(configfile_path):
    log_info(f'quickfix input file {configfile_path}')
    rm_directory(FIX_CONFIG_DIR)
    create_directory(FIX_CONFIG_DIR)

    quickfix_config = QuickfixConfig()
    quickfix_config.load_file(configfile_path)
    update_sessions_disabled(quickfix_config)
    quickfix_config.save_file(os.path.join(FIX_CONFIG_DIR, 'config.txt'))
    create_stunnel_config(quickfix_config, os.path.join(FIX_CONFIG_DIR, 'stunnel.conf'))


def stunnel_start():
    config = os.path.join(FIX_CONFIG_DIR, 'stunnel.conf')

    if os.path.exists(config):
        log_info('stunnel is being initialized')
        subprocess.run(['stunnel', config])
    else:
        log_info('no ssl connections, stunnel will not be initialized')


def stunnel_stop():
    os.system('killall stunnel')
