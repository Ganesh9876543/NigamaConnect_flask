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
    """Initialize Socket.IO with the Flask app."""
    global socketio
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    # Setup event handlers
    setup_socket_handlers(socketio)
    
    return socketio

def setup_socket_handlers(socketio):
    """Setup Socket.IO event handlers."""
    
    @socketio.on('connect')
    def handle_connect():
        logger.info(f"Client connected: {socketio.request.sid}")

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
                
                notify_user(target_email, notification_data)
                
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

    @socketio.on('join_user_channel')
    def handle_join_user_channel(data):
        """Handle user joining their personal notification channel."""
        try:
            if 'userEmail' not in data:
                logger.error("join_user_channel: Missing userEmail in data")
                return {'success': False, 'message': 'userEmail is required'}
            
            user_email = data['userEmail']
            channel = f'notification_{user_email}'
            
            # Join the room
            socketio.server.enter_room(socketio.request.sid, channel)
            logger.info(f"User {user_email} joined channel: {channel}")
            
            return {'success': True, 'message': f'Joined channel: {channel}'}
        except Exception as e:
            logger.error(f"Error in join_user_channel: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    @socketio.on('leave_user_channel')
    def handle_leave_user_channel(data):
        """Handle user leaving their personal notification channel."""
        try:
            if 'userEmail' not in data:
                logger.error("leave_user_channel: Missing userEmail in data")
                return {'success': False, 'message': 'userEmail is required'}
            
            user_email = data['userEmail']
            channel = f'notification_{user_email}'
            
            # Leave the room
            socketio.server.leave_room(socketio.request.sid, channel)
            logger.info(f"User {user_email} left channel: {channel}")
            
            return {'success': True, 'message': f'Left channel: {channel}'}
        except Exception as e:
            logger.error(f"Error in leave_user_channel: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    @socketio.on('join_global_notifications')
    def handle_join_global_notifications():
        """Handle user joining the global notifications channel."""
        try:
            # Join the room
            socketio.server.enter_room(socketio.request.sid, 'notifications')
            logger.info(f"Client {socketio.request.sid} joined global notifications channel")
            
            return {'success': True, 'message': 'Joined global notifications channel'}
        except Exception as e:
            logger.error(f"Error in join_global_notifications: {str(e)}")
            return {'success': False, 'message': str(e)}

    logger.info("Socket.IO event handlers have been set up")
    return socketio

def notify_user(user_email, event_data):
    """
    Send a notification to a specific user via Socket.IO.
    
    Args:
        user_email (str): Email of the user to notify
        event_data (dict): Event data containing type and notification info
    
    Returns:
        bool: True if notification was sent, False otherwise
    """
    global socketio
    if not socketio:
        logger.error("Socket.IO not initialized")
        return False
    
    try:
        # Add timestamp if not present
        if isinstance(event_data, dict) and 'timestamp' not in event_data:
            event_data['timestamp'] = datetime.now().isoformat()
        
        # Emit to the user's personal notification channel
        user_channel = f'notification_{user_email}'
        socketio.emit(user_channel, event_data)
        logger.info(f"Notification sent to channel {user_channel}")
        
        # Also emit to the global notifications channel
        socketio.emit('notifications', {
            'userEmail': user_email,
            'data': event_data
        })
        logger.info(f"Notification sent to global channel for {user_email}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error sending notification to {user_email}: {str(e)}")
        return False

def notify_friend_connection(sender_email, recipient_email, categories_info):
    """Send a friend connection notification to both users."""
    global socketio
    if socketio:
        # Notify sender
        sender_room = f'user_{sender_email}'
        socketio.emit('friend_connection', {
            'email': recipient_email,
            'category': categories_info.get('senderCategory', 'Friend'),
            'status': 'accepted'
        }, room=sender_room)
        
        # Notify recipient
        recipient_room = f'user_{recipient_email}'
        socketio.emit('friend_connection', {
            'email': sender_email,
            'category': categories_info.get('recipientCategory', 'Friend'),
            'status': 'accepted'
        }, room=recipient_room)
        
        return True
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
