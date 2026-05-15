from flask import Blueprint, render_template

home_auth = Blueprint("home_auth",__name__)


from models import Product, Category

# ---------------------HOME----------------------
@home_auth.route("/")
def home():
    featured_products = Product.query.filter_by(is_featured=True).limit(4).all()
    trending_products = Product.query.filter_by(is_promoted=True).limit(4).all()
    new_arrivals = Product.query.filter_by(is_new_arrival=True).limit(4).all()
    categories = Category.query.all()
    
    return render_template("home.html", 
                           featured=featured_products, 
                           trending=trending_products,
                           new_arrivals=new_arrivals,
                           categories=categories)