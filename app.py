from flask import Flask, request, jsonify
import random
import smtplib
from email.mime.text import MIMEText

from flask_cors import CORS  # Import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# In-memory storage for OTPs (for demonstration purposes)
otp_storage = {}

# Email configuration
# Email configuration for Gmail
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587  # Use 465 for SSL
EMAIL_ADDRESS = 'missionimpossible4546@gmail.com'
EMAIL_PASSWORD = 'yuiugahripwqnbme'

def send_email(to_email, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, [to_email], msg.as_string())

@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.json
    email = data.get('email')

    print(f"Received request to send OTP to email: {email}")

    if not email:
        print("Email is required")
        return jsonify({'success': False, 'message': 'Email is required'}), 400

    # Generate a random 4-digit OTP
    otp = ''.join([str(random.randint(0, 9)) for _ in range(4)])
    otp_storage[email] = otp

    print(f"Generated OTP for {email}: {otp}")

    # Send OTP via email
    subject = 'Verify Your OTP to Access Nigama Connect'
    body = (f"Dear User,\n\n"
            f"Greetings from the Nigama Connect team!\n\n"
            f"We’re thrilled to have you as a part of our family-oriented social networking platform. Nigama Connect is designed to help you trace your lineage, connect with relatives, and strengthen bonds while exploring a range of exciting features like:\n"
            f"- Family Tree Creation\n"
            f"- Event Planning and RSVPs\n"
            f"- Classifieds for Buying, Selling, and Services\n"
            f"- Matrimony Search for Matchmaking\n"
            f"- Professional Networking for Opportunities\n\n"
            f"To ensure your account security, please verify your One-Time Password (OTP) below:\n\n"
            f"Your OTP is: {otp}\n\n"
            f"This OTP is valid for the next 10 minutes. Please do not share this code with anyone for your safety.\n\n"
            f"If you did not initiate this request, please contact us immediately at missionimpossible4546@gmail.com.\n\n"
            f"Thank you for joining us on this journey to celebrate heritage and create meaningful connections.\n\n"
            f"Warm regards,\n"
            f"The Nigama Connect Team")

    try:
        print(f"Sending OTP email to {email}")
        send_email(email, subject, body)
        print("OTP email sent successfully")
        return jsonify({'success': True, 'message': 'OTP sent successfully'})
    except Exception as e:
        print(f"Error sending OTP email: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json
    email = data.get('email')
    otp = data.get('otp')

    print(f"Received request to verify OTP for email: {email}")

    if not email or not otp:
        print("Email and OTP are required")
        return jsonify({'success': False, 'message': 'Email and OTP are required'}), 400

    stored_otp = otp_storage.get(email)

    if not stored_otp:
        print(f"No OTP found for email: {email}")
        return jsonify({'success': False, 'message': 'OTP not found or expired'}), 404

    if stored_otp == otp:
        print(f"OTP verified successfully for email: {email}")
        del otp_storage[email]  # Clear the OTP after successful verification
        return jsonify({'success': True, 'message': 'OTP verified successfully'})
    else:
        print(f"Invalid OTP for email: {email}")
        return jsonify({'success': False, 'message': 'Invalid OTP'}), 400

if __name__ == '__main__':
    print("Starting Flask server...")
    app.run(debug=True)