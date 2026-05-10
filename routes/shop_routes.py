from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from models import Product, Category, CartItem, Favourite, db
from datetime import datetime, timedelta

shop_auth = Blueprint('shop_auth', __name__)

def release_expired_reservations():
    """Helper to release expired cart item reservations back to product stock"""
    expired_items = CartItem.query.filter(CartItem.reserved_until < datetime.utcnow()).all()
    for item in expired_items:
        # Decrease reserved_stock
        product = Product.query.get(item.product_id)
        if product and product.reserved_stock >= item.quantity:
            product.reserved_stock -= item.quantity
        db.session.delete(item)
    if expired_items:
        db.session.commit()

shop_auth = Blueprint('shop_auth', __name__)

@shop_auth.route('/shop')
def shop():
    search_query = request.args.get('q', '').strip()
    category_id = request.args.get('category')
    tag = request.args.get('tag')
    
    query = Product.query
    
    # Apply search filter
    if search_query:
        query = query.filter(Product.name.ilike(f'%{search_query}%') | Product.description.ilike(f'%{search_query}%'))
        
    # Apply category filter
    if category_id and category_id.isdigit():
        query = query.filter_by(category_id=int(category_id))
        
    # Apply tag filter
    if tag == 'new':
        query = query.filter_by(is_new_arrival=True)
    elif tag == 'featured':
        query = query.filter_by(is_featured=True)
    elif tag == 'promoted':
        query = query.filter_by(is_promoted=True)
        
    # Order by newest
    products = query.order_by(Product.created_at.desc()).all()
    categories = Category.query.all()
    
    release_expired_reservations()
    
    return render_template('shop.html', 
                           products=products, 
                           categories=categories,
                           search_query=search_query,
                           current_category=int(category_id) if category_id and category_id.isdigit() else None,
                           current_tag=tag)

@shop_auth.route('/product/<int:product_id>')
def product_detail(product_id):
    release_expired_reservations()
    product = Product.query.get_or_404(product_id)
    is_favourite = False
    if current_user.is_authenticated:
        is_favourite = Favourite.query.filter_by(user_id=current_user.id, product_id=product.id).first() is not None
    return render_template('product_detail.html', product=product, is_favourite=is_favourite)

@shop_auth.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    release_expired_reservations()
    product = Product.query.get_or_404(product_id)
    quantity = int(request.form.get('quantity', 1))
    
    if product.available_stock < quantity:
        flash('Not enough stock available.', 'error')
        return redirect(request.referrer or url_for('shop_auth.shop'))
        
    existing_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()
    
    product.reserved_stock += quantity
    
    if existing_item:
        existing_item.quantity += quantity
        existing_item.reserved_until = datetime.utcnow() + timedelta(minutes=15)
    else:
        new_item = CartItem(
            user_id=current_user.id,
            product_id=product.id,
            quantity=quantity,
            reserved_until=datetime.utcnow() + timedelta(minutes=15)
        )
        db.session.add(new_item)
        
    db.session.commit()
    flash('Item added to cart and reserved for 15 minutes.', 'success')
    # Will change this to redirect to cart later
    return redirect(url_for('shop_auth.shop'))

@shop_auth.route('/favourite/toggle/<int:product_id>', methods=['POST'])
@login_required
def toggle_favourite(product_id):
    product = Product.query.get_or_404(product_id)
    existing = Favourite.query.filter_by(user_id=current_user.id, product_id=product.id).first()
    
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('Removed from favourites.', 'success')
    else:
        new_fav = Favourite(user_id=current_user.id, product_id=product.id)
        db.session.add(new_fav)
        db.session.commit()
        flash('Added to favourites.', 'success')
        
    return redirect(request.referrer or url_for('shop_auth.product_detail', product_id=product.id))
