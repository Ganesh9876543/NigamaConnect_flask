import uuid
from datetime import datetime
from typing import Dict, Any, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_noprofile_friend(
    user_profiles_ref,
    user_email: str,
    friend_first_name: str,
    friend_last_name: str,
    friend_category: str,
    friend_email: str = None
) -> Dict[str, Any]:
    """
    Add a friend without a profile to a user's friend list
    
    Args:
        user_profiles_ref: Firestore user profiles collection reference
        user_email: Email of the user adding the friend
        friend_first_name: First name of the friend to add
        friend_last_name: Last name of the friend to add
        friend_category: Category of the friend (e.g., 'close', 'acquaintance', etc.)
        friend_email: Optional email of the friend
        
    Returns:
        Dict: Result of the operation with success status and message
    """
    try:
        # Validate user exists
        user_query = user_profiles_ref.where('email', '==', user_email).limit(1)
        user_docs = user_query.stream()
        user_list = list(user_docs)
        
        if not user_list:
            return {
                "success": False,
                "message": f"User with email {user_email} not found"
            }
            
        user_doc = user_list[0]
        user_data = user_doc.to_dict()
        
        # Create a unique ID for the friend node
        friend_node_id = str(uuid.uuid4())
        
        # Create the friend node object
        friend_node = {
            "nodeId": friend_node_id,
            "firstName": friend_first_name,
            "lastName": friend_last_name,
            "fullName": f"{friend_first_name} {friend_last_name}",
            "category": friend_category,
            "createdAt": datetime.now().isoformat(),
            "hasProfile": False,
            "relationship": "friend"
        }
        
        # Add email if provided
        if friend_email:
            friend_node["email"] = friend_email
        
        # Initialize friends array if it doesn't exist
        if 'friends' not in user_data:
            user_data['friends'] = []
            
        # Check if friend with same name and email already exists
        for existing_friend in user_data.get('friends', []):
            if (existing_friend.get('firstName') == friend_first_name and 
                existing_friend.get('lastName') == friend_last_name):
                # If email is provided, check if it matches
                if friend_email and existing_friend.get('email') == friend_email:
                    return {
                        "success": False,
                        "message": f"Friend with name {friend_first_name} {friend_last_name} and email {friend_email} already exists"
                    }
                # If no email but names match
                elif not friend_email and 'email' not in existing_friend:
                    return {
                        "success": False,
                        "message": f"Friend with name {friend_first_name} {friend_last_name} already exists"
                    }
        
        # Add the friend to the user's friends array
        user_data['friends'].append(friend_node)
        
        # Update the user document
        user_doc.reference.update({
            'friends': user_data['friends']
        })
        
        return {
            "success": True,
            "message": f"Friend {friend_first_name} {friend_last_name} added successfully",
            "friendNodeId": friend_node_id
        }
        
    except Exception as e:
        logger.error(f"Error adding friend without profile: {str(e)}")
        return {
            "success": False,
            "message": f"Error adding friend: {str(e)}"
        }

