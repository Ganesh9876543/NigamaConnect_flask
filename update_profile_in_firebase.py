from flask import Flask, request, jsonify
from firebase_admin import credentials, initialize_app, firestore
from datetime import datetime
import uuid
import os
import logging
from werkzeug.utils import secure_filename


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import uuid

def update_profile_in_firebase(email, data, user_profiles_ref):
    """
    Core function to update profile details in Firebase.
    
    :param email: The email of the user (used as the document ID).
    :param data: The JSON data containing updated profile details.
    :param user_profiles_ref: Reference to the Firestore collection for user profiles.
    :return: A dictionary with success status and message or error.
    """
    try:
        # Reference to the user document
        user_ref = user_profiles_ref.document(email)

        # Update basic profile data
        basic_profile_data = {
            "firstName": data.get('firstName'),
            "lastName": data.get('lastName'),
            "phone": data.get('phone'),
            "DOB": data.get('dob'),
            "GENDER": data.get('gender'),
            "CASTE": data.get('caste'),
            "MARITAL_STATUS": data.get('maritalStatus')
        }
        user_ref.update(basic_profile_data)

        # Update profile image (if provided)
        if data.get('profileImage'):
            current_image_id = str(uuid.uuid4())  # Generate a unique ID for the image
            user_ref.collection('profileImages').document(current_image_id).set({
                "imageData": data.get('profileImage')
            })
            user_ref.update({"currentProfileImageId": current_image_id})

        # Update additional info (if provided)
        additional_info = data.get('additionalInfo')
        if additional_info:
            user_ref.collection('additional_info').document(email).set(additional_info, merge=True)

        # Update uploaded photos (if provided)
        uploaded_photos = data.get('uploadedPhotos')
        if uploaded_photos is not None:  # Check if the field is provided (even if empty)
            # Delete existing uploaded photos
            photos_collection_ref = user_ref.collection('additional_info').document(email).collection('uploaded_photos')
            existing_photos = photos_collection_ref.stream()
            for photo in existing_photos:
                photo.reference.delete()

            # Add new uploaded photos
            for photo in uploaded_photos:
                photo_id = photo.get('id', str(uuid.uuid4()))  # Use provided ID or generate a new one
                photos_collection_ref.document(photo_id).set({
                    "imageData": photo.get('imageData')
                })

        return {
            "success": True,
            "message": "Profile updated successfully",
            "email": email
        }

    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        return {
            "success": False,
            "error": str(e)
        }
