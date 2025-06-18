from flask import Flask, request, jsonify, send_from_directory, url_for
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
from flask_cors import CORS  # Import CORS
from flask import Flask, request, jsonify
from firebase_admin import firestore
import os
import uuid
from datetime import datetime, date
from flask_cors import CORS
import logging
from werkzeug.utils import secure_filename
import hashlib
from get_connections import get_user_connections
from family_spouse_manager import (
    add_spouse_relationship, 
    handle_no_trees_scenario, 
    create_family_tree_with_husband, 
    create_family_tree_with_wife,
    add_husband_to_family_tree,
    add_wife_to_family_tree,
    create_family_tree_with_husband_email,
    create_family_tree_with_wife_email,
    handle_both_spouses_have_trees
)
from invitation_manager import (
    send_invitation, get_invitations, update_invitation_status, 
    invitation_acceptance_handlers, TYPE_FRIEND, TYPE_FAMILY, 
    STATUS_ACCEPTED, STATUS_REJECTED
)
from socket_manager import init_socketio, notify_user
from family_child_manager import add_child_to_family_tree, create_family_tree_with_father_child, add_child_with_subtree
from family_parent_manager import add_parents_to_family_tree, create_family_tree_with_parents, merge_family_trees
from notification_manager import get_user_notifications, mark_notifications_read, archive_notifications, mark_all_notifications_read
from firebase_init import get_firestore_client

# Import the new friend manager module
from friend_manager import add_noprofile_friend

from promocode_manager import add_promocode, get_promocode_details, update_tree_node_with_promocode

import base64
import mimetypes
import threading
import json
from io import BytesIO
from dotenv import load_dotenv

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize SocketIO
socketio = init_socketio(app)

# In-memory storage for OTPs with timestamps
otp_storage = {}  # Will store {email: {'otp': '1234', 'timestamp': 1615293600}}

# OTP expiration time in seconds (10 minutes)
OTP_EXPIRATION_TIME = 600  # 10 minutes * 60 seconds

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Email configuration
# Email configuration for Gmail
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587  # Use 465 for SSL
EMAIL_ADDRESS = 'missionimpossible4546@gmail.com'
EMAIL_PASSWORD = 'yuiugahripwqnbme' 

def send_email(to_email, subject, body):
    # Create a MIMEMultipart message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email

    # Attach HTML version of the message
    html_part = MIMEText(body, 'html')
    msg.attach(html_part)

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
    
    # Store OTP with current timestamp
    current_time = int(time.time())
    otp_storage[email] = {'otp': otp, 'timestamp': current_time}

    print(f"Generated OTP for {email}: {otp}, valid until: {current_time + OTP_EXPIRATION_TIME}")

    # Send OTP via email
    subject = 'Verify Your OTP to Access Nigama Connect'
    body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #007bff;">
        <h2 style="color: #007bff; margin-top: 0;">Welcome to Nigama Connect!</h2>
        
        <p>Dear User,</p>
        
        <p>Greetings from the Nigama Connect team!</p>
        
        <p>We're thrilled to have you as a part of our family-oriented social networking platform. Nigama Connect is designed to help you trace your lineage, connect with relatives, and strengthen bonds while exploring a range of exciting features like:</p>
        
        <ul style="padding-left: 20px;">
            <li>Family Tree Creation</li>
            <li>Event Planning and RSVPs</li>
            <li>Classifieds for Buying, Selling, and Services</li>
            <li>Matrimony Search for Matchmaking</li>
            <li>Professional Networking for Opportunities</li>
        </ul>
        
        <div style="background-color: #e8f4ff; padding: 15px; border-radius: 6px; margin: 20px 0; text-align: center; border: 1px dashed #007bff;">
            <p style="margin: 0; font-size: 16px;">To ensure your account security, please verify with the One-Time Password below:</p>
            <h1 style="color: #007bff; font-size: 42px; letter-spacing: 5px; margin: 15px 0;">{otp}</h1>
            <p style="margin: 0; font-style: italic; color: #666;">This OTP is valid for the next 10 minutes only</p>
        </div>
        
        <p style="color: #dc3545; font-weight: bold;">Please do not share this code with anyone for your safety.</p>
        
        <p>If you did not initiate this request, please contact us immediately at <a href="mailto:missionimpossible4546@gmail.com" style="color: #007bff;">missionimpossible4546@gmail.com</a>.</p>
        
        <p>Thank you for joining us on this journey to celebrate heritage and create meaningful connections.</p>
        
        <p>Warm regards,<br>
        The Nigama Connect Team</p>
    </div>
