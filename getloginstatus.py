from flask import Flask, request, jsonify
from firebase_admin import credentials, initialize_app, firestore
from datetime import datetime
import uuid
import os
import logging
from werkzeug.utils import secure_filename



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_login_status(email,user_profiles_ref):
    """
    Function to get the login status of a user by email.
    
    :param email: The email of the user
    :return: A tuple containing a boolean indicating success and the login status or an error message
    """
    try:
        # Check if Firebase is initialized
        if user_profiles_ref is None:
            logger.warning("Development mode - Firebase not initialized")
            return False, "Development mode - Firebase not initialized"

        # Reference to the document using the email as the document ID
        user_ref = user_profiles_ref.document(email)

        # Check if the document exists
        doc = user_ref.get()

        if doc.exists:
            # Get the login status from the document
            login_status = doc.to_dict().get("login", False)
            logger.info(f"Retrieved login status for email: {email}  login status was {login_status}")
            return True, login_status
        else:
            return False, "Document not found"

    except Exception as e:
        logger.error(f"Error getting login status: {e}")
        return False, str(e)