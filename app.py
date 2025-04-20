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
import hashlib
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
        family_tree_ref = db.collection('family_tree')  # Top-level collection
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
        return jsonify({'image': img_base64})
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error generating family tree: {str(e)}\n{error_details}")
        return jsonify({'error': str(e), 'details': error_details}), 500


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
    Takes family members data and a family tree ID.
    Updates the family tree ID for each member based on their email.
    """
    try:
        data = request.json
        family_members = data.get('familyMembers', [])
        new_family_tree_id = data.get('familyTreeId')

        if not family_members or not new_family_tree_id:
            return jsonify({
                "success": False,
                "error": "Family members data and family tree ID are required"
            }), 400

        logger.info(f"Received request to update family tree members with ID: {new_family_tree_id}")

        for member in family_members:
            email = member.get('email')
            if email:
                # Fetch the user document for the member
                user_doc = user_profiles_ref.document(email).get()

                if user_doc.exists:
                    # Update the family tree ID for this member
                    user_profiles_ref.document(email).set({
                        'familyTreeId': new_family_tree_id,
                        'updatedAt': datetime.now().isoformat()
                    }, merge=True)
                    logger.info(f"Updated family tree ID for {email} to {new_family_tree_id}")
                else:
                    logger.warning(f"User with email {email} not found. Skipping update.")

        return jsonify({
            "success": True,
            "message": "Family tree IDs updated successfully for all members"
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
        # wife_family_tree_id = data.get("wifeFamilyTreeId")
        # wife_email = data.get("wifeEmail")
        # wife_node_id = data.get('wifeNodeId')
        # husband_family_tree_id = data.get('husbandFamilyTreeId')
        # husband_email = data.get('husbandEmail')
        # husband_node_id = data.get('husbandMemberId')
        
        wife_family_tree_id = data["wifeFamilyTreeId"]
        wife_email = data["wifeEmail"]
        wife_node_id = data['wifeNodeId']
        husband_family_tree_id = data['husbandFamilyTreeId']
        husband_email = data['husbandEmail']
        husband_node_id = data['husbandMemberId']
        
        print(wife_email)
        
        # Fetch user profiles
        wife_profile_doc = user_profiles_ref.document(wife_email).get() if wife_email else None
        if not wife_profile_doc or not wife_profile_doc.exists:
            return jsonify({
                "success": False,
                "message": f"Wife profile not found for email {wife_email}"
            }), 404
            
        print("k")
        
        wife_profile = wife_profile_doc.to_dict()
        wife_first_name = wife_profile.get('firstName', 'Unknown')
        wife_last_name = wife_profile.get('lastName', 'Unknown')
        current_image_id = wife_profile.get('currentProfileImageId')
        wife_profile_data = user_profiles_ref.document(wife_email)\
                      .collection('profileImages')\
                      .document(current_image_id)\
                      .get()
                      
        wife_image_data = wife_profile_data.to_dict().get('imageData')
        if wife_image_data:
            wife_image_data = f"data:image/jpeg;base64,{wife_image_data}"
        
        

        husband_profile_doc = user_profiles_ref.document(husband_email).get() if husband_email else None
        if not husband_profile_doc or not husband_profile_doc.exists:
            return jsonify({
                "success": False,
                "message": f"Husband profile not found for email {husband_email}"
            }), 404
        husband_profile = husband_profile_doc.to_dict()
        husband_first_name = husband_profile.get('firstName', 'Unknown')
        husband_last_name = husband_profile.get('lastName', 'Doe')
        hus_current_image_id = husband_profile.get('currentProfileImageId')
        hus_profile_data = user_profiles_ref.document(husband_email)\
                      .collection('profileImages')\
                      .document(hus_current_image_id)\
                      .get()
                      
        husband_image_data = hus_profile_data.to_dict().get('imageData')
        if husband_image_data:
            husband_image_data = f"data:image/jpeg;base64,{husband_image_data}"

        # Helper function to create complete mini-tree with spouse
        def create_complete_mini_tree(member_list, member_id, spouse_details=None):
            members = {member.get('id'): member for member in member_list}
            if member_id not in members:
                return {}
            
            member = members[member_id]
            mini_tree = {
                member_id: {**member, "isSelf": True}
            }
            
            # Add spouse if provided
            if spouse_details:
                spouse_id = f"spouse_{member_id}"
                mini_tree[spouse_id] = {
                    **spouse_details,
                    "id": spouse_id,
                    "isSelf": False,
                    "spouse": member_id
                }
                mini_tree[member_id]["spouse"] = spouse_id
            
            # Add parents
            parent_id = member.get('parentId')
            if parent_id and parent_id in members:
                mini_tree[parent_id] = {**members[parent_id], "isSelf": False}
                
                # Add parent's spouse
                parent_spouse_id = members[parent_id].get('spouse')
                if parent_spouse_id and parent_spouse_id in members:
                    mini_tree[parent_spouse_id] = {**members[parent_spouse_id], "isSelf": False}
            
            # Add siblings and their spouses
            if parent_id:
                for node_id, node in members.items():
                    if node.get('parentId') == parent_id and node_id != member_id:
                        mini_tree[node_id] = {**node, "isSelf": False}
                        
                        sibling_spouse_id = node.get('spouse')
                        if sibling_spouse_id and sibling_spouse_id in members:
                            mini_tree[sibling_spouse_id] = {**members[sibling_spouse_id], "isSelf": False}
            
            return mini_tree

        # --- Scenario 1: Neither has family tree ---
        if not wife_family_tree_id and not husband_family_tree_id:
            print("scenario 1")
            new_family_tree_id = str(uuid.uuid4())
            husband_node_id = "1"
            wife_node_id = "2"

            husband_details = {
                "id": husband_node_id,
                "name": f"{husband_first_name} {husband_last_name}",
                "firstName": husband_first_name,
                "lastName": husband_last_name,
                "email": husband_email,
                "phone": husband_profile.get('phone', ''),
                "gender": "male",
                "generation": 0,
                "parentId": None,
                "spouse": wife_node_id,
                "profileImage":husband_image_data,
                "birthOrder": 1,
                "isSelf": True
            }
            wife_details = {
                "id": wife_node_id,
                "name": f"{wife_first_name} {husband_last_name}",
                "firstName": wife_first_name,
                "lastName": husband_last_name,
                "email": wife_email,
                "phone": wife_profile.get('phone', ''),
                "gender": "female",
                "generation": 0,
                "parentId": None,
                "spouse": husband_node_id,
                "profileImage":wife_image_data,
                "birthOrder": 1,
                "isSelf": False
            }

            family_tree_ref.document(new_family_tree_id).set({
                "familyMembers": [husband_details, wife_details],
                "relatives": {}
            })

            user_profiles_ref.document(wife_email).set({
                "familyTreeId": new_family_tree_id,
                "oldFamilyTreeId": None,
                "lastName": husband_last_name,
                "MARITAL_STATUS": "Married",
                "updatedAt": datetime.now().isoformat()
            }, merge=True)
            user_profiles_ref.document(husband_email).set({
                "familyTreeId": new_family_tree_id,
                "oldFamilyTreeId": None,
                "MARITAL_STATUS": "Married",
                "updatedAt": datetime.now().isoformat()
            }, merge=True)

            return jsonify({
                "success": True,
                "message": "New family tree created",
                "familyTreeId": new_family_tree_id
            })

        # --- Scenario 2: Only wife has family tree ---
        elif not husband_family_tree_id and wife_family_tree_id:
            print("scenario 2")
            wife_family_tree_doc = family_tree_ref.document(wife_family_tree_id).get()
            if not wife_family_tree_doc.exists:
                return jsonify({
                    "success": False,
                    "message": f"Wife's family tree not found: {wife_family_tree_id}"
                }), 404
                
            wife_family_tree = wife_family_tree_doc.to_dict()
            wife_members_list = wife_family_tree.get('familyMembers', [])
            wife_members_dict = {member.get('id'): member for member in wife_members_list}

            if wife_node_id not in wife_members_dict:
                return jsonify({
                    "success": False,
                    "message": f"Wife node ID {wife_node_id} not found"
                }), 404
                
            wife_details = wife_members_dict[wife_node_id]

            # Create husband mini-tree with wife included
            husband_details_for_mini = {
                "name": f"{husband_first_name} {husband_last_name}",
                "firstName": husband_first_name,
                "lastName": husband_last_name,
                "email": husband_email,
                "gender": "male",
                "profileImage": husband_image_data
            }
            
            wife_mini_tree = create_complete_mini_tree(
                wife_members_list,
                wife_node_id,
                spouse_details=husband_details_for_mini
            )

            new_family_tree_id = str(uuid.uuid4())
            husband_node_id = "1"
            new_wife_node_id = "2"

            husband_details = {
                "id": husband_node_id,
                "name": f"{husband_first_name} {husband_last_name}",
                "firstName": husband_first_name,
                "lastName": husband_last_name,
                "email": husband_email,
                "phone": husband_profile.get('phone', ''),
                "gender": "male",
                "generation": wife_details.get('generation', 0),
                "parentId": None,
                "spouse": new_wife_node_id,
                "profileImage": husband_image_data,
                "birthOrder": 1,
                "isSelf": True
            }
            new_wife_details = {
                "id": new_wife_node_id,
                "name": f"{wife_first_name} {husband_last_name}",
                "firstName": wife_first_name,
                "lastName": husband_last_name,
                "email": wife_email,
                "phone": wife_details.get('phone', ''),
                "gender": "female",
                "generation": wife_details.get('generation', 0),
                "parentId": None,
                "spouse": husband_node_id,
                "profileImage": wife_image_data,
                "birthOrder": wife_details.get('birthOrder', 1),
                "isSelf": False
            }

            family_tree_ref.document(new_family_tree_id).set({
                "familyMembers": [husband_details, new_wife_details],
                "relatives": {
                    new_wife_node_id: wife_mini_tree
                }
            })

            # Update wife's original tree with husband's mini-tree
            husband_mini_tree = {
                "1": {
                    "id": "1",
                    "name": f"{husband_first_name} {husband_last_name}",
                    "firstName": husband_first_name,
                    "lastName": husband_last_name,
                    "email": husband_email,
                    "gender": "male",
                    "spouse": "2",
                    "profileImage": husband_image_data,
                    "isSelf": True
                },
                "2": {
                    "id": "2",
                    "name": f"{wife_first_name} {husband_last_name}",
                    "firstName": wife_first_name,
                    "lastName": husband_last_name,
                    "email": wife_email,
                    "gender": "female",
                    "spouse": "1",
                    "profileImage": wife_image_data,
                    "isSelf": False
                }
            }
            
            wife_relatives = wife_family_tree.get('relatives', {})
            wife_relatives[wife_node_id] = husband_mini_tree
            
            for i, member in enumerate(wife_members_list):
                if member.get('id') == wife_node_id:
                    wife_members_list[i]['spouse'] = new_family_tree_id
                    wife_members_list[i]['lastName'] = husband_last_name
                    break
            
            family_tree_ref.document(wife_family_tree_id).set({
                "familyMembers": wife_members_list,
                "relatives": wife_relatives
            })

            # Update user profiles
            user_profiles_ref.document(wife_email).set({
                "familyTreeId": new_family_tree_id,
                "oldFamilyTreeId": wife_family_tree_id,
                "lastName": husband_last_name,
                "MARITAL_STATUS": "Married",
                "updatedAt": datetime.now().isoformat()
            }, merge=True)
            user_profiles_ref.document(husband_email).set({
                "familyTreeId": new_family_tree_id,
                "oldFamilyTreeId": None,
                "MARITAL_STATUS": "Married",
                "updatedAt": datetime.now().isoformat()
            }, merge=True)

            return jsonify({
                "success": True,
                "message": "New family tree created for husband",
                "familyTreeId": new_family_tree_id
            })

        # --- Scenario 3: Only husband has family tree ---
        elif husband_family_tree_id and not wife_family_tree_id:
            print("scenario 3")
            husband_family_tree_doc = family_tree_ref.document(husband_family_tree_id).get()
            if not husband_family_tree_doc.exists:
                return jsonify({
                    "success": False,
                    "message": f"Husband's family tree not found: {husband_family_tree_id}"
                }), 404
                
            husband_family_tree = husband_family_tree_doc.to_dict()
            husband_members_list = husband_family_tree.get('familyMembers', [])
            husband_members_dict = {member.get('id'): member for member in husband_members_list}

            if husband_node_id not in husband_members_dict:
                return jsonify({
                    "success": False,
                    "message": f"Husband node ID {husband_node_id} not found"
                }), 404
                
            husband_details = husband_members_dict[husband_node_id]

            # Create wife mini-tree with husband included
            wife_details_for_mini = {
                "name": f"{wife_first_name} {husband_last_name}",
                "firstName": wife_first_name,
                "lastName": husband_last_name,
                "email": wife_email,
                "gender": "female",
                "profileImage": wife_image_data
            }
            
            husband_mini_tree = create_complete_mini_tree(
                husband_members_list,
                husband_node_id,
                spouse_details=wife_details_for_mini
            )

            new_wife_node_id = str(len(husband_members_list) + 1)
            wife_details = {
                "id": new_wife_node_id,
                "name": f"{wife_first_name} {husband_last_name}",
                "firstName": wife_first_name,
                "lastName": husband_last_name,
                "email": wife_email,
                "phone": wife_profile.get('phone', ''),
                "gender": "female",
                "generation": husband_details.get('generation', 0),
                "parentId": None,
                "spouse": husband_node_id,
                "profileImage": wife_image_data,
                "birthOrder": 1,
                "isSelf": False
            }

            # Update husband's spouse reference
            for i, member in enumerate(husband_members_list):
                if member.get('id') == husband_node_id:
                    husband_members_list[i]['spouse'] = new_wife_node_id
                    break
                    
            husband_members_list.append(wife_details)
            
            # Create wife's mini-tree for relatives
            wife_mini_tree = {
                "1": {
                    "id": "1",
                    "name": f"{wife_first_name} {husband_last_name}",
                    "firstName": wife_first_name,
                    "lastName": husband_last_name,
                    "email": wife_email,
                    "gender": "female",
                    "profileImage":wife_image_data,
                    "isSelf": True
                },
                "2": {
                    "id": "2",
                    "name": f"{husband_first_name} {husband_last_name}",
                    "firstName": husband_first_name,
                    "lastName": husband_last_name,
                    "email": husband_email,
                    "gender": "male",
                    "profileImage": husband_image_data,
                    "isSelf": False,
                    "spouse": "1"
                }
            }
            
            husband_relatives = husband_family_tree.get('relatives', {})
            husband_relatives[new_wife_node_id] = wife_mini_tree
            
            family_tree_ref.document(husband_family_tree_id).set({
                "familyMembers": husband_members_list,
                "relatives": husband_relatives
            })

            # Update user profiles
            user_profiles_ref.document(wife_email).set({
                "familyTreeId": husband_family_tree_id,
                "oldFamilyTreeId": None,
                "lastName": husband_last_name,
                "MARITAL_STATUS": "Married",
                "updatedAt": datetime.now().isoformat()
            }, merge=True)
            user_profiles_ref.document(husband_email).set({
                "MARITAL_STATUS": "Married",
                "updatedAt": datetime.now().isoformat()
            }, merge=True)

            return jsonify({
                "success": True,
                "message": "Wife added to husband's family tree",
                "familyTreeId": husband_family_tree_id
            })

        # --- Scenario 4: Both have family trees ---
        # --- Scenario 4: Both have family trees ---
        else:
            print("Scenario 4: Both wife and husband have family trees")
            
            # Validate wife's family tree
            wife_family_tree_doc = family_tree_ref.document(wife_family_tree_id).get()
            if not wife_family_tree_doc.exists:
                return jsonify({
                    "success": False,
                    "message": f"Wife's family tree not found: {wife_family_tree_id}"
                }), 404
                
            wife_family_tree = wife_family_tree_doc.to_dict()
            wife_members_list = wife_family_tree.get('familyMembers', [])
            wife_members_dict = {member.get('id'): member for member in wife_members_list}
            
            if wife_node_id not in wife_members_dict:
                return jsonify({
                    "success": False,
                    "message": f"Wife node ID {wife_node_id} not found"
                }), 404
                
            wife_details = wife_members_dict[wife_node_id]
            
            # Validate husband's family tree
            husband_family_tree_doc = family_tree_ref.document(husband_family_tree_id).get()
            if not husband_family_tree_doc.exists:
                return jsonify({
                    "success": False,
                    "message": f"Husband's family tree not found: {husband_family_tree_id}"
                }), 404
                
            husband_family_tree = husband_family_tree_doc.to_dict()
            husband_members_list = husband_family_tree.get('familyMembers', [])
            husband_members_dict = {member.get('id'): member for member in husband_members_list}
            
            if husband_node_id not in husband_members_dict:
                return jsonify({
                    "success": False,
                    "message": f"Husband node ID {husband_node_id} not found"
                }), 404
                
            husband_details = husband_members_dict[husband_node_id]
            
            # Create spouse details for mini-trees
            wife_details_for_husband = {
                "name": f"{wife_first_name} {husband_last_name}",
                "firstName": wife_first_name,
                "lastName": husband_last_name,
                "email": wife_email,
                "gender": "female",
                "profileImage": wife_image_data,
                "phone": wife_profile.get('phone', '')
            }
            
            husband_details_for_wife = {
                "name": f"{husband_first_name} {husband_last_name}",
                "firstName": husband_first_name,
                "lastName": husband_last_name,
                "email": husband_email,
                "gender": "male",
                "profileImage": husband_image_data,
                "phone": husband_profile.get('phone', '')
            }
            
            # Create complete mini-trees including spouses
            wife_mini_tree = create_complete_mini_tree(
                wife_members_list,
                wife_node_id,
                spouse_details=husband_details_for_wife
            )
            
            husband_mini_tree = create_complete_mini_tree(
                husband_members_list,
                husband_node_id,
                spouse_details=wife_details_for_husband
            )
            
            print(f"Created wife mini-tree with {len(wife_mini_tree)} members")
            print(f"Created husband mini-tree with {len(husband_mini_tree)} members")
            
            # Add wife to husband's family tree
            new_wife_node_id = str(len(husband_members_list) + 1)
            new_wife_details = {
                "id": new_wife_node_id,
                "name": f"{wife_first_name} {husband_last_name}",
                "firstName": wife_first_name,
                "lastName": husband_last_name,
                "email": wife_email,
                "phone": wife_details.get('phone', ''),
                "gender": "female",
                "generation": wife_details.get('generation', 0),
                "parentId": None,
                "spouse": husband_node_id,
                "profileImage": wife_image_data,
                "birthOrder": wife_details.get('birthOrder', 1),
                "isSelf": False
            }
            
            # Update husband's spouse reference
            for i, member in enumerate(husband_members_list):
                if member.get('id') == husband_node_id:
                    husband_members_list[i]['spouse'] = new_wife_node_id
                    break
                    
            # Add wife to husband's family members
            husband_members_list.append(new_wife_details)
            
            # Update husband's relatives with wife's mini-tree
            husband_relatives = husband_family_tree.get('relatives', {})
            husband_relatives[new_wife_node_id] = wife_mini_tree
            
            # Update husband's family tree
            family_tree_ref.document(husband_family_tree_id).update({
                "familyMembers": husband_members_list,
                "relatives": husband_relatives
            })
            
            # Add husband to wife's family tree
            new_husband_node_id = str(len(wife_members_list) + 1)
            new_husband_details = {
                "id": new_husband_node_id,
                "name": f"{husband_first_name} {husband_last_name}",
                "firstName": husband_first_name,
                "lastName": husband_last_name,
                "email": husband_email,
                "phone": husband_details.get('phone', ''),
                "gender": "male",
                "generation": husband_details.get('generation', 0),
                "parentId": None,
                "spouse": wife_node_id,
                "profileImage": husband_image_data,
                "birthOrder": husband_details.get('birthOrder', 1),
                "husbandNodeIdInFamilyTree": husband_node_id,
                "husbandFamilyTreeId": husband_family_tree_id,
                "isSelf": False
            }
            
            # Update wife's spouse reference
            for i, member in enumerate(wife_members_list):
                if member.get('id') == wife_node_id:
                    wife_members_list[i]['spouse'] = new_husband_node_id
                    wife_members_list[i]['lastName'] = husband_last_name
                    break
                    
            # Add husband to wife's family members
            wife_members_list.append(new_husband_details)
            
            # Update wife's relatives with husband's mini-tree
            wife_relatives = wife_family_tree.get('relatives', {})
            wife_relatives[new_husband_node_id] = husband_mini_tree
            
            # Update wife's family tree
            family_tree_ref.document(wife_family_tree_id).update({
                "familyMembers": wife_members_list,
                "relatives": wife_relatives
            })
            
            # Update user profiles
            user_profiles_ref.document(wife_email).update({
                "familyTreeId": husband_family_tree_id,
                "oldFamilyTreeId": wife_family_tree_id,
                "lastName": husband_last_name,
                "MARITAL_STATUS": "Married",
                "updatedAt": datetime.now().isoformat()
            })
            
            user_profiles_ref.document(husband_email).update({
                "MARITAL_STATUS": "Married",
                "updatedAt": datetime.now().isoformat()
            })
            
            return jsonify({
                "success": True,
                "message": "Spouse details added successfully with complete family mini-trees",
                "familyTreeId": husband_family_tree_id,
                "wifeFamilyTreeId": wife_family_tree_id
            })

    except Exception as e:
        logger.error(f"Error adding spouse details: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
        
        
@app.route('/api/family-tree/add-relatives', methods=['POST'])
def add_relatives():
    """
    API endpoint to add relatives to a specific node in a family tree.
    Takes a family tree ID, node ID, and relatives tree structure.
    Updates the family tree by adding the relatives to the specified node.
    """
    try:
        # Extract data from the request
        data = request.json
        print("Received data:", data)  # Log incoming data for debugging

        # Extract fields from request
        family_tree_id = data.get('familyTreeId')
        node_id = data.get('nodeId')
        relatives_tree = data.get('relativesTree')

        # Validate required fields
        if not family_tree_id or not node_id or not relatives_tree:
            print("Error: Missing required fields")
            return jsonify({
                "success": False,
                "message": "Missing required fields. Please provide familyTreeId, nodeId, and relativesTree"
            }), 400

        # Log received fields
        print(f"Received request to add relatives: "
              f"Family Tree ID: {family_tree_id}, "
              f"Node ID: {node_id}, "
              f"Relatives count: {len(relatives_tree)}")

        # Validate family tree exists
        family_tree_doc = family_tree_ref.document(family_tree_id).get()
        if not family_tree_doc.exists:
            print(f"Error: Family tree not found: {family_tree_id}")
            return jsonify({
                "success": False,
                "message": f"Family tree not found: {family_tree_id}"
            }), 404
        
        family_tree = family_tree_doc.to_dict()
        
        # Debug: Print structure of family tree
        print(f"Family tree structure: {family_tree.keys()}")
        
        # Handle both possible data structures - either directly in familyMembers or as a list
        family_members = family_tree.get('familyMembers', {})
        
        # If family_members is a list, convert to dictionary with id as key
        if isinstance(family_members, list):
            family_members_dict = {member.get('id'): member for member in family_members}
            print(f"Converted list to dict. Available IDs: {list(family_members_dict.keys())}")
            family_members = family_members_dict
        
        # Debug: Print available node IDs
        print(f"Available node IDs: {list(family_members.keys())}")
        
        # Validate node exists in the family tree
        if node_id not in family_members:
            print(f"Error: Node ID {node_id} not found in family tree. Available IDs: {list(family_members.keys())}")
            return jsonify({
                "success": False,
                "message": f"Node ID {node_id} not found in the specified family tree",
                "availableIds": list(family_members.keys())
            }), 404

        # Get or initialize the relatives section
        relatives = family_tree.get('relatives', {})
        
        # Update or create relatives entry for the specified node
        relatives[node_id] = relatives_tree
        
        # Update the family tree document
        family_tree_ref.document(family_tree_id).set({
            "relatives": relatives
        }, merge=True)
        
        print(f"Successfully added relatives to node {node_id} in family tree {family_tree_id}")
        
        # Return success response
        return jsonify({
            "success": True,
            "message": f"Relatives added successfully to node {node_id}",
            "familyTreeId": family_tree_id,
            "nodeId": node_id,
            "relativesCount": len(relatives_tree)
        })

    except Exception as e:
        logger.error(f"Error adding relatives: {e}")
        # Add more detailed error information
       
        
        return jsonify({
            "success": False,
            "error": str(e),
            
        }), 500
        
        
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
    Generate a tree visualization for a user's friends
    
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
    import shutil
    from graphviz import Digraph
    from PIL import Image, ImageDraw, ImageOps
    import io

    # Debug flag
    DEBUG = True
    
    # Make sure Graphviz is available
    try:
        from graphviz.backend import run_check
        run_check()
        print("Graphviz is available and working.")
    except Exception as e:
        print(f"WARNING: Graphviz check failed: {e}")
        
    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix='friends_tree_')
    print(f"Using temporary directory: {temp_dir}")
    
    # Create a Digraph object with simplified background
    dot = Digraph(
        comment='Friends Tree',
        format='png',
        engine='dot',
        graph_attr={
            'rankdir': 'TB',  # Top to bottom direction
            'splines': 'polyline',  # Use polyline for natural connections
            'bgcolor': 'lightblue',  # Simplified background color
            'nodesep': '0.75',  # Node separation
            'ranksep': '1.5',  # Rank separation
            'fontname': 'Arial',
            'style': 'rounded,filled',  # Add rounded style to the graph
            'color': '#000000',  # Black border color
            'penwidth': '3.0',  # Thicker border
        },
        node_attr={
            'shape': 'box',
            'style': 'filled,rounded',
            'fillcolor': 'white',
            'fontcolor': 'black',  # Black text for all nodes
            'penwidth': '2.0',
            'fontsize': '14',
            'fontname': 'Arial',
            'height': '0.6',
            'width': '1.6',
            'margin': '0.2'
        },
        edge_attr={
            'color': '#000000',  # Black color for all edges
            'penwidth': '2.0'  # Thicker edges
        }
    )

    # Create profile image node function with improved handling for different data formats
    def create_profile_image_node(profile_image_data, node_id):
        """Create a temporary profile image file from base64 data, bytes, or use default icon."""
        image_path = os.path.join(temp_dir, f'friend_profile_{node_id}.png')
        
        try:
            if profile_image_data:
                image_bytes = None
                
                # Handle different data formats
                if isinstance(profile_image_data, str):
                    # Check if it has a base64 header
                    if ',' in profile_image_data:
                        # Strip the header if present
                        _, profile_image_data = profile_image_data.split(',', 1)
                    try:
                        # Decode base64 string to bytes
                        image_bytes = base64.b64decode(profile_image_data)
                    except Exception as decode_error:
                        print(f"Error decoding base64 data: {decode_error}")
                        return None
                        
                elif isinstance(profile_image_data, bytes):
                    # Already bytes, use directly
                    image_bytes = profile_image_data
                
                # If we have valid image bytes, process them
                if image_bytes:
                    # Create a PIL Image from bytes
                    img = Image.open(io.BytesIO(image_bytes))
                    
                    # Convert to RGB if needed
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Resize to a standard size
                    img = img.resize((100, 100))
                    
                    # Make circular by creating a mask
                    mask = Image.new('L', (100, 100), 0)
                    draw = ImageDraw.Draw(mask)
                    draw.ellipse((0, 0, 100, 100), fill=255)
                    
                    # Apply the circular mask
                    img = ImageOps.fit(img, mask.size, centering=(0.5, 0.5))
                    img.putalpha(mask)
                    
                    # Save the image
                    img.save(image_path, 'PNG')
                    
                    if DEBUG:
                        print(f"Created profile image at: {image_path}")
                        print(f"Image exists: {os.path.exists(image_path)}")
                        print(f"Image size: {os.path.getsize(image_path)} bytes")
                    
                    return image_path
                else:
                    raise ValueError("Could not convert profile image data to bytes")
            
            # If we reach here, either no data was provided or processing failed
            # Create a simple profile icon using PIL
            img = Image.new('RGB', (100, 100), (204, 204, 204))
            draw = ImageDraw.Draw(img)
            # Draw a circle for the head
            draw.ellipse([25, 25, 75, 75], fill=(255, 255, 255))
            # Draw a path for the body
            draw.polygon([(50, 70), (30, 100), (70, 100)], fill=(255, 255, 255))
            img.save(image_path, 'PNG')
            
            if DEBUG:
                print(f"Created default profile image at: {image_path}")
                
            return image_path
            
        except Exception as e:
            print(f"Error creating profile image: {e}")
            import traceback
            print(traceback.format_exc())
            # Return None on error and let calling code handle the missing image
            return None

    # Create center node for the user
    user_node_id = "user"
    
    # Create user profile image node with improved handling
    print(f"User profile image type: {type(user_profile_image)}")
    if isinstance(user_profile_image, bytes):
        print(f"User profile image is in bytes format, length: {len(user_profile_image)}")
    elif isinstance(user_profile_image, str):
        print(f"User profile image is in string format, length: {len(user_profile_image)}")
    else:
        print(f"User profile image is in format: {type(user_profile_image)}")
    
    user_image_path = create_profile_image_node(user_profile_image, user_node_id)
    
    # Create a stylized label for the user node
    user_label = "<<TABLE BORDER='0' CELLBORDER='1' CELLSPACING='0' CELLPADDING='4'>"
    if user_image_path and os.path.exists(user_image_path):
        # Properly format the path for Graphviz
        image_path = os.path.abspath(user_image_path).replace('\\', '/')
        if DEBUG:
            print(f"User image path for DOT: {image_path}")
        user_label += f"<TR><TD ROWSPAN='2'><IMG SRC='{image_path}' SCALE='TRUE' WIDTH='50' HEIGHT='50'/></TD>"
    else:
        user_label += "<TR><TD ROWSPAN='2'>👤</TD>"
    
    # Add name information
    user_label += f"<TD ALIGN='LEFT'><B>{user_name}</B></TD></TR>"
    
    # Add self label
    user_label += f"<TR><TD ALIGN='LEFT'>Myself</TD></TR>"
    user_label += "</TABLE>>"
    
    # Add user node with special styling
    dot.node(
        user_node_id,
        label=user_label,
        fillcolor='#4CAF50',  # Green background for user node
        fontcolor='white',
        style='filled,rounded',
        penwidth='3.0'
    )

    # Group friends by category
    friend_categories = {}
    for friend in friends_list:
        category = friend.get('category', 'Other')
        if category not in friend_categories:
            friend_categories[category] = []
        friend_categories[category].append(friend)

    # Add invisible connection point node (center point)
    center_point_id = "center_point"
    dot.node(center_point_id, label="", shape="point", width="0.1", height="0.1", style="invis")
    
    # Connect user to center point
    dot.edge(user_node_id, center_point_id, style="dotted", arrowhead="none")

    # Category colors
    category_colors = {
        'Family': '#E6B0AA',  # Light red
        'Close Friends': '#AED6F1',  # Light blue
        'Colleagues': '#A9DFBF',  # Light green
        'Neighbors': '#F9E79F',  # Light yellow
        'School': '#D7BDE2'  # Light purple
    }

    # For each category, create a cluster and add friend nodes
    for category_index, (category, friends) in enumerate(friend_categories.items()):
        # Create a subgraph for this category to group friends
        with dot.subgraph(name=f'cluster_category_{category_index}') as c:
            c.attr(label=category, style="rounded,filled", fillcolor="#F0F0F0", fontname="Arial", fontsize="16")
            
            # Create an ordered chain within this category
            # Remove the 'rank="same"' attribute to allow vertical arrangement
            
            # Create previous node tracker for vertical connections
            prev_friend_id = None
            
            for i, friend in enumerate(friends):
                friend_id = f"friend_{category_index}_{i}"
                
                # Create friend profile image node from base64 data with improved handling
                friend_image_path = create_profile_image_node(friend.get('profileImage'), friend_id)
                
                # Create a stylized label for the friend node
                friend_label = "<<TABLE BORDER='0' CELLBORDER='1' CELLSPACING='0' CELLPADDING='4'>"
                if friend_image_path and os.path.exists(friend_image_path):
                    # Properly format the path for Graphviz
                    image_path = os.path.abspath(friend_image_path).replace('\\', '/')
                    friend_label += f"<TR><TD ROWSPAN='2'><IMG SRC='{image_path}' SCALE='TRUE' WIDTH='50' HEIGHT='50'/></TD>"
                else:
                    friend_label += "<TR><TD ROWSPAN='2'>👤</TD>"
                
                # Add name information
                friend_label += f"<TD ALIGN='LEFT'><B>{friend.get('name', 'Unknown')}</B></TD></TR>"
                
                # Add email information
                friend_label += f"<TR><TD ALIGN='LEFT'>{friend.get('email', '')}</TD></TR>"
                friend_label += "</TABLE>>"
                
                # Get fillcolor based on category
                fillcolor = category_colors.get(category, '#F5F5F5')  # Default to light gray
                
                # Add friend node with proper styling
                c.node(
                    friend_id,
                    label=friend_label,
                    fillcolor=fillcolor,
                    fontcolor='black',
                    style='filled,rounded',
                    penwidth='2.0'
                )
                
                # If this is the first friend in the category, connect it to the center point
                if i == 0:
                    dot.edge(center_point_id, friend_id, style="solid", arrowhead="none")
                
                # If there was a previous friend in this category, connect this friend below it
                if prev_friend_id:
                    # Add invisible edge to enforce vertical ordering
                    c.edge(prev_friend_id, friend_id, style="invis")
                
                # Update previous friend ID for next iteration
                prev_friend_id = friend_id

    # Add a title with a decorative border
    dot.attr(label=r'\nFriends Tree\n', fontsize="24", fontname="Arial", 
             labelloc="t", labeljust="c", 
             style="filled", fillcolor="#E0F7FA", color="#000000", penwidth="3.0")

    # Output files
    output_path = os.path.join(temp_dir, 'friends_tree')
    
    try:
        # Save DOT file for debugging
        with open(f"{output_path}.dot", 'w', encoding='utf-8') as f:
            f.write(dot.source)
        
        if DEBUG:
            print(f"DOT file saved to {output_path}.dot")
            
        # Render the graph
        dot.render(output_path, cleanup=False)
        
        if DEBUG:
            print(f"Graph rendered to {output_path}.png")
            print(f"File exists: {os.path.exists(f'{output_path}.png')}")
            print(f"File size: {os.path.getsize(f'{output_path}.png') if os.path.exists(f'{output_path}.png') else 'N/A'} bytes")
        
        # Read the image and encode it to base64
        with open(f"{output_path}.png", 'rb') as f:
            img_data = f.read()
        
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        
        if DEBUG:
            print(f"Image encoded to base64, length: {len(img_base64)}")
        
        return img_base64
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error rendering graph: {e}")
        print(error_details)
        return f"Error: {str(e)}\nDetails: {error_details}\nDOT file saved to {output_path}.dot for debugging"
    finally:
        try:
            # Clean up temporary directory
            if not DEBUG:  # Keep files if debugging
                shutil.rmtree(temp_dir)
                print(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as cleanup_error:
            print(f"Error cleaning up: {cleanup_error}")
 
from get_connections import get_user_connections
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
        }), 500

if __name__ == '__main__':
    print("Starting Flask server...")
    app.run(host='0.0.0.0', port=5000, debug=True)
