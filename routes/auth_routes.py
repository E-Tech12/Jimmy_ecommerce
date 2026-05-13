from flask import (
    Flask, redirect, render_template, Blueprint,
    request, url_for, flash, session, current_app
)
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_user, login_required, logout_user
from models import User, PasswordReset, OTPVerification
from flask_mail import Message
from extensions import db, mail
import random


auth = Blueprint("auth", __name__)


# -------------------- LOGIN --------------------
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        current_app.logger.info(f"Login attempt for email: {email}")
        
        import os
        if email == os.getenv('ADMIN_EMAIL') and password == os.getenv('ADMIN_PASSWORD'):
            session['is_admin'] = True
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_auth.dashboard'))

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.is_verified:
                flash('Please verify your email address to login.')
                # Generate new OTP and redirect to verify
                otp = str(random.randint(100000, 999999))
                print(f"==========> GENERATED OTP FOR {user.email}: {otp} <==========")
                current_app.logger.info(f"OTP generated for {user.email}: {otp}")
                
                otp_request = OTPVerification(user_id=user.id, otp=otp)
                db.session.add(otp_request)
                db.session.commit()
                
                msg = Message(
                    subject="Your Signup OTP - JimmyElectronics",
                    sender=current_app.config.get('MAIL_USERNAME', 'cyberdev203@gmail.com'),
                    recipients=[user.email],
                    body=f"Hello {user.first_name},\n\nYour OTP for signup verification is: {otp}\n\nThis OTP is valid for 5 minutes.\n\nBest regards."
                )
                try:
                    mail.send(msg)
                except Exception as e:
                    current_app.logger.error(f"Failed to send OTP: {e}")
                
                session['signup_user_id'] = user.id
                return redirect(url_for('auth.verify_signup'))

            login_user(user)
            current_app.logger.info(f"User logged in successfully: {email}")
            print(f"User logged in successfully: {email}")
            return redirect(url_for('dashboard_auth.dashboard'))
        else:
            current_app.logger.warning(f"Failed login attempt for email: {email}")
            print(f"Failed login attempt for email: {email}")
            flash('Invalid username or password')
            return redirect(url_for('auth.login'))

    return render_template("login.html")

# -------------------- REGISTER --------------------
@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')

        current_app.logger.info(f"Registration attempt for email: {email}")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            current_app.logger.warning(f"Registration failed – user exists: {email}")
            print(f"Registration failed – user exists: {email}")
            flash('User already exists, Please login!')
            return redirect(url_for('auth.login'))

        new_user = User(
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            address=request.form.get('address'),
            phone_number=request.form.get('phone_number'),
            email=email
        )
        new_user.set_password(request.form.get('password'))

        db.session.add(new_user)
        db.session.commit()

        # Generate OTP
        otp = str(random.randint(100000, 999999))
        print(f"==========> GENERATED OTP FOR {email}: {otp} <==========")
        current_app.logger.info(f"OTP generated for {email}: {otp}")
        
        otp_request = OTPVerification(user_id=new_user.id, otp=otp)
        db.session.add(otp_request)
        db.session.commit()

        # Send Email
        msg = Message(
            subject="Your Signup OTP - JimmyElectronics",
            sender=current_app.config.get('MAIL_USERNAME', 'cyberdev203@gmail.com'),
            recipients=[email],
            body=f"Hello {new_user.first_name},\n\nYour OTP for signup verification is: {otp}\n\nThis OTP is valid for 5 minutes.\n\nBest regards."
        )
        try:
            mail.send(msg)
            current_app.logger.info(f"Signup OTP sent successfully to {email}")
        except Exception as e:
            current_app.logger.error(f"Failed to send signup OTP to {email}", exc_info=True)
            flash("Failed to send OTP email, but your account was created. Please try logging in to trigger a new OTP.")
            return redirect(url_for('auth.login'))

        current_app.logger.info(f"New user registered: {email}, pending verification.")
        print(f"New user registered: {email}, pending verification.")
        
        # Store user ID in session for verify step
        session['signup_user_id'] = new_user.id
        flash('Registration successful! Please enter the OTP sent to your email to verify your account.')
        return redirect(url_for('auth.verify_signup'))

    return render_template("signup.html")

