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
            # Use the secret file path in Render's secret directory
            secret_file_path = '/etc/secrets/firebase_service_account.json'

            # Verify if the secret file exists
            if os.path.exists(secret_file_path):
                cred = credentials.Certificate(secret_file_path)
                firebase_app = initialize_app(cred)
                
                logger.info("Firebase initialized successfully")
                return firebase_admin.get_app()
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
