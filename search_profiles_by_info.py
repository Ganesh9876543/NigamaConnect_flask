from flask import Flask, request, jsonify
from firebase_admin import credentials, initialize_app, firestore
from datetime import datetime
import uuid
import os
import logging
from werkzeug.utils import secure_filename
from google.cloud.firestore_v1.base_query import FieldFilter



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def search_profiles_by_info(first_name=None, last_name=None, email=None, phone=None, db=None):
    """
    Function to search for profiles matching any combination of:
    first name, last name, email, and phone number, or fetch all profiles if no parameters are provided.
    Returns all matching profiles without a similarity threshold.
    Search order: email (direct lookup), then last name, then first name, then all profiles if no filters.
    
    Args:
        first_name (str, optional): First name to search for
        last_name (str, optional): Last name to search for
        email (str, optional): Email to search for
        phone (str, optional): Phone number to search for
        db: Firestore database instance
        
    Returns:
        list: List of all matching profile data containing email, first name, last name, phone, and profile image
    """
    
    try:
        # Log input parameters
        print(f"Searching profiles with: first_name={first_name}, last_name={last_name}, email={email}, phone={phone}")
        
        # Check if we're in development mode
        if not db:
            logger.warning("Development mode - returning empty results for profile search")
            print("No database provided, returning empty list (dev mode)")
            return []
        
        # Normalize input for comparison
        if first_name:
            first_name = first_name.lower().strip()
            print(f"Normalized first_name: {first_name}")
        if last_name:
            last_name = last_name.lower().strip()
            print(f"Normalized last_name: {last_name}")
        if email:
            email = email.lower().strip()
            print(f"Normalized email: {email}")
        if phone:
            phone = ''.join(filter(str.isdigit, phone))
            print(f"Normalized phone: {phone}")
        
        matches = []
        
        # Step 1: If email is provided, do a direct lookup
        if email:
            print(f"Attempting direct email lookup for: {email}")
            doc = db.collection('user_profiles').document(email).get()
            if doc.exists:
                profile = doc.to_dict()
                
                # Get profile image
                profile_image_base64 = None
                current_image_id = profile.get('currentProfileImageId')
                
                if current_image_id:
                    print(f"Fetching profile image with ID: {current_image_id}")
                    image_doc = db.collection('user_profiles').document(email).collection('profileImages').document(current_image_id).get()
                    if image_doc.exists:
                        profile_image_base64 = image_doc.to_dict().get('imageData')
                
                matches.append({
                    "email": email,
                    "firstName": profile.get('firstName'),
                    "lastName": profile.get('lastName'),
                    "phone": profile.get('phone'),
                    "profileImage": profile_image_base64
                })
                print(f"Email match found: {email}")
                return matches  # Return immediately if email matches
        
        # Step 2: Search by last name if provided
        if last_name:
            print(f"Querying profiles by last_name: {last_name}")
            
            # Get all documents first
            all_docs = db.collection('user_profiles').stream()
            
            # Then filter by lowercase comparison
            for doc in all_docs:
                profile = doc.to_dict()
                doc_last_name = profile.get('lastName', '').lower().strip()
                
                if doc_last_name == last_name:
                    profile_email = doc.id
                    
                    # Get profile image
                    profile_image_base64 = None
                    current_image_id = profile.get('currentProfileImageId')
                    
                    if current_image_id:
                        print(f"Fetching profile image with ID: {current_image_id} for email: {profile_email}")
                        image_doc = db.collection('user_profiles').document(profile_email).collection('profileImages').document(current_image_id).get()
                        if image_doc.exists:
                            profile_image_base64 = image_doc.to_dict().get('imageData')
                    
                    matches.append({
                        "email": profile_email,
                        "firstName": profile.get('firstName'),
                        "lastName": profile.get('lastName'),
                        "phone": profile.get('phone'),
                        "profileImage": profile_image_base64
                    })
                    print(f"Last name match found: {profile_email}")
        
        # Step 3: Search by first name if provided (and no exact email match)
        if first_name and not (email and matches):
            print(f"Querying profiles by first_name: {first_name}")
            
            # Get all documents if we haven't already (for last name)
            if not last_name:
                all_docs = db.collection('user_profiles').stream()
            else:
                # We already retrieved all_docs for last name, so re-use the generator by recreating it
                all_docs = db.collection('user_profiles').stream()
            
            # Then filter by lowercase comparison
            for doc in all_docs:
                profile = doc.to_dict()
                doc_first_name = profile.get('firstName', '').lower().strip()
                doc_last_name = profile.get('lastName', '').lower().strip()
                profile_email = doc.id
                
                if doc_first_name == first_name:
                    # Skip if already matched by last name (avoid duplicates)
                    if last_name and doc_last_name == last_name:
                        continue
                    
                    # Skip if already in matches
                    if any(m['email'] == profile_email for m in matches):
                        continue
                    
                    # Get profile image
                    profile_image_base64 = None
                    current_image_id = profile.get('currentProfileImageId')
                    
                    if current_image_id:
                        print(f"Fetching profile image with ID: {current_image_id} for email: {profile_email}")
                        image_doc = db.collection('user_profiles').document(profile_email).collection('profileImages').document(current_image_id).get()
                        if image_doc.exists:
                            profile_image_base64 = image_doc.to_dict().get('imageData')
                    
                    matches.append({
                        "email": profile_email,
                        "firstName": profile.get('firstName'),
                        "lastName": profile.get('lastName'),
                        "phone": profile.get('phone'),
                        "profileImage": profile_image_base64
                    })
                    print(f"First name match found: {profile_email}")
        
        # Step 4: Search by phone if provided (and no exact email match)
        if phone and not (email and matches):
            print(f"Querying profiles by phone: {phone}")
            phone_query = db.collection('user_profiles').where('phone', '==', phone).stream()
            
            for doc in phone_query:
                profile = doc.to_dict()
                profile_email = doc.id
                
                # Avoid duplicates if already matched by name
                if any(m['email'] == profile_email for m in matches):
                    continue
                
                # Get profile image
                profile_image_base64 = None
                current_image_id = profile.get('currentProfileImageId')
                
                if current_image_id:
                    print(f"Fetching profile image with ID: {current_image_id} for email: {profile_email}")
                    image_doc = db.collection('user_profiles').document(profile_email).collection('profileImages').document(current_image_id).get()
                    if image_doc.exists:
                        profile_image_base64 = image_doc.to_dict().get('imageData')
                
                matches.append({
                    "email": profile_email,
                    "firstName": profile.get('firstName'),
                    "lastName": profile.get('lastName'),
                    "phone": phone,
                    "profileImage": profile_image_base64
                })
                print(f"Phone match found: {profile_email}")
        
        # Step 5: If no parameters provided, fetch all profiles
        if not (first_name or last_name or email or phone):
            print("No search parameters provided, fetching all profiles")
            all_profiles_query = db.collection('user_profiles').stream()
            
            for doc in all_profiles_query:
                profile = doc.to_dict()
                profile_email = doc.id  # Document ID is the email
                
                # Get profile image
                profile_image_base64 = None
                current_image_id = profile.get('currentProfileImageId')
                
                if current_image_id:
                    print(f"Fetching profile image with ID: {current_image_id} for email: {profile_email}")
                    image_doc = db.collection('user_profiles').document(profile_email).collection('profileImages').document(current_image_id).get()
                    if image_doc.exists:
                        profile_image_base64 = image_doc.to_dict().get('imageData')
                
                matches.append({
                    "email": profile_email,
                    "firstName": profile.get('firstName'),
                    "lastName": profile.get('lastName'),
                    "phone": profile.get('phone'),
                    "profileImage": profile_image_base64
                })
                # Print document ID (email), firstName, and lastName
                print(f"Profile found - ID: {profile_email}, FirstName: {profile.get('firstName')}, LastName: {profile.get('lastName')}")

        # Log total matches
        print(f"Total matches found: {len(matches)}")
        return matches
    
    except Exception as e:
        logger.error(f"Error searching profiles: {e}")
        print(f"Exception occurred: {e}")
        raise e  

def calculate_similarity(str1, str2):
    """Optimized similarity calculation (kept for potential future use)"""
    print(f"Calculating similarity between '{str1}' and '{str2}'")
    if not str1 and not str2:
        print("Both strings empty, similarity = 1.0")
        return 1.0
    
    if not str1 or not str2:
        print("One string empty, similarity = 0.0")
        return 0.0
    
    if str1 == str2:
        print("Exact match, similarity = 1.0")
        return 1.0
    
    # Use set operations for faster character comparison
    str1_set = set(str1)
    str2_set = set(str2)
    print(f"str1_set: {str1_set}, str2_set: {str2_set}")
    
    # Calculate Jaccard similarity
    intersection = len(str1_set.intersection(str2_set))
    union = len(str1_set.union(str2_set))
    similarity = intersection / union if union > 0 else 0.0
    print(f"Intersection: {intersection}, Union: {union}, Similarity: {similarity}")
    
    return similarity
