import requests
import json
import logging
from typing import Dict, List, Tuple, Optional
from firebase_admin import messaging
from exponent_server_sdk import PushClient, PushMessage
from requests.exceptions import ConnectionError, HTTPError

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize Expo client
expo_push_client = PushClient()

def send_expo_push_notification(token: str, title: str, body: str, data: Dict = None) -> Tuple[bool, str]:
    """
    Send push notification using Expo's push notification service.
    
    Args:
        token (str): Expo push token
        title (str): Notification title
        body (str): Notification body
        data (dict, optional): Additional data to send
        
    Returns:
        Tuple[bool, str]: Success status and message
    """
    try:
        logger.info(f"Attempting to send Expo push notification")
        logger.info(f"Token: {token[:20]}... (truncated)")
        logger.info(f"Title: {title}")
        logger.info(f"Body: {body}")
        logger.info(f"Additional Data: {json.dumps(data, indent=2) if data else 'None'}")

        if not token.startswith('ExponentPushToken['):
            logger.error(f"Invalid Expo token format: {token[:20]}...")
            return False, "Invalid Expo push token format"

        # Create a proper PushMessage object
        push_message = PushMessage(
            to=token,
            title=title,
            body=body,
            data=data if data else {},
            sound="default",
            priority='high'
        )

        logger.info(f"Sending Expo notification with payload: {json.dumps(push_message.__dict__, indent=2)}")
        
        # Send the message
        response = expo_push_client.publish(push_message)
        
        # Check if the response indicates success
        if response and hasattr(response, 'status') and response.status == 'ok':
            logger.info("✅ Expo notification sent successfully")
            return True, "Notification sent successfully"
        else:
            error_message = getattr(response, 'message', 'Unknown error')
            logger.error(f"❌ Failed to send Expo notification: {error_message}")
            return False, f"Failed to send notification: {error_message}"
            
    except ConnectionError as exc:
        logger.error(f"❌ Connection error while sending Expo notification: {exc}")
        return False, f"Connection error: {exc}"
    except Exception as exc:
        logger.error(f"❌ Unexpected error sending Expo notification: {exc}")
        return False, f"Error sending notification: {exc}"

def send_fcm_push_notification(token: str, title: str, body: str, data: Dict = None) -> Tuple[bool, str]:
    """
    Send push notification using Firebase Cloud Messaging.
    
    Args:
        token (str): FCM device token
        title (str): Notification title
        body (str): Notification body
        data (dict, optional): Additional data to send
        
    Returns:
        Tuple[bool, str]: Success status and message
    """
    try:
        logger.info(f"Attempting to send FCM push notification")
        logger.info(f"Token: {token[:20]}... (truncated)")
        logger.info(f"Title: {title}")
        logger.info(f"Body: {body}")
        logger.info(f"Additional Data: {json.dumps(data, indent=2) if data else 'None'}")

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=token,
        )
        
        if data:
            message.data = data

        logger.info("Sending FCM notification...")
        response = messaging.send(message)
        logger.info(f"✅ FCM notification sent successfully. Message ID: {response}")
        return True, f"Successfully sent message: {response}"
        
    except Exception as e:
        logger.error(f"❌ Error sending FCM notification: {str(e)}")
        return False, f"Error sending FCM notification: {str(e)}"

def send_push_notification_to_device(
    token: str,
    title: str,
    body: str,
    data: Dict = None,
    device_type: str = None
) -> Tuple[bool, str]:
    """
    Send push notification to a specific device based on token type.
    
    Args:
        token (str): Device token (Expo or FCM)
        title (str): Notification title
        body (str): Notification body
        data (dict, optional): Additional data to send
        device_type (str, optional): Device type ('android-expo', 'ios-expo', 'android-fcm', 'ios-fcm')
        
    Returns:
        Tuple[bool, str]: Success status and message
    """
    try:
        logger.info(f"Processing push notification for device type: {device_type or 'unknown'}")
        
        # Determine if it's an Expo token
        is_expo = token.startswith('ExponentPushToken[') or (device_type and 'expo' in device_type.lower())
        logger.info(f"Detected notification service: {'Expo' if is_expo else 'FCM'}")
        
        if is_expo:
            return send_expo_push_notification(token, title, body, data)
        else:
            return send_fcm_push_notification(token, title, body, data)
            
    except Exception as e:
        logger.error(f"❌ Error in send_push_notification_to_device: {str(e)}")
        return False, f"Error sending push notification: {str(e)}"

