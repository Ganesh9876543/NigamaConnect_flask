from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def add_promocode(db, promocode, family_tree_id, node_id, name, sender_name):
    """
    Add a promo code for a user in a family tree.
    
    Args:
        db: Firestore database instance
        promocode: The promo code to add
        family_tree_id: ID of the family tree
        node_id: ID of the node in the family tree
        name: Name of the user
        sender_name: Name of the sender who created the promo code
        
    Returns:
        dict: Result with success status and relevant information
    """
    try:
        # 1. Create a document in promocodes collection
        promocodes_ref = db.collection('promocodes')
        
        # Check if promocode already exists
        existing_promo = promocodes_ref.document(promocode).get()
        if existing_promo.exists:
            return {
                "success": False,
                "message": "Promo code already exists",
                "promocode": promocode
            }
        
        # Create timestamp
        timestamp = datetime.now().isoformat()
        
        # Create promo code data
        promo_data = {
            "promocode": promocode,
            "familyTreeId": family_tree_id,
            "nodeId": node_id,
            "name": name,
            "senderName": sender_name,
            "createdAt": timestamp,
            "used": False  # Flag to track if promo code has been used
        }
        
        # Add the promo code document
        promocodes_ref.document(promocode).set(promo_data)
        
        logger.info(f"Added promo code {promocode} to promocodes collection")
        
        # 2. Update the family tree node to indicate it has a promo code
        family_tree_ref = db.collection('family_tree').document(family_tree_id)
        family_tree_doc = family_tree_ref.get()
        
        if not family_tree_doc.exists:
            return {
                "success": False,
                "message": f"Family tree with ID {family_tree_id} not found",
                "promocode": promocode
            }
        
        # Get the family tree data
        family_tree_data = family_tree_doc.to_dict()
        family_members = family_tree_data.get('familyMembers', [])
        
        # Find the node and update it
        node_found = False
        updated_members = []
        
        for member in family_members:
            if member.get('id') == node_id:
                # Add promo code flag to the node
                member['hasPromoCode'] = True
                member['promoCode'] = promocode
                node_found = True
            updated_members.append(member)
        
        if not node_found:
            return {
                "success": False,
                "message": f"Node with ID {node_id} not found in family tree",
                "promocode": promocode
            }
        
        # Update the family tree with the modified members list
        family_tree_ref.update({
            'familyMembers': updated_members,
            'updatedAt': timestamp
        })
        
        logger.info(f"Updated node {node_id} in family tree {family_tree_id} with promo code flag")
        
        return {
            "success": True,
            "message": "Promo code added successfully",
            "promocode": promocode,
            "familyTreeId": family_tree_id,
            "nodeId": node_id,
            "name": name
        }
    
    except Exception as e:
        logger.error(f"Error adding promo code: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def get_promocode_details(db, promocode):
    """
    Get details for a promo code including family relationships.
    
    Args:
        db: Firestore database instance
        promocode: The promo code to retrieve details for
        
    Returns:
        dict: Result with success status and promo code details including family relationships
    """
    try:
        # 1. Get the promo code document
        promocodes_ref = db.collection('promocodes')
        promo_doc = promocodes_ref.document(promocode).get()
        
        if not promo_doc.exists:
            return {
                "success": False,
                "message": f"Promo code {promocode} not found",
                "promocode": promocode
            }
        
        # Get promo code data
        promo_data = promo_doc.to_dict()
        family_tree_id = promo_data.get('familyTreeId')
        node_id = promo_data.get('nodeId')
        sender_name = promo_data.get('senderName')
        
        # 2. Get the family tree document
        family_tree_ref = db.collection('family_tree').document(family_tree_id)
        family_tree_doc = family_tree_ref.get()
        
        if not family_tree_doc.exists:
            return {
                "success": False,
                "message": f"Family tree with ID {family_tree_id} not found",
                "promocode": promocode
            }
        
        # Get the family tree data
        family_tree_data = family_tree_doc.to_dict()
        family_members = family_tree_data.get('familyMembers', [])
        
        # Find the node in the family tree
        target_node = None
        for member in family_members:
            if member.get('id') == node_id:
                target_node = member
                break
        
        if not target_node:
            return {
                "success": False,
                "message": f"Node with ID {node_id} not found in family tree",
                "promocode": promocode
            }
        
        # 3. Determine the relationship details
        relationship_details = {
            "type": "unknown",
            "relations": []
        }
        
        # Check if node has a parent
        if 'parentId' in target_node:
            parent_id = target_node.get('parentId')
            relationship_details["type"] = "parent"
            
            # Find parents
            for member in family_members:
                if member.get('id') == parent_id:
                    # This is the father/direct parent
                    relationship_details["relations"].append({
                        "relation": "father" if member.get('gender', '').lower() == 'male' else "mother",
                        "name": member.get('name'),
                        "id": member.get('id')
                    })
                
                # Check for spouse of parent (to find mother/other parent)
                if 'spouseId' in member and member.get('id') == parent_id:
                    spouse_id = member.get('spouseId')
                    for spouse in family_members:
                        if spouse.get('id') == spouse_id:
                            relationship_details["relations"].append({
                                "relation": "mother" if spouse.get('gender', '').lower() == 'female' else "father",
                                "name": spouse.get('name'),
                                "id": spouse.get('id')
                            })
        
        # Check if node has a spouse
        elif 'spouseId' in target_node:
            spouse_id = target_node.get('spouseId')
            relationship_details["type"] = "spouse"
            
            # Find spouse
            for member in family_members:
                if member.get('id') == spouse_id:
                    relationship_details["relations"].append({
                        "relation": "spouse",
                        "name": member.get('name'),
                        "id": member.get('id')
                    })
        
        # Prepare the response
        result = {
            "success": True,
            "promocode": promocode,
            "senderName": sender_name,
            "familyTreeId": family_tree_id,
            "nodeId": node_id,
            "nodeName": target_node.get('name'),
            "nodeDetails": {
                "name": target_node.get('name'),
                "gender": target_node.get('gender', ''),
                "email": target_node.get('email', ''),
                "spouse": target_node.get('spouse'),
                "hasPromoCode": target_node.get('hasPromoCode', False)
            },
            "relationships": relationship_details
        }
        
        logger.info(f"Retrieved details for promo code {promocode}")
        return result
    
    except Exception as e:
        logger.error(f"Error retrieving promo code details: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def update_tree_node_with_promocode(db, family_tree_id, node_id, name, promocode, email=None, phone=None, profile_image=None):
    """
    Update a node in a family tree with user details provided through a promocode.
    
    Args:
        db: Firestore database instance
        family_tree_id: ID of the family tree
        node_id: ID of the node to update
        name: Full name of the user
        promocode: The promocode associated with this update
        email: Email of the user (optional)
        phone: Phone number of the user (optional)
        profile_image: Profile image data (base64 encoded, optional)
        
    Returns:
        dict: Result with success status and updated node details
    """
    try:
        logger.info(f"Starting update_tree_node_with_promocode process - Tree ID: {family_tree_id}, Node ID: {node_id}")
        logger.info(f"Processing promocode: {promocode}")
        
        # Get the family tree document
        family_tree_ref = db.collection('family_tree').document(family_tree_id)
        family_tree_doc = family_tree_ref.get()
        
        if not family_tree_doc.exists:
            logger.error(f"Family tree with ID {family_tree_id} not found")
            return {
                "success": False,
                "message": f"Family tree with ID {family_tree_id} not found"
            }
        
        logger.info(f"Family tree document retrieved successfully")
        
        # Verify the promocode exists and is valid for this family tree and node
        promocodes_ref = db.collection('promocodes')
        promo_doc = promocodes_ref.document(promocode).get()
        
        if not promo_doc.exists:
            logger.error(f"Promocode {promocode} not found")
            return {
                "success": False,
                "message": f"Promocode {promocode} not found"
            }
        
        logger.info(f"Promocode document retrieved successfully")
        
        promo_data = promo_doc.to_dict()
        promo_family_tree_id = promo_data.get('familyTreeId')
        promo_node_id = promo_data.get('nodeId')
        
        # Check if promocode matches the provided family tree and node
        if promo_family_tree_id != family_tree_id or promo_node_id != node_id:
            logger.error(f"Promocode validation failed - Expected tree/node: {promo_family_tree_id}/{promo_node_id}, Got: {family_tree_id}/{node_id}")
            return {
                "success": False,
                "message": f"Promocode {promocode} is not valid for this family tree or node"
            }
        
        logger.info(f"Promocode validation successful")
        
        # Get the family tree data
        family_tree_data = family_tree_doc.to_dict()
        family_members = family_tree_data.get('familyMembers', [])
        logger.info(f"Retrieved {len(family_members)} family members from tree")
        
        # Find the node and update it
        node_found = False
        updated_members = []
        updated_node = None
        
        timestamp = datetime.now().isoformat()
        logger.info(f"Update timestamp: {timestamp}")
        
        for member in family_members:
            if member.get('id') == node_id:
                logger.info(f"Found target node with ID: {node_id}")
                # Update node details - use 'name' field instead of firstName/lastName
                member['name'] = name
                
                if email:
                    member['email'] = email
                    logger.info(f"Updated node email")
                
                if phone:
                    member['phone'] = phone
                    logger.info(f"Updated node phone")
                
                if profile_image:
                    # add base64 to the profile image
                    member['profileImage'] = "data:image/jpeg;base64," + profile_image  # Log placeholder instead of actual data
                    logger.info(f"Updated node profile image")
                
                # Set userProfileExists flag to true
                member['userProfileExists'] = True
                
                # Update timestamp
                member['updatedAt'] = timestamp
                
                node_found = True
                updated_node = member
                logger.info(f"Node update complete")
            
            updated_members.append(member)
        
        if not node_found:
            logger.error(f"Node with ID {node_id} not found in family tree")
            return {
                "success": False,
                "message": f"Node with ID {node_id} not found in family tree"
            }
        
        # Update the family tree with modified members list
        family_tree_ref.update({
            'familyMembers': updated_members,
            'updatedAt': timestamp
        })
        
        logger.info(f"Family tree document updated successfully")
        
        # Mark the promocode as used
        promocodes_ref.document(promocode).update({
            'used': True,
            'usedAt': timestamp,
            'usedByName': name,
            'usedByEmail': email
        })
        
        logger.info(f"Marked promocode {promocode} as used")
        
        # Check if user has a profile, if email is provided
        user_has_profile = False
        profile_created = False
        user_profiles_ref = db.collection('user_profiles')
        
        if email:
            logger.info(f"Checking if user profile exists for email")
            user_doc = user_profiles_ref.document(email).get()
            user_has_profile = user_doc.exists
            
            if user_has_profile:
                logger.info(f"Existing user profile found - updating with family tree ID")
                # If user has a profile, update it with family tree ID
                user_profiles_ref.document(email).update({
                    'familyTreeId': family_tree_id,
                    'updatedAt': timestamp
                })
                logger.info(f"User profile updated successfully")
            else:
                logger.info(f"No existing user profile found - creating new profile")
                # Create a new user profile with minimal information
                # Split the name to get first and last name for the profile
                name_parts = name.split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ""
                
                new_profile = {
                    'email': email,
                    'familyTreeId': family_tree_id,
                    'createdViaPromocode': True,
                    'promocode': promocode
                }
                
                # Set the user profile with email as document ID
                user_profiles_ref.document(email).set(new_profile)
                logger.info(f"New user profile created")
                
                # Create profileImages collection and add profile image if provided
                if profile_image:
                    logger.info(f"Adding profile image to new user profile")
                    profile_image_id = "profileimage"
                    profile_images_ref = user_profiles_ref.document(email).collection('profileImages')
                    profile_images_ref.document(profile_image_id).set({
                        'imageData': profile_image,  # Log placeholder instead of actual data
                        'uploadedAt': timestamp,
                        'imageId': profile_image_id
                    })
                    
                    # Update the user document with a reference to the profile image
                    user_profiles_ref.document(email).update({
                        'currentProfileImageId': profile_image_id
                    })
                    logger.info(f"Profile image added successfully")
                
                profile_created = True
                user_has_profile = True
                logger.info(f"User profile creation process complete")
        else:
            logger.info(f"No email provided - skipping user profile operations")
        
        # Add a record of this update to promocode usage history
        history_ref = db.collection('promocode_usage_history')
        history_id = f"{family_tree_id}_{node_id}_{timestamp.replace(':', '-')}"
        
        history_data = {
            "familyTreeId": family_tree_id,
            "nodeId": node_id,
            "name": name,
            "email": email,
            "phone": phone,
            "hasProfileImage": profile_image is not None,
            "timestamp": timestamp,
            "userHasProfile": user_has_profile,
            "profileCreated": profile_created,
            "promocode": promocode
        }
        
        history_ref.document(history_id).set(history_data)
        logger.info(f"Recorded promocode usage history with ID: {history_id}")
        
        logger.info(f"update_tree_node_with_promocode completed successfully")
        return {
            "success": True,
            "message": "Node updated successfully in family tree",
            "familyTreeId": family_tree_id,
            "nodeId": node_id,
            "updatedNode": updated_node,
            "userHasProfile": user_has_profile,
            "profileCreated": profile_created,
            "promocode": promocode
        }
    
    except Exception as e:
        logger.error(f"Error in update_tree_node_with_promocode: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        } 