# -------------------- VERIFY SIGNUP OTP --------------------
@auth.route("/verify-signup", methods=['GET', 'POST'])
def verify_signup():
    user_id = session.get('signup_user_id')
    
    if not user_id:
        flash("Session expired or invalid. Please try logging in.")
        return redirect(url_for('auth.login'))
        
    user = User.query.get(user_id)
    if not user:
        flash("User not found.")
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        current_app.logger.info("Signup OTP verification attempt")

        otp_request = OTPVerification.query.filter_by(
            user_id=user.id,
            otp=entered_otp,
            is_used=False
        ).order_by(OTPVerification.created_at.desc()).first()

        if not otp_request:
            current_app.logger.warning("Invalid Signup OTP entered")
            flash("Invalid OTP.")
            return redirect(url_for('auth.verify_signup'))

        if otp_request.is_expired():
            current_app.logger.warning("Expired Signup OTP used")
            flash("OTP expired. Please login to receive a new one.")
            return redirect(url_for('auth.login'))

        otp_request.is_used = True
        user.is_verified = True
        db.session.commit()

        session.pop('signup_user_id', None)
        current_app.logger.info("Signup OTP verified successfully")
        
        # Auto log in the user
        login_user(user)
        flash("Email verified successfully! Welcome.")
        return redirect(url_for('dashboard_auth.dashboard'))

    return render_template("verify_signup.html", email=user.email)

# -------------------- FORGOT PASSWORD --------------------
@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():

    if request.method == 'POST':

        email = request.form.get('email')

        current_app.logger.info(
            f"Password reset requested for email: {email}"
        )

        user = User.query.filter_by(email=email).first()

        if not user:
            current_app.logger.warning(
                f"Password reset failed – email not found: {email}"
            )

            flash("No user found with this email.")

            return redirect(url_for('auth.forgot_password'))

        # Generate OTP
        otp = str(random.randint(100000, 999999))

        reset_request = PasswordReset(
            user_id=user.id,
            otp=otp
        )

        db.session.add(reset_request)
        db.session.commit()

        # Create email message
        msg = Message(
            subject="Your OTP for Password Reset - BITE ON GO",
            sender=current_app.config['MAIL_USERNAME'],
            recipients=[email],
            body=f"""
Hello {user.first_name},

Your OTP for password reset is: {otp}

This OTP is valid for 1 minute.

If you did not request a password reset,
please ignore this email.

Best regards.
"""
        )

        try:

            print("MAIL_USERNAME:",
                  current_app.config['MAIL_USERNAME'])

            print("MAIL_PASSWORD:",
                  current_app.config['MAIL_PASSWORD'])

            # Send email
            mail.send(msg)

            current_app.logger.info(
                f"OTP sent successfully to {email}"
            )

            flash("OTP sent to your email.")

            return redirect(url_for('auth.verify_otp'))

        except Exception as e:

            current_app.logger.error(
                f"Failed to send OTP: {e}"
            )

            print(e)

            flash("Failed to send OTP. Try again later.")

            return redirect(url_for('auth.forgot_password'))

    return render_template("forgot_password.html")

# -------------------- VERIFY OTP --------------------
@auth.route("/verify-otp", methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        current_app.logger.info("OTP verification attempt")

        reset_request = PasswordReset.query.filter_by(
            otp=entered_otp,
            is_used=False
        ).order_by(PasswordReset.created_at.desc()).first()

        if not reset_request:
            current_app.logger.warning("Invalid OTP entered")
            flash("Invalid OTP.")
            return redirect(url_for('auth.verify_otp'))

        if reset_request.is_expired():
            current_app.logger.warning("Expired OTP used")
            flash("OTP expired.")
            return redirect(url_for('auth.forgot_password'))

        reset_request.is_used = True
        db.session.commit()

        session['reset_user_id'] = reset_request.user_id
        current_app.logger.info("OTP verified successfully")

        flash("OTP verified successfully!")
        return redirect(url_for('auth.reset_password'))

    return render_template("verify_otp.html")

# -------------------- RESET PASSWORD --------------------
@auth.route("/reset-password", methods=['GET', 'POST'])
def reset_password():
    user_id = session.get('reset_user_id')

    if not user_id:
        current_app.logger.warning("Reset password session expired")
        flash("Session expired.")
        return redirect(url_for('auth.forgot_password'))

    user = User.query.get(user_id)
    if not user:
        current_app.logger.error("User not found during password reset")
        flash("User not found.")
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        user.password = generate_password_hash(request.form.get('password'))
        db.session.commit()

        session.pop('reset_user_id', None)
        current_app.logger.info(f"Password reset successful for user ID {user_id}")

        flash("Password updated successfully!")
        return redirect(url_for('auth.login'))

    return render_template("reset_password.html")


# -------------------- LOGOUT --------------------
@auth.route("/logout")
@login_required
def logout():
    current_app.logger.info("User logged out")
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for("auth.login"))
