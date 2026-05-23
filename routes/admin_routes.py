import os
import uuid
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.utils import secure_filename
from models import db, Product, Order, OrderItem, Category, ProductImage, User, Notification

admin_auth = Blueprint('admin_auth', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_auth.route('/dashboard')
@admin_required
def dashboard():
    products_count = Product.query.count()
    orders_count = Order.query.count()
    total_revenue = db.session.query(db.func.sum(Order.total_amount)).scalar() or 0.0
    
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                           products_count=products_count, 
                           orders_count=orders_count,
                           total_revenue=total_revenue,
                           recent_orders=recent_orders)

@admin_auth.route('/products')
@admin_required
def products():
    all_products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('admin/products.html', products=all_products)

@admin_auth.route('/categories', methods=['GET', 'POST'])
@admin_required
def categories():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            existing = Category.query.filter_by(name=name).first()
            if existing:
                flash('Category already exists.', 'error')
            else:
                new_category = Category(name=name)
                db.session.add(new_category)
                db.session.commit()
                flash('Category added successfully.', 'success')
        return redirect(url_for('admin_auth.categories'))
        
    all_categories = Category.query.all()
    return render_template('admin/categories.html', categories=all_categories)

@admin_auth.route('/categories/<int:category_id>/delete', methods=['POST'])
@admin_required
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted.', 'success')
    return redirect(url_for('admin_auth.categories'))

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")

def upload_to_supabase(file):
    if not supabase:
        return None
        
    try:
        filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        file_bytes = file.read()
        
        # Reset file pointer if needed, but we already read it
        res = supabase.storage.from_("products").upload(
            filename,
            file_bytes,
            {"content-type": file.content_type}
        )
        
        public_url = supabase.storage.from_("products").get_public_url(filename)
        return {"filename": filename, "url": public_url}
    except Exception as e:
        print(f"Supabase upload error: {e}")
        return None


@admin_auth.route('/products/add', methods=['GET', 'POST'])
@admin_required
def add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')
        stock = request.form.get('stock')
        category_id = request.form.get('category_id')
        
        is_new_arrival = request.form.get('is_new_arrival') == 'on'
        is_featured = request.form.get('is_featured') == 'on'
        is_promoted = request.form.get('is_promoted') == 'on'
        is_installmental_payment = request.form.get('is_installmental_payment') == 'on'
        try:
            installment_base_percent = float(request.form.get('installment_base_percent') or 0)
        except ValueError:
            installment_base_percent = 0.0
        try:
            installment_months = int(request.form.get('installment_months') or 0)
        except ValueError:
            installment_months = 0
        try:
            installment_interval_days = int(request.form.get('installment_interval_days') or 30)
        except ValueError:
            installment_interval_days = 30
        try:
            installment_charge_percent = float(request.form.get('installment_charge_percent') or 0)
        except ValueError:
            installment_charge_percent = 0.0
        
        if not name or not price:
            flash('Name and Price are required.', 'error')
            return redirect(url_for('admin_auth.add_product'))
            
        try:
            price = float(price)
            stock = int(stock) if stock else 0
        except ValueError:
            flash('Price and Stock must be valid numbers.', 'error')
            return redirect(url_for('admin_auth.add_product'))
            
        new_product = Product(
            name=name,
            description=description,
            price=price,
            stock=stock,
            category_id=category_id if category_id else None,
            is_new_arrival=is_new_arrival,
            is_featured=is_featured,
            is_promoted=is_promoted,
            is_installmental_payment=is_installmental_payment
            ,installment_base_percent=installment_base_percent
            ,installment_months=installment_months
            ,installment_interval_days=installment_interval_days
            ,installment_charge_percent=installment_charge_percent
        )
        db.session.add(new_product)
        db.session.commit()
        
        # Handle multiple images
        images = request.files.getlist('images')
        image_count = 0
        for img in images:
            if img and img.filename and image_count < 5:
                upload_result = upload_to_supabase(img)
                
                if upload_result:
                    new_image = ProductImage(
                        product_id=new_product.id,
                        filename=upload_result["filename"],
                        url=upload_result["url"]
                    )
                    db.session.add(new_image)
                    image_count += 1
                else:
                    # Fallback to local storage if Supabase fails or is not configured
                    original_filename = secure_filename(img.filename)
                    image_filename = f"{uuid.uuid4().hex}_{original_filename}"
                    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename)
                    
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                    
                    # Since we might have read the file in upload_to_supabase, we might need to handle the stream
                    # But if upload_to_supabase returned None, we probably have the bytes or can seek back if it's a file
                    # However, upload_to_supabase reads it into memory. Let's assume we can still save it or pass the bytes.
                    img.seek(0)
                    img.save(upload_path)
                    
                    new_image = ProductImage(
                        product_id=new_product.id,
                        filename=image_filename,
                        url=None
                    )
                    db.session.add(new_image)
                    image_count += 1

        db.session.commit()
        
        flash('Product added successfully!', 'success')
        return redirect(url_for('admin_auth.products'))
        
    categories = Category.query.all()
    return render_template('admin/add_product.html', categories=categories)

