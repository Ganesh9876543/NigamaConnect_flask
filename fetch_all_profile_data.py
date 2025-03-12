from flask import Flask, request, jsonify
from firebase_admin import credentials, initialize_app, firestore
from datetime import datetime
import uuid
import os
import logging
from werkzeug.utils import secure_filename


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_all_profile_data(email,user_profiles_ref):
    """
    Helper function to fetch all profile data for a given email.
    Returns a dictionary containing:
    - Basic profile data
    - Profile image
    - Additional info
    - Uploaded photos
    """
    try:
        # Fetch profile from Firebase
        if not user_profiles_ref:
            logger.warning("Development mode - returning mock profile data")
            return {
                "firstName": "Venkateswararo",
                "lastName": "Megadula",
                "email": email,
                "phone": "+91 9032038890",
                "dob": "17/11/1986",
                "gender": "Male",
                "caste": "OC",
                "maritalStatus": "Married",
                "profileImage": None,  # Mock data has no image
                "additionalInfo": {
                    "occupation": "Software Engineer",
                    "education": "B.Tech",
                    "hometown": "Hyderabad",
                    "alive": True,
                    "dod": None,
                    "country": "India",
                    "pincode": "500001",
                    "flatHouseNo": "123",
                    "areaStreet": "Main Street",
                    "townCity": "Hyderabad",
                    "state": "Telangana",
                    "biography": "I am a software engineer.",
                    "openForWork": True
                },
                "uploadedPhotos": {
                    "uploadedphoto1": "base64_image_data_1",
                    "uploadedphoto2": "base64_image_data_2",
                    "uploadedphoto3": "base64_image_data_3"
                }
            }

        # Get user document with email as ID
        user_doc = user_profiles_ref.document(email).get()
        
        if not user_doc.exists:
            return None  # Profile not found
        
        # Get user data
        user_data = user_doc.to_dict()
        
        # Fetch profile image
        current_image_id = user_data.get('currentProfileImageId')
        profile_image_base64 = None
        
        if current_image_id:
            # Get profile image from subcollection
            image_doc = user_profiles_ref.document(email).collection('profileImages').document(current_image_id).get()
            
            if image_doc.exists:
                image_data = image_doc.to_dict()
                profile_image_base64 = image_data.get('imageData')
        
        # Fetch additional info
        additional_info = {}
        additional_info_doc = user_profiles_ref.document(email).collection('additional_info').document(email).get()
        
        if additional_info_doc.exists:
            additional_info = additional_info_doc.to_dict()
        
        # Fetch uploaded photos
        uploaded_photos = {}
        uploaded_photos_ref = user_profiles_ref.document(email).collection('additional_info').document(email).collection('uploaded_photos').stream()
        
        for photo_doc in uploaded_photos_ref:
            uploaded_photos[photo_doc.id] = photo_doc.to_dict().get('imageData')
        
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
            "profileImage": profile_image_base64,
            "additionalInfo": additional_info,
            "uploadedPhotos": uploaded_photos
        }
        
        return profile_data
    
    except Exception as e:
        logger.error(f"Error fetching all profile data: {e}")
        raise e  # Re-raise the exception to handle it in the API endpoint