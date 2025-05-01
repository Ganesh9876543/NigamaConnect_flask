import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def add_noprofile_friend(
    db,
    user_email: str,
    friend_first_name: str,
    friend_last_name: str,
    friend_category: str,
    friend_email: str = None
) -> Dict[str, Any]:
    """
    Add a friend without a profile to a user's friend list
    
    Args:
        db: Firestore database instance
        user_email: Email of the user adding the friend
        friend_first_name: First name of the friend to add
        friend_last_name: Last name of the friend to add
        friend_category: Category of the friend (e.g., 'close', 'acquaintance', etc.)
        friend_email: Optional email of the friend
        
    Returns:
        Dict: Result of the operation with success status and message
    """
    logger.info(f"Adding no-profile friend to user {user_email}: {friend_first_name} {friend_last_name}, category: {friend_category}")
    try:
        # Get direct reference to user document
        user_ref = db.collection('user_profiles').document(user_email)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            logger.warning(f"User not found with email: {user_email}")
            return {
                "success": False,
                "message": f"User with email {user_email} not found"
            }
            
        user_data = user_doc.to_dict()
        logger.debug(f"Found user: {user_email}")
        
        # Generate a timestamp-based ID for better organization
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        clean_name = f"{friend_first_name}{friend_last_name}".replace(" ", "")
        friend_node_id = f"{timestamp}-{clean_name}"
        logger.debug(f"Generated friend node ID: {friend_node_id}")
        
        # Get reference to the friendsData collection and tree document
        friends_data_ref = user_ref.collection('friendsData').document('friendstree')
        friends_data = friends_data_ref.get()
        
        # Get current friends list or initialize if it doesn't exist
        friends_list = friends_data.to_dict().get('friends', []) if friends_data.exists else []
        logger.debug(f"User has {len(friends_list)} existing friends in friendstree")
        
        # Check if friend already exists in the friendstree
        for existing_friend in friends_list:
            if existing_friend.get('name') == f"{friend_first_name} {friend_last_name}":
                # If email is provided, check if it matches
                if friend_email and existing_friend.get('email') == friend_email:
                    logger.warning(f"Friend with name {friend_first_name} {friend_last_name} and email {friend_email} already exists for user {user_email}")
                    return {
                        "success": False,
                        "message": f"Friend with name {friend_first_name} {friend_last_name} and email {friend_email} already exists"
                    }
                # If no email but names match
                elif not friend_email and 'email' not in existing_friend:
                    logger.warning(f"Friend with name {friend_first_name} {friend_last_name} (no email) already exists for user {user_email}")
                    return {
                        "success": False,
                        "message": f"Friend with name {friend_first_name} {friend_last_name} already exists"
                    }
        
        # Generate sequential ID for the new friend
        max_id = 0
        for f in friends_list:
            try:
                id_val = int(f.get('id', 0))
                if id_val > max_id:
                    max_id = id_val
            except (ValueError, TypeError):
                logger.warning(f"Non-integer id value found in friends list: {f.get('id')}")
        
        new_id = str(max_id + 1)
        logger.debug(f"Generated sequential ID for friend: {new_id}")
        
        # Create the friend node object for friendstree
        friend_tree_node = {
            'id': new_id,
            'nodeId': friend_node_id,
            'name': f"{friend_first_name} {friend_last_name}",
            'category': friend_category,
            'email': friend_email if friend_email else "",
            'profileImage': None,
            'createdAt': datetime.now().isoformat(),
            'userProfileExists': False
        }
        
        # Also create friend node for legacy format in user profile (if needed)
        friend_profile_node = {
            "nodeId": friend_node_id,
            "firstName": friend_first_name,
            "lastName": friend_last_name,
            "fullName": f"{friend_first_name} {friend_last_name}",
            "category": friend_category,
            "createdAt": datetime.now().isoformat(),
            "userProfileExists": False,
            "relationship": "friend"
        }
        
        # Add email if provided to the profile node
        if friend_email:
            friend_profile_node["email"] = friend_email
            
        # Add friend to friendstree
        friends_list.append(friend_tree_node)
        friends_data_ref.set({'friends': friends_list}, merge=True)
        logger.info(f"Added friend {friend_first_name} {friend_last_name} to user {user_email}'s friendstree")
        
        # Also ensure the legacy format is maintained (if needed)
        try:
            # Check if the user profile has the old friends array format
            if 'friends' in user_data:
                legacy_friends = user_data.get('friends', [])
                legacy_friends.append(friend_profile_node)
                user_ref.update({
                    'friends': legacy_friends
                })
                logger.debug(f"Also added friend to legacy friends array in user profile")
        except Exception as legacy_e:
            logger.warning(f"Failed to update legacy friends array: {str(legacy_e)}")
        
        logger.info(f"Successfully added friend {friend_first_name} {friend_last_name} to user {user_email}'s friends list")
        
        return {
            "success": True,
            "message": f"Friend {friend_first_name} {friend_last_name} added successfully",
            "friendNodeId": friend_node_id
        }
        
    except Exception as e:
        logger.error(f"Error adding friend without profile: {str(e)}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
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
    logger.info(f"Creating mutual friendship between users: {user1_email} and {user2_email}")
    logger.debug(f"Categories - {user1_email} categorizes {user2_email} as: {user1_category}")
    logger.debug(f"Categories - {user2_email} categorizes {user1_email} as: {user2_category}")
    
    # Define refs outside the transaction for reuse
    user1_ref = db.collection('user_profiles').document(user1_email)
    user2_ref = db.collection('user_profiles').document(user2_email)
    user1_friends_data_ref = user1_ref.collection('friendsData').document('friendstree')
    user2_friends_data_ref = user2_ref.collection('friendsData').document('friendstree')
    
    try:
        # Validate users exist before starting transaction
        if not user1_ref.get().exists:
            error_msg = f"User profile not found for email: {user1_email}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}
            
        if not user2_ref.get().exists:
            error_msg = f"User profile not found for email: {user2_email}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}
            
        # Get user profiles data
        user1_doc = user1_ref.get()
        user2_doc = user2_ref.get()
        
        user1_data = user1_doc.to_dict()
        user2_data = user2_doc.to_dict()
        logger.debug(f"Retrieved profile data for both users")
        
        # Get friends data with defaults if not existing
        user1_friends_data = user1_friends_data_ref.get()
        user2_friends_data = user2_friends_data_ref.get()
        
        user1_friends_list = user1_friends_data.to_dict().get('friends', []) if user1_friends_data.exists else []
        user2_friends_list = user2_friends_data.to_dict().get('friends', []) if user2_friends_data.exists else []
        
        logger.debug(f"User1 ({user1_email}) has {len(user1_friends_list)} existing friends")
        logger.debug(f"User2 ({user2_email}) has {len(user2_friends_list)} existing friends")
        
        # Extract profile data
        user1_first_name = user1_data.get('firstName', '')
        user1_last_name = user1_data.get('lastName', '')
        user1_full_name = f"{user1_first_name} {user1_last_name}".strip()
        
        user2_first_name = user2_data.get('firstName', '')
        user2_last_name = user2_data.get('lastName', '')
        user2_full_name = f"{user2_first_name} {user2_last_name}".strip()
        
        # Get profile images 
        user1_profile_image = None
        user1_profile_image_id = user1_data.get('currentProfileImageId')
        if user1_profile_image_id:
            try:
                user1_image_ref = user1_ref.collection('profileImages').document(user1_profile_image_id)
                user1_image_doc = user1_image_ref.get()
                if user1_image_doc.exists:
                    image_data = user1_image_doc.to_dict().get('imageData')
                    # Ensure image data has proper data URI prefix if it doesn't already
                    if image_data and not image_data.startswith('data:image/'):
                        # Add standard base64 image prefix if missing
                        if not image_data.startswith('data:'):
                            image_data = f"data:image/jpeg;base64,{image_data}"
                    user1_profile_image = image_data
                    logger.debug(f"Found profile image for user1 (ID: {user1_profile_image_id})")
            except Exception as e:
                logger.warning(f"Error retrieving profile image for user1: {str(e)}")
                
        user2_profile_image = None
        user2_profile_image_id = user2_data.get('currentProfileImageId')
        if user2_profile_image_id:
            try:
                user2_image_ref = user2_ref.collection('profileImages').document(user2_profile_image_id)
                user2_image_doc = user2_image_ref.get()
                if user2_image_doc.exists:
                    image_data = user2_image_doc.to_dict().get('imageData')
                    # Ensure image data has proper data URI prefix if it doesn't already
                    if image_data and not image_data.startswith('data:image/'):
                        # Add standard base64 image prefix if missing
                        if not image_data.startswith('data:'):
                            image_data = f"data:image/jpeg;base64,{image_data}"
                    user2_profile_image = image_data
                    logger.debug(f"Found profile image for user2 (ID: {user2_profile_image_id})")
            except Exception as e:
                logger.warning(f"Error retrieving profile image for user2: {str(e)}")
        
        # Generate sequential IDs
        max_id_user1 = 0
        for f in user1_friends_list:
            try:
                id_val = int(f.get('id', 0))
                if id_val > max_id_user1:
                    max_id_user1 = id_val
            except (ValueError, TypeError):
                logger.warning(f"Non-integer id value found in user1's friends list: {f.get('id')}")
                
        user2_node_id = str(max_id_user1 + 1)
        
        max_id_user2 = 0
        for f in user2_friends_list:
            try:
                id_val = int(f.get('id', 0))
                if id_val > max_id_user2:
                    max_id_user2 = id_val
            except (ValueError, TypeError):
                logger.warning(f"Non-integer id value found in user2's friends list: {f.get('id')}")
                
        user1_node_id = str(max_id_user2 + 1)
        
        # Create friend nodes
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        
        user2_node = {
            'id': user2_node_id,
            'nodeId': f"{timestamp}-{user2_email.split('@')[0]}",
            'name': user2_full_name,
            'category': user1_category,
            'email': user2_email,
            'profileImage': user2_profile_image,
            'createdAt': datetime.now().isoformat(),
            'userProfileExists': True
        }
        
        user1_node = {
            'id': user1_node_id,
            'nodeId': f"{timestamp}-{user1_email.split('@')[0]}",
            'name': user1_full_name,
            'category': user2_category,
            'email': user1_email,
            'profileImage': user1_profile_image,
            'createdAt': datetime.now().isoformat(),
            'userProfileExists': True
        }
        
        # Update mutual friends if they don't already exist
        updates_performed = False
        
        # Check if user2 is already in user1's friends list
        if not any(f.get('email') == user2_email for f in user1_friends_list):
            user1_friends_list.append(user2_node)
            user1_friends_data_ref.set({'friends': user1_friends_list}, merge=True)
            logger.info(f"Added user {user2_email} to user {user1_email}'s friend list with category {user1_category}")
            updates_performed = True
        else:
            logger.info(f"User {user2_email} already exists in user {user1_email}'s friend list")
        
        # Check if user1 is already in user2's friends list
        if not any(f.get('email') == user1_email for f in user2_friends_list):
            user2_friends_list.append(user1_node)
            user2_friends_data_ref.set({'friends': user2_friends_list}, merge=True)
            logger.info(f"Added user {user1_email} to user {user2_email}'s friend list with category {user2_category}")
            updates_performed = True
        else:
            logger.info(f"User {user1_email} already exists in user {user2_email}'s friend list")
            
        if updates_performed:
            logger.info(f"Successfully established mutual friendship between {user1_email} and {user2_email}")
            return {
                "success": True,
                "message": f"Mutual friendship established between {user1_email} and {user2_email}",
                "user1Email": user1_email,
                "user2Email": user2_email,
                "user1Category": user1_category,
                "user2Category": user2_category
            }
        else:
            logger.info(f"No changes were needed. Friendship already exists between {user1_email} and {user2_email}")
            return {
                "success": True,
                "message": f"Friendship already exists between {user1_email} and {user2_email}",
                "user1Email": user1_email,
                "user2Email": user2_email
            }
        
    except Exception as e:
        logger.error(f"Error adding mutual friendship: {str(e)}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
        return {
            "success": False,
            "message": f"Error adding mutual friendship: {str(e)}"
        } 
