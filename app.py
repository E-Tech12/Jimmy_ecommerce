import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash

from flask_mail import Mail, Message
from flask_login import LoginManager, login_manager, login_user, login_required, logout_user
from models import User, PasswordReset
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from extensions import db, mail

from routes.home_auth import home_auth
from routes.auth_routes import auth 
from routes.dashboard_routes import dashboard_auth
from routes.contact_routes import contact_auth
from routes.admin_routes import admin_auth
from routes.shop_routes import shop_auth
from routes.checkout_routes import checkout_auth

load_dotenv(override=True)

app = Flask(__name__)


# Configurarion
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', "cyberdev203@gmail.com")
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'gvje rctp ycmv nqdd')
app.config['MAIL_TIMEOUT'] = os.getenv('MAIL_TIMEOUT', 30)
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME', "cyberdev203@gmail.com")
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads', 'products')



mail = Mail(app)
db.init_app(app)

with app.app_context():
    db.create_all()
    
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    app.logger.debug(f"Loading user with ID: {user_id}")
    return User.query.get(int(user_id))


app.register_blueprint(home_auth)
app.register_blueprint(auth)
app.register_blueprint(dashboard_auth)
app.register_blueprint(contact_auth)
app.register_blueprint(admin_auth)
app.register_blueprint(shop_auth)
app.register_blueprint(checkout_auth)


if __name__ == "__main__":
    app.run(debug=True)