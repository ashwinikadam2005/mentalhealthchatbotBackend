import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime, timedelta

def generate_otp(length=6):
    """Generate a random OTP of specified length"""
    return ''.join(random.choices(string.digits, k=length))

def _get_sender_credentials():
    """
    Sender is fixed to mentalcareapp2024@gmail.com by default, but can be overridden
    via env vars to avoid hardcoding secrets.
    """
    sender_email = os.getenv("MENTALCARE_SENDER_EMAIL", "mentalcareapp2024@gmail.com")
    password = os.getenv("MENTALCARE_SENDER_APP_PASSWORD", "rxym mogt hxmc mwur")
    return sender_email, password

def send_otp_email(recipient_email, otp):
    """Send OTP verification email to the user"""
    sender_email, password = _get_sender_credentials()
    
    # Create message
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = recipient_email
    message['Subject'] = 'MentalCare - Email Verification OTP'
    
    # Email body
    body = f"""
    <html>
    <body>
        <h2>Welcome to MentalCare!</h2>
        <p>Thank you for registering with us. To complete your registration, please use the following OTP:</p>
        <h3 style="background-color: #f2f2f2; padding: 10px; text-align: center; font-size: 24px;">{otp}</h3>
        <p>This OTP is valid for 10 minutes.</p>
        <p>If you did not request this verification, please ignore this email.</p>
        <p>Best regards,<br>MentalCare Team</p>
    </body>
    </html>
    """
    
    message.attach(MIMEText(body, 'html'))
    
    try:
        # Print OTP to console for debugging
        print(f"Sending OTP to {recipient_email}: {otp}")
        
        # Send actual email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, password)
        server.send_message(message)
        server.quit()
        
        print(f"Email sent successfully to {recipient_email}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def send_doctor_added_email(recipient_email: str, doctor_name: str = "", qualification: str = ""):
    """Notify a doctor that they were added to MentalCare."""
    if not recipient_email:
        return False

    sender_email, password = _get_sender_credentials()

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = "MentalCare - You have been added as a Doctor"

    display_name = doctor_name.strip() or "Doctor"
    qual_line = f"<p><b>Qualification:</b> {qualification}</p>" if qualification else ""

    body = f"""
    <html>
    <body>
        <h2>Welcome to MentalCare!</h2>
        <p>Hello {display_name},</p>
        <p>You have been added as a doctor on the MentalCare platform.</p>
        {qual_line}
        <p>If this was not expected, please reply to this email.</p>
        <p>Best regards,<br/>MentalCare Team</p>
    </body>
    </html>
    """

    message.attach(MIMEText(body, "html"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, password)
        server.send_message(message)
        server.quit()
        print(f"Doctor notification email sent to {recipient_email}")
        return True
    except Exception as e:
        print(f"Error sending doctor notification email: {e}")
        return False