@admin_auth.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.category_id = request.form.get('category_id') or None
        
        try:
            product.price = float(request.form.get('price'))
            product.stock = int(request.form.get('stock')) if request.form.get('stock') else 0
        except ValueError:
            flash('Price and Stock must be valid numbers.', 'error')
            return redirect(url_for('admin_auth.edit_product', product_id=product.id))
            
        product.is_new_arrival = request.form.get('is_new_arrival') == 'on'
        product.is_featured = request.form.get('is_featured') == 'on'
        product.is_promoted = request.form.get('is_promoted') == 'on'
        product.is_installmental_payment = request.form.get('is_installmental_payment') == 'on'
        try:
            product.installment_base_percent = float(request.form.get('installment_base_percent') or 0)
        except ValueError:
            product.installment_base_percent = 0.0
        try:
            product.installment_months = int(request.form.get('installment_months') or 0)
        except ValueError:
            product.installment_months = 0
        try:
            product.installment_interval_days = int(request.form.get('installment_interval_days') or 30)
        except ValueError:
            product.installment_interval_days = 30
        try:
            product.installment_charge_percent = float(request.form.get('installment_charge_percent') or 0)
        except ValueError:
            product.installment_charge_percent = 0.0
        
        # Handle new images
        images = request.files.getlist('images')
        image_count = len(product.images)
        for img in images:
            if img and img.filename and image_count < 5:
                upload_result = upload_to_supabase(img)
                if upload_result:
                    new_image = ProductImage(
                        product_id=product.id,
                        filename=upload_result["filename"],
                        url=upload_result["url"]
                    )
                    db.session.add(new_image)
                    image_count += 1
                else:
                    # Fallback to local
                    from werkzeug.utils import secure_filename
                    import uuid
                    original_filename = secure_filename(img.filename)
                    image_filename = f"{uuid.uuid4().hex}_{original_filename}"
                    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename)
                    os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                    img.seek(0)
                    img.save(upload_path)
                    new_image = ProductImage(product_id=product.id, filename=image_filename, url=None)
                    db.session.add(new_image)
                    image_count += 1

        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('admin_auth.products'))
        
    categories = Category.query.all()
    return render_template('admin/edit_product.html', product=product, categories=categories)

@admin_auth.route('/orders')
@admin_required
def orders():
    all_orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=all_orders)

@admin_auth.route('/orders/<int:order_id>/status', methods=['POST'])
@admin_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    
    valid_statuses = ['Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled']
    if new_status in valid_statuses:
        order.status = new_status
        
        notif = Notification(user_id=order.user_id, message=f"Your Order #{order.id} status is now: {new_status}")
        db.session.add(notif)
        
        db.session.commit()
        flash(f'Order #{order.id} status updated to {new_status}.', 'success')
    else:
        flash('Invalid status.', 'error')
        
    return redirect(url_for('admin_auth.orders'))

@admin_auth.route('/users')
@admin_required
def users():
    all_users = User.query.all()
    return render_template('admin/users.html', users=all_users)

@admin_auth.route('/users/<int:user_id>')
@admin_required
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('admin/user_detail.html', user=user)

@admin_auth.route('/payments')
@admin_required
def payments():
    page = request.args.get('page', 1, type=int)
    pagination = Order.query.order_by(Order.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/payments.html', pagination=pagination)

@admin_auth.route('/logout')
def logout():
    session.pop('is_admin', None)
    flash('Admin logged out.', 'success')
    return redirect(url_for('auth.login'))
