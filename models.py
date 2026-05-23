from extensions import db
from flask_login import UserMixin
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    address=db.Column(db.String(255), nullable=False)
    phone_number=db.Column(db.String(20), nullable=False)  
    is_verified = db.Column(db.Boolean, default=False)
    

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

  
    def check_password(self, raw_password):
        return check_password_hash(self.password, raw_password)
    
 

class PasswordReset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    otp = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_used = db.Column(db.Boolean, default=False)

    def is_expired(self):
        return datetime.utcnow() > self.created_at + timedelta(minutes=1)

class OTPVerification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    otp = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_used = db.Column(db.Boolean, default=False)

    def is_expired(self):
        return datetime.utcnow() > self.created_at + timedelta(minutes=5)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    reserved_stock = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # New Fields
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    is_new_arrival = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    is_promoted = db.Column(db.Boolean, default=False)
    is_installmental_payment = db.Column(db.Boolean, default=False)
    installment_base_percent = db.Column(db.Float, default=0.0)
    installment_months = db.Column(db.Integer, default=0)
    installment_interval_days = db.Column(db.Integer, default=30)
    installment_charge_percent = db.Column(db.Float, default=0.0)
    
    @property
    def available_stock(self):
        return max(0, self.stock - self.reserved_stock)
    
    # Relationships
    category = db.relationship('Category', backref=db.backref('products', lazy=True))
    images = db.relationship('ProductImage', backref='product', lazy=True, cascade="all, delete-orphan")

class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    address_id = db.Column(db.Integer, db.ForeignKey('address.id'), nullable=True)
    status = db.Column(db.String(50), default='Pending') # Pending, Processing, Shipped, Delivered, Cancelled
    total_amount = db.Column(db.Float, nullable=False)
    payment_reference = db.Column(db.String(255), nullable=True)
    payment_status = db.Column(db.String(50), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    stock_deducted = db.Column(db.Boolean, default=False)
    
    # Relationship to user and order items
    user = db.relationship('User', backref=db.backref('orders', lazy=True))
    address = db.relationship('Address')
    installment_plan = db.relationship('InstallmentPlan', uselist=False, backref='order')

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price_at_time = db.Column(db.Float, nullable=False)

    order = db.relationship('Order', backref=db.backref('items', lazy=True))
    product = db.relationship('Product')


class InstallmentPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    base_amount = db.Column(db.Float, nullable=False)
    remaining_amount = db.Column(db.Float, nullable=False)
    months = db.Column(db.Integer, nullable=False)
    interval_days = db.Column(db.Integer, nullable=False, default=30)
    next_due_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), default='Active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    payments = db.relationship('InstallmentPayment', backref='plan', lazy=True, cascade='all, delete-orphan')


class InstallmentPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('installment_plan.id'), nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    is_paid = db.Column(db.Boolean, default=False)
    paid_at = db.Column(db.DateTime, nullable=True)
    payment_reference = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    reserved_until = db.Column(db.DateTime, nullable=False)

    user = db.relationship('User', backref=db.backref('cart_items', lazy=True, cascade="all, delete-orphan"))
    product = db.relationship('Product')

    def is_expired(self):
        return datetime.utcnow() > self.reserved_until

class Address(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    street = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    is_default = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref=db.backref('addresses', lazy=True, cascade="all, delete-orphan"))

class Favourite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)

    user = db.relationship('User', backref=db.backref('favourites', lazy=True, cascade="all, delete-orphan"))
    product = db.relationship('Product')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('notifications', lazy=True, cascade="all, delete-orphan"))
