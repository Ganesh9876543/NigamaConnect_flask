from flask import Flask, request, jsonify
from firebase_admin import credentials, initialize_app, firestore
from datetime import datetime
import uuid
import os
import logging
from werkzeug.utils import secure_filename
from google.cloud.firestore_v1.base_query import FieldFilter



# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



# Function to save sent invitation
def save_sent_invitation(sent_invitation,user_profiles_ref):
    """
    Save a single sent invitation to the 'sent_invitations' collection in Firestore.
    The invitation is stored as a document with an ID combining the timestamp and the sender's email.
    
    Args:
        sent_invitation (dict): The sent invitation data
        
    Returns:
        bool: True if saved successfully, False otherwise
    """
    try:
        if not sent_invitation:
            logger.warning("No sent invitation provided")
            return False

        # Validate required fields
        required_fields = ['promoCode', 'time', 'recipientEmail', 'valid', 'recipientName', 'recipientMobile', 'senderEmail']
        # if not all(field in sent_invitation for field in required_fields):
        #     logger.error(f"Missing required fields in sent invitation: {sent_invitation}")
        #     raise ValueError("Missing required fields in sent invitation")

        # Parse the timestamp and create document ID
        sent_invitation=sent_invitation[0]
        timestamp_str = sent_invitation['time']
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except ValueError as e:
            logger.error(f"Invalid timestamp format in sent invitation: {timestamp_str}, error: {e}")
            raise ValueError(f"Invalid timestamp format: {timestamp_str}")

        # Create document ID: timestamp_senderEmail
        sender_email = sent_invitation['senderEmail']
        timestamp_formatted = timestamp.strftime('%Y%m%d%H%M%S%f')  # Format: YYYYMMDDHHMMSSmicroseconds
        doc_id = f"{timestamp_formatted}_{sender_email.replace('@', '_at_')}"  # Replace @ with _at_ to avoid invalid characters

        # Add the invitation type and document ID to the data
        invitation_data = sent_invitation.copy()
        invitation_data['type'] = 'sent'
        invitation_data['createdAt'] = timestamp

        # Save to Firestore in 'sent_invitations' collection
        user_profiles_ref.document(sender_email).collection('sent_invitations').document(doc_id).set(invitation_data)
        logger.info(f"Saved sent invitation with ID: {doc_id}")
        return True

    except Exception as e:
        logger.error(f"Error saving sent invitation: {str(e)}")
        raise e

# Function to save received invitation
def save_received_invitation(received_invitation,user_profiles_ref):
    """
    Save a single received invitation to the 'received_invitations' collection in Firestore.
    The invitation is stored as a document with an ID combining the timestamp and the recipient's email.
    
    Args:
        received_invitation (dict): The received invitation data
        
    Returns:
        bool: True if saved successfully, False otherwise
    """
    try:
        if not received_invitation:
            logger.warning("No received invitation provided")
            return False

        # Validate required fields
        required_fields = ['senderEmail', 'recipientEmail', 'inviteCode', 'time', 'valid', 'senderFullName']
        # if not all(field in received_invitation for field in required_fields):
        #     logger.error(f"Missing required fields in received invitation: {received_invitation}")
        #     raise ValueError("Missing required fields in received invitation")

        # Parse the timestamp and create document ID
        received_invitation=received_invitation[0]
        timestamp_str = received_invitation['time']
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except ValueError as e:
            logger.error(f"Invalid timestamp format in received invitation: {timestamp_str}, error: {e}")
            raise ValueError(f"Invalid timestamp format: {timestamp_str}")

        # Create document ID: timestamp_recipientEmail
        recipient_email = received_invitation['recipientEmail']
        timestamp_formatted = timestamp.strftime('%Y%m%d%H%M%S%f')  # Format: YYYYMMDDHHMMSSmicroseconds
        doc_id = f"{timestamp_formatted}_{recipient_email.replace('@', '_at_')}"  # Replace @ with _at_ to avoid invalid characters

        # Add the invitation type and document ID to the data
        invitation_data = received_invitation.copy()
        invitation_data['type'] = 'received'
        invitation_data['createdAt'] = timestamp

        # Save to Firestore in 'received_invitations' collection
        user_profiles_ref.document(recipient_email).collection('received_invitations').document(doc_id).set(invitation_data)
        logger.info(f"Saved received invitation with ID: {doc_id}")
        return True

    except Exception as e:
        logger.error(f"Error saving received invitation: {str(e)}")
        raise e


