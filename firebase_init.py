import firebase_admin
from firebase_admin import credentials, firestore
import logging

logger = logging.getLogger(__name__)

def initialize_firebase():
    """
    Initialize Firebase Admin SDK if not already initialized.
    Returns the Firestore client.
    """
    try:
        # Try to get the existing app
        return firebase_admin.get_app()
    except ValueError:
        # If no app exists, initialize a new one
        try:
            cred = credentials.Certificate('./nigamaconnectapp-firebase-adminsdk-fbsvc-cfdb46d5b8.json')
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized successfully")
            return firebase_admin.get_app()
        except Exception as e:
            logger.error(f"Error initializing Firebase: {str(e)}")
            raise

def get_firestore_client():
    """
    Get the Firestore client instance.
    """
    try:
        initialize_firebase()
        return firestore.client()
    except Exception as e:
        logger.error(f"Error getting Firestore client: {str(e)}")
        raise 