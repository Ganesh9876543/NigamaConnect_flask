from flask import Flask, request, jsonify
from firebase_admin import credentials, initialize_app, firestore
from datetime import datetime
import uuid
import os
import logging
from werkzeug.utils import secure_filename


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_all_profile_data(email, user_profiles_ref):
    """
    Helper function to fetch all profile data for a given email.
    Returns a dictionary containing:
    - Basic profile data
    - Profile image
    - Additional info
    - Uploaded photos (as a list)
    """
    try:
        # Fetch profile from Firebase
        if not user_profiles_ref:
            logger.warning("Development mode - returning mock profile data")
            return {
                "firstName": "",
                "lastName": "",
                "email": email,
                "phone": "",
                "dob": "",
                "gender": "",
                "caste": "",
                "maritalStatus": "",
                "profileImage": None,  # Mock data has no image
                "additionalInfo": {
                    "occupation": "",
                    "education": "",
                    "hometown": "",
                    "alive": None,
                    "dod": None,
                    "country": "",
                    "pincode": "",
                    "flatHouseNo": "",
                    "areaStreet": "",
                    "townCity": "",
                    "state": "",
                    "biography": "",
                    "openForWork": None
                },
                "uploadedPhotos": []  # Return an empty list for mock data
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
        
        # Fetch uploaded photos as a list
        uploaded_photos = []
        uploaded_photos_ref = user_profiles_ref.document(email).collection('additional_info').document(email).collection('uploaded_photos').stream()
        
        for photo_doc in uploaded_photos_ref:
            uploaded_photos.append({
                "id": photo_doc.id,  # Include the document ID for reference
                "imageData": photo_doc.to_dict().get('imageData')
            })
        
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
            "uploadedPhotos": uploaded_photos,  # Return as a list
          
            "familyTreeId": user_data.get('familyTreeId') or None,
            
            
        }
        
        return profile_data
    
    except Exception as e:
        logger.error(f"Error fetching all profile data: {e}")
        raise e  # Re-raise the exception to handle it in the API endpoint
