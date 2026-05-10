from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import Order, Favourite, Notification, Address, db

dashboard_auth = Blueprint("dashboard_auth", __name__, url_prefix="/dashboard")

@dashboard_auth.route("")
@login_required
def dashboard():
    # Overview metrics
    order_count = Order.query.filter_by(user_id=current_user.id).count()
    fav_count = Favourite.query.filter_by(user_id=current_user.id).count()
    unread_notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    
    recent_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).limit(3).all()
    
    return render_template("dashboard/index.html", 
                           order_count=order_count, 
                           fav_count=fav_count, 
                           unread_notifications=unread_notifications,
                           recent_orders=recent_orders)

@dashboard_auth.route("/orders")
@login_required
def orders():
    all_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("dashboard/orders.html", orders=all_orders)

@dashboard_auth.route("/orders/<int:order_id>/receipt")
@login_required
def order_receipt(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    if order.payment_status != 'Paid':
        flash('Receipt only available for paid orders.', 'error')
        return redirect(url_for('dashboard_auth.orders'))
    return render_template("dashboard/receipt.html", order=order)

@dashboard_auth.route("/favourites")
@login_required
def favourites():
    favs = Favourite.query.filter_by(user_id=current_user.id).all()
    return render_template("dashboard/favourites.html", favourites=favs)

@dashboard_auth.route("/notifications")
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    # Mark as read
    for n in notifs:
        n.is_read = True
    db.session.commit()
    return render_template("dashboard/notifications.html", notifications=notifs)

@dashboard_auth.route("/addresses", methods=['GET', 'POST'])
@login_required
def addresses():
    if request.method == 'POST':
        street = request.form.get('street')
        city = request.form.get('city')
        state = request.form.get('state')
        phone = request.form.get('phone')
        
        # If it's the first address, make it default
        is_default = Address.query.filter_by(user_id=current_user.id).count() == 0
        
        new_addr = Address(
            user_id=current_user.id,
            street=street,
            city=city,
            state=state,
            phone=phone,
            is_default=is_default
        )
        db.session.add(new_addr)
        db.session.commit()
        flash('Address saved successfully!', 'success')
        return redirect(url_for('dashboard_auth.addresses'))
        
    user_addresses = Address.query.filter_by(user_id=current_user.id).all()
    return render_template("dashboard/addresses.html", addresses=user_addresses)

@dashboard_auth.route("/addresses/delete/<int:addr_id>", methods=['POST'])
@login_required
def delete_address(addr_id):
    addr = Address.query.filter_by(id=addr_id, user_id=current_user.id).first_or_404()
    db.session.delete(addr)
    db.session.commit()
    flash('Address deleted.', 'success')
    return redirect(url_for('dashboard_auth.addresses'))