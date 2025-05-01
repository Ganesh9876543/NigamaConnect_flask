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

def update_profile_in_firebase(email, data, user_profiles_ref,db):
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
        
        # Get Firestore client for family tree updates
        

        # Store the key profile fields that will be synchronized with family trees
        first_name = data.get('firstName')
        last_name = data.get('lastName')
        phone = data.get('phone')
        gender = data.get('gender')

        # Update basic profile data
        basic_profile_data = {
            "firstName": first_name,
            "lastName": last_name,
            "phone": phone,
            "DOB": data.get('dob'),
            "GENDER": gender.lower(),
          
          
        }
        user_ref.update(basic_profile_data)

        # Update profile image (if provided)
        profile_image_data = None
        if data.get('profileImage'):
            current_image_id = str(uuid.uuid4())  # Generate a unique ID for the image
            profile_image_data = data.get('profileImage')
            user_ref.collection('profileImages').document(current_image_id).set({
                "imageData": profile_image_data
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
        
        # Update user in family tree if they exist there
        trees_updated = update_user_in_family_tree(
            db=db,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            gender=gender,
            profile_image=profile_image_data
        )

        return {
            "success": True,
            "message": f"Profile updated successfully. Updated in {trees_updated} family trees.",
            "email": email,
            "familyTreesUpdated": trees_updated
        }

    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def update_user_in_family_tree(db, email, first_name, last_name, phone, gender, profile_image):
    """
    Update a user's details in ALL family trees where they exist.
    Searches across all family trees for nodes with the specified email and updates their details.
    
    :param db: Firestore database instance
    :param email: User's email (used to find them in family trees)
    :param first_name: User's first name
    :param last_name: User's last name
    :param phone: User's phone number
    :param gender: User's gender
    :param profile_image: User's profile image data
    """
    try:
        # Query all family trees
        family_trees_ref = db.collection('family_tree')
        family_trees = family_trees_ref.stream()
        
        update_count = 0
        
        # Loop through all family trees
        for tree_doc in family_trees:
            tree_id = tree_doc.id
            tree_data = tree_doc.to_dict()
            family_members = tree_data.get('familyMembers', [])
            
            # Check if any members in this tree have the specified email
            updated = False
            for i, member in enumerate(family_members):
                if member.get('email') == email:
                    logger.info(f"Found user {email} in family tree {tree_id}, updating details")
                    
                    # Create full name
                    full_name = f"{first_name} {last_name}".strip()
                    
                    # Update member details
                    family_members[i]['name'] = full_name
                    family_members[i]['firstName'] = first_name
                    family_members[i]['lastName'] = last_name
                    
                    if phone:
                        family_members[i]['phone'] = phone
                    
                    if gender:
                        family_members[i]['gender'] = gender.lower()
                    
                    if profile_image:
                        # Add base64 prefix if not already present
                        if profile_image and not profile_image.startswith('data:'):
                            logger.info(f"Adding base64 prefix to profile image for user: {email}")
                            family_members[i]['profileImage'] = 'data:image/jpeg;base64,' + profile_image
                        else:
                            family_members[i]['profileImage'] = profile_image
                    
                    updated = True
            
            # If any members were updated, save the changes
            if updated:
                family_trees_ref.document(tree_id).update({
                    'familyMembers': family_members
                })
                update_count += 1
        
        logger.info(f"Updated user {email} in {update_count} family trees")
        return update_count
        
    except Exception as e:
        logger.error(f"Error updating user in family trees: {e}")
        # We don't want to fail the entire profile update if family tree update fails
        # So we just log the error and continue
        return 0
