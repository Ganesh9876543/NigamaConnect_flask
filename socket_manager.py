import logging
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import request
import json
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize SocketIO instance
socketio = None

# User email to socket session mapping
connected_users = {}

# Track users' online status with timestamps
user_status = {}  # {email: {'status': 'online'|'offline', 'lastSeen': timestamp}}

def init_socketio(app):
    """Initialize SocketIO with the Flask app"""
    global socketio
    socketio = SocketIO(app, cors_allowed_origins="*")
    register_handlers(socketio)
    return socketio

def register_handlers(socketio):
    """Register all socket event handlers"""
    
    @socketio.on('connect')
    def handle_connect():
        logger.info(f"Client connected: {request.sid}")
        emit('connection_response', {'status': 'connected'})

    @socketio.on('disconnect')
    def handle_disconnect():
        # Remove user from connected users on disconnect
        user_email = None
        for email, sid in connected_users.items():
            if sid == request.sid:
                user_email = email
                break
        
        if user_email:
            logger.info(f"User disconnected: {user_email}")
            
            # Update user status
            user_status[user_email] = {
                'status': 'offline',
                'lastSeen': datetime.now().isoformat()
            }
            
            # Notify others about user going offline
            socketio.emit('user_status_change', {
                'email': user_email,
                'status': 'offline',
                'lastSeen': user_status[user_email]['lastSeen']
            }, broadcast=True, include_self=False)
            
            # Clean up
            del connected_users[user_email]
            leave_room(user_email)
        
        logger.info(f"Client disconnected: {request.sid}")

    @socketio.on('register_user')
    def handle_register(data):
        """Handle user registration with their email"""
        try:
            user_email = data.get('email')
            if not user_email:
                emit('register_response', {'status': 'error', 'message': 'Email is required'})
                return
            
            # Store user session
            connected_users[user_email] = request.sid
            
            # Update user status
            user_status[user_email] = {
                'status': 'online',
                'lastSeen': datetime.now().isoformat()
            }
            
            # Join a room named after the user's email
            join_room(user_email)
            
            # Notify others about user coming online
            socketio.emit('user_status_change', {
                'email': user_email,
                'status': 'online',
                'lastSeen': user_status[user_email]['lastSeen']
            }, broadcast=True, include_self=False)
            
            logger.info(f"User registered: {user_email}")
            emit('register_response', {'status': 'success', 'message': f'Registered as {user_email}'})
        except Exception as e:
            logger.error(f"Error registering user: {str(e)}")
            emit('register_response', {'status': 'error', 'message': str(e)})

    @socketio.on('unregister_user')
    def handle_unregister(data):
        """Handle user unregistration"""
        try:
            user_email = data.get('email')
            if not user_email or user_email not in connected_users:
                emit('unregister_response', {'status': 'error', 'message': 'User not registered'})
                return
            
            # Update user status
            user_status[user_email] = {
                'status': 'offline',
                'lastSeen': datetime.now().isoformat()
            }
            
            # Notify others about user going offline
            socketio.emit('user_status_change', {
                'email': user_email,
                'status': 'offline',
                'lastSeen': user_status[user_email]['lastSeen']
            }, broadcast=True, include_self=False)
            
            # Remove user session
            del connected_users[user_email]
            
            # Leave the room
            leave_room(user_email)
            
            logger.info(f"User unregistered: {user_email}")
            emit('unregister_response', {'status': 'success', 'message': 'Unregistered successfully'})
        except Exception as e:
            logger.error(f"Error unregistering user: {str(e)}")
            emit('unregister_response', {'status': 'error', 'message': str(e)})
    
    @socketio.on('invitation_action')
    def handle_invitation_action(data):
        """Handle invitation actions initiated by users"""
        try:
            action_type = data.get('action')
            invitation_id = data.get('invitationId')
            user_email = data.get('userEmail')
            target_email = data.get('targetEmail')
            
            logger.info(f"Invitation action: {action_type} by {user_email} for invitation {invitation_id}")
            
            # Validate required fields
            if not all([action_type, user_email, invitation_id]):
                emit('invitation_action_response', {
                    'status': 'error', 
                    'message': 'Missing required fields: action, userEmail, invitationId'
                })
                return
            
            # Forward notification to target user if they are online
            if target_email and target_email in connected_users:
                notification_data = {
                    'action': action_type,
                    'invitationId': invitation_id,
                    'userEmail': user_email,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Add any additional data
                for key, value in data.items():
                    if key not in ['action', 'invitationId', 'userEmail', 'targetEmail']:
                        notification_data[key] = value
                
                notify_user(target_email, 'invitation_action_notification', notification_data)
                
                emit('invitation_action_response', {
                    'status': 'success',
                    'message': f'Action {action_type} notification sent to {target_email}',
                    'targetOnline': True
                })
            else:
                emit('invitation_action_response', {
                    'status': 'success',
                    'message': f'Action {action_type} recorded but target user is offline',
                    'targetOnline': False
                })
                
        except Exception as e:
            logger.error(f"Error handling invitation action: {str(e)}")
            emit('invitation_action_response', {'status': 'error', 'message': str(e)})

def notify_user(email, event_type, data):
    """Send a notification to a specific user by email"""
    if not socketio:
        logger.error("SocketIO not initialized")
        return False
    
    try:
        # Check if user is online
        is_online = email in connected_users
        
        # Add timestamp to notification
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
        
        # Add current online status
        data['recipientOnline'] = is_online
        
        # Emit to the room named after the user's email
        socketio.emit(event_type, data, room=email)
        logger.info(f"Notification sent to {email}, event: {event_type}, online: {is_online}")
        
        # If the event is invitation related, also send a generic notification
        if event_type in ['invitation_accepted', 'invitation_rejected', 'invitation_processed', 'new_invitation']:
            socketio.emit('invitation_notification', {
                'type': event_type,
                'data': data,
                'timestamp': data.get('timestamp')
            }, room=email)
            logger.info(f"Generic invitation notification sent to {email}")
        
        return True
    except Exception as e:
        logger.error(f"Error sending notification to {email}: {str(e)}")
        return False

def get_connected_users():
    """Get list of currently connected users"""
    return list(connected_users.keys())

def is_user_online(email):
    """Check if a user is currently online"""
    return email in connected_users

def get_user_status(email):
    """Get a user's online status and last seen time"""
    if email in user_status:
        return user_status[email]
    return {'status': 'unknown', 'lastSeen': None}

def notify_friend_connection(sender_email, recipient_email, categories_info):
    """
    Send a real-time notification about a new friend connection
    
    Args:
        sender_email (str): Email of the invitation sender
        recipient_email (str): Email of the invitation recipient
        categories_info (dict): Information about the categories selected by both users
    """
    try:
        # Notify sender
        if sender_email in connected_users:
            notification_data = {
                'event': 'friend_connection_established',
                'recipientEmail': recipient_email,
                'senderCategory': categories_info.get('user1Category'),
                'recipientCategory': categories_info.get('user2Category'),
                'timestamp': datetime.now().isoformat(),
                'message': f"You are now connected with {recipient_email} as friends"
            }
            
            socketio = connected_users[sender_email].get('socketio')
            if socketio:
                socketio.emit('friend_connection', notification_data, room=connected_users[sender_email].get('sid'))
                logger.info(f"Friend connection notification sent to {sender_email}")
        
        # Notify recipient
        if recipient_email in connected_users:
            notification_data = {
                'event': 'friend_connection_established',
                'senderEmail': sender_email,
                'senderCategory': categories_info.get('user1Category'),
                'recipientCategory': categories_info.get('user2Category'),
                'timestamp': datetime.now().isoformat(),
                'message': f"You are now connected with {sender_email} as friends"
            }
            
            socketio = connected_users[recipient_email].get('socketio')
            if socketio:
                socketio.emit('friend_connection', notification_data, room=connected_users[recipient_email].get('sid'))
                logger.info(f"Friend connection notification sent to {recipient_email}")
    
    except Exception as e:
        logger.error(f"Error sending friend connection notification: {str(e)}")
        import traceback
        logger.error(traceback.format_exc()) 