def send_push_notification_to_user(
    db,
    user_email: str,
    title: str,
    body: str,
    data: Dict = None,
    priority: str = 'high'
) -> Tuple[bool, Dict]:
    """
    Send push notification to all devices registered for a user.
    
    Args:
        db: Firestore database instance
        user_email (str): User's email
        title (str): Notification title
        body (str): Notification body
        data (dict, optional): Additional data to send
        priority (str): Notification priority ('high', 'normal', 'low')
        
    Returns:
        Tuple[bool, Dict]: Success status and result details
    """
    try:
        logger.info(f"====== PUSH NOTIFICATION REQUEST START ======")
        logger.info(f"Sending push notification to user: {user_email}")
        logger.info(f"Title: {title}")
        logger.info(f"Body: {body}")
        logger.info(f"Priority: {priority}")
        logger.info(f"Additional Data: {json.dumps(data, indent=2) if data else 'None'}")

        # Get user's device tokens
        user_ref = db.collection('user_profiles').document(user_email)
        device_tokens_ref = user_ref.collection('device_tokens')
        device_docs = device_tokens_ref.get()
        
        if not device_docs:
            logger.info(f"No registered devices found for user: {user_email}")
            logger.info(f"====== PUSH NOTIFICATION REQUEST END ======")
            return True, {"message": "No registered devices found", "count": 0}
        
        total_devices = len([doc for doc in device_docs])
        logger.info(f"Found {total_devices} registered device(s)")
        
        successful_sends = 0
        failed_sends = 0
        failed_tokens = []
        
        for doc in device_docs:
            device_data = doc.to_dict()
            token = device_data.get('token')
            device_type = device_data.get('device_type')
            
            if not token:
                logger.warning(f"Skipping device - No token found in device data")
                continue
                
            logger.info(f"Processing device: {device_type or 'unknown type'}")
            logger.info(f"Token: {token[:20]}... (truncated)")
            
            success, message = send_push_notification_to_device(
                token=token,
                title=title,
                body=body,
                data=data,
                device_type=device_type
            )
            
            if success:
                successful_sends += 1
                logger.info(f"✅ Successfully sent to device {successful_sends}/{total_devices}")
            else:
                failed_sends += 1
                failed_tokens.append({
                    'token': token,
                    'error': message
                })
                logger.error(f"❌ Failed to send to device. Error: {message}")
                
                # If device is not registered, remove the token
                if 'Device not registered' in message or 'Invalid registration' in message:
                    doc.reference.delete()
                    logger.info(f"🗑️ Removed invalid device token for user {user_email}")
        
        result = {
            "successful_sends": successful_sends,
            "failed_sends": failed_sends,
            "total_devices": successful_sends + failed_sends,
            "failed_tokens": failed_tokens
        }
        
        logger.info(f"Push Notification Summary:")
        logger.info(f"- Total devices processed: {result['total_devices']}")
        logger.info(f"- Successful sends: {result['successful_sends']}")
        logger.info(f"- Failed sends: {result['failed_sends']}")
        if failed_tokens:
            logger.info("Failed tokens details:")
            for failed in failed_tokens:
                logger.info(f"- Token: {failed['token'][:20]}... Error: {failed['error']}")
        
        logger.info(f"====== PUSH NOTIFICATION REQUEST END ======")
        
        if successful_sends > 0:
            return True, {
                "message": f"Successfully sent to {successful_sends} devices" + 
                          (f" ({failed_sends} failed)" if failed_sends > 0 else ""),
                "result": result
            }
        else:
            return False, {
                "message": "Failed to send to any devices",
                "result": result
            }
            
    except Exception as e:
        logger.error(f"❌ Error sending push notification to user {user_email}: {str(e)}")
        logger.info(f"====== PUSH NOTIFICATION REQUEST END ======")
        return False, {"error": str(e)} 