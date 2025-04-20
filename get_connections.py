from typing import Dict, List, Any
from firebase_admin import firestore
from build_family_relationships import build_family_relationships
from family_tree_relations import get_extended_family
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_user_connections(email: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get all connections (family, relatives, friends) for a user.
    
    Args:
        email (str): User's email address
        
    Returns:
        Dict[str, List[Dict[str, Any]]]: Dictionary containing family, relatives, and friends
    """
    logger.info(f"Starting to fetch connections for user: {email}")
    db = firestore.client()
    
    # Initialize connections dictionary
    connections = {
        'family': [],
        'relatives': [],
        'friends': []
    }
    
    try:
        # Get user profile
        logger.info(f"Fetching user profile for email: {email}")
        user_ref = db.collection('user_profiles').document(email)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            logger.warning(f"No user profile found for email: {email}")
            return connections
        
        user_data = user_doc.to_dict()
        logger.info(f"Successfully retrieved user profile for: {email}")
        
        # Get family tree data
        if user_data.get('familyTreeId'):
            family_tree_id = user_data['familyTreeId']
            logger.info(f"Found family tree ID: {family_tree_id} for user: {email}")
            
            family_tree_ref = db.collection('family_tree').document(family_tree_id)
            family_tree_doc = family_tree_ref.get()
            
            if family_tree_doc.exists:
                family_tree_data = family_tree_doc.to_dict()
                family_members = family_tree_data.get('familyMembers', [])
                relatives_data = family_tree_data.get('relatives', {})
                print("relatives_data",relatives_data)
                logger.info(f"Found {len(family_members)} family members")
                logger.info(f"Relatives data structure: {type(relatives_data)}")
                
                # Set isSelf for all members
                for member in family_members:
                    if member.get('email') == email:
                        member['isSelf'] = True
                    else:
                        member['isSelf'] = False
                
                # Build family relationships for all members first
                family_members = build_family_relationships(family_members)
                logger.info("Built family relationships for all members")
                
                # Process family members first
                for member in family_members:
                    try:
                        # Get the member's relatives if they exist
                        member_id = member.get('id')
                        print("member_id",member_id)
                        print("relatives_data",relatives_data)
                        
                        member_relatives=relatives_data.get(member_id, {})
                        print("member_relatives",member_relatives)
                        
                        print(member.get('email'))
                        email2=member.get('email')
                        print("member_relatives for email",email2,member_relatives)
                        if email2:                        # Check if user profile exists for family member
                            member_profile = db.collection('user_profiles').document(member.get('email', '')).get()
                            user_profile_exists = member_profile.exists if member.get('email') else False
                        else:
                            user_profile_exists = False
                        # Add the family member
                        if user_profile_exists:
                            connections['family'].append({
                                'email': member.get('email', ''),
                                'fullName': member.get('name', ''),
                                'profileImage': member.get('profileImage', ''),
                                'relation': member.get('relation', 'family member'),
                                'userProfileExists': user_profile_exists
                            })
                        else:
                            connections['family'].append({
                                'email': member.get('email', ''),
                                'fullName': member.get('name', ''),
                                
                                'gender': member.get('gender', ''),
                                'maritalStatus': member.get('maritalStatus', ''),
                                'phone': member.get('phone', ''),
                                'relation': member.get('relation', 'family member'),
                                'userProfileExists': user_profile_exists
                            })
                        
                        # Process relatives for this family member
                        if member_relatives:
                            try:
                                # Get extended family data
                                relatives_data = get_extended_family(member_relatives.get('familyTreeId'), member_relatives.get('originalNodeId'))
                                
                                if relatives_data:
                                    for relative in relatives_data:
                                        try:
                                            # Check if user profile exists for relative
                                            email3 = relative.get('email')
                                            if email3:
                                                relative_profile = db.collection('user_profiles').document(relative.get('email', '')).get()
                                                relative_profile_exists = relative_profile.exists if relative.get('email') else False
                                            else:
                                                relative_profile_exists = False
                                                
                                            if relative_profile_exists:
                                                connections['relatives'].append({
                                                    'email': relative.get('email', ''),
                                                    'fullName': relative.get('name', ''),
                                                    'profileImage': relative.get('profileImage', ''),
                                                    'relation': f"{relative.get('relation', '')} of {member.get('name')}",
                                                    'userProfileExists': relative_profile_exists
                                                })
                                            else:
                                                connections['relatives'].append({
                                                    'email': relative.get('email', ''),
                                                    'fullName': relative.get('name', ''),
                                                    'gender': relative.get('gender', ''),
                                                    'maritalStatus': relative.get('maritalStatus', ''),
                                                    'phone': relative.get('phone', ''),
                                                    'relation': f"{relative.get('relation', '')} of {member.get('name')}",
                                                    'userProfileExists': relative_profile_exists
                                                })
                                        except Exception as e:
                                            logger.warning(f"Error processing relative for family member {member_id}: {str(e)}")
                                            continue
                            except Exception as e:
                                logger.warning(f"Error fetching relatives data for family member {member_id}: {str(e)}")
                                continue
                    except Exception as e:
                        logger.warning(f"Error processing family member {member.get('id')}: {str(e)}")
                        continue
                
                logger.info(f"Added {len(connections['family'])} family members")
                logger.info(f"Added {len(connections['relatives'])} relatives")
                
                # Get friends
                logger.info("Fetching friends data")
                friends_ref = user_ref.collection('friendsData').document('friendstree')
                friends_doc = friends_ref.get()
                
                if friends_doc.exists:
                    friends_data = friends_doc.to_dict()
                    friends = friends_data.get('friends', [])
                    logger.info(f"Found {len(friends)} friends")
                    
                    # Format friends
                    logger.info("Formatting friends")
                    for friend in friends:
                        try:
                            # Simplify friend category by removing "friend in" prefix
                            category = friend.get('category', 'general')
                            if category.startswith('friend in '):
                                category = category.replace('friend in ', '')
                            
                            # Add base64 prefix for friends' profile images
                            profile_image = friend.get('profileImage', '')
                            if profile_image and not profile_image.startswith('data:image/jpeg;base64,'):
                                profile_image = f"data:image/jpeg;base64,{profile_image}"
                            
                            # Check if user profile exists for friend
                            friend_email = friend.get('email', '')
                            user_profile_exists = False
                            if friend_email:
                                friend_profile = db.collection('user_profiles').document(friend_email).get()
                                user_profile_exists = friend_profile.exists
                            
                            connections['friends'].append({
                                'email': friend_email,
                                'fullName': friend.get('name', ''),
                                'profileImage': profile_image,
                                'relation': category,
                                'userProfileExists': user_profile_exists
                            })
                            logger.info(f"Successfully added friend: {friend.get('email')}")
                        except Exception as e:
                            logger.warning(f"Error processing friend data: {str(e)}")
                            logger.warning(f"Problematic friend data: {friend}")
                            continue
                    logger.info(f"Added {len(connections['friends'])} friends to connections")
                else:
                    logger.info(f"No friends data found for user: {email}")
            else:
                logger.warning(f"Family tree document not found for ID: {family_tree_id}")
        else:
            logger.info(f"No family tree ID found for user: {email}")
        
        logger.info(f"Successfully retrieved all connections for user: {email}")
        return connections
        
    except Exception as e:
        logger.error(f"Error fetching connections for user {email}: {str(e)}")
        raise 
