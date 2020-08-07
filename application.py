from flask import Flask
from flask import redirect
from flask import url_for
from flask import render_template
from auth import auth
from fxconfig import fxconfig
from fxndf import fxndf
from fxspot import fxspot
from fxsupplier import fxsupplier
from log import log
from tests import test
from flask_cors import CORS

def create_app():
    app = Flask(__name__, static_url_path='/static')
    app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
    app.template_folder = "/home/duanribeiro/PycharmProjects/exemplo_flask_decorator/templates"
    app.static_folder = "/home/duanribeiro/PycharmProjects/exemplo_flask_decorator/static"
    CORS(app)

    register_blueprints(app)

    @app.route('/')
    def index():
        return redirect(url_for('auth_bp.login'))

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    return app


def register_blueprints(app):
    with app.app_context():
        app.register_blueprint(auth.auth_bp)
        app.register_blueprint(fxconfig.fxconfig_bp)
        app.register_blueprint(fxndf.fxndf_bp)
        app.register_blueprint(fxspot.fxspot_bp)
        app.register_blueprint(fxsupplier.fxsupplier_bp)
        app.register_blueprint(log.log_bp)
        app.register_blueprint(test.test_bp)

        return app
