import os
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import CartItem, Product, Order, OrderItem, Address, Notification, InstallmentPlan, InstallmentPayment, db
from datetime import datetime
from datetime import timedelta

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
    
    # Check if any item supports installment
    installment_eligible_items = [item for item in cart_items if item.product.is_installmental_payment]
    
    if request.method == 'POST':
        address_id = request.form.get('address_id')
        payment_method = request.form.get('payment_method', 'full')  # 'full' or 'installment'
        
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
        db.session.flush()
        
        for item in cart_items:
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price_at_time=item.product.price
            )
            db.session.add(order_item)
            
        db.session.commit()
        
        # Determine payment amount and create installment plans
        pay_amount = total
        if payment_method == 'installment' and installment_eligible_items:
            # Create per-product installment plans
            for cart_item in installment_eligible_items:
                product = cart_item.product
                quantity = cart_item.quantity
                
                # Calculate installment price with surcharge
                base_price = product.price * quantity
                surcharge = base_price * (product.installment_charge_percent / 100.0)
                total_with_surcharge = base_price + surcharge
                
                # Base amount (down payment)
                base_amount = total_with_surcharge * (product.installment_base_percent / 100.0)
                remaining = total_with_surcharge - base_amount
                
                # Create InstallmentPlan for this product
                plan = InstallmentPlan(
                    order_id=new_order.id,
                    total_amount=total_with_surcharge,
                    base_amount=base_amount,
                    remaining_amount=remaining,
                    months=product.installment_months,
                    interval_days=product.installment_interval_days,
                    next_due_date=datetime.utcnow() + timedelta(days=product.installment_interval_days)
                )
                db.session.add(plan)
                db.session.flush()
                
                # Create initial payment attempt for base amount
                initial_payment = InstallmentPayment(
                    plan_id=plan.id,
                    due_date=datetime.utcnow(),
                    amount=base_amount,
                    is_paid=False,
                    payment_reference=tx_ref
                )
                db.session.add(initial_payment)
                
                # Create scheduled payments for remaining balance
                if product.installment_months > 0 and remaining > 0:
                    per_month = round(remaining / product.installment_months, 2)
                    for i in range(1, product.installment_months + 1):
                        due = datetime.utcnow() + timedelta(days=product.installment_interval_days * i)
                        sched = InstallmentPayment(plan_id=plan.id, due_date=due, amount=per_month, is_paid=False)
                        db.session.add(sched)
            
            # For non-installment items, add full price to first payment tx_ref
            non_install_total = sum(item.product.price * item.quantity for item in cart_items if not item.product.is_installmental_payment)
            
            # Calculate total to pay now (sum of all base amounts + full price of non-installment items)
            all_base_amounts = sum(plan.base_amount for plan in InstallmentPlan.query.filter_by(order_id=new_order.id).all())
            pay_amount = all_base_amounts + non_install_total
            
            db.session.commit()
        
        return render_template('payment.html', order=new_order, flw_public_key=os.getenv('FLW_PUBLIC_KEY'), pay_amount=round(pay_amount, 2))
        
    return render_template('checkout.html', cart_items=cart_items, total=total, addresses=addresses, installment_eligible_items=installment_eligible_items)

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
                # Mark all initial payments (with this tx_ref) as paid
                initial_payments = InstallmentPayment.query.filter_by(payment_reference=tx_ref, is_paid=False).all()
                
                for payment in initial_payments:
                    payment.is_paid = True
                    payment.paid_at = datetime.utcnow()
                    # Update plan remaining
                    plan = payment.plan
                    plan.remaining_amount = round(plan.remaining_amount - payment.amount, 2)
                    # Find next unpaid payment
                    next_unpaid = InstallmentPayment.query.filter(InstallmentPayment.plan_id == plan.id, InstallmentPayment.is_paid == False).order_by(InstallmentPayment.due_date).first()
                    if next_unpaid:
                        plan.next_due_date = next_unpaid.due_date
                    else:
                        if plan.remaining_amount <= 0:
                            plan.status = 'Completed'

                # If stock hasn't been deducted yet, deduct and clear cart
                if not order.stock_deducted:
                    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
                    for item in cart_items:
                        product = Product.query.get(item.product_id)
                        product.stock -= item.quantity
                        if product.reserved_stock >= item.quantity:
                            product.reserved_stock -= item.quantity
                        db.session.delete(item)
                    order.stock_deducted = True

                # Check if all installment plans are completed
                all_plans = InstallmentPlan.query.filter_by(order_id=order.id).all()
                if all_plans:
                    # If all plans are completed, mark order as paid
                    all_completed = all(plan.status == 'Completed' or plan.remaining_amount <= 0 for plan in all_plans)
                    if all_completed:
                        order.payment_status = 'Paid'
                    else:
                        order.payment_status = 'Partially Paid'
                else:
                    # No installment plans (full payment)
                    order.payment_status = 'Paid'
                
                if order.payment_status == 'Paid':
                    order.status = 'Processing'

                notif = Notification(user_id=current_user.id, message=f"Payment received for Order #{order.id}.")
                db.session.add(notif)
                db.session.commit()
                flash('Payment successful! Thank you.', 'success')
                return redirect(url_for('dashboard_auth.dashboard'))
                
        except Exception as e:
            current_app.logger.error(f"Flutterwave verification failed: {e}")
            
    # If failed or cancelled
    order.payment_status = 'Failed'
    db.session.commit()
    flash('Payment failed or was cancelled.', 'error')
    return redirect(url_for('checkout_auth.checkout'))


@checkout_auth.route('/order/<int:order_id>/pay-next')
@login_required
def pay_next(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    plans = InstallmentPlan.query.filter_by(order_id=order.id).all()
    
    if not plans:
        flash('No installment plan for this order.', 'error')
        return redirect(url_for('dashboard_auth.dashboard'))

    # Find all next unpaid scheduled payments across all plans
    next_payments = []
    for plan in plans:
        if plan.remaining_amount > 0:
            next_unpaid = InstallmentPayment.query.filter(
                InstallmentPayment.plan_id == plan.id, 
                InstallmentPayment.is_paid == False
            ).order_by(InstallmentPayment.due_date).first()
            if next_unpaid:
                next_payments.append(next_unpaid)

    if not next_payments:
        flash('No pending installment payment found.', 'error')
        return redirect(url_for('dashboard_auth.dashboard'))

    # Calculate total of all next payments due
    total_next_payment = sum(p.amount for p in next_payments)
    
    # Assign a single tx_ref for this batch of payments
    import uuid
    tx_ref = f"jimmy-{uuid.uuid4().hex[:10]}"
    
    # Link all these payments to the tx_ref
    for payment in next_payments:
        payment.payment_reference = tx_ref
    
    # Update order payment reference for verification
    order.payment_reference = tx_ref
    db.session.commit()

    return render_template('payment.html', order=order, flw_public_key=os.getenv('FLW_PUBLIC_KEY'), pay_amount=round(total_next_payment, 2))
