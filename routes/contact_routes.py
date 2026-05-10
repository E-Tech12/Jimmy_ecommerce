from flask import Blueprint, render_template, request, flash, redirect, url_for
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

contact_auth = Blueprint('contact_auth', __name__)

# Email configuration
SMTP_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('MAIL_PORT', 587))
EMAIL_ADDRESS = os.getenv('MAIL_USERNAME', 'your_email@gmail.com')
EMAIL_PASSWORD = os.getenv('MAIL_PASSWORD', 'your_app_password')

@contact_auth.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        
        # Validate inputs
        if not name or not email or not message:
            flash('Please fill in all fields', 'error')
            return redirect(url_for('contact_auth.contact'))
        
        try:
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = EMAIL_ADDRESS
            msg['To'] = EMAIL_ADDRESS  # Send to yourself
            msg['Subject'] = f'New Contact Form Message from {name}'
            
            # Email body
            body = f"""
            Name: {name}
            Email: {email}
            
            Message:
            {message}
            
            ---
            Sent from BiteOnGo Contact Form
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.send_message(msg)
            
            # Optional: Send auto-reply to user
            auto_reply = MIMEMultipart()
            auto_reply['From'] = EMAIL_ADDRESS
            auto_reply['To'] = email
            auto_reply['Subject'] = 'Thank you for contacting BiteOnGo!'
            
            reply_body = f"""
            Hello {name},

            Thank you for reaching out to BiteOnGo!

            We have received your message and will get back to you within 24 hours.

            Here's a copy of your message:
            "{message}"

            Best regards,
            BiteOnGo Team
            """
            
            auto_reply.attach(MIMEText(reply_body, 'plain'))
            
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.send_message(auto_reply)
            
            flash('Your message has been sent successfully! We\'ll get back to you soon.', 'success')
            
        except Exception as e:
            print(f"Error sending email: {e}")
            flash('There was an error sending your message. Please try again later.', 'error')
        
        return redirect(url_for('contact_auth.contact'))
    
    return render_template('contact.html')