</body>
</html>
"""

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

    stored_data = otp_storage.get(email)

    if not stored_data:
        print(f"No OTP found for email: {email}")
        return jsonify({'success': False, 'message': 'OTP not found or expired'}), 404

    # Check if OTP has expired
    current_time = int(time.time())
    if current_time - stored_data['timestamp'] > OTP_EXPIRATION_TIME:
        print(f"OTP expired for email: {email}")
        # Remove expired OTP
        del otp_storage[email]
        return jsonify({'success': False, 'message': 'OTP has expired. Please request a new one.'}), 400

    if stored_data['otp'] == otp:
        print(f"OTP verified successfully for email: {email}")
        del otp_storage[email]  # Clear the OTP after successful verification
        return jsonify({'success': True, 'message': 'OTP verified successfully'})
    else:
        print(f"Invalid OTP for email: {email}")
        return jsonify({'success': False, 'message': 'Invalid OTP'}), 400

# Optional: Add a cleanup function to periodically remove expired OTPs
def cleanup_expired_otps():
    current_time = int(time.time())
    expired_emails = []

    for email, data in otp_storage.items():
        if current_time - data['timestamp'] > OTP_EXPIRATION_TIME:
            expired_emails.append(email)
     
    for email in expired_emails:
        del otp_storage[email]
    
    print(f"Cleaned up {len(expired_emails)} expired OTPs")

# You could call this function periodically, or implement a scheduled task





try:
    db = get_firestore_client()
    user_profiles_ref = db.collection('user_profiles')  # Ensure this line is executed
    family_tree_ref = db.collection('family_tree')  # Top-level collection
    logger.info("Firebase initialized successfully")
except Exception as e:
    logger.error(f"Error initializing Firebase: {e}")
    if os.environ.get('FLASK_ENV') == 'development':
        logger.warning("Running in development mode without Firebase")
        db = None
        user_profiles_ref = None  # Ensure this is set to None if Firebase fails
        family_tree_ref = None
    else:
        raise

# File upload configuration
UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/health', methods=['GET'])
def health_check():
    """Simple endpoint to check if the API is running."""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/api/profile/create', methods=['POST'])
def create_profile():
    """
    API endpoint to create a new user profile.
    Stores basic user data in the main document and only the profile image 
    in a subcollection.
    """
    try:
        # Get profile data from request
        profile_data = request.json
        logger.info(f"Received profile creation request for: {profile_data.get('email')}")
        
        # Validate required fields
        required_fields = ['firstName', 'lastName', 'email', 'phone', 'DOB', 'GENDER', 'CASTE', 'MARITAL_STATUS']
        for field in required_fields:
            if not profile_data.get(field):
                return jsonify({
                    "success": False,
                    "error": f"Missing required field: {field}"
                }), 400
        
        # Extract email to use as document ID
        email = profile_data.get('email')
        first_name = profile_data.get('firstName')
        
        # create a numbercollection and add the phone number to it
        number_collection_ref = db.collection('numbers')
        number_doc_ref = number_collection_ref.document('+91'+profile_data.get('phone'))
        number_doc_ref.set({
            'phone': profile_data.get('phone'),
            'email': email
        })
        
        # Generate a unique ID for the profile image entry
        image_entry_id = "profileimage"
        
        # Add timestamps
        now = datetime.now().isoformat()
        
        # Extract image data
        profile_image = profile_data.pop('profileImage', None)
        
        # Save to Firebase
        if user_profiles_ref:
            # Set user document with email as ID and all profile data except the image
            user_doc_ref = user_profiles_ref.document(email)
            
            # Add the user data to the outer document
            user_data = {
                'email': email,
                'firstName': profile_data.get('firstName'),
                'lastName': profile_data.get('lastName'),
                'phone': profile_data.get('phone'),
                'DOB': profile_data.get('DOB'),
                'GENDER': profile_data.get('GENDER'),
                'CASTE': profile_data.get('CASTE'),
                'MARITAL_STATUS': profile_data.get('MARITAL_STATUS'),
                'createdAt': now,
                'updatedAt': now
            }
            
            user_doc_ref.set(user_data, merge=True)
            
            # Store only profile image in the subcollection if it exists
            if profile_image:
                profile_images_ref = user_doc_ref.collection('profileImages')
                image_doc_ref = profile_images_ref.document(image_entry_id)
                image_doc_ref.set({
                    'imageData': profile_image,
                    'uploadedAt': now,
                    'imageId': image_entry_id
                })
                
                # Update the user document with a reference to the latest image
                user_doc_ref.update({
                    'currentProfileImageId': image_entry_id
                })
                
                logger.info(f"Profile and image created for {email} with image ID: {image_entry_id}")
            else:
                logger.info(f"Profile created for {email} without image")
            
            # Send welcome email
            welcome_subject = "Welcome to Nigama Connect!"
            welcome_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #007bff;">
        <h2 style="color: #007bff; margin-top: 0;">Welcome to Nigama Connect!</h2>
        
        <p>Dear {first_name},</p>
        
        <p>Welcome to Nigama Connect! We're thrilled to have you join our growing community.</p>
        
        <p>At Nigama Connect, we offer a unique platform designed to help you:</p>
        
        <ul style="padding-left: 20px;">
            <li>Build and explore your family tree</li>
            <li>Connect with relatives and strengthen family bonds</li>
            <li>Share and discover family events</li>
            <li>Access matrimony services</li>
            <li>Browse and post classifieds within the community</li>
            <li>Network professionally with community members</li>
        </ul>
        
        <div style="background-color: #e8f4ff; padding: 15px; border-radius: 6px; margin: 20px 0;">
            <h3 style="color: #007bff; margin-top: 0;">Getting Started</h3>
            <ol style="margin: 0; padding-left: 20px;">
                <li>Complete your profile</li>
                <li>Start building your family tree</li>
                <li>Connect with family members</li>
                <li>Explore community features</li>
            </ol>
        </div>
        
        <p>Need help? Our support team is always here to assist you. Feel free to reach out to us at <a href="nigamaconnect@gmail.com" style="color: #007bff;">nigamaconnect@gmail.com</a>.</p>
        
        <p>Thank you for joining Nigama Connect. We look forward to helping you strengthen your family bonds and build meaningful connections within the community.</p>
        
        <p>Best regards,<br>
        The Nigama Connect Team</p>
    </div>
</body>
</html>
"""
            try:
                send_email(email, welcome_subject, welcome_body)
                logger.info(f"Welcome email sent to {email}")
            except Exception as email_error:
                logger.error(f"Error sending welcome email to {email}: {str(email_error)}")
                # Continue execution even if email fails
            
            return jsonify({
                "success": True,
                "message": "Profile created successfully",
                "email": email,
                "imageId": image_entry_id if profile_image else None
            })
        else:
            # For development without Firebase
            logger.warning("Development mode - profile not saved to Firebase")
            return jsonify({
                "success": True,
                "message": "Development mode - profile data received but not saved",
                "userData": user_data,
                "hasImage": profile_image is not None,
                "email": email
            })
            
    except Exception as e:
        logger.error(f"Error creating profile: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
        
        
        
@app.route('/api/profile/get', methods=['GET'])
def get_profile():
    """
    API endpoint to fetch user profile details using email.
    Returns basic profile data and converts profile image from bytecode to base64.
    """
    try:
        # Get email from query parameter
        print('request')
        email = request.args.get('email')
        print('email',email)
        
        if not email:
            return jsonify({
                "success": False,
                "error": "Email parameter is required"
            }), 400
            
        logger.info(f"Received profile fetch request for email: {email}")
        
        # Fetch profile from Firebase
        if user_profiles_ref:
            # Get user document with email as ID
            user_doc = user_profiles_ref.document(email).get()
            
            if not user_doc.exists:
                return jsonify({
                    "success": False,
                    "error": "Profile not found"
                }), 404
                
            # Get user data
            user_data = user_doc.to_dict()
            
            # Check if user has a profile image
            current_image_id = user_data.get('currentProfileImageId')
            profile_image_base64 = None
            print(current_image_id)
            if current_image_id:
                # Get profile image from subcollection
                image_doc = user_profiles_ref.document(email).collection('profileImages').document(current_image_id).get()
                
                if image_doc.exists:
                    image_data = image_doc.to_dict()
                    # Convert bytecode to base64 string for transmission
                    profile_image_base64 = image_data.get('imageData')
            
            # Prepare response data
            profile_data = {
                "firstName": user_data.get('firstName'),
                "lastName": user_data.get('lastName'),
                "email": user_data.get('email'),
                "phone": user_data.get('phone'),
                "dob": user_data.get('DOB'),
                "gender": user_data.get('GENDER'),
                "caste": user_data.get('CASTE'),
                "maritalStatus": user_data.get('MARITAL_STATUS'),
                "profileImage": profile_image_base64
            }
            print('data')
            
            return jsonify({
                "success": True,
                "profile": profile_data
            })
        else:
            # For development without Firebase
            logger.warning("Development mode - returning mock profile data")
            return jsonify({
                "success": True,
                "profile": {
                    "firstName": "Venkateswararo",
                    "lastName": "Megadula",
                    "email": email,
                    "phone": "+91 9032038890",
                    "dob": "17/11/1986",
                    "gender": "Male",
                    "caste": "OC",
                    "maritalStatus": "Married",
                    "profileImage": None  # Mock data has no image
                }
            })
            
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
        
        

@app.route('/api/profile/save_additional_info', methods=['POST'])
def save_additional_info():
    """
    API endpoint to save additional profile information and uploaded photos.
    Expects JSON data with form data and uploaded photos.
    """
    try:
        # Get the form data and uploaded photos from the request
        data = request.json
        email = data.get('email')

        if not email:
            return jsonify({
                "success": False,
                "error": "Email is required"
            }), 400

        # Extract form data
        form_data = {
            "occupation": data.get("occupation"),
            "education": data.get("education"),
            "hometown": data.get("hometown"),
            "alive": data.get("alive"),
            "dod": data.get("dod"),
            "country": data.get("country"),
            "pincode": data.get("pincode"),
            "flatHouseNo": data.get("flatHouseNo"),
            "areaStreet": data.get("areaStreet"),
            "townCity": data.get("townCity"),
            "state": data.get("state"),
            "biography": data.get("biography"),
            "openForWork": data.get("openForWork"),
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat()
        }

        # Extract uploaded photos
        uploaded_photos = {
            "uploadedphoto1": data.get("uploadPhoto1"),
            "uploadedphoto2": data.get("uploadPhoto2"),
            "uploadedphoto3": data.get("uploadPhoto3")
        }

        # Save form data to Firestore in the 'additional_info' collection
        if user_profiles_ref:
            # Reference to the 'additional_info' collection with email as the document ID
            
            user_doc = user_profiles_ref.document(email).get()
            additional_info_ref = user_profiles_ref.document(email).collection('additional_info').document(email)
            additional_info_ref.set(form_data, merge=True)

            # Save uploaded photos in the 'uploaded_photos' subcollection
            uploaded_photos_ref = additional_info_ref.collection('uploaded_photos')
            for photo_id, photo_data in uploaded_photos.items():
                if photo_data:  # Only save if photo data exists
                    uploaded_photos_ref.document(photo_id).set({
                        "imageData": photo_data,
                        "uploadedAt": datetime.now().isoformat()
                    })

            logger.info(f"Additional info and photos saved for email: {email}")
            return jsonify({
                "success": True,
                "message": "Additional info and photos saved successfully",
                "email": email
            })
        else:
            # For development without Firebase
            logger.warning("Development mode - data not saved to Firebase")
            return jsonify({
                "success": True,
                "message": "Development mode - data received but not saved",
                "formData": form_data,
                "uploadedPhotos": uploaded_photos,
                "email": email
            })

    except Exception as e:
        logger.error(f"Error saving additional info and photos: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500




@app.route('/api/profile/set_login_true', methods=['POST'])
def set_login_true():
    """
    API endpoint to set the 'login' attribute to true for a document referenced by email.
    Expects JSON data with the email.
    """
    try:
        # Get the email from the request
        print('request====================== login true')
        
        data = request.json
        email = data.get('email')
        print('email====================== login true',email)

        if not email:
            return jsonify({
                "success": False,
                "error": "Email is required"
            }), 400

        # Check if Firebase is initialized
        if db is None or user_profiles_ref is None:
            logger.warning("Development mode - Firebase not initialized")
            return jsonify({
                "success": True,
                "message": "Development mode - login status not updated in Firebase",
                "email": email
            })

        # Reference to the document using the email as the document ID
        user_ref = user_profiles_ref.document(email)

        # Check if the document exists
        doc = user_ref.get()

        if doc.exists:
            # Update the document to set 'login' to true
            user_ref.update({"login": True})
            logger.info(f"Login set to true for email: {email}")
            
            # Get user's name for personalized email
            user_data = doc.to_dict()
            first_name = user_data.get('firstName', '')
            
            # Send thank you email
            thank_you_subject = "Thankyou for logging into Nigama Connect!"
            thank_you_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #007bff;">
        <h2 style="color: #007bff; margin-top: 0;">Welcome to Nigama Connect!</h2>
        
        <p>Dear {first_name},</p>
        
        <p>Thank you for logging into Nigama Connect! We're glad to have you here.</p>
        
        <p>Here are the amazing features available for you:</p>
        
        <div style="background-color: #e8f4ff; padding: 15px; border-radius: 6px; margin: 20px 0;">
            <h3 style="color: #007bff; margin-top: 0;">Your Nigama Connect Features</h3>
            <ul style="padding-left: 20px;">
                <li><strong>Family Tree:</strong> Build, explore, and connect with your family history</li>
                <li><strong>Events & RSVPs:</strong> Stay updated with family gatherings and celebrations</li>
                <li><strong>Classifieds:</strong> Browse or post items and services within the community</li>
                <li><strong>Matrimony Search:</strong> Find potential matches that align with your preferences</li>
                <li><strong>Professional Network:</strong> Connect with community members professionally</li>
                <li><strong>Real-time Chat:</strong> Stay in touch with your connections</li>
            </ul>
        </div>
        
        <div style="background-color: #fff4e8; padding: 15px; border-radius: 6px; margin: 20px 0;">
            <h3 style="color: #ff7f00; margin-top: 0;">Quick Tips</h3>
            <ul style="padding-left: 20px;">
                <li>Update your profile to connect better</li>
                <li>Start building your family tree</li>
                <li>Check out upcoming events</li>
                <li>Browse the community classifieds</li>
            </ul>
        </div>
        
        <p>Need assistance? Our support team is here to help at <a href="nigamaconnect@gmail.com" style="color: #007bff;">nigamaconnect@gmail.com</a>.</p>
        
        <p>Happy connecting!</p>
        
        <p>Best regards,<br>
        The Nigama Connect Team</p>
    </div>
</body>
</html>
"""
            try:
                send_email(email, thank_you_subject, thank_you_body)
                logger.info(f"Thank you email sent to {email}")
            except Exception as email_error:
                logger.error(f"Error sending thank you email to {email}: {str(email_error)}")
                # Continue execution even if email fails
            
            return jsonify({
                "success": True,
                "message": "Login set to true successfully",
                "email": email
            })
        else:
            return jsonify({
                "success": False,
                "error": "Document not found"
            }), 404

    except Exception as e:
        logger.error(f"Error setting login to true: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/profile/set_login_false', methods=['POST'])
def set_login_false():
    """
    API endpoint to set the 'login' attribute to false for a document referenced by email.
    Expects JSON data with the email.
    """
    try:
        # Get the email from the request
        data = request.json
        email = data.get('email')

        if not email:
            return jsonify({
                "success": False,
                "error": "Email is required"
            }), 400

        # Check if Firebase is initialized
        if db is None or user_profiles_ref is None:
            logger.warning("Development mode - Firebase not initialized")
            return jsonify({
                "success": True,
                "message": "Development mode - login status not updated in Firebase",
                "email": email
            })

        # Reference to the document using the email as the document ID
        user_ref = user_profiles_ref.document(email)

        # Check if the document exists
        doc = user_ref.get()

        if doc.exists:
            # Update the document to set 'login' to false
            user_ref.update({"login": False})
            logger.info(f"Login set to false for email: {email}")
            return jsonify({
                "success": True,
                "message": "Login set to false successfully",
                "email": email
            })
        else:
            return jsonify({
                "success": False,
                "error": "Document not found"
            }), 404

    except Exception as e:
        logger.error(f"Error setting login to false: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
        
        
from getloginstatus import get_login_status
@app.route('/api/profile/get_login_status', methods=['POST'])
def get_login_status_api():
    """
    API endpoint to get the login status of a user by email.
    Expects JSON data with the email.
    """
    try:
        # Get the email from the request
        data = request.json
        email = data.get('email')

        if not email:
            return jsonify({
                "success": False,
                "error": "Email is required"
            }), 400

        # Call the get_login_status function
        success, result = get_login_status(email,user_profiles_ref)

        if success:
            return jsonify({
                "success": True,
                "login_status": result,
                "email": email
            })
        else:
            return jsonify({
                "success": False,
                "error": result
            }), 404

    except Exception as e:
        logger.error(f"Error getting login status: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
        
        
        
@app.route('/api/profile/dashboard-image', methods=['POST'])
def set_dashboard_profile():
    """
    API endpoint to set a specific profile image as the dashboard profile.
    It takes an email and image byte data, updates the image in the database, 
    and marks it as the dashboard profile image.
    """
    try:
        # Get data from request
        data = request.json
        email = data.get('email')
        profile_image = data.get('profileImage')  # Byte code image data

        # Validate input
        if not email:
            return jsonify({
                "success": False,
                "error": "Email is required"
            }), 400

        if not profile_image:
            return jsonify({
                "success": False,
                "error": "Profile image data is required"
            }), 400

        # Fetch the user document reference
        user_doc_ref = user_profiles_ref.document(email)
        user_doc = user_doc_ref.get()

        if not user_doc.exists:
            return jsonify({
                "success": False,
                "error": "User with the provided email does not exist"
            }), 404

        # Use 'dashboardprofile' as the document ID for the dashboard image
        dashboard_image_id = "dashboardprofile"

        # Save the image to the profileImages subcollection
        profile_images_ref = user_doc_ref.collection('profileImages')
        image_doc_ref = profile_images_ref.document(dashboard_image_id)
        now = datetime.now().isoformat()

        image_doc_ref.set({
            'imageData': profile_image,
            'uploadedAt': now,
            'imageId': dashboard_image_id,
            'isDashboardProfile': True
        })

        # Update the user document with a reference to the dashboard profile image
        user_doc_ref.update({
            'dashboardProfileImageId': dashboard_image_id
        })

        logger.info(f"Dashboard profile image set for {email} with image ID: {dashboard_image_id}")
        return jsonify({
            "success": True,
            "message": "Dashboard profile image set successfully",
            "email": email,
            "dashboardImageId": dashboard_image_id
        })

    except Exception as e:
        logger.error(f"Error setting dashboard profile image: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/profile/dashboard-image/<email>', methods=['GET'])
def get_dashboard_profile(email):
    """
    API endpoint to get the dashboard profile image for a user by email.
    """
    try:
        # Fetch the user document reference
        user_doc_ref = user_profiles_ref.document(email)
        user_doc = user_doc_ref.get()

        if not user_doc.exists:
            return jsonify({
                "success": False,
                "error": "User with the provided email does not exist"
            }), 404

        # Get the dashboard profile image ID from the user document
        dashboard_image_id = user_doc.get('dashboardProfileImageId')

        if not dashboard_image_id:
            return jsonify({
                "success": False,
                "error": "Dashboard profile image is not set for this user"
            }), 404

        # Fetch the image data from the profileImages subcollection
        profile_images_ref = user_doc_ref.collection('profileImages')
        image_doc_ref = profile_images_ref.document(dashboard_image_id)
        image_doc = image_doc_ref.get()

        if not image_doc.exists:
            return jsonify({
                "success": False,
                "error": "Dashboard profile image data not found"
            }), 404

        # Return the image data
        image_data = image_doc.get('imageData')

        logger.info(f"Retrieved dashboard profile image for {email}")
        return jsonify({
            "success": True,
            "email": email,
            "dashboardImageId": dashboard_image_id,
            "imageData": image_data
        })

    except Exception as e:
        logger.error(f"Error retrieving dashboard profile image: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500 
      
        
from fetch_all_profile_data import fetch_all_profile_data        
@app.route('/api/profile/get_all_data', methods=['GET'])
def get_all_profile_data():
    """
    API endpoint to fetch all user profile data, including:
    - Basic profile data
    - Profile image
    - Additional info
    - Uploaded photos
    """
    try:
        # Get email from query parameter
        email = request.args.get('email')
        
        if not email:
            return jsonify({
                "success": False,
                "error": "Email parameter is required"
            }), 400
            
        logger.info(f"Received request to fetch all profile data for email: {email}")
        
        # Fetch all profile data using the helper function
        profile_data = fetch_all_profile_data(email,user_profiles_ref)
        
        if not profile_data:
            return jsonify({
                "success": False,
                "error": "Profile not found"
            }), 404
        
        return jsonify({
            "success": True,
            "profile": profile_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching all profile data: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

from update_profile_in_firebase import update_profile_in_firebase        
@app.route('/api/profile/update_profile', methods=['POST'])
def update_profile():

    try:
        # Get the JSON data from the request
        data = request.json
        email = data.get('email')

        if not email:
            return jsonify({
                "success": False,
                "error": "Email is required"
            }), 400

        # Check if Firebase is initialized
        if db is None or user_profiles_ref is None:
            logger.warning("Development mode - Firebase not initialized")
            return jsonify({
                "success": True,
                "message": "Development mode - profile not updated in Firebase",
                "email": email
            })

        # Call the core function to update the profile
        result = update_profile_in_firebase(email, data, user_profiles_ref,db)

        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f"Error in update_profile API: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
# write store family tree image in firebase storage
def store_family_tree_image(img_base64, family_tree_id):
    try:
        # ge thedocument ref of family tree using family tree id
        family_tree_ref = db.collection('family_tree').document(family_tree_id)
        family_tree_doc = family_tree_ref.get()
        if not family_tree_doc.exists:
            logger.error("Family tree document not found")
            return jsonify({'error': 'Family tree document not found'}), 404
        # create or updatethe field family_tree_image with the image base64
        family_tree_ref.update({'family_tree_image': img_base64})
        return jsonify({'success': True, 'message': 'Family tree image stored successfully'})
    except Exception as e:
        logger.error(f"Error in store_family_tree_image: {e}")
        return jsonify({'error': str(e)}), 500


from generate_family_tree import generate_family_tree
@app.route('/generate-tree', methods=['POST'])
def generate_tree():
    data = request.get_json()
    family_members = data.get('familyMembers', [])
    family_tree_id = data.get('familyTreeId', '')
    
    print(family_tree_id)
    
    if not family_members:
        return jsonify({'error': 'No family data provided'}), 400

    try:
        img_base64 = generate_family_tree(family_members)
        # store the image in firebase storage
        if family_tree_id:
            store_family_tree_image(img_base64, family_tree_id)     
        else:
            logger.error("No family tree ID provided")
            return jsonify({'error': 'No family tree ID provided'}), 400
        # write store family tree image in firebase storage
        
        
        return jsonify({'image': img_base64})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


from search_profiles_by_info import search_profiles_by_info    
@app.route('/api/search-profiles', methods=['POST'])
def search_profiles():
    try:
        data = request.json
        first_name = data.get('firstName', '')
        last_name = data.get('lastName', '')
        email = data.get('email', '')
        phone = data.get('phone', '')
        
        # Ensure at least one search parameter is provided
        if not any([first_name, last_name, email, phone]):
            return jsonify({"error": "At least one search parameter (firstName, lastName, email, or phone) is required"}), 400
        
        # Pass all search parameters to the function
        matches = search_profiles_by_info(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            db=db
        )
        
        return jsonify({
            "success": True,
            "matches": matches
        })
        
    except Exception as e:
        logger.error(f"Error in search-profiles endpoint: {e}")
        return jsonify({"error": str(e)}), 500
    

from sendinvite import save_received_invitation, save_sent_invitation   

@app.route('/api/invitations/save', methods=['POST'])
def save_invitations():
 
    try:
        # Get the request data
        data = request.get_json()
        if not data:
            logger.error("No data provided in the request")
            return jsonify({"error": "No data provided"}), 400

        sent_invitation = data.get('sentInvitations')
        received_invitation = data.get('receivedInvitations')
        print(sent_invitation)
        print(received_invitation)
        
        if not sent_invitation or not received_invitation:
            logger.error("Both sentInvitation and receivedInvitation are required")
            return jsonify({"error": "Both sentInvitation and receivedInvitation are required"}), 400

        # Save sent invitation
        sent_success = save_sent_invitation(sent_invitation,user_profiles_ref)

        # Save received invitation
        received_success = save_received_invitation(received_invitation,user_profiles_ref)

        if not sent_success or not received_success:
            logger.error("Failed to save one or both invitations")
            return jsonify({"error": "Failed to save one or both invitations"}), 500

        # Return success response
        return jsonify({
            "success": True,
            "message": "Invitations saved successfully",
            "sentCount": 1,
            "receivedCount": 1
        }), 200

    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}")
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error saving invitations: {str(e)}")
        return jsonify({"error": f"Failed to save invitations: {str(e)}"}), 500


# @app.route('/api/profile/update', methods=['PUT'])
# def update_profile():
#     """
#     API endpoint to update an existing user profile.
#     Expects JSON data with user profile information and userId.
#     """
#     try:
#         profile_data = request.json
        
#         # Validate userId
#         user_id = profile_data.get('userId')
#         if not user_id:
#             return jsonify({
#                 "success": False,
#                 "error": "Missing userId"
#             }), 400
        
#         # Update timestamp
#         profile_data['updatedAt'] = datetime.now().isoformat()
        
#         # Update in Firebase
#         if user_profiles_ref:
#             doc_ref = user_profiles_ref.document(user_id)
            
#             # Check if document exists
#             doc = doc_ref.get()
#             if not doc.exists:
#                 return jsonify({
#                     "success": False,
#                     "error": f"Profile with ID {user_id} not found"
#                 }), 404
                
#             doc_ref.update(profile_data)
#             logger.info(f"Profile updated with ID: {user_id}")
            
#             return jsonify({
#                 "success": True,
#                 "message": "Profile updated successfully"
#             })
#         else:
#             # For development without Firebase
#             return jsonify({
#                 "success": True,
#                 "message": "Development mode - update request received",
#                 "data": profile_data
#             })
            
#     except Exception as e:
#         logger.error(f"Error updating profile: {e}")
#         return jsonify({
#             "success": False,
#             "error": str(e)
#         }), 500

# @app.route('/api/profile/upload_photo', methods=['POST'])
# def upload_profile_photo():
#     """
#     API endpoint to upload a profile photo.
#     Expects a file and userId in the request.
#     """
#     try:
#         # Check if the post request has the file part
#         if 'file' not in request.files:
#             return jsonify({
#                 "success": False,
#                 "error": "No file part"
#             }), 400
        
#         file = request.files['file']
#         user_id = request.form.get('userId')
        
#         # Validate userId
#         if not user_id:
#             return jsonify({
#                 "success": False,
#                 "error": "Missing userId"
#             }), 400
        
#         # If the user does not select a file, the browser submits an empty file without a filename
#         if file.filename == '':
#             return jsonify({
#                 "success": False,
#                 "error": "No selected file"
#             }), 400
        
#         if file and allowed_file(file.filename):
#             filename = secure_filename(file.filename)
#             file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#             file.save(file_path)
            
#             # Save the file path to the user's profile in Firebase
#             if user_profiles_ref:
#                 doc_ref = user_profiles_ref.document(user_id)
#                 doc_ref.update({'profilePhotoUrl': file_path})
            
#             return jsonify({
#                 "success": True,
#                 "message": "File uploaded successfully",
#                 "filePath": file_path
#             })
#         else:
#             return jsonify({
#                 "success": False,
#                 "error": "File type not allowed"
#             }), 400
            
#     except Exception as e:
#         logger.error(f"Error uploading profile photo: {e}")
#         return jsonify({
#             "success": False,
#             "error": str(e)
#         }), 500

@app.route('/api/family-tree/update', methods=['POST'])
def update_family_tree():
    """
    API endpoint to update or create a family tree.
    Receives email and family members data.
    Checks if a family tree ID exists for the email, and updates or creates a new document.
    """
    try:
        data = request.json
        email = data.get('email')
        family_members = data.get('familyMembers')
        
        if not email or not family_members:
            return jsonify({
                "success": False,
                "error": "Email and family members data are required"
            }), 400
            
        logger.info(f"Received family tree update request for email: {email}")
        
        # Check if family tree ID exists for the email in user profiles
        user_doc = user_profiles_ref.document(email).get()
        family_tree_id = None
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            family_tree_id = user_data.get('familyTreeId')
        
        # If family tree ID doesn't exist, create a new one
        if not family_tree_id:
            # Create a new family tree ID based on email and timestamp
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            hash_input = f"{email}_{timestamp}"
            family_tree_id = hashlib.md5(hash_input.encode()).hexdigest()
            
            # Update user profile with the new family tree ID
            user_profiles_ref.document(email).set({
                'familyTreeId': family_tree_id,
                'updatedAt': datetime.now().isoformat()
            }, merge=True)
            
            logger.info(f"Created new family tree ID for {email}: {family_tree_id}")
        
        # Update or create the family tree document in the separate family_tree collection
        family_tree_ref.document(family_tree_id).set({
            'email': email,
            'familyMembers': family_members,
            'updatedAt': datetime.now().isoformat(),
            'createdAt': datetime.now().isoformat()
        }, merge=True)
        
        return jsonify({
            "success": True,
            "message": "Family tree updated successfully",
            "familyTreeId": family_tree_id
        })
    
    except Exception as e:
        logger.error(f"Error updating family tree: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/family-tree/get', methods=['GET'])
def get_family_tree():
    """
    API endpoint to fetch family tree data using email.
    Returns family tree data if it exists, otherwise returns false.
    """
    try:
        # Get email from query parameter
        email = request.args.get('email')
        
        if not email:
            return jsonify({
                "success": False,
                "error": "Email parameter is required"
            }), 400
            
        logger.info(f"Received request to fetch family tree for email: {email}")
        
        # Check if family tree ID exists for the email in user profiles
        user_doc = user_profiles_ref.document(email).get()
        family_tree_id = None
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            family_tree_id = user_data.get('familyTreeId')
        
        # If no family tree ID found, return false
        if not family_tree_id:
            return jsonify({
                "success": False,
                "message": "No family tree found for this email"
            }), 404
        
        # Fetch family tree data using the ID
        family_tree_doc = family_tree_ref.document(family_tree_id).get()
        
        
        
        if not family_tree_doc.exists:
            return jsonify({
                "success": False,
                "message": "Family tree document not found"
            }), 404
        
        # Return the family tree data
        family_tree_data = family_tree_doc.to_dict()
        
        return jsonify({
            "success": True,
            "familyTree": family_tree_data,
            "familyTreeId": family_tree_id
        })
    
    except Exception as e:
        logger.error(f"Error fetching family tree: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/family-tree/add-member', methods=['POST'])
def add_member():
    """
    API endpoint to add a member to a family tree.
    Takes two emails: main user and secondary user.
    Fetches the family tree ID from the main user and updates the secondary user's family tree.
    """
    try:
        data = request.json
        main_user_email = data.get('mainUserEmail')
        secondary_user_email = data.get('secondaryUserEmail')

        if not main_user_email or not secondary_user_email:
            return jsonify({
                "success": False,
                "error": "Both main user email and secondary user email are required"
            }), 400

        logger.info(f"Received request to add member from {main_user_email} to {secondary_user_email}")

        # Fetch family tree ID from the main user's profile
        main_user_doc = user_profiles_ref.document(main_user_email).get()
        
        if not main_user_doc.exists:
            return jsonify({
                "success": False,
                "message": "Main user not found"
            }), 404

        main_user_data = main_user_doc.to_dict()
        family_tree_id = main_user_data.get('familyTreeId')

        if not family_tree_id:
            return jsonify({
                "success": False,
                "message": "No family tree found for the main user"
            }), 404

      

        # Update the secondary user's profile with the family tree ID
        user_profiles_ref.document(secondary_user_email).set({
            'familyTreeId': family_tree_id,
            'updatedAt': datetime.now().isoformat()
        }, merge=True)

        return jsonify({
            "success": True,
            "message": "Family tree updated for the secondary user",
            "familyTreeId": family_tree_id
        })

    except Exception as e:
        logger.error(f"Error adding member to family tree: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/family-tree/update-members', methods=['POST'])
def update_family_tree_members():
    """
    API endpoint to update family tree IDs for each member in the family tree.
    Takes family members data, a family tree ID, and email data for self and father.
    Updates the family tree ID for each member based on their email.
    Adds userProfileExists flag to each member indicating if their email has an existing profile.
    """
    try:
        data = request.json
        family_members = data.get('familyMembers', [])
        new_family_tree_id = data.get('familyTreeId')
        self_email = data.get('selfEmail')
        father_email = data.get('fatherEmail')
        
        # Essential email logs
        print("self_email", self_email)
        print("father_email", father_email)

        if self_email is None:
            self_email = ""
            return jsonify({
                "success": False,
                "error": "Self email is required"
            }), 400
        if father_email is None:
            father_email = ""
            return jsonify({
                "success": False,
                "error": "Father email is required"
            }), 400

        # Convert family_members to list if it's a dictionary
        if isinstance(family_members, dict):
            # If it's a dictionary, convert it to a list of its values
            family_members = list(family_members.values())
        elif isinstance(family_members, str):
            try:
                # Try to parse the string as JSON
                family_members = json.loads(family_members)
                # If the parsed result is a dictionary, convert to list
                if isinstance(family_members, dict):
                    family_members = list(family_members.values())
            except json.JSONDecodeError:
                return jsonify({
                    "success": False,
                    "error": "Invalid family members data format"
                }), 400
        elif not isinstance(family_members, list):
            return jsonify({
                "success": False,
                "error": "Family members must be a list or dictionary"
            }), 400

        if not family_members or not new_family_tree_id:
            return jsonify({
                "success": False,
                "error": "Family members data and family tree ID are required"
            }), 400

        # Process each family member and check if their user profile exists
        updated_family_members = []
        for member in family_members:
            if isinstance(member, dict):
                email = member.get('email')
                if email:
                    # Fetch the user document for the member
                    user_doc = user_profiles_ref.document(email).get()

                        # Add userProfileExists flag to the member
                    member['userProfileExists'] = user_doc.exists
                        
                        # Update the family tree ID if user exists
                    if user_doc.exists:
                        user_profiles_ref.document(email).set({
                            'familyTreeId': new_family_tree_id,
                            'updatedAt': datetime.now().isoformat()
                        }, merge=True)
                    else:
                        logger.warning(f"User with email {email} not found. Skipping update.")
                   
                        member['userProfileExists'] = False
                    
                    updated_family_members.append(member)

        # If self_email is provided, update the family tree ID for the self user
        if self_email:
            user_profiles_ref.document(self_email).set({
                'familyTreeId': new_family_tree_id,
                'updatedAt': datetime.now().isoformat()
            }, merge=True)

        # If father_email is provided, update the family tree ID for the father
        if father_email:
            user_profiles_ref.document(father_email).set({
                'familyTreeId': new_family_tree_id,
                'updatedAt': datetime.now().isoformat()
            }, merge=True)

        return jsonify({
            "success": True,
            "message": "Family tree IDs updated successfully for all members",
            "updatedFamilyMembers": updated_family_members
        })

    except Exception as e:
        logger.error(f"Error updating family tree members: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
        


        

import json
@app.route('/api/family-tree/add-spouse', methods=['POST'])
def add_spouse_details():
    """
    API endpoint to add spouse details to family trees.
    Handles cases where wife and/or husband may or may not have family trees.
    Creates new family trees as needed and updates user profiles.
    Also adds mini-trees of each spouse's family to the other's family tree as relatives.
    """
    try:
        # Extract data from the request
        data = request.json
        print("Received data:", data)

        # Extract fields from request
        wife_family_tree_id = data["wifeFamilyTreeId"]
        wife_email = data["wifeEmail"]
        wife_node_id = data['wifeNodeId']
        husband_family_tree_id = data['husbandFamilyTreeId']
        husband_email = data['husbandEmail']
        husband_node_id = data['husbandMemberId']
        
        # Call the add_spouse_relationship function
        result = add_spouse_relationship(
            family_tree_ref=family_tree_ref,
            user_profiles_ref=user_profiles_ref,
            wife_family_tree_id=wife_family_tree_id,
            wife_email=wife_email,
            wife_node_id=wife_node_id,
            husband_family_tree_id=husband_family_tree_id,
            husband_email=husband_email,
            husband_node_id=husband_node_id
        )
        
        # Check if the result contains an error status code
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], int):
            return jsonify(result[0]), result[1]
            
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error adding spouse details: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
        
        
# @app.route('/api/family-tree/add-relatives', methods=['POST'])
# def add_relatives():
#     """
#     API endpoint to add relatives to a specific node in a family tree.
#     Takes a family tree ID, node ID, and relatives tree structure.
#     Updates the family tree by adding the relatives to the specified node.
#     """
#     try:
#         # Extract data from the request
#         data = request.json
#         print("Received data:", data)  # Log incoming data for debugging

#         # Extract fields from request
#         family_tree_id = data.get('familyTreeId')
#         node_id = data.get('nodeId')
#         relatives_tree = data.get('relativesTree')

#         # Validate required fields
#         if not family_tree_id or not node_id or not relatives_tree:
#             print("Error: Missing required fields")
#             return jsonify({
#                 "success": False,
#                 "message": "Missing required fields. Please provide familyTreeId, nodeId, and relativesTree"
#             }), 400

#         # Log received fields
#         print(f"Received request to add relatives: "
#               f"Family Tree ID: {family_tree_id}, "
#               f"Node ID: {node_id}, "
#               f"Relatives count: {len(relatives_tree)}")

#         # Validate family tree exists
#         family_tree_doc = family_tree_ref.document(family_tree_id).get()
#         if not family_tree_doc.exists:
#             print(f"Error: Family tree not found: {family_tree_id}")
#             return jsonify({
#                 "success": False,
#                 "message": f"Family tree not found: {family_tree_id}"
#             }), 404
        
#         family_tree = family_tree_doc.to_dict()
        
#         # Debug: Print structure of family tree
#         print(f"Family tree structure: {family_tree.keys()}")
        
#         # Handle both possible data structures - either directly in familyMembers or as a list
#         family_members = family_tree.get('familyMembers', {})
        
#         # If family_members is a list, convert to dictionary with id as key
#         if isinstance(family_members, list):
#             family_members_dict = {member.get('id'): member for member in family_members}
#             print(f"Converted list to dict. Available IDs: {list(family_members_dict.keys())}")
#             family_members = family_members_dict
        
#         # Debug: Print available node IDs
#         print(f"Available node IDs: {list(family_members.keys())}")
        
#         # Validate node exists in the family tree
#         if node_id not in family_members:
#             print(f"Error: Node ID {node_id} not found in family tree. Available IDs: {list(family_members.keys())}")
#             return jsonify({
#                 "success": False,
#                 "message": f"Node ID {node_id} not found in the specified family tree",
#                 "availableIds": list(family_members.keys())
#             }), 404

#         # Get or initialize the relatives section
#         relatives = family_tree.get('relatives', {})
        
#         # Update or create relatives entry for the specified node
#         relatives[node_id] = relatives_tree
        
#         # Update the family tree document
#         family_tree_ref.document(family_tree_id).set({
#             "relatives": relatives
#         }, merge=True)
        
#         print(f"Successfully added relatives to node {node_id} in family tree {family_tree_id}")
        
#         # Return success response
#         return jsonify({
#             "success": True,
#             "message": f"Relatives added successfully to node {node_id}",
#             "familyTreeId": family_tree_id,
#             "nodeId": node_id,
#             "relativesCount": len(relatives_tree)
#         })

#     except Exception as e:
#         logger.error(f"Error adding relatives: {e}")
#         # Add more detailed error information
       
        
#         return jsonify({
#             "success": False,
#             "error": str(e),
            
#         }), 500
        
        
from generate_relatives_tree import generate_relatives_tree
from flask import jsonify, request

@app.route('/generate-relatives-tree', methods=['POST'])
def generate_relatives_tree_route():
    data = request.get_json()
    relatives_data = data.get('relativesData', {})
    
    if not relatives_data:
        return jsonify({'error': 'No relatives data provided'}), 400

    try:
        img_base64 = generate_relatives_tree(relatives_data)
        # Check if the result is an error message (string starting with "Error:")
        if isinstance(img_base64, str) and img_base64.startswith("Error:"):
            return jsonify({'error': img_base64}), 500
        return jsonify({'image': img_base64})
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return jsonify({'error': f"{str(e)}\nDetails: {error_details}"}), 500
    
    
    
from flask import request, jsonify
from firebase_admin import firestore
import logging



@app.route('/api/friends-tree/add-friend', methods=['POST'])
def add_friend():
    """
    API endpoint to add a friend node to a user's friends tree and vice versa.
    Takes a user email and a friend node with id, name, category, email, and profileImage.
    Updates both the user's and friend's friends tree with mutual friendship.
    """
    try:
        # Extract data from the request
        data = request.json
        print("Received data:", data)  # Log incoming data for debugging

        # Extract fields from request
        user_email = data.get('userEmail')
        friend_node = data.get('friendNode')

        # Validate required fields
        if not user_email or not friend_node:
            print("Error: Missing required fields")
            return jsonify({
                "success": False,
                "message": "Missing required fields. Please provide userEmail and friendNode"
            }), 400

        # Validate friend node structure
        required_fields = ['id', 'name', 'category', 'email', 'profileImage']
        if not all(field in friend_node for field in required_fields):
            print("Error: Invalid friend node structure")
            return jsonify({
                "success": False,
                "message": "Friend node must contain id, name, category, email, and profileImage"
            }), 400

        # Extract friend's email
        friend_email = friend_node.get('email')
        if not friend_email:
            print("Error: Friend's email is missing in friendNode")
            return jsonify({
                "success": False,
                "message": "Friend's email is required in friendNode"
            }), 400

        # Log received fields
        print(f"Received request to add friend: User Email: {user_email}, Friend Node: {friend_node}")

        # Start a transaction to ensure mutual updates
        @firestore.transactional
        def update_friends(transaction):
            # FIRST: Do ALL reads
            # Get user profile document
            user_profile_ref = db.collection('user_profiles').document(user_email)
            user_profile = user_profile_ref.get(transaction=transaction)

            if not user_profile.exists:
                print(f"Error: User profile not found for email: {user_email}")
                raise ValueError(f"User profile not found for email: {user_email}")

            # Get friend's profile document
            friend_profile_ref = db.collection('user_profiles').document(friend_email)
            friend_profile = friend_profile_ref.get(transaction=transaction)

            if not friend_profile.exists:
                print(f"Error: Friend profile not found for email: {friend_email}")
                raise ValueError(f"Friend profile not found for email: {friend_email}")

            # Get user's friends data
            user_friends_data_ref = user_profile_ref.collection('friendsData').document('friendstree')
            user_friends_data = user_friends_data_ref.get(transaction=transaction)
            
            user_data_dict = user_friends_data.to_dict() if user_friends_data.exists else {}
            user_friends_list = user_data_dict.get('friends', [])

            # Get friend's friends data
            friend_friends_data_ref = friend_profile_ref.collection('friendsData').document('friendstree')
            friend_friends_data = friend_friends_data_ref.get(transaction=transaction)
            
            friend_data_dict = friend_friends_data.to_dict() if friend_friends_data.exists else {}
            friend_friends_list = friend_data_dict.get('friends', [])

            # SECOND: Process user profile data
            user_profile_data = user_profile.to_dict()
            
            # Merge first and last name
            first_name = user_profile_data.get('firstName', '')
            last_name = user_profile_data.get('lastName', '')
            full_name = f"{first_name} {last_name}".strip()
            if not full_name:
                full_name = 'Unknown User'
                
            # Get profile image
            profile_image = None
            profile_image_id = user_profile_data.get('currentProfileImageId')
            
            if profile_image_id:
                # Get the profile image from the profileImages collection
                profile_image_ref = user_profile_ref.collection('profileImages').document(profile_image_id)
                profile_image_doc = profile_image_ref.get(transaction=transaction)
                print(profile_image_id)
                print(profile_image_doc)
                
                if profile_image_doc.exists:
                    profile_image_data = profile_image_doc.to_dict()
                    print(profile_image_data)
                    profile_image = profile_image_data.get('imageData')  # Assuming the image URL is stored in a 'url' field
            
            # THIRD: Generate a unique ID for the reciprocal node
            # Find the maximum ID currently in use and add 1
            max_id = 0
            for f in friend_friends_list:
                try:
                    id_val = int(f.get('id', 0))
                    if id_val > max_id:
                        max_id = id_val
                except ValueError:
                    # Skip non-integer IDs
                    pass
            
            new_id = str(max_id + 1)
            
            # Create a reciprocal friend node for the user
            user_node = {
                'id': new_id,  # Generate a unique ID
                'name': full_name,
                'category': friend_node.get('category'),
                'email': user_email,
                'profileImage': profile_image
            }
            
            print("user node ", user_node)

            # Add friend to user's friends list if not already there
            # Check by email to ensure uniqueness
            if not any(f.get('email') == friend_email for f in user_friends_list):
                user_friends_list.append(friend_node)
                transaction.set(user_friends_data_ref, {'friends': user_friends_list}, merge=True)
                print(f"Added friend {friend_email} to user {user_email}'s friend list")
            else:
                print(f"Friend {friend_email} already exists in user {user_email}'s friend list")

            # Add user to friend's friends list if not already there
            if not any(f.get('email') == user_email for f in friend_friends_list):
                friend_friends_list.append(user_node)
                transaction.set(friend_friends_data_ref, {'friends': friend_friends_list}, merge=True)
                print(f"Added user {user_email} to friend {friend_email}'s friend list")
            else:
                print(f"User {user_email} already exists in friend {friend_email}'s friend list")

            print(f"Successfully added mutual friendship: {user_email} ↔ {friend_email}")

        # Execute the transaction
        transaction = db.transaction()
        update_friends(transaction)

        # Return success response
        return jsonify({
            "success": True,
            "message": f"Mutual friendship established between {user_email} and {friend_email}",
            "userEmail": user_email,
            "friendEmail": friend_email,
        })

    except Exception as e:
        print(f"Error adding mutual friendship: {e}")
        logger.error(f"Error adding mutual friendship: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/friends-tree/get-friends', methods=['GET'])
def get_friends():
    """
    API endpoint to retrieve a user's friends tree based on email.
    Returns the list of friends for the specified user.
    """
    try:
        # Get user email from query parameters
       
        user_email = request.args.get('email')

        # Validate user email
        if not user_email:
            return jsonify({
                "success": False,
                "message": "Missing required parameter: email"
            }), 400

        # Log request
        print(f"Received request to get friends for user: {user_email}")

        # Get user profile document
        user_profile_ref = db.collection('user_profiles').document(user_email)
        user_profile = user_profile_ref.get()

        if not user_profile.exists:
            print(f"Error: User profile not found for email: {user_email}")
            return jsonify({
                "success": False,
                "message": f"User profile not found for email: {user_email}"
            }), 404

        # Get user's friends data
        friends_data_ref = user_profile_ref.collection('friendsData').document('friendstree')
        friends_data = friends_data_ref.get()

        # If friends data exists, return it, otherwise return empty list
        if friends_data.exists:
            friends_list = friends_data.to_dict().get('friends', [])
        else:
            friends_list = []

        # Return friends list
        return jsonify({
            "success": True,
            "userEmail": user_email,
            "friends": friends_list,
            "totalFriends": len(friends_list)
        })

    except Exception as e:
        logger.error(f"Error retrieving friends data: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
        

@app.route('/api/friends-tree/generate-visualization', methods=['GET', 'POST'])
def generate_friends_tree_visualization():
    """
    API endpoint to generate a visual representation of a user's friends tree.
    Takes a user email and returns a base64 encoded image of the friends tree.
    """
    try:
        # Get email from either query parameters (GET) or JSON body (POST)
        if request.method == 'GET':
            user_email = request.args.get('email')
        else:  # POST
            data = request.json
            user_email = data.get('email')

        # Validate user email
        if not user_email:
            return jsonify({
                "success": False,
                "message": "Missing required parameter: email"
            }), 400

        # Log request
        print(f"Received request to generate friends tree visualization for user: {user_email}")

        # Get user profile document
        user_profile_ref = db.collection('user_profiles').document(user_email)
        user_profile = user_profile_ref.get()

        if not user_profile.exists:
            print(f"Error: User profile not found for email: {user_email}")
            return jsonify({
                "success": False,
                "message": f"User profile not found for email: {user_email}"
            }), 404

        # Get user's basic info
        user_data = user_profile.to_dict()
        user_name = f"{user_data.get('firstName', '')} {user_data.get('lastName', '')}"
        
        # Get user's profile image
        user_profile_image = None
        current_profile_image_id = user_data.get('currentProfileImageId')
        if current_profile_image_id:
            # Get the profile image from the profileImages collection
            profile_image_ref = user_profile_ref.collection('profileImages').document(current_profile_image_id)
            profile_image_doc = profile_image_ref.get()
            
            if profile_image_doc.exists:
                profile_image_data = profile_image_doc.to_dict()
                print(profile_image_data)
                user_profile_image = profile_image_data.get('imageData')  # Assuming base64 data is stored in 'data' field

        # Get user's friends data
        friends_data_ref = user_profile_ref.collection('friendsData').document('friendstree')
        friends_data = friends_data_ref.get()

        # If friends data exists, use it, otherwise return empty list
        if friends_data.exists:
            friends_list = friends_data.to_dict().get('friends', [])
        else:
            friends_list = []

        # Generate friends tree visualization
        image_base64 = generate_friends_tree(user_email, user_name, user_profile_image, friends_list)

        # Return the image data
        return jsonify({
            "success": True,
            "userEmail": user_email,
            "image": image_base64
        })

    except Exception as e:
        logger.error(f"Error generating friends tree visualization: {e}")
        import traceback
        error_details = traceback.format_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "details": error_details
        }), 500

def generate_friends_tree(user_email, user_name, user_profile_image, friends_list):
    """
    Generate a tree visualization for a user's friends using the same theme as family tree
    
    Args:
        user_email (str): Email of the user
        user_name (str): Name of the user
        user_profile_image (str or bytes): Base64 encoded profile image data or bytes
        friends_list (list): List of friend nodes
        
    Returns:
        str: Base64 encoded image of the friends tree
    """
    import tempfile
    import os
    import base64
    from graphviz import Digraph
    from PIL import Image, ImageDraw, ImageOps
    import io

    # Create temp directory for profile images
    temp_dir = tempfile.mkdtemp(prefix='friends_tree_')
    
    # Create a Digraph object with enhanced background (same as family tree)
    dot = Digraph(
        comment='Friends Tree',
        format='png',
        engine='dot',
        graph_attr={
            'rankdir': 'TB',  # Top to bottom direction
            'splines': 'polyline',  # Use polyline for natural connections
            'bgcolor': '#FFFFFF',  # Pure white background
            'nodesep': '1.4',  # Increased node separation
            'ranksep': '2.0',  # Increased rank separation
            'fontname': 'Arial',
            'style': 'rounded',  # Rounded style
            'color': '#000000',  # Black border color
            'penwidth': '2.0',  # Border thickness
        },
        node_attr={
            'shape': 'box',
            'style': 'filled,rounded',
            'fillcolor': 'white',
            'fontcolor': 'black',
            'penwidth': '1.5',
            'fontsize': '22',
            'fontname': 'Arial',
            'height': '1.2',
            'width': '2.8',
            'margin': '0.5'
        },
        edge_attr={
            'color': '#444444',
            'penwidth': '4.0'
        }
    )

    def create_profile_image_node(profile_image_data, node_id):
        """Create a temporary profile image file from base64 data or use default icon."""
        image_path = os.path.join(temp_dir, f'friend_profile_{node_id}.png')
        
        try:
            if profile_image_data:
                # Handle base64 string
                if isinstance(profile_image_data, str):
                    if profile_image_data.startswith('data:image'):
                        # Extract the base64 data
                        base64_data = profile_image_data.split(',')[1]
                        image_data = base64.b64decode(base64_data)
                        
                        # Convert to PIL Image
                        img = Image.open(BytesIO(image_data))
                        img = img.convert('RGBA')
                        # Resize to a reasonable size
                        img = img.resize((100, 100), Image.Resampling.LANCZOS)
                        img.save(image_path, 'PNG')
                        return image_path
                
                # Handle bytes directly
                elif isinstance(profile_image_data, bytes):
                    img = Image.open(BytesIO(profile_image_data))
                    img = img.convert('RGBA')
                    img = img.resize((100, 100), Image.Resampling.LANCZOS)
                    img.save(image_path, 'PNG')
                    return image_path
            
            # Create default profile icon
            img = Image.new('RGBA', (100, 100), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            # Draw a circle for the head
            draw.ellipse([25, 25, 75, 75], fill=(204, 204, 204, 255))
            # Draw a path for the body
            draw.polygon([(50, 70), (30, 100), (70, 100)], fill=(204, 204, 204, 255))
            img.save(image_path, 'PNG')
            return image_path
            
        except Exception as e:
            print(f"Error creating profile image: {e}")
            return None

    # Create center node for the user with special styling
    user_node_id = "user"
    user_image_path = create_profile_image_node(user_profile_image, user_node_id)
    
    # Create a stylized label for the user node
    user_label = f"<<TABLE BORDER='0' CELLBORDER='0' CELLSPACING='0' CELLPADDING='10'>"
    if user_image_path:
        image_path = user_image_path.replace('\\', '/')
        user_label += f"<TR><TD ROWSPAN='2'><IMG SRC='{image_path}' SCALE='TRUE' FIXEDSIZE='TRUE' WIDTH='90' HEIGHT='90'/></TD>"
    else:
        user_label += "<TR><TD ROWSPAN='2'><FONT POINT-SIZE='50'>👤</FONT></TD>"
    
    # Add name with larger font
    user_label += f"<TD ALIGN='LEFT'><FONT POINT-SIZE='35'><B>{user_name}</B></FONT></TD></TR>"
    user_label += f"<TR><TD ALIGN='LEFT'><FONT POINT-SIZE='31'>Myself</FONT></TD></TR>"
    user_label += "</TABLE>>"
    
    # Add user node with special styling
    dot.node(
        user_node_id,
        label=user_label,
        fillcolor='#00a3ee',  # Special blue color for self node
        fontcolor='white',
        style='filled,rounded',
        penwidth='1.5'
    )

    # Group friends by category
    friend_categories = {}
    for friend in friends_list:
        category = friend.get('category', 'Other')
        if category not in friend_categories:
            friend_categories[category] = []
        friend_categories[category].append(friend)

    # Category colors (using a softer palette)
    category_colors = {
        'Family': '#E8F5E9',  # Soft green
        'Close Friends': '#E3F2FD',  # Soft blue
        'Colleagues': '#FFF3E0',  # Soft orange
        'School': '#F3E5F5',  # Soft purple
        'Neighbors': '#FFFDE7',  # Soft yellow
        'Other': '#FAFAFA'  # Light gray
    }

    # Create a central point for better organization
    center_point = "center_point"
    dot.node(center_point, "", shape="point", style="invis")
    dot.edge(user_node_id, center_point, style="invis")

    # For each category, create a subgraph
    for category_index, (category, friends) in enumerate(friend_categories.items()):
        # Create a subgraph for this category
        with dot.subgraph(name=f'cluster_{category}') as c:
            c.attr(
                label=category,
                style='filled,rounded',
                fillcolor=category_colors.get(category, '#FAFAFA'),
                fontname='Arial',
                fontsize='25',
                penwidth='2.0'
            )
            
            # Create a chain of nodes for vertical arrangement
            prev_node_id = None
            
            # Add friend nodes in this category
            for i, friend in enumerate(friends):
                friend_id = f"friend_{category_index}_{i}"
                
                # Create friend profile image
                friend_image_path = create_profile_image_node(friend.get('profileImage'), friend_id)
                
                # Create stylized label for friend node
                friend_label = f"<<TABLE BORDER='0' CELLBORDER='0' CELLSPACING='0' CELLPADDING='10'>"
                if friend_image_path:
                    image_path = friend_image_path.replace('\\', '/')
                    friend_label += f"<TR><TD ROWSPAN='2'><IMG SRC='{image_path}' SCALE='TRUE' FIXEDSIZE='TRUE' WIDTH='90' HEIGHT='90'/></TD>"
                else:
                    friend_label += "<TR><TD ROWSPAN='2'><FONT POINT-SIZE='50'>👤</FONT></TD>"
                
                # Add name and category
                friend_label += f"<TD ALIGN='LEFT'><FONT POINT-SIZE='35'><B>{friend.get('name', 'Unknown')}</B></FONT></TD></TR>"
                friend_label += f"<TR><TD ALIGN='LEFT'><FONT POINT-SIZE='31'>{category}</FONT></TD></TR>"
                friend_label += "</TABLE>>"
                
                # Add friend node
                c.node(
                    friend_id,
                    label=friend_label,
                    fillcolor='white',
                    style='filled,rounded',
                    penwidth='1.5'
                )
                
                # Connect to previous node in the category for vertical arrangement
                if prev_node_id:
                    # Add invisible edge to force vertical arrangement
                    c.edge(prev_node_id, friend_id, style="invis", constraint='true')
                elif i == 0:
                    # Connect first node of category to center point
                    dot.edge(center_point, friend_id, 
                        color='#444444',
                        penwidth='4.0',
                        arrowhead='none'
                    )
                
                # Update previous node ID for next iteration
                prev_node_id = friend_id
                
            # Force all nodes in this category to be arranged vertically
            c.attr(rankdir='TB')  # Top to bottom arrangement within category
            if len(friends) > 1:
                c.attr(rank='same')  # Ensure nodes in same category stay together

    # Render the graph to PNG
    temp_dir = tempfile.gettempdir()
    output_path = os.path.abspath(os.path.join(temp_dir, 'friends_tree'))
    
    try:
        # Create the output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Render the graph
        dot.render(output_path, format='png', cleanup=True)
        
        # Read the image and encode it to base64
        with open(f"{output_path}.png", 'rb') as f:
            img_data = f.read()
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        
        # Clean up temporary files
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.startswith('friend_profile_'):
                    try:
                        os.remove(os.path.join(root, file))
                    except:
                        pass
        
        return img_base64
        
    except Exception as e:
        print(f"Error generating friends tree: {e}")
        return None

@app.route('/api/get-connections', methods=['GET'])
def get_connections():
    
    """
    Get all connections (family, relatives, friends) for a user.
    
    Query Parameters:
        email (str): User's email address
        
    Returns:
        JSON response containing family, relatives, and friends
    """
    try:
        print("get_connections--")
        email = request.args.get('email')
        print(email)        
        if not email:
            return jsonify({
                'success': False,
                'message': 'Email is required'
            }), 400
        
        connections = get_user_connections(email)
        
        return jsonify({
            'success': True,
            'data': connections
        })
        
    except Exception as e:
        print("error")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 
        
from family_tree_relations import get_extended_family
@app.route('/api/get-member-relatives-tree', methods=['POST'])
def get_member_relatives_tree():
    """
    API endpoint to get a relatives tree for a specific member in a family tree,
    with relationship labels showing how each person is related to the specified member.
    
    Request Body (JSON):
        family_tree_id (str): ID of the family tree
        node_id (str): ID of the node in the family tree
        email (str): Email of the user making the request
        
    Returns:
        JSON response containing the relatives tree with relationship labels
    """
    try:
        # Get data from request body
        print("hi")
        data = request.get_json()
        print(data)
        
        # Extract parameters
        family_tree_id = data['family_tree_id']
        node_id = data['node_id']
        email = data['email']
        
        print(family_tree_id)
        print(node_id)
        print(email) 
        
        # Validate required parameters
        if not all([family_tree_id, node_id]):
            return jsonify({
                'success': False,  
                'message': 'Missing required parameters: family_tree_id, node_id, and email are required'
            }), 400
        print("hi1")
        # Validate user has permission to access this family tree
        # user_doc = user_profiles_ref.document(email).get()
        # if not user_doc.exists:
        #     return jsonify({
        #         'success': False,
        #         'message': 'User not found'
        #     }), 404
        # print("hi2")    
        # user_data = user_doc.to_dict()
        user_family_tree_id = family_tree_id  
        
        # Check if user has access to the requested family tree
        # if user_family_tree_id != family_tree_id:
        #     return jsonify({
        #         'success': False,
        #         'message': 'User does not have permission to access this family tree'
        #     }), 403
        
        # Get the relatives tree with relationship labels
        relatives_tree = get_extended_family(family_tree_id, node_id, db)
        
        # Log the relationships for debugging
        logger.info(f"Retrieved {len(relatives_tree)} relatives for node {node_id} in tree {family_tree_id}")
        relation_summary = [f"{node.get('name')}: {node.get('relation')}" for node in relatives_tree]
        logger.info(f"Relationships: {relation_summary}")
        print("hi3")
        return jsonify({
            'success': True,
            'data': {
                'relatives_tree': relatives_tree,
                'centered_node_id': node_id
            }
        })
        
    except Exception as e:
        logger.error(f"Error in get-member-relatives-tree endpoint: {e}")
        import traceback
        error_details = traceback.format_exc()
        return jsonify({
            'success': False,
            'message': str(e),
            'details': error_details
        }), 500

@app.route('/api/users/get-names', methods=['POST'])
def get_user_names():
    """
    API endpoint to get full names of users from a list of email addresses.
    Takes a list of emails in the request body and returns the full names for each user.
    """
    try:
        # Extract data from the request
        data = request.json
        print("Received data:", data)  # Log incoming data for debugging

        # Extract emails from request
        emails = data.get('emails', [])

        if not emails or not isinstance(emails, list):
            return jsonify({
                "success": False,
                "message": "Please provide a valid list of emails"
            }), 400

        # Log the number of emails received
        print(f"Received request to get names for {len(emails)} emails")

        # Initialize results dictionary
        user_names = {}

        # Get users data from Firestore
        for email in emails:
            if not email or not isinstance(email, str):
                user_names[email] = None
                continue

            try:
                # Get user document
                user_doc = user_profiles_ref.document(email).get()
                
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    first_name = user_data.get('firstName', '')
                    last_name = user_data.get('lastName', '')
                    full_name = f"{first_name} {last_name}".strip()
                    user_profile_exists = True
                    
                    # If name is empty, use email as fallback
                    if not full_name:
                        full_name = 'Unknown User'
                else:
                    full_name = 'User Not Found'
                    user_profile_exists = False
                
                # Add to results
                user_names[email] = {
                    'fullName': full_name,
                    'userProfileExists': user_profile_exists
                }
                
            except Exception as e:
                print(f"Error processing email {email}: {e}")
                user_names[email] = {
                    'fullName': 'Error',
                    'userProfileExists': False,
                    'error': str(e)
                }

        # Return results
        return jsonify({
            "success": True,
            "userNames": user_names,
            "count": len(user_names)
        })

    except Exception as e:
        print(f"Error getting user names: {e}")
        logger.error(f"Error getting user names: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Invitation Management API Endpoints
@app.route('/api/invitations/send', methods=['POST'])
def send_invitation_api():
    """
    API endpoint to send an invitation from one user to another.
    
    Request body should include:
    - senderEmail: Email of the sending user
    - recipientEmail: Email of the receiving user
    - invitationType: Type of invitation (friend, family, relative, etc.)
    - additionalData: Any additional data needed for the invitation
    
    Returns JSON with success status and invitation details or error message.
    """
    try:
        # Extract data from request
        data = request.json
        sender_email = data.get('senderEmail')
        recipient_email = data.get('recipientEmail')
        invitation_type = data.get('invitationType')
        additional_data = data.get('additionalData', {})
        
        print("=========== the data was ===============\n",data)
        
        # Validate required fields
        if not all([sender_email, recipient_email, invitation_type]):
            return jsonify({
                "success": False,
                "message": "Missing required fields: senderEmail, recipientEmail, and invitationType are required"
            }), 400
        
        # Log the incoming data
        logger.info(f"Received invitation request - Type: {invitation_type}")
        logger.info(f"Additional data: {additional_data}")
        
        # Get sender's profile information for the notification
        sender_doc = user_profiles_ref.document(sender_email).get()
        sender_name = sender_email  # Default to email if name not found
        sender_avatar = None
        
        if sender_doc.exists:
            sender_data = sender_doc.to_dict()
            first_name = sender_data.get('firstName', '')
            last_name = sender_data.get('lastName', '')
            sender_name = f"{first_name} {last_name}".strip() or sender_email
            sender_avatar = sender_data.get('profileImage')
        
        # Send the invitation with the additional data directly
        success, result = send_invitation(
            sender_email=sender_email,
            recipient_email=recipient_email,
            invitation_type=invitation_type,
            data=additional_data,  # Pass additional_data directly
            db=db,
            user_profiles_ref=user_profiles_ref
        )
        
        if success:
            # Create notification for the recipient
            notification_data = {
                "userEmail": recipient_email,
                "type": "invitation",
                "data": {
                    "invitationType": invitation_type,
                    "senderId": sender_email,
                    "senderName": sender_name,  # Now sender_name is properly defined
                    "senderAvatar": sender_avatar,
                    "message": f"{sender_name} sent you a {invitation_type} invitation",
                    "status": "pending",
                    "relationshipType": additional_data.get('relationshipType'),
                    "invitationId": result.get('invitationId')  # Include the invitation ID
                },
                "priority": "high"  # Set priority as high for invitation notifications
            }
            
            try:
                # Create notification in Firebase
                user_notifications_ref = db.collection('user_profiles').document(recipient_email).collection('notifications')
                notification_id = str(uuid.uuid4())
                
                notification = {
                    '_id': notification_id,
                    'userId': recipient_email,
                    'type': "invitation",
                    'data': notification_data['data'],
                    'createdAt': datetime.now().isoformat(),
                    'updatedAt': datetime.now().isoformat(),
                    'isRead': False,
                    'isArchived': False,
                    'priority': "high"
                }
                
                user_notifications_ref.document(notification_id).set(notification)
                
                # Send real-time notification
                try:
                    notify_user(recipient_email, {
                        'type': 'new_notification',
                        'notification': notification
                    })
                except Exception as socket_error:
                    logger.warning(f"Failed to send real-time notification: {str(socket_error)}")
                
            except Exception as notif_error:
                logger.error(f"Failed to create notification: {str(notif_error)}")
                # Continue execution even if notification creation fails
            
            logger.info(f"Successfully sent invitation to {recipient_email}")
            return jsonify({
                "success": True,
                "message": f"Invitation sent successfully to {recipient_email}",
                "data": result
            })
        else:
            logger.error(f"Failed to send invitation: {result}")
            return jsonify({
                "success": False,
                "message": f"Failed to send invitation: {result}"
            }), 500
    
    except Exception as e:
        logger.error(f"Error sending invitation: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/api/invitations/get', methods=['GET'])
def get_invitations_api():
    """
    API endpoint to get invitations for a user.
    
    Query parameters:
    - email: Email of the user
    - status (optional): Filter by status (pending, accepted, rejected)
    - direction (optional): Filter by direction (sent, received)
    
    Returns JSON with success status and invitations or error message.
    """
    try:
        # Extract query parameters
        email = request.args.get('email')
        status = request.args.get('status')
        direction = request.args.get('direction')
        
        # Validate required parameters
        if not email:
            return jsonify({
                "success": False,
                "message": "Email parameter is required"
            }), 400
        
        # Get invitations
        success, result = get_invitations(
            email=email,
            status=status,
            direction=direction,
            db=db
        )
        
        if success:
            return jsonify({
                "success": True,
                "data": result
            })
        else:
            return jsonify({
                "success": False,
                "message": f"Failed to get invitations: {result}"
            }), 500
    
    except Exception as e:
        logger.error(f"Error getting invitations: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/api/invitations/respond', methods=['POST'])
def respond_to_invitation():
    """
    API endpoint to respond to an invitation (accept or reject).
    
    Request body should include:
    - invitationId: ID of the invitation
    - recipientEmail: Email of the recipient (the responder)
    - status: New status (accepted, rejected)
    
    Returns JSON with success status and updated invitation or error message.
    """
    try:
        # Extract data from request
        data = request.json
        invitation_id = data.get('invitationId')
        recipient_email = data.get('recipientEmail')
        status = data.get('status')
        
        # Validate required fields
        if not all([invitation_id, recipient_email, status]):
            return jsonify({
                "success": False,
                "message": "Missing required fields: invitationId, recipientEmail, and status are required"
            }), 400
        
        # Validate status
        if status not in [STATUS_ACCEPTED, STATUS_REJECTED]:
            return jsonify({
                "success": False,
                "message": f"Invalid status: {status}. Must be 'accepted' or 'rejected'"
            }), 400
        
        # Update the invitation status
        success, result = update_invitation_status(
            invitation_id=invitation_id,
            recipient_email=recipient_email,
            status=status,
            db=db,
            # Custom handler will be selected internally based on invitation type
            custom_handler=None
        )
        
        if success:
            # If accepted, check if we need to perform additional actions
            if status == STATUS_ACCEPTED:
                invitation_type = result.get('updatedInvitation', {}).get('type')
                
                # Get sender information for notification
                sender_email = result.get('updatedInvitation', {}).get('senderEmail')
                
                # Get recipient profile for a better notification
                recipient_doc = user_profiles_ref.document(recipient_email).get()
                recipient_name = recipient_email
                
                if recipient_doc.exists:
                    recipient_data = recipient_doc.to_dict()
                    first_name = recipient_data.get('firstName', '')
                    last_name = recipient_data.get('lastName', '')
                    recipient_name = f"{first_name} {last_name}".strip() or recipient_email
                
                # Prepare detailed notification data for sender
                notification_data = {
                    'invitationId': invitation_id,
                    'recipientEmail': recipient_email,
                    'recipientName': recipient_name,
                    'status': status,
                    'type': invitation_type,
                    'timestamp': datetime.now().isoformat(),
                    'message': f"{recipient_name} has accepted your {invitation_type} invitation"
                }
                
                # Send real-time notification to sender
                notify_user(sender_email, {
                    'type': 'invitation_accepted',
                    'data': notification_data
                })
                logger.info(f"Sent real-time acceptance notification to {sender_email}")
                
                # Handle invitation type-specific actions
                if invitation_type in invitation_acceptance_handlers:
                    try:
                        handler = invitation_acceptance_handlers[invitation_type]
                        handler_result = handler(result.get('updatedInvitation'), db)
                        result['handlerResult'] = handler_result
                        
                        # Add additional handler result to notification
                        notification_data['handlerResult'] = handler_result
                        # Send a follow-up notification with the handler result
                        notify_user(sender_email, {
                            'type': 'invitation_processed',
                            'data': notification_data
                        })
                        
                        # Send friend connection notification for friend invitations
                        if invitation_type == TYPE_FRIEND and handler_result.get('success'):
                            from socket_manager import notify_friend_connection
                            notify_friend_connection(
                                sender_email=sender_email,
                                recipient_email=recipient_email,
                                categories_info=handler_result
                            )
                            logger.info(f"Friend connection notification sent for {sender_email} and {recipient_email}")
                            
                    except Exception as handler_error:
                        logger.error(f"Error in custom handler for {invitation_type}: {handler_error}")
                        result['handlerError'] = str(handler_error)
            elif status == STATUS_REJECTED:
                # Get sender information for notification
                sender_email = result.get('updatedInvitation', {}).get('senderEmail')
                invitation_type = result.get('updatedInvitation', {}).get('type')
                
                # Get recipient profile for a better notification
                recipient_doc = user_profiles_ref.document(recipient_email).get()
                recipient_name = recipient_email
                
                if recipient_doc.exists:
                    recipient_data = recipient_doc.to_dict()
                    first_name = recipient_data.get('firstName', '')
                    last_name = recipient_data.get('lastName', '')
                    recipient_name = f"{first_name} {last_name}".strip() or recipient_email
                
                # Prepare notification data for rejection
                notification_data = {
                    'invitationId': invitation_id,
                    'recipientEmail': recipient_email,
                    'recipientName': recipient_name,
                    'status': status,
                    'type': invitation_type,
                    'timestamp': datetime.now().isoformat(),
                    'message': f"{recipient_name} has declined your {invitation_type} invitation"
                }
                
                # Send real-time notification to sender
                notify_user(sender_email, {
                    'type': 'invitation_rejected',
                    'data': notification_data
                })
                logger.info(f"Sent real-time rejection notification to {sender_email}")
            
            return jsonify({
                "success": True,
                "message": f"Invitation {status}",
                "data": result
            })
        else:
            return jsonify({
                "success": False,
                "message": f"Failed to update invitation: {result}"
            }), 500
    
    except Exception as e:
        logger.error(f"Error responding to invitation: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/api/invitations/notify', methods=['POST'])
def notify_about_invitation():
    """
    API endpoint to send a notification about an invitation to a specific user.
    
    Request body should include:
    - email: Email of the user to notify
    - eventType: Type of notification event
    - data: Notification data
    
    Returns JSON with success status or error message.
    """
    try:
        # Extract data from request
        data = request.json
        email = data.get('email')
        event_type = data.get('eventType')
        notification_data = data.get('data', {})
        
        # Validate required fields
        if not all([email, event_type]):
            return jsonify({
                "success": False,
                "message": "Missing required fields: email and eventType are required"
            }), 400
        
        # Send notification
        success = notify_user(email, {
            'type': event_type,
            'data': notification_data
        })
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Notification sent to {email}"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Failed to send notification"
            }), 500
    
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/api/family-tree/add-child', methods=['POST'])
def add_child_api():
    """
    API endpoint to add a child to a parent in the family tree.
    Takes child node data, father's node ID, and family tree ID.
    Adds the child to the family tree with the father as the parent.
    """
    try:
        data = request.json
        child_data = data.get('childNode')
        father_node_id = data.get('fatherNodeId')
        family_tree_id = data.get('familyTreeId')

        if not child_data or not father_node_id or not family_tree_id:
            return jsonify({
                "success": False,
                "error": "Child data, father node ID, and family tree ID are required"
            }), 400

        logger.info(f"Received request to add child to father ID {father_node_id} in family tree {family_tree_id}")

        # Call the function from family_child_manager.py
        family_tree_ref = db.collection('family_tree')
        result = add_child_to_family_tree(
            family_tree_ref,
            user_profiles_ref,
            family_tree_id,
            father_node_id,
            child_data
        )
        
        if not result.get("success"):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in add_child_api: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/family-tree/create-with-father-child', methods=['POST'])
def create_family_tree_with_child_api():
    """
    API endpoint to create a new family tree with a father and child.
    Takes father email and child data.
    Fetches father's details from their profile, 
    creates a new family tree, adds both father and child to it,
    and updates the family tree ID in the father's profile.
    """
    try:
        data = request.json
        father_email = data.get('fatherEmail')
        child_data = data.get('childNode')

        if not father_email or not child_data:
            return jsonify({
                "success": False,
                "error": "Father email and child data are required"
            }), 400

        logger.info(f"Received request to create family tree with father {father_email} and child")

        # Call the function from family_child_manager.py
        family_tree_ref = db.collection('family_tree')
        result = create_family_tree_with_father_child(
            family_tree_ref,
            user_profiles_ref,
            father_email,
            child_data
        )
        
        if not result.get("success"):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in create_family_tree_with_child_api: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/family-tree/add-child-with-subtree', methods=['POST'])
def add_child_with_subtree_api():
    """
    API endpoint to add a child to a father's family tree, with complex merging.
    
    Scenarios:
    1. If child has no family tree: Creates a node for the child in father's tree
    2. If child has own family tree: Merges the child's entire subtree into father's tree
       including spouse, children, grandchildren, and all relatives
    
    Takes father's family tree ID, father's node ID, child's email, and child's birth order.
    """
    try:
        data = request.json
        father_family_tree_id = data.get('fatherFamilyTreeId')
        father_node_id = data.get('fatherNodeId')
        child_email = data.get('childEmail')
        child_birth_order = data.get('childBirthOrder', 1)  # Default to 1 if not provided

        if not father_family_tree_id or not father_node_id or not child_email:
            return jsonify({
                "success": False,
                "error": "Father's family tree ID, father's node ID, and child's email are required"
            }), 400

        logger.info(f"Received request to add child {child_email} to father in family tree {father_family_tree_id}")

        # Call the function from family_child_manager.py
        family_tree_ref = db.collection('family_tree')
        result = add_child_with_subtree(
            family_tree_ref,
            user_profiles_ref,
            father_family_tree_id,
            father_node_id,
            child_email,
            child_birth_order
        )
        
        if not result.get("success"):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in add_child_with_subtree_api: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/family-tree/add-parents', methods=['POST'])
def add_parents_api():
    """
    API endpoint to add parents (father and mother) to a child's family tree.
    
    Takes father node data, mother node data, child's family tree ID, and child's node ID.
    Adds the parents to the child's family tree and updates the child's parentId.
    
    Both father and mother are optional, but at least one must be provided.
    """
    try:
        data = request.json
        father_node = data.get('fatherNode')
        mother_node = data.get('motherNode')
        child_family_tree_id = data.get('familyTreeId')
        child_node_id = data.get('childNodeId')

        # Validate required fields
        if not child_family_tree_id or not child_node_id:
            return jsonify({
                "success": False,
                "error": "Child's family tree ID and child node ID are required"
            }), 400
            
        # Validate that at least one parent is provided
        if not father_node and not mother_node:
            return jsonify({
                "success": False,
                "error": "At least one parent (father or mother) data must be provided"
            }), 400

        logger.info(f"Received request to add parents to child ID {child_node_id} in family tree {child_family_tree_id}")

        # Call the function from family_parent_manager.py
        family_tree_ref = db.collection('family_tree')
        result = add_parents_to_family_tree(
            family_tree_ref,
            user_profiles_ref,
            child_family_tree_id,
            child_node_id,
            father_node,
            mother_node
        )
        
        if not result.get("success"):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in add_parents_api: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/family-tree/create-with-parents', methods=['POST'])
def create_family_tree_with_parents_api():
    """
    API endpoint to create a new family tree for a child and add parents.
    
    Takes child's email, father node data (optional), and mother node data (optional).
    Creates a new family tree with the child and parents, sets up the relationships,
    and updates the family tree IDs in their profiles.
    
    Both father and mother are optional, but at least one must be provided.
    """
    try:
        data = request.json
        child_email1 = data.get('childNode')
        father_node = data.get('fatherNode')
        mother_node = data.get('motherNode')
        print('child eail was ,',child_email1.get('email'))
        child_email=child_email1.get('email')

        # Validate required fields
        if not child_email:
            return jsonify({
                "success": False,
                "error": "Child's email is required"
            }), 400
            
        # Validate that at least one parent is provided
        if not father_node and not mother_node:
            return jsonify({
                "success": False,
                "error": "At least one parent (father or mother) data must be provided"
            }), 400

        logger.info(f"Received request to create family tree for child {child_email} with parents")

        # Call the function from family_parent_manager.py
        family_tree_ref = db.collection('family_tree')
        result = create_family_tree_with_parents(
            family_tree_ref,
            user_profiles_ref,
            child_email,
            father_node,
            mother_node
        )
        
        if not result.get("success"):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in create_family_tree_with_parents_api: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/family-tree/merge-trees', methods=['POST'])
def merge_family_trees_api():
    """
    API endpoint to intelligently merge family trees between child and father.
    
    Takes:
    - childEmail: Email of the child
    - childFamilyTreeId: ID of the child's family tree
    - childNodeId: ID of the child node in the family tree
    - fatherEmail: Email of the father
    """
    try:
        data = request.json
        child_email = data.get('childEmail')
        child_family_tree_id = data.get('childFamilyTreeId')
        child_node_id = data.get('childNodeId')
        father_email = data.get('fatherEmail')

        # Validate required fields
        if not child_email:
            return jsonify({
                "success": False,
                "error": "Child email is required"
            }), 400
            
        if not father_email:
            return jsonify({
                "success": False,
                "error": "Father email is required"
            }), 400

        logger.info(f"Received request to merge family trees for child {child_email} with father {father_email}")

        # Get father's profile to create father node data
        father_profile = user_profiles_ref.document(father_email).get()
        if not father_profile.exists:
            return jsonify({
                "success": False,
                "error": f"Father profile not found for email: {father_email}"
            }), 404

        father_data = father_profile.to_dict()
        father_node = {
            'email': father_email,
            'firstName': father_data.get('firstName', ''),
            'lastName': father_data.get('lastName', ''),
            'gender': 'male',
            'nodeType': 'father'
        }

        # Call the function from family_parent_manager.py
        family_tree_ref = db.collection('family_tree')
        result = merge_family_trees(
            family_tree_ref,
            user_profiles_ref,
            child_email,
            father_node,
            None,  # No mother node data
            child_family_tree_id,
            child_node_id
        )
        
        if not result.get("success"):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in merge_family_trees_api: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/family-tree/create-with-husband', methods=['POST'])
def create_family_tree_with_husband_api():
    """
    API endpoint to create a new family tree with a husband and add a wife.
    
    Takes husband node data and wife's email.
    Fetches wife's details from her profile, creates a new family tree with the husband,
    adds the wife node for the husband, and updates both profiles with the family tree ID.
    """
    try:
        data = request.json
        husband_node = data.get('husbandNode')
        wife_email = data.get('wifeEmail')

        if not husband_node or not wife_email:
            return jsonify({
                "success": False,
                "error": "Husband node data and wife email are required"
            }), 400

        logger.info(f"Received request to create family tree with husband and wife {wife_email}")

        # Call the function from family_spouse_manager.py
        family_tree_ref = db.collection('family_tree')
        result = create_family_tree_with_husband(
            family_tree_ref,
            user_profiles_ref,
            husband_node,
            wife_email
        )
        
        if not result.get("success"):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in create_family_tree_with_husband_api: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/family-tree/create-with-wife', methods=['POST'])
def create_family_tree_with_wife_api():
    """
    API endpoint to create a new family tree with a wife and add a husband.
    
    Takes wife node data and husband's email.
    Fetches husband's details from his profile, creates a new family tree with the wife,
    adds the husband node for the wife, and updates both profiles with the family tree ID.
    """
    try:
        data = request.json
        wife_node = data.get('wifeNode')
        husband_email = data.get('husbandEmail')

        if not wife_node or not husband_email:
            return jsonify({
                "success": False,
                "error": "Wife node data and husband email are required"
            }), 400

        logger.info(f"Received request to create family tree with wife and husband {husband_email}")

        # Call the function from family_spouse_manager.py
        family_tree_ref = db.collection('family_tree')
        result = create_family_tree_with_wife(
            family_tree_ref,
            user_profiles_ref,
            wife_node,
            husband_email
        )
        
        if not result.get("success"):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in create_family_tree_with_wife_api: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/family-tree/add-husband', methods=['POST'])
def add_husband_to_family_tree_api():
    """
    API endpoint to add a husband to an existing wife's family tree.
    
    Takes husband node data, wife node ID and wife's family tree ID.
    Adds the husband to the wife's family tree, updates wife's last name to match husband's,
    and updates both profiles with marital status.
    """
    try:
        data = request.json
        print(data)
        husband_node = data.get('husbandNode')
        wife_node_id = data.get('wifeNodeId')
        wife_family_tree_id = data.get('wifeFamilyTreeId')
         
        # wifeFamilyTreeId family-tree-20250524213720
#  (NOBRIDGE) LOG  wifeNodeId 1748859314786-Parvati_Yarrampati
#  (NOBRIDGE) LOG  Adding husband to family tree: {"husbandNode": {"birthOrder": null, "email": "", "gender": "male", "generation": 1, "id": "1748860140573-Vera_Krishna_Kurumala", "isSelf": false, "name": "Vera Krishna  Kurumala", "parentId": null, "phone": "", "profileImage": null, "spouse": "1748859314786-Parvati_Yarrampati", "userProfileExists": false}, "wifeFamilyTreeId": "family-tree-20250524213720", "wifeNodeId": "1748859314786-Parvati_Yarrampati"}
        # chcek whentehr handling data correnctly befor sending to function     
        print('wife family tree id',wife_family_tree_id)
        print('wife node id',wife_node_id)
        print('husband node',husband_node)

        if not husband_node or not wife_node_id or not wife_family_tree_id:
            return jsonify({
                "success": False,
                "error": "Husband node data, wife node ID, and wife family tree ID are required"
            }), 400

        logger.info(f"Received request to add husband to wife's family tree {wife_family_tree_id}")

        # Call the function from family_spouse_manager.py
        family_tree_ref = db.collection('family_tree')
        result = add_husband_to_family_tree(
            family_tree_ref,
            user_profiles_ref,
            husband_node,
            wife_node_id,
            wife_family_tree_id
        )
        
        if not result.get("success"):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in add_husband_to_family_tree_api: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/family-tree/add-wife', methods=['POST']) 
def add_wife_to_family_tree_api(): 
    """ 
    API endpoint to add a wife to an existing husband's family tree.
    
    Takes wife node data, husband node ID and husband's family tree ID.
    Adds the wife to the husband's family tree with the husband's last name,
    and updates both profiles with marital status.
    """
    try:
        data = request.json
        wife_node = data.get('wifeNode')
        husband_node_id = data.get('husbandNodeId')
        husband_family_tree_id = data.get('husbandFamilyTreeId')

        if not wife_node or not husband_node_id or not husband_family_tree_id:
            return jsonify({
                "success": False,
                "error": "Wife node data, husband node ID, and husband family tree ID are required"
            }), 400

        logger.info(f"Received request to add wife to husband's family tree {husband_family_tree_id}")

        # Call the function from family_spouse_manager.py
        family_tree_ref = db.collection('family_tree')
        result = add_wife_to_family_tree( 
            family_tree_ref,
            user_profiles_ref,
            wife_node, 
            husband_node_id,
            husband_family_tree_id
        )
        
        if not result.get("success"):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in add_wife_to_family_tree_api: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/family-tree/create-with-husband-email', methods=['POST'])
def create_family_tree_with_husband_email_api():
    """
    API endpoint to create a new family tree with a husband and wife using their emails.
    
    Takes husband and wife emails, creates a family tree for husband,
    and adds wife to it or handles existing trees as needed.
    """
    try:
        data = request.json
        husband_email = data.get('husbandEmail')
        wife_email = data.get('wifeEmail')

        if not husband_email or not wife_email:
            return jsonify({
                "success": False,
                "error": "Husband email and wife email are required"
            }), 400

        logger.info(f"Received request to create family tree with husband email {husband_email} and wife email {wife_email}")

        # Call the function from family_spouse_manager.py
        family_tree_ref = db.collection('family_tree')
        result = create_family_tree_with_husband_email(
            family_tree_ref,
            user_profiles_ref,
            husband_email,
            wife_email
        )
        
        if not result.get("success"):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in create_family_tree_with_husband_email_api: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/family-tree/create-with-wife-email', methods=['POST'])
def create_family_tree_with_wife_email_api():
    """
    API endpoint to create a new family tree with a wife and husband using their emails.
    
    Takes wife and husband emails, creates a family tree for wife,
    and adds husband to it or handles existing trees as needed.
    """
    try:
        data = request.json
        wife_email = data.get('wifeEmail')
        husband_email = data.get('husbandEmail')

        if not wife_email or not husband_email:
            return jsonify({
                "success": False,
                "error": "Wife email and husband email are required"
            }), 400

        logger.info(f"Received request to create family tree with wife email {wife_email} and husband email {husband_email}")

        # Call the function from family_spouse_manager.py
        family_tree_ref = db.collection('family_tree')
        result = create_family_tree_with_wife_email(
            family_tree_ref,
            user_profiles_ref,
            wife_email,
            husband_email
        )
        
        if not result.get("success"):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in create_family_tree_with_wife_email_api: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
from family_spouse_manager import (
    adding_husband_to_family_tree,
    adding_wife_to_family_tree
)

@app.route('/api/family-tree/addspouseforboth', methods=['POST'])
def add_spouse_for_both_api():
    """
    API endpoint to add spouse relationship between husband and wife using their emails.
    
    Handles two cases when isTreeFound is true:
    1. isAdding: "wife" - Add wife to husband's family tree
    2. isAdding: "husband" - Add husband to wife's family tree
    
    If isTreeFound is false, it handles original scenarios:
    1. If husband has no family tree but wife does - Create husband's tree and link to wife
    2. If wife has no family tree but husband does - Add wife to husband's tree
    3. If both have family trees - Link both trees and update references
    4. If neither has a family tree - create new one
    """
    try:
        data = request.json
        logger.info(f"Received request to add spouse: {data}")
        
        # Check if isTreeFound exists and is true
        if data.get('isTreeFound'):
            # Check if the relationship is spouse
            if data.get('relationship') == 'spouse':
                # Case 1: Adding wife to husband's family tree
                if data.get('isAdding') == 'wife':
                    result = adding_wife_to_family_tree(
                        family_tree_ref=db.collection('family_tree'),
                        user_profiles_ref=user_profiles_ref,
                        husband_family_tree_id=data.get('husbandFamilyTreeId'),
                        husband_node_id=data.get('husbandNodeId'),
                        husband_email=data.get('husbandEmail'),
                        wife_email=data.get('wifeEmail')
                    )
                    return jsonify(result)
                
                # Case 2: Adding husband to wife's family tree
                elif data.get('isAdding') == 'husband':
                    result = adding_husband_to_family_tree(
                        family_tree_ref=db.collection('family_tree'),
                        user_profiles_ref=user_profiles_ref,
                        wife_family_tree_id=data.get('wifeFamilyTreeId'),
                        wife_node_id=data.get('wifeNodeId'),
                        wife_email=data.get('wifeEmail'),
                        husband_email=data.get('husbandEmail')
                    )
                    return jsonify(result)
                else:
                    return jsonify({
                        "success": False,
                        "error": "Invalid isAdding value. Must be 'husband' or 'wife'."
                    }), 400
            else:
                return jsonify({
                    "success": False,
                    "error": "Relationship must be 'spouse' for this endpoint."
                }), 400
        
        # Original functionality if isTreeFound is false
        husband_email = data.get('husbandEmail')
        wife_email = data.get('wifeEmail')

        if not husband_email or not wife_email:
            return jsonify({
                "success": False,
                "error": "Both husband email and wife email are required"
            }), 400

        logger.info(f"Processing original scenario for husband email {husband_email} and wife email {wife_email}")

        # Get user profiles to check if they exist and have family trees
        husband_profile_doc = user_profiles_ref.document(husband_email).get()
        wife_profile_doc = user_profiles_ref.document(wife_email).get()
        
        if not husband_profile_doc.exists:
            return jsonify({
                "success": False,
                "error": f"Husband profile not found for email {husband_email}"
            }), 404
            
        if not wife_profile_doc.exists:
            return jsonify({
                "success": False,
                "error": f"Wife profile not found for email {wife_email}"
            }), 404
            
        husband_profile = husband_profile_doc.to_dict()
        wife_profile = wife_profile_doc.to_dict()
        
        husband_family_tree_id = husband_profile.get('familyTreeId')
        wife_family_tree_id = wife_profile.get('familyTreeId')
        
        family_tree_ref = db.collection('family_tree')
        
        # SCENARIO 1: Husband has no family tree but wife does
        if not husband_family_tree_id and wife_family_tree_id:
            result = create_family_tree_with_husband_email(
                family_tree_ref,
                user_profiles_ref,
                husband_email,
                wife_email
            )
        
        # SCENARIO 2: Wife has no family tree but husband does
        elif husband_family_tree_id and not wife_family_tree_id:
            result = create_family_tree_with_wife_email(
                family_tree_ref,
                user_profiles_ref,
                wife_email,
                husband_email
            )
        
        # SCENARIO 3: Both have family trees - needs special handling
        elif husband_family_tree_id and wife_family_tree_id:
            result = handle_both_spouses_have_trees(
                family_tree_ref,
                user_profiles_ref,
                husband_email,
                husband_family_tree_id,
                wife_email,
                wife_family_tree_id
            )
        
        # SCENARIO 4: Neither has a family tree - create new
        else:
            result = create_family_tree_with_husband_email(
                family_tree_ref,
                user_profiles_ref,
                husband_email,
                wife_email
            )
        
        if not result.get("success"):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in add_spouse_for_both_api: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/invitations/send-spouse', methods=['POST'])
def send_spouse_invitation_api():
    """
    API endpoint to send spouse relationship invitations.
    
    Handles the following data structures:
    1. Family Tree Exists + Selected Member is Male (isAdding: 'wife')
    2. Family Tree Exists + Selected Member is Female (isAdding: 'husband')
    3. Family Tree Does Not Exist + Selected Member is Male (isAdding: 'wife')
    4. Family Tree Does Not Exist + Selected Member is Female (isAdding: 'husband')
    
    Request body should include:
    - senderEmail: Email of the sender
    - recipientEmail: Email of the recipient
    - isTreeFound: Whether a family tree exists
    - isAdding: Which spouse is being added ('husband' or 'wife')
    - relationship: Should be 'spouse'
    - invitationType: Should be 'FAMILY'
    
    For when isTreeFound is true and isAdding is 'wife':
    - husbandFamilyTreeId: ID of husband's family tree
    - husbandNodeId: ID of husband in family tree
    - husbandEmail: Email of the husband
    - wifeEmail: Email of the wife
    
    For when isTreeFound is true and isAdding is 'husband':
    - wifeFamilyTreeId: ID of wife's family tree
    - wifeNodeId: ID of wife in family tree
    - wifeEmail: Email of the wife
    - husbandEmail: Email of the husband
    
    For when isTreeFound is false:
    - husbandEmail/wifeEmail: Emails of the spouses
    
    Returns JSON with success status and invitation token or error message.
    """
    try:
        # Extract data from request
        data = request.json
        logger.info(f"Received spouse invitation request: {data}")
        
        # Get basic invitation parameters
        sender_email = data.get('senderEmail')
        recipient_email = data.get('recipientEmail')
        relationship = data.get('relationship')
        invitation_type = data.get('invitationType')
        is_tree_found = data.get('isTreeFound', False)
        is_adding = data.get('isAdding')
        
        # Validate required fields
        if not all([sender_email, recipient_email, relationship, is_adding]):
            return jsonify({
                "success": False,
                "message": "Missing required fields: senderEmail, recipientEmail, relationship, and isAdding are required"
            }), 400
        
        # Validate relationship type
        if relationship != 'spouse':
            return jsonify({
                "success": False,
                "message": f"Invalid relationship type: {relationship}. Must be 'spouse' for this endpoint."
            }), 400
            
        # Prepare parameters based on invitation type
        spouse_params = {
            'is_tree_found': is_tree_found,
            'is_adding': is_adding
        }
        
        # Add specific parameters based on which spouse is being added and if tree exists
        if is_adding == 'wife':
            spouse_params['husband_email'] = data.get('husbandEmail')
            spouse_params['wife_email'] = data.get('wifeEmail')
            
            if is_tree_found:
                spouse_params['husband_family_tree_id'] = data.get('husbandFamilyTreeId')
                spouse_params['husband_node_id'] = data.get('husbandNodeId')
        
        elif is_adding == 'husband':
            spouse_params['wife_email'] = data.get('wifeEmail')
            spouse_params['husband_email'] = data.get('husbandEmail')
            
            if is_tree_found:
                spouse_params['wife_family_tree_id'] = data.get('wifeFamilyTreeId')
                spouse_params['wife_node_id'] = data.get('wifeNodeId')
        
        else:
            return jsonify({
                "success": False,
                "message": f"Invalid isAdding value: {is_adding}. Must be 'husband' or 'wife'."
            }), 400
        
        # Add any additional data
        additional_data = data.get('additionalData', {})
        
        # Send the invitation using invitation_manager
        from invitation_manager import send_family_invitation
        
        result = send_family_invitation(
            sender_email=sender_email,
            recipient_email=recipient_email,
            relationship_type='spouse',
            db=db,
            **spouse_params  # Unpack the spouse parameters
        )
        
        if result.get('success'):
            # Also notify the recipient about the invitation in real-time
            # Get sender's profile for the notification
            sender_doc = user_profiles_ref.document(sender_email).get()
            sender_name = sender_email
            
            if sender_doc.exists:
                sender_data = sender_doc.to_dict()
                first_name = sender_data.get('firstName', '')
                last_name = sender_data.get('lastName', '')
                sender_name = f"{first_name} {last_name}".strip() or sender_email
            
            # Create notification data
            notification_data = {
                'invitationId': result.get('token'),
                'senderEmail': sender_email,
                'senderName': sender_name,
                'type': 'family',
                'relationshipType': 'spouse',
                'isTreeFound': is_tree_found,
                'isAdding': is_adding,
                'message': f"You have received a spouse invitation from {sender_name}"
            }
            
            # Add specific fields based on which spouse is being added
            if is_adding == 'wife':
                notification_data['husbandEmail'] = spouse_params['husband_email']
                notification_data['wifeEmail'] = spouse_params['wife_email']
                if is_tree_found:
                    notification_data['husbandFamilyTreeId'] = spouse_params.get('husband_family_tree_id')
                    notification_data['husbandNodeId'] = spouse_params.get('husband_node_id')
            else:
                notification_data['wifeEmail'] = spouse_params['wife_email']
                notification_data['husbandEmail'] = spouse_params['husband_email']
                if is_tree_found:
                    notification_data['wifeFamilyTreeId'] = spouse_params.get('wife_family_tree_id')
                    notification_data['wifeNodeId'] = spouse_params.get('wife_node_id')
                    
            # Add any additional data from the request
            if additional_data:
                notification_data['additionalData'] = additional_data
            
            # Send real-time notification to recipient
            from socket_manager import notify_user
            notify_user(recipient_email, {
                'type': 'new_invitation',
                'data': notification_data
            })
            
            return jsonify({
                "success": True,
                "message": "Spouse invitation sent successfully",
                "data": {
                    "token": result.get('token'),
                    "invitation": notification_data
                }
            })
        else:
            return jsonify({
                "success": False,
                "message": result.get('message') or result.get('error'),
                "error": result.get('error')
            }), 400
    
    except Exception as e:
        logger.error(f"Error sending spouse invitation: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error sending spouse invitation: {str(e)}",
            "error": str(e)
        }), 500

@app.route('/api/add-friend-noprofile', methods=['POST'])
def add_friend_noprofile_api():
    try:
        data = request.json
        user_email = data.get('userEmail')
        friend_first_name = data.get('friendFirstName')
        friend_last_name = data.get('friendLastName')
        friend_category = data.get('friendCategory')
        friend_email = data.get('friendEmail', None)  # Optional email

        # Validate required fields
        if not user_email:
            return jsonify({"error": "User email is required"}), 400
        if not friend_first_name or not friend_last_name:
            return jsonify({"error": "Friend first name and last name are required"}), 400
        if not friend_category:
            return jsonify({"error": "Friend category is required"}), 400

        # Get database references
        
        user_profiles_ref = db.collection('user_profiles')
        
        # Call the function to add a friend without a profile
        result = add_noprofile_friend(
            db=db,
            user_email=user_email,
            friend_first_name=friend_first_name,
            friend_last_name=friend_last_name,
            friend_category=friend_category,
            friend_email=friend_email
        )
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/friends/add-mutual', methods=['POST'])
def add_mutual_friends_api():
    """
    API endpoint to add two users as mutual friends with their respective categories
    Takes user1_email, user2_email, user1_category, and user2_category
    Both users must have existing profiles
    """
    try:
        # Extract data from the request
        data = request.json
        logger.info(f"Received data for mutual friends: {data}")
        
        # Extract required fields
        user1_email = data.get('user1Email')
        user2_email = data.get('user2Email')
        user1_category = data.get('user1Category')  # Category assigned by user1 to user2
        user2_category = data.get('user2Category')  # Category assigned by user2 to user1
        
        # Validate required fields
        if not user1_email or not user2_email:
            return jsonify({
                "success": False,
                "message": "Both user emails are required"
            }), 400
            
        if not user1_category or not user2_category:
            return jsonify({
                "success": False,
                "message": "Categories for both users are required"
            }), 400
            
        # Get database instance
        db = firestore.client()
        
        # Call the function to establish mutual friendship
        from friend_manager import add_mutual_friends
        result = add_mutual_friends(
            db=db,
            user1_email=user1_email,
            user2_email=user2_email,
            user1_category=user1_category,
            user2_category=user2_category
        )
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error in add_mutual_friends_api: {str(e)}")
        import traceback
        error_details = traceback.format_exc()
        logger.error(error_details)
        return jsonify({
            "success": False,
            "message": f"Error establishing mutual friendship: {str(e)}",
            "details": error_details
        }), 500

@app.route('/api/promocode/add', methods=['POST'])
def add_promocode_api():
    """
    API endpoint to add a promo code for a user in a family tree.
    
    Takes:
    - promocode: The promo code to add
    - familyTreeId: ID of the family tree
    - nodeId: ID of the node in the family tree
    - name: Name of the user
    - senderName: Name of the sender who created the promo code
    
    Returns:
    - JSON with success status and result details
    """
    try:
        # Extract data from request
        data = request.json
        promocode = data.get('promocode')
        family_tree_id = data.get('familyTreeId')
        node_id = data.get('nodeId')
        name = data.get('name')
        sender_name = data.get('senderName')
        
        # Validate required fields
        if not all([promocode, family_tree_id, node_id, name, sender_name]):
            return jsonify({
                "success": False,
                "error": "Missing required fields: promocode, familyTreeId, nodeId, name, and senderName are required"
            }), 400
        
        logger.info(f"Received request to add promo code {promocode} for node {node_id} in family tree {family_tree_id}")
        
        # Call the function from promocode_manager.py
        result = add_promocode(
            db=db,
            promocode=promocode,
            family_tree_id=family_tree_id,
            node_id=node_id,
            name=name,
            sender_name=sender_name
        )
        
        if not result.get("success"):
            return jsonify(result), 400
            
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in add_promocode_api: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/promocode/get', methods=['GET'])
def get_promocode_api():
    """
    API endpoint to get promo code details including family relationships.
    
    Query Parameters:
    - promocode: The promo code to retrieve details for
    
    Returns:
    - JSON with success status and promo code details including family relationships
    """
    try:
        # Get promocode from query parameters
        promocode = request.args.get('promocode')
        
        if not promocode:
            return jsonify({
                "success": False,
                "error": "Promocode parameter is required"
            }), 400
        
        logger.info(f"Received request to get details for promo code: {promocode}")
        
        # Call the function from promocode_manager.py
        result = get_promocode_details(
            db=db,
            promocode=promocode
        )
        
        if not result.get("success"):
            return jsonify(result), 404
            
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in get_promocode_api: {e}")
        return jsonify({
            "success": False, 
            "error": str(e)
        }), 500

@app.route('/api/update-tree-withpromocode', methods=['POST'])
def update_tree_with_promocode():
    """
    API endpoint to update a node in a family tree with details like name, email, phone, and profileImage.
    
    Request body should include:
    - familyTreeId: ID of the family tree
    - nodeId: ID of the node to update
    - name: Name of the user
    - promocode: The promocode associated with this update
    - email: Email of the user (optional)
    - phone: Phone number of the user (optional)
    - profileImage: Profile image data (base64 encoded, optional)
    
    Returns:
    - JSON with success status and updated node details
    """
    try:
        logger.info(f"Received request to /api/update-tree-withpromocode endpoint")
        
        # Extract data from request
        data = request.json
        family_tree_id = data.get('familyTreeId')
        node_id = data.get('nodeId')
        name = data.get('name')
        promocode = data.get('promocode')
        email = data.get('email') 
        phone = data.get('phone')
        has_profile_image = 'profileImage' in data
        profile_image = data.get('profileImage')
        
        # Log request details without sensitive data
        logger.info(f"Request parameters - Tree ID: {family_tree_id}, Node ID: {node_id}")
        logger.info(f"Promocode: {promocode}")
        logger.info(f"Has name: {bool(name)}, Has email: {bool(email)}, Has phone: {bool(phone)}, Has profile image: {has_profile_image}")
        
        # Validate required fields
        if not all([family_tree_id, node_id, name, promocode]):
            missing_fields = []
            if not family_tree_id:
                missing_fields.append("familyTreeId")
            if not node_id:
                missing_fields.append("nodeId")
            if not name:
                missing_fields.append("name")
            if not promocode:
                missing_fields.append("promocode")
                
            logger.error(f"Missing required fields: {', '.join(missing_fields)}")
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400
         
        logger.info(f"Validation successful, processing request")
        
        # Call the function from promocode_manager.py
        logger.info(f"Calling update_tree_node_with_promocode function")
        result = update_tree_node_with_promocode(
            db=db,
            family_tree_id=family_tree_id,
            node_id=node_id,
            name=name,
            promocode=promocode,
            email=email,
            phone=phone,
            profile_image=profile_image
        )
        
        if not result.get("success"):
            logger.error(f"Function call failed: {result.get('message') or result.get('error')}")
            return jsonify(result), 404
        
        logger.info(f"Function call successful: {result.get('message')}")
        logger.info(f"User has profile: {result.get('userHasProfile')}, Profile created: {result.get('profileCreated')}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in update_tree_with_promocode API: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/notifications/create', methods=['POST'])
def create_notification():
    try:
        logger.info(f"====== CREATE NOTIFICATION REQUEST START ======")
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        required_fields = ['userEmail', 'type']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400

        user_email = data['userEmail']
        notification_type = data['type']
        notification_data = data.get('data', {})
        
        logger.info(f"Creating {notification_type} notification for user: {user_email}")

        # Create a new notification document
        notification = {
            '_id': str(uuid.uuid4()),  # Generate unique ID
            'userId': user_email,
            'type': notification_type,
            'data': notification_data,
            'createdAt': datetime.now().isoformat(),
            'updatedAt': datetime.now().isoformat(),
            'isRead': False,
            'isArchived': False,
            'priority': data.get('priority', 'medium')  # Default priority is medium
        }

        # Add type-specific validation and processing
        if notification_type == 'group_message':
            required_message_fields = ['groupId', 'groupName', 'senderId', 'senderName', 'messagePreview']
            if not all(field in notification_data for field in required_message_fields):
                return jsonify({'success': False, 'message': 'Missing required fields for group message'}), 400

        elif notification_type == 'invitation':
            required_invitation_fields = ['invitationType', 'senderId', 'senderName', 'message']
            if not all(field in notification_data for field in required_invitation_fields):
                return jsonify({'success': False, 'message': 'Missing required fields for invitation'}), 400
            notification_data['status'] = notification_data.get('status', 'pending')

        elif notification_type == 'event':
            required_event_fields = ['eventId', 'eventTitle', 'eventType', 'startDate']
            if not all(field in notification_data for field in required_event_fields):
                return jsonify({'success': False, 'message': 'Missing required fields for event'}), 400
            notification_data['status'] = notification_data.get('status', 'upcoming')

        elif notification_type == 'classified':
            required_classified_fields = ['classifiedId', 'title', 'category', 'posterId']
            if not all(field in notification_data for field in required_classified_fields):
                return jsonify({'success': False, 'message': 'Missing required fields for classified'}), 400
            notification_data['status'] = notification_data.get('status', 'new')

        else:
            return jsonify({'success': False, 'message': 'Invalid notification type'}), 400

        # Create notifications collection for user if it doesn't exist
        user_notifications_ref = db.collection('user_profiles').document(user_email).collection('notifications')
        
        # Add the notification
        user_notifications_ref.document(notification['_id']).set(notification)
        
        # Get unread count for the response
        unread_docs = user_notifications_ref.where('isRead', '==', False).get()
        unread_count = len(list(unread_docs))
        
        logger.info(f"Added notification {notification['_id']} to database. Current unread count: {unread_count}")

        # Create response data including unread count
        response_data = {
            'notificationId': notification['_id'],
            'notification': notification,
            'unreadCount': unread_count
        }

        # Send notifications (both Socket.IO and Push) in parallel
        notification_sent = False
        
        # 1. Attempt to send real-time notification via Socket.IO
        try:
            # Emit to the user's personal notification channel
            socketio.emit(
                f'notification_{user_email}', 
                {
                    'type': 'new_notification',
                    'notification': notification,
                    'unreadCount': unread_count
                }
            )
            logger.info(f"✅ Socket.IO: Sent to personal channel notification_{user_email}")
            
            # Also emit to a general notification channel
            socketio.emit(
                'notifications', 
                {
                    'userEmail': user_email,
                    'type': 'new_notification',
                    'notification': notification,
                    'unreadCount': unread_count
                }
            )
            logger.info("✅ Socket.IO: Sent to general channel")
            notification_sent = True
            
        except Exception as socket_error:
            logger.error(f"❌ Socket.IO: Failed to send notification: {str(socket_error)}")
        
        # 2. Send push notification
        try:
            from push_notification_service import send_push_notification_to_user
            
            # Prepare push notification content
            push_title = "Nigama Connect"
            push_body = "You have a new notification"
            
            # Customize notification content based on type
            if notification_type == 'group_message':
                sender_name = notification_data.get('senderName', 'Someone')
                group_name = notification_data.get('groupName', 'a group')
                message_preview = notification_data.get('messagePreview', '...')
                push_title = f"Message from {sender_name}"
                push_body = f"{group_name}: {message_preview}"
                
            elif notification_type == 'invitation':
                sender_name = notification_data.get('senderName', 'Someone')
                invitation_type = notification_data.get('invitationType', 'connection')
                push_title = f"New Invitation"
                push_body = f"{sender_name} sent you a {invitation_type} invitation"
                
            elif notification_type == 'event':
                event_title = notification_data.get('eventTitle', 'Event')
                event_type = notification_data.get('eventType', '')
                push_title = f"New {event_type} Event"
                push_body = f"{event_title}"
                
            elif notification_type == 'classified':
                title = notification_data.get('title', 'Classified')
                category = notification_data.get('category', '')
                push_title = f"New {category} Listing"
                push_body = f"{title}"
            
            # Send push notification directly using the service
            push_success, push_result = send_push_notification_to_user(
                db=db,
                user_email=user_email,
                title=push_title,
                body=push_body,
                data={
                    'notificationId': notification['_id'],
                    'type': notification_type,
                    'createdAt': notification['createdAt'],
                    'data': notification_data
                }
            )
            
            if push_success:
                logger.info(f"✅ Push: Notification sent successfully - {push_result.get('message')}")
                notification_sent = True
            else:
                logger.warning(f"❌ Push: Failed to send notification - {push_result.get('error')}")
            
        except Exception as push_error:
            logger.error(f"❌ Push: Error sending notification - {str(push_error)}")
        
        # Add delivery status to response
        response_data['notification_delivery'] = {
            'success': notification_sent,
            'methods': {
                'socket': notification_sent,
                'push': push_success if 'push_success' in locals() else False
            }
        }
        
        logger.info(f"====== CREATE NOTIFICATION REQUEST END ======")
        return jsonify({
            'success': True,
            'message': 'Notification created and delivered successfully' if notification_sent else 'Notification created but delivery partially failed',
            'data': response_data
        })

    except Exception as e:
        logger.error(f"Error creating notification: {str(e)}")
        logger.info(f"====== CREATE NOTIFICATION REQUEST END ======")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/notifications/get', methods=['GET'])
def get_notifications():
    """
    Get notifications for a user with optional filtering and pagination.
    
    Query Parameters:
    - email (required): User's email
    - type (optional): Filter by notification type (invitation, group_message, event, classified)
    - is_read (optional): Filter by read status (true/false)
    - is_archived (optional): Filter by archive status (true/false)
    - limit (optional): Maximum number of notifications to return (default: 50)
    - last_notification_id (optional): Last notification ID for pagination
    
    Returns:
    - JSON with notifications list, unread count, and pagination info
    """
    try:
        # Get query parameters
        email = request.args.get('email')
        if not email:
            return jsonify({
                "success": False,
                "message": "Email parameter is required"
            }), 400
            
        # Get optional filters
        notification_type = request.args.get('type')
        is_read = request.args.get('is_read')
        is_archived = request.args.get('is_archived')
        limit = request.args.get('limit', type=int, default=50)
        last_notification_id = request.args.get('last_notification_id')
        
        # Convert string boolean parameters to actual booleans
        if is_read is not None:
            is_read = is_read.lower() == 'true'
        if is_archived is not None:
            is_archived = is_archived.lower() == 'true'
            
        # Call notification manager function
        success, result = get_user_notifications(
            user_email=email,
            db=db,
            filter_type=notification_type,
            is_read=is_read,
            is_archived=is_archived,
            limit=limit,
            last_notification_id=last_notification_id
        )
        
        if success:
            return jsonify({
                "success": True,
                "data": result
            })
        else:
            return jsonify({
                "success": False,
                "message": result.get("error", "Unknown error occurred")
            }), 500
            
    except Exception as e:
        logger.error(f"Error in get_notifications: {str(e)}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/api/notifications/mark-read', methods=['POST'])
def mark_notifications_read_api():
    """
    Mark one or more notifications as read.
    
    Request Body:
    {
        "email": "user@example.com",
        "notificationIds": ["id1", "id2", ...]
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({
                "success": False,
                "message": "No data provided"
            }), 400
            
        email = data.get('email')
        notification_ids = data.get('notificationIds', [])
        
        if not email or not notification_ids:
            return jsonify({
                "success": False,
                "message": "Email and notificationIds are required"
            }), 400
            
        success, result = mark_notifications_read(
            user_email=email,
            db=db,
            notification_ids=notification_ids
        )
        
        if success:
            return jsonify({
                "success": True,
                "message": result["message"]
            })
        else:
            return jsonify({
                "success": False,
                "message": result.get("error", "Unknown error occurred")
            }), 500
            
    except Exception as e:
        logger.error(f"Error in mark_notifications_read_api: {str(e)}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/api/notifications/archive', methods=['POST'])
def archive_notifications_api():
    """
    Archive one or more notifications.
    
    Request Body:
    {
        "email": "user@example.com",
        "notificationIds": ["id1", "id2", ...]
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({
                "success": False,
                "message": "No data provided"
            }), 400
            
        email = data.get('email')
        notification_ids = data.get('notificationIds', [])
        
        if not email or not notification_ids:
            return jsonify({
                "success": False,
                "message": "Email and notificationIds are required"
            }), 400
            
        success, result = archive_notifications(
            user_email=email,
            db=db,
            notification_ids=notification_ids
        )
        
        if success:
            return jsonify({
                "success": True,
                "message": result["message"]
            })
        else:
            return jsonify({
                "success": False,
                "message": result.get("error", "Unknown error occurred")
            }), 500
            
    except Exception as e:
        logger.error(f"Error in archive_notifications_api: {str(e)}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/notifications/unread-count/<email>', methods=['GET'])
def get_unread_notifications_count(email):
    """
    Get the count of unread notifications for a specific user, broken down by type.
    
    Args:
        email (str): User's email address
    
    Returns:
        JSON with unread notification counts by type
    """
    try:
        if not email:
            return jsonify({
                "success": False,
                "message": "Email is required"
            }), 400
            
        # Get reference to user's notifications collection
        notifications_ref = db.collection('user_profiles').document(email).collection('notifications')
        
        # Get all unread notifications
        unread_query = notifications_ref.where('isRead', '==', False)
        unread_docs = unread_query.get()
        
        # Initialize counters
        total_count = 0
        event_count = 0
        invitation_count = 0
        classified_count = 0
        message_count = 0
        
        # Count notifications by type
        for doc in unread_docs:
            notification = doc.to_dict()
            total_count += 1
            
            notification_type = notification.get('type', '')
            if notification_type == 'event':
                event_count += 1
            elif notification_type == 'invitation':
                invitation_count += 1
            elif notification_type == 'classified':
                classified_count += 1
            elif notification_type == 'group_message':
                message_count += 1
        
        return jsonify({
            "success": True,
            "counts": {
                "total": total_count,
                "events": event_count,
                "invitations": invitation_count,
                "classifieds": classified_count,
                "messages": message_count
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting unread notifications count for {email}: {str(e)}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/notifications/<email>', methods=['GET'])
def get_user_notifications_by_email(email):
    """
    Get all notifications for a specific user with optional filters.
    
    Args:
        email (str): User's email address
    
    Query Parameters:
        type (optional): Filter by notification type
        is_read (optional): Filter by read status
        is_archived (optional): Filter by archive status
        limit (optional): Maximum number of notifications to return
        last_notification_id (optional): Last notification ID for pagination
        count_only (optional): If true, returns only the unread count
    """
    try:
        logger.info(f"====== NOTIFICATION REQUEST START ======")
        logger.info(f"Fetching notifications for user: {email}")
        
        if not email:
            logger.warning("Email parameter is missing")
            return jsonify({
                "success": False,
                "message": "Email is required"
            }), 400
        
        # Check if only count is requested
        count_only = request.args.get('count_only', '').lower() == 'true'
        
        if count_only:
            logger.info(f"Getting unread notification count for user: {email}")
            # Get reference to user's notifications collection
            notifications_ref = db.collection('user_profiles').document(email).collection('notifications')
            
            # Get unread notifications query
            unread_query = notifications_ref.where('isRead', '==', False)
            
            # Get the count using get() instead of count()
            unread_docs = unread_query.get()
            unread_count = len(list(unread_docs))
            
            logger.info(f"Unread notification count for {email}: {unread_count}")
            
            response = {
                "success": True,
                "unreadCount": unread_count
            }
            logger.info(f"Returning unread count response: {response}")
            logger.info(f"====== NOTIFICATION REQUEST END ======")
            return jsonify(response)
            
        # If not count_only, proceed with full notification retrieval
        # Get optional query parameters
        notification_type = request.args.get('type')
        is_read = request.args.get('is_read')
        is_archived = request.args.get('is_archived')
        limit = request.args.get('limit', type=int, default=50)
        last_notification_id = request.args.get('last_notification_id')
        
        logger.info(f"Query parameters - type: {notification_type}, is_read: {is_read}, " \
                   f"is_archived: {is_archived}, limit: {limit}, last_id: {last_notification_id}")
        
        # Convert string boolean parameters to actual booleans
        if is_read is not None:
            is_read = is_read.lower() == 'true'
        if is_archived is not None:
            is_archived = is_archived.lower() == 'true'
            
        # Get notifications using the manager function
        success, result = get_user_notifications(
            user_email=email,
            db=db,
            filter_type=notification_type,
            is_read=is_read,
            is_archived=is_archived,
            limit=limit,
            last_notification_id=last_notification_id
        )
        
        if success:
            notification_count = len(result.get('notifications', []))
            unread_count = result.get('unread_count', 0)
            logger.info(f"Successfully retrieved notifications for {email}. " \
                       f"Count: {notification_count}, Unread: {unread_count}")
            
            # Log individual notifications
            logger.info(f"Notification details:")
            for i, notification in enumerate(result.get('notifications', [])):
                try:
                    notif_id = notification.get('_id', 'unknown')
                    notif_type = notification.get('type', 'unknown')
                    created_at = notification.get('createdAt', 'unknown')
                    is_read = notification.get('isRead', 'unknown')
                    priority = notification.get('priority', 'unknown')
                    
                    # Get type-specific key details
                    data = notification.get('data', {})
                    details = ""
                    
                    if notif_type == 'invitation':
                        sender = data.get('senderName', data.get('senderId', 'unknown'))
                        invite_type = data.get('invitationType', 'unknown')
                        status = data.get('status', 'unknown')
                        details = f"From: {sender}, Type: {invite_type}, Status: {status}"
                    
                    elif notif_type == 'group_message':
                        group = data.get('groupName', 'unknown')
                        sender = data.get('senderName', data.get('senderId', 'unknown'))
                        preview = data.get('messagePreview', '')[:20] + '...' if data.get('messagePreview') else 'no preview'
                        details = f"Group: {group}, From: {sender}, Preview: {preview}"
                    
                    elif notif_type == 'event':
                        title = data.get('eventTitle', 'unknown')
                        event_type = data.get('eventType', 'unknown')
                        date = data.get('startDate', 'unknown')
                        details = f"Title: {title}, Type: {event_type}, Date: {date}"
                    
                    elif notif_type == 'classified':
                        title = data.get('title', 'unknown')
                        category = data.get('category', 'unknown')
                        price = data.get('price', 'unknown')
                        details = f"Title: {title}, Category: {category}, Price: {price}"
                        
                    logger.info(f"  [{i+1}] ID: {notif_id}, Type: {notif_type}, Created: {created_at}, Read: {is_read}, Priority: {priority}")
                    logger.info(f"      Details: {details}")
                except Exception as e:
                    logger.error(f"Error logging notification details: {str(e)}")
            
            # Create response object
            response = {
                "success": True,
                "data": result
            }
            
            # Log the full JSON response
            import json
            try:
                # Using a custom default serializer for non-serializable types
                def json_serializer(obj):
                    if isinstance(obj, (datetime, date)):
                        return obj.isoformat()
                    return str(obj)
                
                # Format the JSON with indentation for better readability in logs
                formatted_json = json.dumps(response, indent=2, default=json_serializer)
                logger.info(f"Full JSON response: \n{formatted_json}")
            except Exception as json_error:
                logger.error(f"Error serializing JSON response: {str(json_error)}")
                # Fallback to simpler representation
                logger.info(f"Response structure: success={response['success']}, notification_count={notification_count}")
                
            logger.info(f"====== NOTIFICATION REQUEST END ======")
            return jsonify(response)
        else:
            logger.error(f"Failed to get notifications for {email}: {result.get('error')}")
            logger.info(f"====== NOTIFICATION REQUEST END ======")
            return jsonify({
                "success": False,
                "message": result.get("error", "Unknown error occurred")
            }), 500
            
    except Exception as e:
        logger.error(f"Error getting notifications for {email}: {str(e)}", exc_info=True)
        logger.info(f"====== NOTIFICATION REQUEST END ======")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/notifications/<email>/mark-all-read', methods=['POST'])
def mark_all_notifications_read_api(email):
    """
    Mark all unread notifications as read for a specific user.
    
    Args:
        email (str): User's email address
    
    Returns:
        JSON with success status and count of notifications marked as read
    """
    try:
        logger.info(f"====== MARK ALL READ REQUEST START ======")
        logger.info(f"Marking all notifications as read for user: {email}")
        
        if not email:
            logger.warning("Email parameter is missing")
            return jsonify({
                "success": False,
                "message": "Email is required"
            }), 400
        
        # Call the function to mark all notifications as read
        success, result = mark_all_notifications_read(
            user_email=email,
            db=db
        )
        
        if success:
            count = result.get('count', 0)
            logger.info(f"Successfully marked {count} notifications as read for {email}")
            logger.info(f"====== MARK ALL READ REQUEST END ======")
            return jsonify({
                "success": True,
                "message": result.get('message'),
                "count": count
            })
        else:
            logger.error(f"Failed to mark notifications as read: {result.get('error')}")
            logger.info(f"====== MARK ALL READ REQUEST END ======")
            return jsonify({
                "success": False,
                "message": result.get("error", "Unknown error occurred")
            }), 500
    
    except Exception as e:
        logger.error(f"Error in mark_all_notifications_read_api: {str(e)}", exc_info=True)
        logger.info(f"====== MARK ALL READ REQUEST END ======")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/notifications/mark-all-read', methods=['POST'])
def mark_all_notifications_from_body():
    """
    API endpoint to mark all notifications as read using email from request body.
    Supports the client-side pattern of posting to /notifications/mark-all-read
    with email in the request body.
    """
    try:
        # Get email from request body
        data = request.json
        if not data or 'email' not in data:
            return jsonify({
                "success": False,
                "message": "Email is required in request body"
            }), 400
            
        email = data.get('email')
        logger.info(f"Marking all notifications as read for user (from body): {email}")
        
        # Reuse the existing function
        return mark_all_notifications_read_api(email)
    
    except Exception as e:
        logger.error(f"Error in mark_all_notifications_from_body: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/notifications/register-device', methods=['POST'])
def register_device():
    """
    API endpoint to register a device token for push notifications.
    
    Request Body:
    {
        "email": "user@example.com",
        "token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
        "device_type": "android-expo" or "ios-expo"
    }
    
    Returns:
    {
        "success": true,
        "message": "Device registered successfully"
    }
    """
    try:
        logger.info("="*50)
        logger.info("DEVICE REGISTRATION REQUEST START")
        logger.info("="*50)
        
        data = request.json
        logger.info(f"Received registration request data: {json.dumps(data, indent=2)}")
        
        # Validate required fields
        if not data:
            logger.error("Registration failed: No data provided in request body")
            return jsonify({
                "success": False,
                "message": "No data provided"
            }), 400
        
        required_fields = ['email', 'token', 'device_type']
        for field in required_fields:
            if field not in data:
                logger.error(f"Registration failed: Missing required field '{field}'")
                return jsonify({
                    "success": False,
                    "message": f"Missing required field: {field}"
                }), 400
        
        email = data['email']
        token = data['token']
        device_type = data['device_type']
        
        logger.info("-"*30)
        logger.info("Registration Details:")
        logger.info(f"Email: {email}")
        logger.info(f"Device Type: {device_type}")
        logger.info(f"Token: {token}")
        logger.info("-"*30)
        
        # Check if token has valid format
        if not ('ExponentPushToken' in token or 'fcm' in token):
            logger.warning(f"Warning: Potentially invalid token format detected")
            logger.warning(f"Token received: {token}")
        
        # Store in Firestore
        device_data = {
            'email': email,
            'token': token,
            'device_type': device_type,
            'last_updated': datetime.now().isoformat()
        }
        
        # Get reference to user's device tokens collection
        user_ref = db.collection('user_profiles').document(email)
        logger.info(f"Checking user profile in Firestore for email: {email}")
        
        # Check if user exists
        user_doc = user_ref.get()
        if not user_doc.exists:
            logger.error(f"User profile not found in database for email: {email}")
            return jsonify({
                "success": False,
                "message": "User profile not found"
            }), 404
        
        logger.info(f"User profile found for email: {email}")
        
        # Store token in device_tokens subcollection
        token_id = token.replace(':', '_').replace('[', '_').replace(']', '_')  # Sanitize for Firestore ID
        logger.info(f"Sanitized token ID for storage: {token_id}")
        
        device_tokens_ref = user_ref.collection('device_tokens')
        device_tokens_ref.document(token_id).set(device_data, merge=True)
        
        logger.info(f"Successfully stored device token in Firestore")
        logger.info(f"Storage location: user_profiles/{email}/device_tokens/{token_id}")
        
        logger.info("="*50)
        logger.info("DEVICE REGISTRATION REQUEST COMPLETED SUCCESSFULLY")
        logger.info("="*50)
        
        return jsonify({
            "success": True,
            "message": "Device registered successfully"
        })
        
    except Exception as e:
        logger.error("="*50)
        logger.error("DEVICE REGISTRATION ERROR")
        logger.error(f"Error Type: {type(e).__name__}")
        logger.error(f"Error Message: {str(e)}")
        logger.error(f"Stack Trace:", exc_info=True)
        logger.error("="*50)
        return jsonify({
            "success": False,
            "message": f"Server error registering device: {str(e)}"
        }), 500

def send_push_notification(user_email, title, body, data=None):
    """
    Send push notification to a user's registered devices.
    
    Args:
        user_email (str): Email of the user to send notification to
        title (str): Title of the notification
        body (str): Body text of the notification
        data (dict, optional): Additional data to send with the notification
    
    Returns:
        tuple: (success, result)
            - success (bool): Whether the operation was successful
            - result (dict): Contains count of notifications sent or error message
    """
    try:
        logger.info(f"====== PUSH NOTIFICATION HANDLER START ======")
        logger.info(f"Initiating push notification for user: {user_email}")
        logger.info(f"Notification Content:")
        logger.info(f"- Title: {title}")
        logger.info(f"- Body: {body}")
        logger.info(f"- Additional Data: {json.dumps(data, indent=2) if data else 'None'}")

        from push_notification_service import send_push_notification_to_user
        
        # Send push notification using the service
        logger.info("Delegating to push notification service...")
        success, result = send_push_notification_to_user(
            db=db,
            user_email=user_email,
            title=title,
            body=body,
            data=data
        )
        
        if success:
            logger.info(f"✅ Push notification processed successfully")
            logger.info(f"Result: {result.get('message')}")
            if 'result' in result:
                details = result['result']
                logger.info(f"Detailed Results:")
                logger.info(f"- Successful sends: {details.get('successful_sends', 0)}")
                logger.info(f"- Failed sends: {details.get('failed_sends', 0)}")
                logger.info(f"- Total devices: {details.get('total_devices', 0)}")
        else:
            logger.warning(f"❌ Push notification processing failed")
            logger.warning(f"Error: {result.get('message', 'Unknown error')}")
            
        logger.info(f"====== PUSH NOTIFICATION HANDLER END ======")
        return success, result
        
    except Exception as e:
        logger.error(f"❌ Error in push notification handler: {str(e)}")
        logger.info(f"====== PUSH NOTIFICATION HANDLER END ======")
        return False, {"error": str(e)}

@app.route('/api/notifications/test-push', methods=['POST'])
def test_push_notification():
    """
    Test endpoint to trigger a push notification to a specific user.
    
    Request Body:
    {
        "email": "user@example.com",
        "title": "Test Notification",
        "body": "This is a test notification",
        "data": {
            "key1": "value1",
            "key2": "value2"
        }
    }
    
    Returns:
    {
        "success": true,
        "message": "Push notification sent successfully",
        "result": {
            "count": 1,
            "message": "Push notification sent to 1 devices"
        }
    }
    """
    try:
        logger.info(f"====== TEST PUSH NOTIFICATION REQUEST START ======")
        data = request.json
        
        # Validate required fields
        if not data:
            logger.warning("No data provided in the request")
            return jsonify({
                "success": False,
                "message": "No data provided"
            }), 400
        
        email = data.get('email')
        title = data.get('title', 'Test Notification')
        body = data.get('body', 'This is a test notification')
        additional_data = data.get('data', {})
        
        if not email:
            logger.warning("Missing required field: email")
            return jsonify({
                "success": False,
                "message": "Missing required field: email"
            }), 400
        
        logger.info(f"Sending test push notification to user: {email}")
        
        # Send the push notification
        success, result = send_push_notification(
            user_email=email,
            title=title,
            body=body,
            data=additional_data
        )
        
        if success:
            logger.info(f"Test push notification sent successfully: {result.get('message')}")
            logger.info(f"====== TEST PUSH NOTIFICATION REQUEST END ======")
            return jsonify({
                "success": True,
                "message": "Push notification sent successfully",
                "result": result
            })
        else:
            logger.error(f"Failed to send test push notification: {result.get('error')}")
            logger.info(f"====== TEST PUSH NOTIFICATION REQUEST END ======")
            return jsonify({
                "success": False,
                "message": f"Failed to send push notification: {result.get('error')}"
            }), 500
        
    except Exception as e:
        logger.error(f"Error sending test push notification: {str(e)}", exc_info=True)
        logger.info(f"====== TEST PUSH NOTIFICATION REQUEST END ======")
        return jsonify({
            "success": False,
            "message": f"Error sending test push notification: {str(e)}"
        }), 500

def save_temp_profile_image(base64_image, sender_id):
    """Helper function to save a temporary profile image and return its URL"""
    try:
        # Extract the actual base64 data after the data:image/format;base64, prefix
        if ',' in base64_image:
            image_data = base64_image.split(',')[1]
        else:
            image_data = base64_image

        # Decode base64 image
        image_bytes = base64.b64decode(image_data)
        
        # Create temp directory if it doesn't exist
        temp_dir = os.path.join(os.getcwd(), 'temp_profile_images')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Generate filename using sender_id
        filename = f"profile_{sender_id}_{int(time.time())}.jpg"
        filepath = os.path.join(temp_dir, secure_filename(filename))
        
        # Save the image
        with open(filepath, 'wb') as f:
            f.write(image_bytes)
            
        # Return the URL path
        return f"/temp_profile_images/{filename}"
    except Exception as e:
        logger.error(f"Error saving profile image: {str(e)}")
        return None

@app.route('/temp_profile_images/<filename>')
def serve_temp_profile_image(filename):
    """Serve temporary profile images"""
    return send_from_directory('temp_profile_images', filename)

@app.route('/api/notifications/send-message', methods=['POST'])
def send_message_notification():
    """
    Send a direct message notification to a user without storing in database.
    Profile images will be temporarily saved and served via URL for notifications.
    """
    try:
        logger.info(f"====== MESSAGE NOTIFICATION REQUEST START ======")
        data = request.json
        
        # Validate required fields
        required_fields = ['receiverEmail', 'senderName', 'senderProfileImage', 'message']
        if not data or not all(field in data for field in required_fields):
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400
        
        receiver_email = data['receiverEmail']
        sender_name = data['senderName']
        sender_profile_image = data['senderProfileImage']
        message_text = data['message']
        chat_type = data.get('chatType', 'direct')
        chat_id = data.get('chatId', str(uuid.uuid4()))
        group_name = data.get('groupName', '')
        
        logger.info(f"Processing message notification for receiver: {receiver_email}")
        logger.info(f"From: {sender_name}")
        logger.info(f"Chat Type: {chat_type}")
        
        # Save profile image and get URL
        profile_image_url = save_temp_profile_image(sender_profile_image, chat_id)
        if not profile_image_url:
            logger.warning("Failed to save profile image, proceeding without image")
        
        notification_sent = False
        socket_success = False
        push_success = False
        
        # Prepare message data
        message_data = {
            'senderId': chat_id,
            'senderName': sender_name,
            'senderProfileImage': profile_image_url if profile_image_url else None,
            'message': message_text,
            'chatType': chat_type,
            'chatId': chat_id,
            'groupName': group_name if chat_type == 'group' else '',
            'timestamp': datetime.now().isoformat()
        }
        
        # 1. Send Socket.IO notification
        try:
            # Send to personal channel
            socketio.emit(
                f'message_{receiver_email}',
                {
                    'type': 'new_message',
                    'data': message_data
                }
            )
            
            # Send to global messages channel
            socketio.emit(
                'messages',
                {
                    'userEmail': receiver_email,
                    'type': 'new_message',
                    'data': message_data
                }
            )
            
            logger.info(f"✅ Socket.IO: Message notification sent to {receiver_email}")
            socket_success = True
            notification_sent = True
            
        except Exception as socket_error:
            logger.error(f"❌ Socket.IO: Failed to send message notification: {str(socket_error)}")
        
        # 2. Send Push Notification
        try:
            from push_notification_service import send_push_notification_to_user
            
            # Prepare push notification content
            push_title = f"Message from {sender_name}"
            push_body = message_text[:100] + ('...' if len(message_text) > 100 else '')
            
            if chat_type == 'group':
                push_title = f"{group_name}"
                push_body = f"{sender_name}: {push_body}"

            # Prepare notification data with image
            notification_data = {
                'type': 'message',
                'chatId': chat_id,
                'chatType': chat_type,
                'senderName': sender_name,
                'timestamp': message_data['timestamp'],
                # Add full server URL for the profile image
                'image': f"{request.host_url.rstrip('/')}{profile_image_url}" if profile_image_url else None,
                # Add specific payload for Android
                'android': {
                    'notification': {
                        'imageUrl': f"{request.host_url.rstrip('/')}{profile_image_url}" if profile_image_url else None,
                        'style': 'BIGPICTURE',
                        'priority': 'high',
                        'defaultSound': True
                    }
                },
                # Add specific payload for iOS
                'apns': {
                    'payload': {
                        'aps': {
                            'mutable-content': 1,
                            'sound': 'default'
                        },
                        'imageUrl': f"{request.host_url.rstrip('/')}{profile_image_url}" if profile_image_url else None
                    }
                }
            }
            
            # Send push notification
            push_result, push_details = send_push_notification_to_user(
                db=db,
                user_email=receiver_email,
                title=push_title,
                body=push_body,
                data=notification_data
            )
            
            if push_result:
                logger.info(f"✅ Push: Message notification sent successfully")
                push_success = True
                notification_sent = True
            else:
                logger.warning(f"❌ Push: Failed to send message notification - {push_details.get('error')}")
                
        except Exception as push_error:
            logger.error(f"❌ Push: Error sending message notification - {str(push_error)}")
        
        # Schedule cleanup of temporary profile image
        def cleanup_temp_image():
            try:
                if profile_image_url:
                    filepath = os.path.join(os.getcwd(), profile_image_url.lstrip('/'))
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        logger.info(f"Cleaned up temporary profile image: {filepath}")
            except Exception as e:
                logger.error(f"Error cleaning up temporary profile image: {str(e)}")
        
        # Schedule cleanup after 1 hour
        threading.Timer(3600, cleanup_temp_image).start()
        
        # Prepare response
        response_data = {
            'deliveryStatus': {
                'socket': socket_success,
                'push': push_success,
                'overall': notification_sent
            },
            'profileImageUrl': f"{request.host_url.rstrip('/')}{profile_image_url}" if profile_image_url else None
        }
        
        logger.info(f"====== MESSAGE NOTIFICATION REQUEST END ======")
        return jsonify({
            'success': True,
            'message': 'Message notification sent successfully' if notification_sent else 'Message delivery partially failed',
            'data': response_data
        })
        
    except Exception as e:
        logger.error(f"Error processing message notification: {str(e)}")
        logger.info(f"====== MESSAGE NOTIFICATION REQUEST END ======")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/notifications/send-matrimony', methods=['POST'])
def send_matrimony_notification():
    try:
        data = request.json
        if not data or 'userEmail' not in data:
            return jsonify({'success': False, 'message': 'Receiver email is required'}), 400
        
        

        receiver_email = data['userEmail']
        matrimony_data = data.get('data', {})
        
        # Prepare notification content
        notification_title = matrimony_data.get('title', 'New Matrimony Profile')
        notification_body = f"New profile: {matrimony_data.get('name', '')} - {matrimony_data.get('education', '')}, {matrimony_data.get('occupation', '')}"

        # Prepare the data payload
        notification_data = {
            'type': 'matrimony',
            'profileId': matrimony_data.get('profileId'),
            'name': matrimony_data.get('name'),
            'education': matrimony_data.get('education'),
            'occupation': matrimony_data.get('occupation'),
            'caste': matrimony_data.get('caste'),
            'profileOwnerId': matrimony_data.get('profileOwnerId'),
            'profileOwnerName': matrimony_data.get('profileOwnerName'),
            'audience': matrimony_data.get('audience', 'All'),
            'status': matrimony_data.get('status', 'new')
        }

        # Handle thumbnail/profile image if provided
        thumbnail_url = matrimony_data.get('thumbnail')
        if thumbnail_url and thumbnail_url.startswith('data:image'):
            # If it's a base64 image, save it temporarily
            filename = save_temp_profile_image(thumbnail_url, matrimony_data.get('profileOwnerId'))
            if filename:
                notification_data['thumbnail'] = url_for('serve_temp_profile_image', 
                                                       filename=filename, 
                                                       _external=True)
        elif thumbnail_url:
            # If it's already a URL, use it directly
            notification_data['thumbnail'] = thumbnail_url

        # Send the push notification
        success = send_push_notification(
            receiver_email,
            notification_title,
            notification_body,
            notification_data
        )

        if success:
            return jsonify({
                'success': True,
                'message': 'Matrimony notification sent successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to send matrimony notification'
            }), 500

    except Exception as e:
        print(f"Error sending matrimony notification: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error sending matrimony notification: {str(e)}'
        }), 500
        
# write a api call  to get family tree image from firebasestorege using family tree id
@app.route('/api/family-tree/get-image', methods=['GET'])
def get_family_tree_image():
    print("get family tree image api called")
    family_tree_id = request.args.get('familyTreeId')
    print("family tree id",family_tree_id)
    try:
        # get the document ref of family tree using family tree id
        family_tree_ref = db.collection('family_tree').document(family_tree_id)
        print("family tree ref",family_tree_ref)
        family_tree_doc = family_tree_ref.get()
        if not family_tree_doc.exists:
            return jsonify({'error': 'Family tree document not found'}), 404
        # get the family tree image from the document
        family_tree_image = family_tree_doc.get('family_tree_image')
        print("tree image fetched successfullly")
        return jsonify({'family_tree_image': family_tree_image})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


from twilio.rest import Client
import random
# Storage for phone OTPs
phone_otp_storage = {}

@app.route('/send-phone-otp', methods=['POST'])
def send_phone_otp():
    data = request.json
    phone_number = data.get('phone_number')
    
    phone_number = '+91'+phone_number

    print(f"Received request to send OTP to phone: {phone_number}")

    if not phone_number:
        print("Phone number is required")
        return jsonify({'success': False, 'message': 'Phone number is required'}), 400

    # Generate a random 4-digit OTP
    otp = ''.join([str(random.randint(0, 9)) for _ in range(4)])
    
    # Store OTP with current timestamp
    current_time = int(time.time())
    phone_otp_storage[phone_number] = {'otp': otp, 'timestamp': current_time}

    print(f"Generated OTP for {phone_number}: {otp}, valid until: {current_time + OTP_EXPIRATION_TIME}")

    try:
        # Send OTP via Twilio
        # account_sid = 'AC1d845f7c006cc615c355e7b7aba4a9e2'
        # auth_token = '559af056d5d28b986b6471c48217af18'
        # twilio_phone_number = '+15709345635'

        # secret_file_path = '/etc/secrets/firebase_service_account.json'

        #     # Verify if the secret file exists
        #     if os.path.exists(secret_file_path):
       
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        twilio_phone_number = os.getenv('TWILIO_PHONE_NUMBER')

        

        client = Client(account_sid, auth_token)
        
        message = client.messages.create(
            body=f'Your Nigama Connect verification code is: {otp}. This code is valid for 10 minutes.',
            from_=twilio_phone_number,
            to=phone_number
        )
        print("OTP SMS sent successfully")
        return jsonify({'success': True, 'message': 'OTP sent successfully'})
    except Exception as e:
        print(f"Error sending OTP SMS: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/verify-phone-otp', methods=['POST'])
def verify_phone_otp():
    data = request.json
    phone_number = data.get('phone_number')
    phone_number = '+91'+phone_number
    otp = data.get('otp')

    print(f"Received request to verify OTP for phone: {phone_number}")

    if not phone_number or not otp:
        print("Phone number and OTP are required")
        return jsonify({'success': False, 'message': 'Phone number and OTP are required'}), 400

    stored_data = phone_otp_storage.get(phone_number)

    if not stored_data:
        print(f"No OTP found for phone: {phone_number}")
        return jsonify({'success': False, 'message': 'OTP not found or expired'}), 404

    # Check if OTP has expired
    current_time = int(time.time())
    if current_time - stored_data['timestamp'] > OTP_EXPIRATION_TIME:
        print(f"OTP expired for phone: {phone_number}")
        # Remove expired OTP
        del phone_otp_storage[phone_number]
        return jsonify({'success': False, 'message': 'OTP has expired. Please request a new one.'}), 400

    if stored_data['otp'] == otp:
        print(f"OTP verified successfully for phone: {phone_number}")
        del phone_otp_storage[phone_number]  # Clear the OTP after successful verification
        return jsonify({'success': True, 'message': 'OTP verified successfully'})
    else:
        print(f"Invalid OTP for phone: {phone_number}")
        return jsonify({'success': False, 'message': 'Invalid OTP'}), 400

# Update cleanup function to handle both email and phone OTPs
def cleanup_expired_otps():
    current_time = int(time.time())
    expired_emails = []
    expired_phones = []

    # Clean up email OTPs
    for email, data in otp_storage.items():
        if current_time - data['timestamp'] > OTP_EXPIRATION_TIME:
            expired_emails.append(email)
     
    for email in expired_emails:
        del otp_storage[email]

    # Clean up phone OTPs
    for phone, data in phone_otp_storage.items():
        if current_time - data['timestamp'] > OTP_EXPIRATION_TIME:
            expired_phones.append(phone)
     
    for phone in expired_phones:
        del phone_otp_storage[phone]
    
    print(f"Cleaned up {len(expired_emails)} expired email OTPs and {len(expired_phones)} expired phone OTPs")


@app.route('/api/number/get-email', methods=['GET'])
def get_email_from_number():
    phone_number = request.args.get('phone_number')
    phone_number = '+91'+phone_number
    number_collection_ref = db.collection('numbers')
    if number_collection_ref:
        number_doc_ref = number_collection_ref.document(phone_number)
        if not number_doc_ref.get().exists: 
            return jsonify({'email': None}), 200
        number_data = number_doc_ref.get().to_dict()
        print("number data",number_data)
    return jsonify({'email': number_data.get('email')})

@app.route('/notifications/<email>/mark-events-read', methods=['POST'])
def mark_events_notifications_read(email):
    """
    Mark all event notifications as read for a specific user.
    
    Args:
        email (str): User's email address
    
    Returns:
        JSON with success status and count of notifications marked as read
    """
    try:
        logger.info(f"====== MARK EVENTS READ REQUEST START ======")
        logger.info(f"Marking all event notifications as read for user: {email}")
        
        if not email:
            logger.warning("Email parameter is missing")
            return jsonify({
                "success": False,
                "message": "Email is required"
            }), 400
        
        # Get reference to user's notifications collection
        notifications_ref = db.collection('user_profiles').document(email).collection('notifications')
        
        # Get all unread event notifications
        unread_events = notifications_ref.where('isRead', '==', False).where('type', '==', 'event').get()
        
        # Get the IDs of unread event notifications
        event_ids = [doc.id for doc in unread_events]
        count = len(event_ids)
        
        if count == 0:
            return jsonify({
                "success": True,
                "message": "No unread event notifications found",
                "count": 0
            })
        
        # Mark all event notifications as read
        batch = db.batch()
        now = datetime.now().isoformat()
        
        for notification_id in event_ids:
            doc_ref = notifications_ref.document(notification_id)
            batch.update(doc_ref, {
                'isRead': True,
                'updatedAt': now
            })
        
        # Commit the batch update
        batch.commit()
        
        logger.info(f"Successfully marked {count} event notifications as read for {email}")
        logger.info(f"====== MARK EVENTS READ REQUEST END ======")
        
        return jsonify({
            "success": True,
            "message": f"Successfully marked {count} event notifications as read",
            "count": count
        })
        
    except Exception as e:
        logger.error(f"Error marking event notifications as read: {str(e)}", exc_info=True)
        logger.info(f"====== MARK EVENTS READ REQUEST END ======")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/notifications/<email>/mark-invitations-read', methods=['POST'])
def mark_invitations_notifications_read(email):
    """
    Mark all invitation notifications as read for a specific user.
    
    Args:
        email (str): User's email address
    
    Returns:
        JSON with success status and count of notifications marked as read
    """
    try:
        logger.info(f"====== MARK INVITATIONS READ REQUEST START ======")
        logger.info(f"Marking all invitation notifications as read for user: {email}")
        
        if not email:
            logger.warning("Email parameter is missing")
            return jsonify({
                "success": False,
                "message": "Email is required"
            }), 400
        
        # Get reference to user's notifications collection
        notifications_ref = db.collection('user_profiles').document(email).collection('notifications')
        
        # Get all unread invitation notifications
        unread_invitations = notifications_ref.where('isRead', '==', False).where('type', '==', 'invitation').get()
        
        # Get the IDs of unread invitation notifications
        invitation_ids = [doc.id for doc in unread_invitations]
        count = len(invitation_ids)
        
        if count == 0:
            return jsonify({
                "success": True,
                "message": "No unread invitation notifications found",
                "count": 0
            })
        
        # Mark all invitation notifications as read
        batch = db.batch()
        now = datetime.now().isoformat()
        
        for notification_id in invitation_ids:
            doc_ref = notifications_ref.document(notification_id)
            batch.update(doc_ref, {
                'isRead': True,
                'updatedAt': now
            })
        
        # Commit the batch update
        batch.commit()
        
        logger.info(f"Successfully marked {count} invitation notifications as read for {email}")
        logger.info(f"====== MARK INVITATIONS READ REQUEST END ======")
        
        return jsonify({
            "success": True,
            "message": f"Successfully marked {count} invitation notifications as read",
            "count": count
        })
        
    except Exception as e:
        logger.error(f"Error marking invitation notifications as read: {str(e)}", exc_info=True)
        logger.info(f"====== MARK INVITATIONS READ REQUEST END ======")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/notifications/<email>/mark-classifieds-read', methods=['POST'])
def mark_classifieds_notifications_read(email):
    """
    Mark all classified notifications as read for a specific user.
    
    Args:
        email (str): User's email address
    
    Returns:
        JSON with success status and count of notifications marked as read
    """
    try:
        logger.info(f"====== MARK CLASSIFIEDS READ REQUEST START ======")
        logger.info(f"Marking all classified notifications as read for user: {email}")
        
        if not email:
            logger.warning("Email parameter is missing")
            return jsonify({
                "success": False,
                "message": "Email is required"
            }), 400
        
        # Get reference to user's notifications collection
        notifications_ref = db.collection('user_profiles').document(email).collection('notifications')
        
        # Get all unread classified notifications
        unread_classifieds = notifications_ref.where('isRead', '==', False).where('type', '==', 'classified').get()
        
        # Get the IDs of unread classified notifications
        classified_ids = [doc.id for doc in unread_classifieds]
        count = len(classified_ids)
        
        if count == 0:
            return jsonify({
                "success": True,
                "message": "No unread classified notifications found",
                "count": 0
            })
        
        # Mark all classified notifications as read
        batch = db.batch()
        now = datetime.now().isoformat()
        
        for notification_id in classified_ids:
            doc_ref = notifications_ref.document(notification_id)
            batch.update(doc_ref, {
                'isRead': True,
                'updatedAt': now
            })
        
        # Commit the batch update
        batch.commit()
        
        logger.info(f"Successfully marked {count} classified notifications as read for {email}")
        logger.info(f"====== MARK CLASSIFIEDS READ REQUEST END ======")
        
        return jsonify({
            "success": True,
            "message": f"Successfully marked {count} classified notifications as read",
            "count": count
        })
        
    except Exception as e:
        logger.error(f"Error marking classified notifications as read: {str(e)}", exc_info=True)
        logger.info(f"====== MARK CLASSIFIEDS READ REQUEST END ======")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

if __name__ == '__main__':
    print("Starting Flask server with SocketIO...")
    # Use SocketIO instead of app.run() for WebSocket support
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
