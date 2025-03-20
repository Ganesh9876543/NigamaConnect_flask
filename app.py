from flask import Flask, request, jsonify
import random
import smtplib
from email.mime.text import MIMEText
import time
from flask_cors import CORS  # Import CORS
from flask import Flask, request, jsonify
from firebase_admin import credentials, firestore, initialize_app
import os
import uuid
from datetime import datetime
from flask_cors import CORS
import logging

import json
import os


from flask import Flask, request, jsonify
from firebase_admin import credentials, initialize_app, firestore
from datetime import datetime
import uuid
import os
import logging
from werkzeug.utils import secure_filename


app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

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
    
    # Store OTP with current timestamp
    current_time = int(time.time())
    otp_storage[email] = {'otp': otp, 'timestamp': current_time}

    print(f"Generated OTP for {email}: {otp}, valid until: {current_time + OTP_EXPIRATION_TIME}")

    # Send OTP via email
    subject = 'Verify Your OTP to Access Nigama Connect'
    body = (f"Dear User,\n\n"
            f"Greetings from the Nigama Connect team!\n\n"
            f"We're thrilled to have you as a part of our family-oriented social networking platform. Nigama Connect is designed to help you trace your lineage, connect with relatives, and strengthen bonds while exploring a range of exciting features like:\n"
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



# try:
#     # Get service account key JSON from environment variable
#     firebase_config = os.environ.get('FIREBASE_SERVICE_ACCOUNT')

#     if firebase_config:
#         # Parse the JSON string from environment variable
#         service_account_info = json.loads(firebase_config)
#         cred = credentials.Certificate(service_account_info)
#         firebase_app = firebase_admin.initialize_app(cred)
#         db = firestore.client()
#         user_profiles_ref = db.collection('user_profiles')
#         logger.info("Firebase initialized successfully")
#     else:
#         raise ValueError("FIREBASE_SERVICE_ACCOUNT environment variable not set")
# except Exception as e:
#     logger.error(f"Error initializing Firebase: {e}")
#     if os.environ.get('FLASK_ENV') == 'development':
#         logger.warning("Running in development mode without Firebase")
#         firebase_app = None
#         db = None
#         user_profiles_ref = None
#     else:
#         raise


try:
    # Use the secret file path in Render's secret directory
    secret_file_path = '/etc/secrets/firebase_service_account.json'

    # Verify if the secret file exists
    if os.path.exists(secret_file_path):
        cred = credentials.Certificate(secret_file_path)
        firebase_app = initialize_app(cred)
        db = firestore.client()
        user_profiles_ref = db.collection('user_profiles')
        logger.info("Firebase initialized successfully")
    else:
        raise FileNotFoundError(f"Secret file not found at: {secret_file_path}")
except Exception as e:
    logger.error(f"Error initializing Firebase: {e}")

    # Handle development mode scenario
    if os.environ.get('FLASK_ENV') == 'development':
        logger.warning("Running in development mode without Firebase")
        firebase_app = None
        db = None
        user_profiles_ref = None
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
        email = request.args.get('email')
        
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
            # Update the document to set 'login' to true
            user_ref.update({"login": True})
            logger.info(f"Login set to true for email: {email}")
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
        result = update_profile_in_firebase(email, data, user_profiles_ref)

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

from generate_family_tree import generate_family_tree
@app.route('/generate-tree', methods=['POST'])
def generate_tree():
    data = request.get_json()
    family_members = data.get('familyMembers', [])
    
    if not family_members:
        return jsonify({'error': 'No family data provided'}), 400

    try:
        img_base64 = generate_family_tree(family_members)
        
        # Check if the result is an error message (string) or actual base64 data
        if isinstance(img_base64, str) and img_base64.startswith('Error:'):
            return jsonify({'error': img_base64}), 500
            
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



if __name__ == '__main__':
    print("Starting Flask server...")
    app.run(debug=True)
