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
    Returns profiles sorted by relevance score, with highest matches first.
    
    Args:
        first_name (str, optional): First name to search for
        last_name (str, optional): Last name to search for
        email (str, optional): Email to search for
        phone (str, optional): Phone number to search for
        db: Firestore database instance
        
    Returns:
        list: List of all matching profile data sorted by relevance score (highest first)
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
        scored_matches = []
        
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
                    "profileImage": profile_image_base64,
                    "matchScore": 100  # Perfect match score for exact email
                })
                print(f"Email match found: {email}")
                return matches  # Return immediately if email matches, as it's already perfect match
        
        # Create a collection of all profiles to score
        all_profiles = []
        
        # Fetch all profiles
        all_docs = db.collection('user_profiles').stream()
        for doc in all_docs:
            profile = doc.to_dict()
            profile_email = doc.id
            profile_data = {
                "email": profile_email,
                "firstName": profile.get('firstName', ''),
                "lastName": profile.get('lastName', ''),
                "phone": profile.get('phone', ''),
                "currentProfileImageId": profile.get('currentProfileImageId')
            }
            all_profiles.append(profile_data)
        
        # Score and filter profiles
        for profile in all_profiles:
            score = 0
            match_reasons = []
            
            profile_first_name = profile["firstName"].lower().strip() if profile["firstName"] else ""
            profile_last_name = profile["lastName"].lower().strip() if profile["lastName"] else ""
            profile_email = profile["email"].lower().strip()
            profile_phone = ''.join(filter(str.isdigit, profile["phone"])) if profile["phone"] else ""
            
            # Score by field matches
            if email and email == profile_email:
                score += 50
                match_reasons.append("email_exact")
            
            if last_name and last_name == profile_last_name:
                score += 30
                match_reasons.append("last_name_exact")
            
            if first_name and first_name == profile_first_name:
                score += 20
                match_reasons.append("first_name_exact")
            
            if phone and phone == profile_phone:
                score += 40
                match_reasons.append("phone_exact")
            
            # Add partial matching (can be improved with better string matching algorithm)
            if email and not "email_exact" in match_reasons and email in profile_email:
                score += 10
                match_reasons.append("email_partial")
            
            if last_name and not "last_name_exact" in match_reasons and last_name in profile_last_name:
                score += 8
                match_reasons.append("last_name_partial")
            
            if first_name and not "first_name_exact" in match_reasons and first_name in profile_first_name:
                score += 5
                match_reasons.append("first_name_partial")
            
            # Only include profiles with a score > 0 or if no search criteria provided
            if score > 0 or not (first_name or last_name or email or phone):
                if not (first_name or last_name or email or phone):
                    # If no criteria provided, give base score for sorting
                    score = 1
                
                # Get profile image
                profile_image_base64 = None
                current_image_id = profile.get("currentProfileImageId")
                
                if current_image_id:
                    print(f"Fetching profile image with ID: {current_image_id} for email: {profile_email}")
                    image_doc = db.collection('user_profiles').document(profile_email).collection('profileImages').document(current_image_id).get()
                    if image_doc.exists:
                        profile_image_base64 = image_doc.to_dict().get('imageData')
                
                scored_matches.append({
                    "email": profile_email,
                    "firstName": profile["firstName"],
                    "lastName": profile["lastName"],
                    "phone": profile["phone"],
                    "profileImage": profile_image_base64,
                    "matchScore": score,
                    "matchReasons": match_reasons
                })
                print(f"Match found: {profile_email}, Score: {score}, Reasons: {match_reasons}")
        
        # Sort by match score in descending order
        sorted_matches = sorted(scored_matches, key=lambda x: x["matchScore"], reverse=True)
        
        # Remove score and match_reasons from the final result if not needed in the response
        final_matches = []
        for match in sorted_matches:
            final_match = {
                "email": match["email"],
                "firstName": match["firstName"],
                "lastName": match["lastName"],
                "phone": match["phone"],
                "profileImage": match["profileImage"]
            }
            final_matches.append(final_match)
        
        # Log total matches
        print(f"Total matches found: {len(final_matches)}")
        return final_matches
    
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