def add_mutual_friends(
    db,
    user1_email: str,
    user2_email: str,
    user1_category: str,
    user2_category: str
) -> Dict[str, Any]:
    """
    Add two users as mutual friends with their selected categories for each other
    
    Args:
        db: Firestore database instance
        user1_email: Email of the first user
        user2_email: Email of the second user
        user1_category: Category assigned by user1 to user2 (e.g., 'close', 'acquaintance')
        user2_category: Category assigned by user2 to user1
        
    Returns:
        Dict: Result of the operation with success status and message
    """
    try:
        # Start a transaction to ensure consistency
        transaction = db.transaction()
        
        @db.transactional
        def update_both_friend_lists(transaction):
            # Get user1 profile
            user1_ref = db.collection('user_profiles').document(user1_email)
            user1_doc = user1_ref.get(transaction=transaction)
            
            if not user1_doc.exists:
                raise ValueError(f"User profile not found for email: {user1_email}")
            
            # Get user2 profile
            user2_ref = db.collection('user_profiles').document(user2_email)
            user2_doc = user2_ref.get(transaction=transaction)
            
            if not user2_doc.exists:
                raise ValueError(f"User profile not found for email: {user2_email}")
            
            # Get user profiles data
            user1_data = user1_doc.to_dict()
            user2_data = user2_doc.to_dict()
            
            # Get user1's friends data
            user1_friends_data_ref = user1_ref.collection('friendsData').document('friendstree')
            user1_friends_data = user1_friends_data_ref.get(transaction=transaction)
            
            user1_friends_dict = user1_friends_data.to_dict() if user1_friends_data.exists else {}
            user1_friends_list = user1_friends_dict.get('friends', [])
            
            # Get user2's friends data
            user2_friends_data_ref = user2_ref.collection('friendsData').document('friendstree')
            user2_friends_data = user2_friends_data_ref.get(transaction=transaction)
            
            user2_friends_dict = user2_friends_data.to_dict() if user2_friends_data.exists else {}
            user2_friends_list = user2_friends_dict.get('friends', [])
            
            # Extract profile data for user1
            user1_first_name = user1_data.get('firstName', '')
            user1_last_name = user1_data.get('lastName', '')
            user1_full_name = f"{user1_first_name} {user1_last_name}".strip()
            
            # Extract profile data for user2
            user2_first_name = user2_data.get('firstName', '')
            user2_last_name = user2_data.get('lastName', '')
            user2_full_name = f"{user2_first_name} {user2_last_name}".strip()
            
            # Get profile images for both users
            user1_profile_image = None
            user1_profile_image_id = user1_data.get('currentProfileImageId')
            if user1_profile_image_id:
                user1_image_ref = user1_ref.collection('profileImages').document(user1_profile_image_id)
                user1_image_doc = user1_image_ref.get(transaction=transaction)
                if user1_image_doc.exists:
                    user1_profile_image = user1_image_doc.to_dict().get('imageData')
                    
            user2_profile_image = None
            user2_profile_image_id = user2_data.get('currentProfileImageId')
            if user2_profile_image_id:
                user2_image_ref = user2_ref.collection('profileImages').document(user2_profile_image_id)
                user2_image_doc = user2_image_ref.get(transaction=transaction)
                if user2_image_doc.exists:
                    user2_profile_image = user2_image_doc.to_dict().get('imageData')
            
            # Generate IDs for the friend nodes
            # For user1's friends list
            max_id_user1 = 0
            for f in user1_friends_list:
                try:
                    id_val = int(f.get('id', 0))
                    if id_val > max_id_user1:
                        max_id_user1 = id_val
                except ValueError:
                    pass
            
            user2_node_id = str(max_id_user1 + 1)
            
            # For user2's friends list
            max_id_user2 = 0
            for f in user2_friends_list:
                try:
                    id_val = int(f.get('id', 0))
                    if id_val > max_id_user2:
                        max_id_user2 = id_val
                except ValueError:
                    pass
            
            user1_node_id = str(max_id_user2 + 1)
            
            # Create friend node for user2 (to be added to user1's list)
            user2_node = {
                'id': user2_node_id,
                'name': user2_full_name,
                'category': user1_category,
                'email': user2_email,
                'profileImage': user2_profile_image
            }
            
            # Create friend node for user1 (to be added to user2's list)
            user1_node = {
                'id': user1_node_id,
                'name': user1_full_name,
                'category': user2_category,
                'email': user1_email,
                'profileImage': user1_profile_image
            }
            
            # Check if user2 is already in user1's friends list
            if not any(f.get('email') == user2_email for f in user1_friends_list):
                user1_friends_list.append(user2_node)
                transaction.set(user1_friends_data_ref, {'friends': user1_friends_list}, merge=True)
                logger.info(f"Added user {user2_email} to user {user1_email}'s friend list with category {user1_category}")
            else:
                logger.info(f"User {user2_email} already exists in user {user1_email}'s friend list")
            
            # Check if user1 is already in user2's friends list
            if not any(f.get('email') == user1_email for f in user2_friends_list):
                user2_friends_list.append(user1_node)
                transaction.set(user2_friends_data_ref, {'friends': user2_friends_list}, merge=True)
                logger.info(f"Added user {user1_email} to user {user2_email}'s friend list with category {user2_category}")
            else:
                logger.info(f"User {user1_email} already exists in user {user2_email}'s friend list")
        
        # Execute the transaction
        update_both_friend_lists(transaction)
        
        return {
            "success": True,
            "message": f"Mutual friendship established between {user1_email} and {user2_email}",
            "user1Email": user1_email,
            "user2Email": user2_email,
            "user1Category": user1_category,
            "user2Category": user2_category
        }
        
    except Exception as e:
        logger.error(f"Error adding mutual friendship: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "message": f"Error adding mutual friendship: {str(e)}"
        } 