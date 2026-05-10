import os
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import CartItem, Product, Order, OrderItem, Address, Notification, db
from datetime import datetime

checkout_auth = Blueprint('checkout_auth', __name__)

@checkout_auth.route('/cart')
@login_required
def cart():
    # Helper to release expired from shop_routes, ideally move to a shared utils file
    from routes.shop_routes import release_expired_reservations
    release_expired_reservations()
    
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.product.price * item.quantity for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)

@checkout_auth.route('/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    
    # Release reservation
    product = Product.query.get(item.product_id)
    if product and product.reserved_stock >= item.quantity:
        product.reserved_stock -= item.quantity
        
    db.session.delete(item)
    db.session.commit()
    flash('Item removed from cart.', 'success')
    return redirect(url_for('checkout_auth.cart'))

@checkout_auth.route('/cart/update/<int:item_id>', methods=['POST'])
@login_required
def update_cart_quantity(item_id):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    
    try:
        new_quantity = int(request.form.get('quantity', item.quantity))
    except ValueError:
        new_quantity = item.quantity
        
    if new_quantity < 1:
        new_quantity = 1
        
    product = Product.query.get(item.product_id)
    diff = new_quantity - item.quantity
    
    if diff > 0:
        # Increasing quantity
        if product.available_stock < diff:
            flash(f'Only {product.available_stock + item.quantity} available in stock.', 'error')
            return redirect(url_for('checkout_auth.cart'))
        product.reserved_stock += diff
    elif diff < 0:
        # Decreasing quantity
        product.reserved_stock += diff # diff is negative, so this subtracts
        
    item.quantity = new_quantity
    
    from datetime import timedelta
    item.reserved_until = datetime.utcnow() + timedelta(minutes=15)
    
    db.session.commit()
    return redirect(url_for('checkout_auth.cart'))

@checkout_auth.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    from routes.shop_routes import release_expired_reservations
    release_expired_reservations()
    
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('shop_auth.shop'))
        
    total = sum(item.product.price * item.quantity for item in cart_items)
    addresses = Address.query.filter_by(user_id=current_user.id).all()
    
    if request.method == 'POST':
        address_id = request.form.get('address_id')
        if not address_id:
            flash('Please select a delivery address.', 'error')
            return redirect(url_for('checkout_auth.checkout'))
            
        import uuid
        tx_ref = f"jimmy-{uuid.uuid4().hex[:10]}"
        
        # Create Pending Order
        new_order = Order(
            user_id=current_user.id,
            address_id=address_id,
            total_amount=total,
            payment_reference=tx_ref,
            status='Pending',
            payment_status='Pending'
        )
        db.session.add(new_order)
        db.session.flush() # get ID
        
        for item in cart_items:
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price_at_time=item.product.price
            )
            db.session.add(order_item)
            
        db.session.commit()
        
        # Here we would normally redirect to Flutterwave standard checkout
        # For simplicity in MVP, we can render a page with the Flutterwave JS inline
        return render_template('payment.html', order=new_order, flw_public_key=os.getenv('FLW_PUBLIC_KEY'))
        
    return render_template('checkout.html', cart_items=cart_items, total=total, addresses=addresses)

@checkout_auth.route('/checkout/verify')
@login_required
def verify_payment():
    tx_ref = request.args.get('tx_ref')
    transaction_id = request.args.get('transaction_id')
    status = request.args.get('status')
    
    order = Order.query.filter_by(payment_reference=tx_ref, user_id=current_user.id).first_or_404()
    
    if status in ['successful', 'completed']:
        # Verify with Flutterwave API
        secret_key = os.getenv('FLW_SECRET_KEY')
        headers = {'Authorization': f'Bearer {secret_key}'}
        verify_url = f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify"
        
        try:
            response = requests.get(verify_url, headers=headers)
            res_data = response.json()
            
            if res_data['status'] == 'success' and res_data['data']['status'] == 'successful':
                # Payment successful!
                order.payment_status = 'Paid'
                order.status = 'Processing'
                
                # Clear cart and deduct actual stock
                cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
                for item in cart_items:
                    product = Product.query.get(item.product_id)
                    # Deduct actual stock
                    product.stock -= item.quantity
                    # Remove from reserved stock since it's bought
                    product.reserved_stock -= item.quantity
                    db.session.delete(item)
                    
                # Create Notification
                notif = Notification(user_id=current_user.id, message=f"Payment successful for Order #{order.id}. Your order is now processing.")
                db.session.add(notif)
                
                db.session.commit()
                flash('Payment successful! Your order has been placed.', 'success')
                return redirect(url_for('dashboard_auth.dashboard'))
                
        except Exception as e:
            current_app.logger.error(f"Flutterwave verification failed: {e}")
            
    # If failed or cancelled
    order.payment_status = 'Failed'
    db.session.commit()
    flash('Payment failed or was cancelled.', 'error')
    return redirect(url_for('checkout_auth.checkout'))
