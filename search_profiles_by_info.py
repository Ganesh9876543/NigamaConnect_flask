from flask import Flask, request, jsonify
from firebase_admin import credentials, initialize_app, firestore
from datetime import datetime
import uuid
import os
import logging
from werkzeug.utils import secure_filename


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



def search_profiles_by_info(first_name=None, last_name=None, email=None, phone=None, db=None):
    """
    Function to efficiently search for profiles matching any combination of:
    first name, last name, email, and phone number.
    Returns a list of matching profiles if they meet a 90% overall similarity threshold.
    
    Args:
        first_name (str, optional): First name to search for
        last_name (str, optional): Last name to search for
        email (str, optional): Email to search for
        phone (str, optional): Phone number to search for
        db: Firestore database instance
        
    Returns:
        list: List of matching profile data containing email, first name, last name, and profile image
    """
    try:
        # Check if we're in development mode
        if not db:
            logger.warning("Development mode - returning empty results for profile search")
            return []
        
        # Normalize input for comparison
        if first_name:
            first_name = first_name.lower().strip()
        if last_name:
            last_name = last_name.lower().strip()
        if email:
            email = email.lower().strip()
        if phone:
            # Remove any non-numeric characters from phone number
            phone = ''.join(filter(str.isdigit, phone))
        
        matches = []
        
        # If we have an email, try direct lookup first (most efficient)
        if email:
            doc = db.collection('user_profiles').document(email).get()
            if doc.exists:
                profile = doc.to_dict()
                
                # Get profile image
                profile_image_base64 = None
                current_image_id = profile.get('currentProfileImageId')
                
                if current_image_id:
                    image_doc = db.collection('user_profiles').document(email).collection('profileImages').document(current_image_id).get()
                    if image_doc.exists:
                        profile_image_base64 = image_doc.to_dict().get('imageData')
                
                matches.append({
                    "email": email,
                    "firstName": profile.get('firstName'),
                    "lastName": profile.get('lastName'),
                    "phone": profile.get('phone'),
                    "profileImage": profile_image_base64,
                    "similarity": 1.0  # Exact match by email
                })
                return matches  # Return early if we find an exact email match
        
        # If we have a phone number, query by phone (still very efficient)
        if phone and not matches:
            phone_query = db.collection('user_profiles').where('phone', '==', phone).limit(5).stream()
            
            for doc in phone_query:
                profile = doc.to_dict()
                profile_email = profile.get('email')
                
                # Get profile image
                profile_image_base64 = None
                current_image_id = profile.get('currentProfileImageId')
                
                if current_image_id:
                    image_doc = db.collection('user_profiles').document(profile_email).collection('profileImages').document(current_image_id).get()
                    if image_doc.exists:
                        profile_image_base64 = image_doc.to_dict().get('imageData')
                
                matches.append({
                    "email": profile_email,
                    "firstName": profile.get('firstName'),
                    "lastName": profile.get('lastName'),
                    "phone": phone,
                    "profileImage": profile_image_base64,
                    "similarity": 1.0  # Exact match by phone
                })
            
            if matches:
                return matches  # Return early if we find exact phone matches
        
        # If still no matches, use name-based search with limits
        if (first_name or last_name) and not matches:
            # Query optimization - use the more specific field if available
            if first_name and not last_name:
                name_query = db.collection('user_profiles').filter('firstName', '==', first_name.capitalize()).limit(50).stream()
            elif last_name and not first_name:
                name_query = db.collection('user_profiles').filter('firstName', '==', first_name.capitalize()).limit(50).stream()
            else:
                # If both names provided, start with first name for better efficiency
                name_query = db.collection('user_profiles').filter('firstName', '==', first_name.capitalize()).limit(50).stream()
            
            # Process first batch of results
            for doc in name_query:
                profile = doc.to_dict()
                profile_email = profile.get('email')
                profile_first_name = profile.get('firstName', '').lower().strip()
                profile_last_name = profile.get('lastName', '').lower().strip()
                profile_phone = profile.get('phone', '')
                
                # Calculate similarity scores based on available criteria
                similarity_scores = []
                
                if first_name and profile_first_name:
                    similarity_scores.append(calculate_similarity(first_name, profile_first_name))
                
                if last_name and profile_last_name:
                    similarity_scores.append(calculate_similarity(last_name, profile_last_name))
                
                if email and profile_email:
                    similarity_scores.append(calculate_similarity(email, profile_email.lower()))
                
                if phone and profile_phone:
                    # Normalize phone numbers for comparison
                    profile_phone_digits = ''.join(filter(str.isdigit, profile_phone))
                    if phone == profile_phone_digits:
                        similarity_scores.append(1.0)  # Exact phone match
                    else:
                        # Partial phone match
                        similarity_scores.append(0.5)
                
                # Calculate overall similarity as average of individual scores
                if similarity_scores:
                    overall_similarity = sum(similarity_scores) / len(similarity_scores)
                    
                    # If similarity is 90% or higher, consider it a match
                    if overall_similarity >= 0.9:
                        # Get profile image
                        profile_image_base64 = None
                        current_image_id = profile.get('currentProfileImageId')
                        
                        if current_image_id:
                            image_doc = db.collection('user_profiles').document(profile_email).collection('profileImages').document(current_image_id).get()
                            if image_doc.exists:
                                profile_image_base64 = image_doc.to_dict().get('imageData')
                        
                        matches.append({
                            "email": profile_email,
                            "firstName": profile.get('firstName'),
                            "lastName": profile.get('lastName'),
                            "phone": profile.get('phone'),
                            "profileImage": profile_image_base64,
                            "similarity": overall_similarity
                        })
            
            # If no matches from the first query and we provided both names, try with last name
            if not matches and first_name and last_name:
                name_query = db.collection('user_profiles').where('lastName', '==', last_name.capitalize()).limit(50).stream()
                
                # Process same as above
                for doc in name_query:
                    profile = doc.to_dict()
                    profile_email = profile.get('email')
                    profile_first_name = profile.get('firstName', '').lower().strip()
                    profile_last_name = profile.get('lastName', '').lower().strip()
                    profile_phone = profile.get('phone', '')
                    
                    # Calculate similarity scores
                    similarity_scores = []
                    
                    if first_name and profile_first_name:
                        similarity_scores.append(calculate_similarity(first_name, profile_first_name))
                    
                    if last_name and profile_last_name:
                        similarity_scores.append(calculate_similarity(last_name, profile_last_name))
                    
                    if email and profile_email:
                        similarity_scores.append(calculate_similarity(email, profile_email.lower()))
                    
                    if phone and profile_phone:
                        profile_phone_digits = ''.join(filter(str.isdigit, profile_phone))
                        if phone == profile_phone_digits:
                            similarity_scores.append(1.0)
                        else:
                            similarity_scores.append(0.5)
                    
                    if similarity_scores:
                        overall_similarity = sum(similarity_scores) / len(similarity_scores)
                        
                        if overall_similarity >= 0.9:
                            # Get profile image
                            profile_image_base64 = None
                            current_image_id = profile.get('currentProfileImageId')
                            
                            if current_image_id:
                                image_doc = db.collection('user_profiles').document(profile_email).collection('profileImages').document(current_image_id).get()
                                if image_doc.exists:
                                    profile_image_base64 = image_doc.to_dict().get('imageData')
                            
                            matches.append({
                                "email": profile_email,
                                "firstName": profile.get('firstName'),
                                "lastName": profile.get('lastName'),
                                "phone": profile.get('phone'),
                                "profileImage": profile_image_base64,
                                "similarity": overall_similarity
                            })
        
        # Sort matches by similarity (highest first)
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        return matches
    
    except Exception as e:
        logger.error(f"Error searching profiles: {e}")
        raise e

def calculate_similarity(str1, str2):
    """Optimized similarity calculation"""
    if not str1 and not str2:
        return 1.0
    
    if not str1 or not str2:
        return 0.0
    
    if str1 == str2:
        return 1.0
    
    # Use set operations for faster character comparison
    str1_set = set(str1)
    str2_set = set(str2)
    
    # Calculate Jaccard similarity
    intersection = len(str1_set.intersection(str2_set))
    union = len(str1_set.union(str2_set))
    
    return intersection / union if union > 0 else 0.0