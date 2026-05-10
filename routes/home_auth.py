from flask import Blueprint, render_template

home_auth = Blueprint("home_auth",__name__)


# ---------------------HOME----------------------
@home_auth.route("/")
def home():
    return render_template("home.html")