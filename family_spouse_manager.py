import uuid
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

def add_spouse_relationship(
    # Firestore references
    family_tree_ref,
    user_profiles_ref,
    # Wife details
    wife_family_tree_id: str,
    wife_email: str,
    wife_node_id: str,
    # Husband details
    husband_family_tree_id: str,
    husband_email: str,
    husband_node_id: str
) -> Dict[str, Any]:
    """
    Adds spouse details to family trees.
    Handles cases where wife and/or husband may or may not have family trees.
    Creates new family trees as needed and updates user profiles.
    Also adds mini-trees of each spouse's family to the other's family tree as relatives.
    
    Args:
        family_tree_ref: Firestore reference for family trees
        user_profiles_ref: Firestore reference for user profiles
        wife_family_tree_id: ID of wife's family tree (can be None)
        wife_email: Email of wife
        wife_node_id: ID of wife node in her family tree
        husband_family_tree_id: ID of husband's family tree (can be None)
        husband_email: Email of husband
        husband_node_id: ID of husband node in his family tree
        
    Returns:
        Dict with success status, message and family tree IDs
    """
    # Fetch user profiles
    wife_profile_doc = user_profiles_ref.document(wife_email).get() if wife_email else None
    if not wife_profile_doc or not wife_profile_doc.exists:
        return {
            "success": False,
            "message": f"Wife profile not found for email {wife_email}"
        }, 404
        
    wife_profile = wife_profile_doc.to_dict()
    wife_first_name = wife_profile.get('firstName', 'Unknown')
    wife_last_name = wife_profile.get('lastName', 'Unknown')
    current_image_id = wife_profile.get('currentProfileImageId')
    wife_profile_data = user_profiles_ref.document(wife_email)\
                  .collection('profileImages')\
                  .document(current_image_id)\
                  .get()
                  
    wife_image_data = wife_profile_data.to_dict().get('imageData')
    if wife_image_data:
        wife_image_data = f"data:image/jpeg;base64,{wife_image_data}"
    
    husband_profile_doc = user_profiles_ref.document(husband_email).get() if husband_email else None
    if not husband_profile_doc or not husband_profile_doc.exists:
        return {
            "success": False,
            "message": f"Husband profile not found for email {husband_email}"
        }, 404
    husband_profile = husband_profile_doc.to_dict()
    husband_first_name = husband_profile.get('firstName', 'Unknown')
    husband_last_name = husband_profile.get('lastName', 'Doe')
    hus_current_image_id = husband_profile.get('currentProfileImageId')
    hus_profile_data = user_profiles_ref.document(husband_email)\
                  .collection('profileImages')\
                  .document(hus_current_image_id)\
                  .get()
                  
    husband_image_data = hus_profile_data.to_dict().get('imageData')
    if husband_image_data:
        husband_image_data = f"data:image/jpeg;base64,{husband_image_data}"

    # --- Scenario 1: Neither has family tree ---
    if not wife_family_tree_id and not husband_family_tree_id:
        return handle_no_trees_scenario(
            family_tree_ref, user_profiles_ref,
            wife_email, husband_email,
            wife_first_name, husband_first_name, husband_last_name,
            wife_profile, husband_profile,
            wife_image_data, husband_image_data
        )

    # --- Scenario 2: Only wife has family tree ---
    elif not husband_family_tree_id and wife_family_tree_id:
        return handle_only_wife_has_tree_scenario(
            family_tree_ref, user_profiles_ref,
            wife_family_tree_id, wife_email, wife_node_id,
            husband_email,
            wife_first_name, husband_first_name, husband_last_name,
            wife_profile, husband_profile,
            wife_image_data, husband_image_data
        )

    # --- Scenario 3: Only husband has family tree ---
    elif husband_family_tree_id and not wife_family_tree_id:
        return handle_only_husband_has_tree_scenario(
            family_tree_ref, user_profiles_ref,
            husband_family_tree_id, husband_email, husband_node_id,
            wife_email,
            wife_first_name, husband_first_name, husband_last_name,
            wife_profile, husband_profile,
            wife_image_data, husband_image_data
        )

    # --- Scenario 4: Both have family trees ---
    else:
        return handle_both_have_trees_scenario(
            family_tree_ref, user_profiles_ref,
            wife_family_tree_id, wife_email, wife_node_id,
            husband_family_tree_id, husband_email, husband_node_id,
            wife_first_name, husband_first_name, husband_last_name,
            wife_profile, husband_profile,
            wife_image_data, husband_image_data
        )

def create_complete_mini_tree(member_list, member_id, spouse_details=None):
    """
    Helper function to create complete mini-tree with spouse
    
    Args:
        member_list: List of family members
        member_id: ID of the member to center the mini-tree around
        spouse_details: Optional details of spouse to add
        
    Returns:
        Dictionary representing the mini-tree
    """
    members = {member.get('id'): member for member in member_list}
    if member_id not in members:
        return {}
    
    member = members[member_id]
    mini_tree = {
        member_id: {**member, "isSelf": True}
    }
    
    # Add spouse if provided
    if spouse_details:
        spouse_id = f"spouse_{member_id}"
        mini_tree[spouse_id] = {
            **spouse_details,
            "id": spouse_id,
            "isSelf": False,
            "spouse": member_id
        }
        mini_tree[member_id]["spouse"] = spouse_id
    
    # Add parents
    parent_id = member.get('parentId')
    if parent_id and parent_id in members:
        mini_tree[parent_id] = {**members[parent_id], "isSelf": False}
        
        # Add parent's spouse
        parent_spouse_id = members[parent_id].get('spouse')
        if parent_spouse_id and parent_spouse_id in members:
            mini_tree[parent_spouse_id] = {**members[parent_spouse_id], "isSelf": False}
    
    # Add siblings and their spouses
    if parent_id:
        for node_id, node in members.items():
            if node.get('parentId') == parent_id and node_id != member_id:
                mini_tree[node_id] = {**node, "isSelf": False}
                
                sibling_spouse_id = node.get('spouse')
                if sibling_spouse_id and sibling_spouse_id in members:
                    mini_tree[sibling_spouse_id] = {**members[sibling_spouse_id], "isSelf": False}
    
    return mini_tree

def handle_no_trees_scenario(
    family_tree_ref, user_profiles_ref,
    wife_email, husband_email,
    wife_first_name, husband_first_name, husband_last_name,
    wife_profile, husband_profile,
    wife_image_data, husband_image_data
) -> Dict[str, Any]:
    """Handle scenario where neither spouse has a family tree"""
    new_family_tree_id = str(uuid.uuid4())
    husband_node_id = "1"
    wife_node_id = "2"

    # Check if profiles exist
    husband_profile_exists = True  # We already verified these profiles exist at the beginning
    wife_profile_exists = True

    husband_details = {
        "id": husband_node_id,
        "name": f"{husband_first_name} {husband_last_name}",
        "firstName": husband_first_name,
        "lastName": husband_last_name,
        "email": husband_email,
        "phone": husband_profile.get('phone', ''),
        "gender": "male",
        "generation": 0,
        "parentId": None,
        "spouse": wife_node_id,
        "profileImage": husband_image_data,
        "birthOrder": 1,
        "isSelf": True,
        "userProfileExists": husband_profile_exists
    }
    wife_details = {
        "id": wife_node_id,
        "name": f"{wife_first_name} {husband_last_name}",
        "firstName": wife_first_name,
        "lastName": husband_last_name,
        "email": wife_email,
        "phone": wife_profile.get('phone', ''),
        "gender": "female",
        "generation": 0,
        "parentId": None,
        "spouse": husband_node_id,
        "profileImage": wife_image_data,
        "birthOrder": 1,
        "isSelf": False,
        "userProfileExists": wife_profile_exists
    }
    
    # Create simple relative reference structure
    relatives = {
        wife_node_id: {
            "name": f"{wife_first_name} {husband_last_name}",
            "email": wife_email
        }
    }

    family_tree_ref.document(new_family_tree_id).set({
        "familyMembers": [husband_details, wife_details],
        "relatives": relatives
    })

    user_profiles_ref.document(wife_email).set({
        "familyTreeId": new_family_tree_id,
        "oldFamilyTreeId": None,
        "lastName": husband_last_name,
        "MARITAL_STATUS": "Married",
        "updatedAt": datetime.now().isoformat()
    }, merge=True)
    user_profiles_ref.document(husband_email).set({
        "familyTreeId": new_family_tree_id,
        "oldFamilyTreeId": None,
        "MARITAL_STATUS": "Married",
        "updatedAt": datetime.now().isoformat()
    }, merge=True)

    return {
        "success": True,
        "message": "New family tree created",
        "familyTreeId": new_family_tree_id
    }

def handle_only_wife_has_tree_scenario(
    family_tree_ref, user_profiles_ref,
    wife_family_tree_id, wife_email, wife_node_id,
    husband_email,
    wife_first_name, husband_first_name, husband_last_name,
    wife_profile, husband_profile,
    wife_image_data, husband_image_data
) -> Dict[str, Any]:
    """Handle scenario where only wife has a family tree"""
    wife_family_tree_doc = family_tree_ref.document(wife_family_tree_id).get()
    if not wife_family_tree_doc.exists:
        return {
            "success": False,
            "message": f"Wife's family tree not found: {wife_family_tree_id}"
        }, 404
        
    wife_family_tree = wife_family_tree_doc.to_dict()
    wife_members_list = wife_family_tree.get('familyMembers', [])
    wife_members_dict = {member.get('id'): member for member in wife_members_list}

    if wife_node_id not in wife_members_dict:
        return {
            "success": False,
            "message": f"Wife node ID {wife_node_id} not found"
        }, 404
        
    wife_details = wife_members_dict[wife_node_id]

    # Create new family tree for husband
    new_family_tree_id = str(uuid.uuid4())
    husband_node_id = "1"
    new_wife_node_id = "2"

    # Check if profiles exist
    husband_profile_exists = True  # We already verified these profiles exist at the beginning
    wife_profile_exists = True

    husband_details = {
        "id": husband_node_id,
        "name": f"{husband_first_name} {husband_last_name}",
        "firstName": husband_first_name,
        "lastName": husband_last_name,
        "email": husband_email,
        "phone": husband_profile.get('phone', ''),
        "gender": "male",
        "generation": wife_details.get('generation', 0),
        "parentId": None,
        "spouse": new_wife_node_id,
        "profileImage": husband_image_data,
        "birthOrder": 1,
        "isSelf": True,
        "userProfileExists": husband_profile_exists
    }
    new_wife_details = {
        "id": new_wife_node_id,
        "name": f"{wife_first_name} {husband_last_name}",
        "firstName": wife_first_name,
        "lastName": husband_last_name,
        "email": wife_email,
        "phone": wife_details.get('phone', ''),
        "gender": "female",
        "generation": wife_details.get('generation', 0),
        "parentId": None,
        "spouse": husband_node_id,
        "profileImage": wife_image_data,
        "birthOrder": wife_details.get('birthOrder', 1),
        "isSelf": False,
        "userProfileExists": wife_profile_exists
    }
    wife_last_name=wife_details.get('lastName')
    # Create reference mapping for wife's original tree
    husband_relatives = {}
    husband_relatives[new_wife_node_id] = {
        "familyTreeId": wife_family_tree_id,
        "originalNodeId": wife_node_id,
        "name": f"{wife_first_name} {wife_last_name}",
        "email": wife_email
    }

    family_tree_ref.document(new_family_tree_id).set({
        "familyMembers": [husband_details, new_wife_details],
        "relatives": husband_relatives
    })

    # Update wife's original tree with reference to husband
    wife_relatives = wife_family_tree.get('relatives', {})
    wife_relatives[wife_node_id] = {
        "familyTreeId": new_family_tree_id,
        "originalNodeId": husband_node_id,
        "name": f"{husband_first_name} {husband_last_name}",
        "email": husband_email
    }
    
    for i, member in enumerate(wife_members_list):
        if member.get('id') == wife_node_id:
            wife_members_list[i]['spouse'] = new_family_tree_id
            wife_members_list[i]['lastName'] = husband_last_name
            break
    
    family_tree_ref.document(wife_family_tree_id).set({
        "familyMembers": wife_members_list,
        "relatives": wife_relatives
    })

    # Update user profiles
    user_profiles_ref.document(wife_email).set({
        "familyTreeId": new_family_tree_id,
        "oldFamilyTreeId": wife_family_tree_id,
        "lastName": husband_last_name,
        "MARITAL_STATUS": "Married",
        "updatedAt": datetime.now().isoformat()
    }, merge=True)
    user_profiles_ref.document(husband_email).set({
        "familyTreeId": new_family_tree_id,
        "oldFamilyTreeId": None,
        "MARITAL_STATUS": "Married",
        "updatedAt": datetime.now().isoformat()
    }, merge=True)

    return {
        "success": True,
        "message": "New family tree created for husband",
        "familyTreeId": new_family_tree_id
    }

def handle_only_husband_has_tree_scenario(
    family_tree_ref, user_profiles_ref,
    husband_family_tree_id, husband_email, husband_node_id,
    wife_email,
    wife_first_name, husband_first_name, husband_last_name,
    wife_profile, husband_profile,
    wife_image_data, husband_image_data
) -> Dict[str, Any]:
    """Handle scenario where only husband has a family tree"""
    husband_family_tree_doc = family_tree_ref.document(husband_family_tree_id).get()
    if not husband_family_tree_doc.exists:
        return {
            "success": False,
            "message": f"Husband's family tree not found: {husband_family_tree_id}"
        }, 404
        
    husband_family_tree = husband_family_tree_doc.to_dict()
    husband_members_list = husband_family_tree.get('familyMembers', [])
    husband_members_dict = {member.get('id'): member for member in husband_members_list}

    if husband_node_id not in husband_members_dict:
        return {
            "success": False,
            "message": f"Husband node ID {husband_node_id} not found"
        }, 404
        
    husband_details = husband_members_dict[husband_node_id]

    # Check if profile exists
    wife_profile_exists = True  # We already verified this profile exists at the beginning

    # Add wife to husband's tree
    new_wife_node_id = str(len(husband_members_list) + 1)
    wife_details = {
        "id": new_wife_node_id,
        "name": f"{wife_first_name} {husband_last_name}",
        "firstName": wife_first_name,
        "lastName": husband_last_name,
        "email": wife_email,
        "phone": wife_profile.get('phone', ''),
        "gender": "female",
        "generation": husband_details.get('generation', 0),
        "parentId": None,
        "spouse": husband_node_id,
        "profileImage": wife_image_data,
        "birthOrder": 1,
        "isSelf": False,
        "userProfileExists": wife_profile_exists
    }

    # Update husband's spouse reference
    for i, member in enumerate(husband_members_list):
        if member.get('id') == husband_node_id:
            husband_members_list[i]['spouse'] = new_wife_node_id
            break
            
    husband_members_list.append(wife_details)
    
    # Create simple reference mapping
    husband_relatives = husband_family_tree.get('relatives', {})
    husband_relatives[new_wife_node_id] = {
        "name": f"{wife_first_name} {husband_last_name}",
        "email": wife_email
    }
    
    family_tree_ref.document(husband_family_tree_id).set({
        "familyMembers": husband_members_list,
        "relatives": husband_relatives
    })

    # Update user profiles
    user_profiles_ref.document(wife_email).set({
        "familyTreeId": husband_family_tree_id,
        "oldFamilyTreeId": None,
        "lastName": husband_last_name,
        "MARITAL_STATUS": "Married",
        "updatedAt": datetime.now().isoformat()
    }, merge=True)
    user_profiles_ref.document(husband_email).set({
        "MARITAL_STATUS": "Married",
        "updatedAt": datetime.now().isoformat()
    }, merge=True)

    return {
        "success": True,
        "message": "Wife added to husband's family tree",
        "familyTreeId": husband_family_tree_id
    }

def handle_both_have_trees_scenario(
    family_tree_ref, user_profiles_ref,
    wife_family_tree_id, wife_email, wife_node_id,
    husband_family_tree_id, husband_email, husband_node_id,
    wife_first_name, husband_first_name, husband_last_name,
    wife_profile, husband_profile,
    wife_image_data, husband_image_data
) -> Dict[str, Any]:
    """Handle scenario where both wife and husband have family trees"""
    # Validate wife's family tree
    wife_family_tree_doc = family_tree_ref.document(wife_family_tree_id).get()
    if not wife_family_tree_doc.exists:
        return {
            "success": False,
            "message": f"Wife's family tree not found: {wife_family_tree_id}"
        }, 404
        
    wife_family_tree = wife_family_tree_doc.to_dict()
    wife_members_list = wife_family_tree.get('familyMembers', [])
    wife_members_dict = {member.get('id'): member for member in wife_members_list}
    
    if wife_node_id not in wife_members_dict:
        return {
            "success": False,
            "message": f"Wife node ID {wife_node_id} not found"
        }, 404
        
    wife_details = wife_members_dict[wife_node_id]
    
    # Validate husband's family tree
    husband_family_tree_doc = family_tree_ref.document(husband_family_tree_id).get()
    if not husband_family_tree_doc.exists:
        return {
            "success": False,
            "message": f"Husband's family tree not found: {husband_family_tree_id}"
        }, 404
        
    husband_family_tree = husband_family_tree_doc.to_dict()
    husband_members_list = husband_family_tree.get('familyMembers', [])
    husband_members_dict = {member.get('id'): member for member in husband_members_list}
    
    if husband_node_id not in husband_members_dict:
        return {
            "success": False,
            "message": f"Husband node ID {husband_node_id} not found"
        }, 404
        
    husband_details = husband_members_dict[husband_node_id]
    
    # Check if profiles exist
    wife_profile_exists = True  # We already verified these profiles exist at the beginning
    husband_profile_exists = True
    
    # Add wife to husband's family tree
    new_wife_node_id = str(len(husband_members_list) + 1)
    new_wife_details = {
        "id": new_wife_node_id,
        "name": f"{wife_first_name} {husband_last_name}",
        "firstName": wife_first_name,
        "lastName": husband_last_name,
        "email": wife_email,
        "phone": wife_details.get('phone', ''),
        "gender": "female",
        "generation": wife_details.get('generation', 0),
        "parentId": None,
        "spouse": husband_node_id,
        "profileImage": wife_image_data,
        "birthOrder": wife_details.get('birthOrder', 1),
        "isSelf": False,
        "userProfileExists": wife_profile_exists
    }
    
    # Update husband's spouse reference
    for i, member in enumerate(husband_members_list):
        if member.get('id') == husband_node_id:
            husband_members_list[i]['spouse'] = new_wife_node_id
            break
            
    # Add wife to husband's family members
    husband_members_list.append(new_wife_details)
    wife_last_name = wife_details.get('lastName')
    
    # Create spouse reference mapping instead of relatives tree
    husband_relatives = husband_family_tree.get('relatives', {})
    husband_relatives[new_wife_node_id] = {
        "familyTreeId": wife_family_tree_id,
        "originalNodeId": wife_node_id,
        "name": f"{wife_first_name} {wife_last_name}",
        "email": wife_email
    }
    
    # Update husband's family tree
    family_tree_ref.document(husband_family_tree_id).update({
        "familyMembers": husband_members_list,
        "relatives": husband_relatives
    })
    
    # Add husband to wife's family tree
    new_husband_node_id = str(len(wife_members_list) + 1)
    new_husband_details = {
        "id": new_husband_node_id,
        "name": f"{husband_first_name} {husband_last_name}",
        "firstName": husband_first_name,
        "lastName": husband_last_name,
        "email": husband_email,
        "phone": husband_details.get('phone', ''),
        "gender": "male",
        "generation": husband_details.get('generation', 0),
        "parentId": None,
        "spouse": wife_node_id,
        "profileImage": husband_image_data,
        "birthOrder": husband_details.get('birthOrder', 1),
        "husbandNodeIdInFamilyTree": husband_node_id,
        "husbandFamilyTreeId": husband_family_tree_id,
        "isSelf": False,
        "userProfileExists": husband_profile_exists
    }
    
    # Update wife's spouse reference
    for i, member in enumerate(wife_members_list):
        if member.get('id') == wife_node_id:
            wife_members_list[i]['spouse'] = new_husband_node_id
            wife_members_list[i]['lastName'] = husband_last_name
            break
            
    # Add husband to wife's family members
    wife_members_list.append(new_husband_details)
    
    # Create spouse reference mapping instead of mini-tree
    wife_relatives = wife_family_tree.get('relatives', {})
    wife_relatives[new_husband_node_id] = {
        "familyTreeId": husband_family_tree_id,
        "originalNodeId": husband_node_id,
        "name": f"{husband_first_name} {husband_last_name}",
        "email": husband_email
    }
    
    # Update wife's family tree
    family_tree_ref.document(wife_family_tree_id).update({
        "familyMembers": wife_members_list,
        "relatives": wife_relatives
    })
    
    # Update user profiles
    user_profiles_ref.document(wife_email).update({
        "familyTreeId": husband_family_tree_id,
        "oldFamilyTreeId": wife_family_tree_id,
        "lastName": husband_last_name,
        "MARITAL_STATUS": "Married",
        "updatedAt": datetime.now().isoformat()
    })
    
    user_profiles_ref.document(husband_email).update({
        "MARITAL_STATUS": "Married",
        "updatedAt": datetime.now().isoformat()
    })
    
    return {
        "success": True,
        "message": "Spouse details added successfully",
        "familyTreeId": husband_family_tree_id,
        "wifeFamilyTreeId": wife_family_tree_id
    }

def handle_neither_has_tree_scenario(
    family_tree_ref, user_profiles_ref,
    wife_email, wife_node_id, wife_family_tree_id,
    husband_email, husband_member_id, husband_family_tree_id
) -> Dict[str, Any]:
    """Handle scenario where both spouses have created accounts but neither has family tree yet.
    They get married and we need to create a new family tree for them."""
    
    # Get both user profiles
    wife_profile_doc = user_profiles_ref.document(wife_email).get()
    husband_profile_doc = user_profiles_ref.document(husband_email).get()
    
    if not wife_profile_doc.exists or not husband_profile_doc.exists:
        return {
            "success": False,
            "message": "One or both user profiles not found"
        }
    
    wife_profile = wife_profile_doc.to_dict()
    husband_profile = husband_profile_doc.to_dict()
    
    wife_first_name = wife_profile.get('firstName', '')
    husband_first_name = husband_profile.get('firstName', '')
    husband_last_name = husband_profile.get('lastName', '')
    
    # Get profile images
    wife_image_data = wife_profile.get('profileImage', '')
    husband_image_data = husband_profile.get('profileImage', '')
    
    return handle_no_trees_scenario(
        family_tree_ref, user_profiles_ref,
        wife_email, husband_email,
        wife_first_name, husband_first_name, husband_last_name,
        wife_profile, husband_profile,
        wife_image_data, husband_image_data
    ) 

def create_family_tree_with_husband(
    family_tree_ref,
    user_profiles_ref,
    husband_node,
    wife_email
) -> Dict[str, Any]:
    """
    Creates a new family tree with a husband node and adds a wife using her email.
    
    Args:
        family_tree_ref: Firestore reference for family trees
        user_profiles_ref: Firestore reference for user profiles
        husband_node: Dictionary containing husband node details
        wife_email: Email of the wife
        
    Returns:
        Dict with success status, message and family tree ID
    """
    try:
        # Get wife profile data
        wife_profile_doc = user_profiles_ref.document(wife_email).get()
        if not wife_profile_doc or not wife_profile_doc.exists:
            return {
                "success": False, 
                "message": f"Wife profile not found for email {wife_email}"
            }
        wife_profile = wife_profile_doc.to_dict()
        
        # Get wife's profile details - extract first and last name from full name
        wife_first_name = wife_profile.get('firstName', 'Unknown')
        wife_last_name = wife_profile.get('lastName', 'Unknown')
        
        current_image_id = wife_profile.get('currentProfileImageId')
        wife_image_data = None
        if current_image_id:
            wife_profile_data = user_profiles_ref.document(wife_email)\
                      .collection('profileImages')\
                      .document(current_image_id)\
                      .get()
            if wife_profile_data.exists:
                image_data = wife_profile_data.to_dict().get('imageData')
                if image_data:
                    wife_image_data = f"data:image/jpeg;base64,{image_data}"
        
        # Get husband details directly from husband_node
        husband_email = husband_node.get('email')
        husband_name = husband_node.get('name', 'Unknown')
        husband_name_parts = husband_name.split()
        husband_first_name = husband_name_parts[0] if husband_name_parts else 'Unknown'
        husband_last_name = husband_name_parts[-1] if len(husband_name_parts) > 1 else 'Unknown'
        husband_image_data = husband_node.get('profileImage')
        
        # Add base64 prefix if not already present for wife's image
        if wife_image_data and isinstance(wife_image_data, str) and not wife_image_data.startswith('data:'):
            logger.info(f"Adding base64 prefix to wife's profile image")
            wife_image_data = 'data:image/jpeg;base64,' + wife_image_data
        
        # Create the family tree
        new_family_tree_id = str(uuid.uuid4())
        
        # Create timestamp-based IDs for husband and wife
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        husband_node_id = f"{timestamp}-{husband_name.replace(' ', '')}"
        # Add a millisecond to ensure wife node ID is different
        timestamp_wife = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Update wife's last name to match husband's
        wife_updated_name_parts = [wife_first_name, wife_last_name]
        wife_updated_name_parts.append(husband_last_name)
        wife_updated_name = ' '.join(wife_updated_name_parts)
        wife_node_id = f"{timestamp_wife}-{wife_updated_name.replace(' ', '')}"

        # Check if profiles exist
        husband_profile_exists = husband_email is not None
        wife_profile_exists = True  # We already verified this profile exists

        husband_details = {
            "id": husband_node_id,
            "name": husband_name,
            "gender": "male",
            "generation": 0,
            "parentId": None,
            "spouse": wife_node_id,
            "email": husband_email,
            "phone": husband_node.get('phone', ''),
            "profileImage": husband_image_data,
            "birthOrder": 1,
            "isSelf": True,
            "userProfileExists": husband_profile_exists
        }
        
        wife_details = {
            "id": wife_node_id,
            "name": wife_updated_name,
            "gender": "female",
            "generation": 0,
            "parentId": None,
            "spouse": husband_node_id,
            "email": wife_email,
            "phone": wife_profile.get('phone', ''),
            "profileImage": wife_image_data,
            "birthOrder": 1,
            "isSelf": False,
            "userProfileExists": wife_profile_exists
        }

        family_tree_ref.document(new_family_tree_id).set({
            "familyMembers": [husband_details, wife_details],
        })

        # Update wife's profile with new last name, marital status and family tree ID
        user_profiles_ref.document(wife_email).set({
            "familyTreeId": new_family_tree_id,
            "oldFamilyTreeId": None,
            "lastName": husband_last_name,
            "MARITAL_STATUS": "Married",
            "updatedAt": datetime.now().isoformat()
        }, merge=True)
        
        # Update husband's profile with family tree ID and marital status
        if husband_email:
            user_profiles_ref.document(husband_email).set({
                "familyTreeId": new_family_tree_id,
                "oldFamilyTreeId": None,
                "MARITAL_STATUS": "Married",
                "updatedAt": datetime.now().isoformat()
            }, merge=True)

        return {
            "success": True,
            "message": "Family tree created successfully with husband and wife",
            "familyTreeId": new_family_tree_id,
            "husbandNodeId": husband_node_id,
            "wifeNodeId": wife_node_id
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Error creating family tree: {str(e)}"
        }

def create_family_tree_with_wife(
    family_tree_ref,
    user_profiles_ref,
    wife_node,
    husband_email
) -> Dict[str, Any]:
    """
    Creates a new family tree with a wife node and adds a husband using his email.
    
    Args:
        family_tree_ref: Firestore reference for family trees
        user_profiles_ref: Firestore reference for user profiles
        wife_node: Dictionary containing wife node details
        husband_email: Email of the husband
        
    Returns:
        Dict with success status, message and family tree ID
    """
    try:
        # Get husband profile data
        husband_profile_doc = user_profiles_ref.document(husband_email).get()
        if not husband_profile_doc or not husband_profile_doc.exists:
            return {
                "success": False, 
                "message": f"Husband profile not found for email {husband_email}"
            }
        husband_profile = husband_profile_doc.to_dict()
        
        # Get husband's profile details - extract first and last name from full name
        husband_first_name = husband_profile.get('firstName', 'Unknown')
        husband_last_name = husband_profile.get('lastName', 'Unknown')
        husband_name = f"{husband_first_name} {husband_last_name}"
        
        current_image_id = husband_profile.get('currentProfileImageId')
        husband_image_data = None
        if current_image_id:
            husband_profile_data = user_profiles_ref.document(husband_email)\
                      .collection('profileImages')\
                      .document(current_image_id)\
                      .get()
            if husband_profile_data.exists:
                image_data = husband_profile_data.to_dict().get('imageData')
                if image_data:
                    husband_image_data = f"data:image/jpeg;base64,{image_data}"
        
        # Get wife details directly from wife_node
        wife_email = wife_node.get('email')
        wife_name = wife_node.get('name', 'Unknown')
        wife_name_parts = wife_name.split()
        wife_first_name = wife_name_parts[0] if wife_name_parts else 'Unknown'
        wife_image_data = wife_node.get('profileImage')
        
        # Create the family tree
        new_family_tree_id = str(uuid.uuid4())
        
        # Create timestamp-based IDs for husband and wife
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        husband_node_id = f"{timestamp}-{husband_name.replace(' ', '')}"
        
        # Update wife's name with husband's last name
        wife_updated_name_parts = wife_name_parts[:-1] if len(wife_name_parts) > 1 else [wife_first_name]
        wife_updated_name_parts.append(husband_last_name)
        wife_updated_name = ' '.join(wife_updated_name_parts)
        
        # Add a millisecond to ensure wife node ID is different
        timestamp_wife = datetime.now().strftime("%Y%m%d%H%M%S")
        wife_node_id = f"{timestamp_wife}-{wife_updated_name.replace(' ', '')}"

        # Check if profiles exist
        husband_profile_exists = True  # We already verified this profile exists
        wife_profile_exists = wife_email is not None

        husband_details = {
            "id": husband_node_id,
            "name": husband_name,
            "gender": "male",
            "generation": 0,
            "parentId": None,
            "spouse": wife_node_id,
            "email": husband_email,
            "phone": husband_profile.get('phone', ''),
            "profileImage": husband_image_data,
            "birthOrder": 1,
            "isSelf": True,
            "userProfileExists": husband_profile_exists
        }
        
        wife_details = {
            "id": wife_node_id,
            "name": wife_updated_name,
            "gender": "female",
            "generation": 0,
            "parentId": None,
            "spouse": husband_node_id,
            "email": wife_email,
            "phone": wife_node.get('phone', ''),
            "profileImage": wife_image_data,
            "birthOrder": 1,
            "isSelf": False,
            "userProfileExists": wife_profile_exists
        }

        family_tree_ref.document(new_family_tree_id).set({
            "familyMembers": [husband_details, wife_details],
        })

        # Update husband's profile with family tree ID and marital status
        user_profiles_ref.document(husband_email).set({
            "familyTreeId": new_family_tree_id,
            "oldFamilyTreeId": None,
            "MARITAL_STATUS": "Married",
            "updatedAt": datetime.now().isoformat()
        }, merge=True)
        
   

        return {
            "success": True,
            "message": "Family tree created successfully with wife and husband",
            "familyTreeId": new_family_tree_id,
            "husbandNodeId": husband_node_id,
            "wifeNodeId": wife_node_id
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Error creating family tree: {str(e)}"
        }

def add_husband_to_family_tree(
    family_tree_ref,
    user_profiles_ref,
    husband_node,
    wife_node_id,
    wife_family_tree_id
) -> Dict[str, Any]:
    """
    Adds a husband to an existing wife's family tree.
    
    Args:
        family_tree_ref: Firestore reference for family trees
        user_profiles_ref: Firestore reference for user profiles
        husband_node: Dictionary containing husband node details
        wife_node_id: ID of the wife node in her family tree
        wife_family_tree_id: ID of the wife's family tree
        
    Returns:
        Dict with success status, message and family tree ID
    """
    try:
        # Validate wife's family tree
        wife_family_tree_doc = family_tree_ref.document(wife_family_tree_id).get()
        if not wife_family_tree_doc.exists:
            return {
                "success": False,
                "message": f"Wife's family tree not found: {wife_family_tree_id}"
            }
            
        wife_family_tree = wife_family_tree_doc.to_dict()
        wife_members_list = wife_family_tree.get('familyMembers', [])
        wife_members_dict = {member.get('id'): member for member in wife_members_list}
        
        if wife_node_id not in wife_members_dict:
            return {
                "success": False,
                "message": f"Wife node ID {wife_node_id} not found in family tree"
            }
            
        wife_details = wife_members_dict[wife_node_id]
        
        # Extract husband details from husband_node
        husband_email = husband_node.get('email')
        husband_name = husband_node.get('name', 'Unknown')
        husband_name_parts = husband_name.split()
        husband_last_name = husband_name_parts[-1] if len(husband_name_parts) > 1 else husband_name
        husband_image_data = husband_node.get('profileImage')
        
        # Create timestamp-based ID for husband
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        husband_node_id = f"{timestamp}-{husband_name.replace(' ', '')}"
        
        # Check if husband profile exists
        husband_profile_exists = husband_email is not None
        
        # Update wife's name to match husband's last name
        wife_name = wife_details.get('name', 'Unknown')
        wife_name_parts = wife_name.split()
        wife_first_name = wife_name_parts[0] if wife_name_parts else 'Unknown'
        
        wife_updated_name_parts = wife_name_parts[:-1] if len(wife_name_parts) > 1 else [wife_first_name]
        wife_updated_name_parts.append(husband_last_name)
        wife_updated_name = ' '.join(wife_updated_name_parts)
        
        # Create husband details with spouse ID pointing to wife
        husband_details = {
            "id": husband_node_id,
            "name": husband_name,
            "gender": "male",
            "generation": wife_details.get('generation', 0),
            "parentId": None,
            "spouse": wife_node_id,  # Set husband's spouse to wife's node ID
            "email": husband_email,
            "phone": husband_node.get('phone', ''),
            "profileImage": husband_image_data,
            "birthOrder": 1,
            "isSelf": False,
            "userProfileExists": husband_profile_exists
        }
        
        # Update wife's spouse reference and name
        for i, member in enumerate(wife_members_list):
            if member.get('id') == wife_node_id:
                wife_members_list[i]['spouse'] = husband_node_id  # Set wife's spouse to husband's node ID
                wife_members_list[i]['name'] = wife_updated_name
                break
                
        # Add husband to wife's family members
        wife_members_list.append(husband_details)
        
        # Update wife's family tree
        family_tree_ref.document(wife_family_tree_id).update({
            "familyMembers": wife_members_list,
            "updatedAt": datetime.now().isoformat()
        })
        
        # Update wife profile if exists
        wife_email = wife_details.get('email')
        wife_profile_exists = wife_details.get('userProfileExists', False)
        
        if wife_email and wife_profile_exists:
            user_profiles_ref.document(wife_email).set({
                "name": wife_updated_name,
                "lastName": husband_last_name,
                "MARITAL_STATUS": "Married",
                "updatedAt": datetime.now().isoformat()
            }, merge=True)
        
        # Update husband's profile if exists
        if husband_email:
            user_profiles_ref.document(husband_email).set({
                "familyTreeId": wife_family_tree_id,
                "MARITAL_STATUS": "Married",
                "updatedAt": datetime.now().isoformat()
            }, merge=True)
            
        return {
            "success": True,
            "message": "Husband added successfully to wife's family tree",
            "familyTreeId": wife_family_tree_id,
            "husbandNodeId": husband_node_id,
            "wifeNodeId": wife_node_id
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Error adding husband to family tree: {str(e)}"
        }

def add_wife_to_family_tree(
    family_tree_ref,
    user_profiles_ref,
    wife_node,
    husband_node_id,
    husband_family_tree_id
) -> Dict[str, Any]:
    """
    Adds a wife to an existing husband's family tree.
    
    Args:
        family_tree_ref: Firestore reference for family trees
        user_profiles_ref: Firestore reference for user profiles
        wife_node: Dictionary containing wife node details
        husband_node_id: ID of the husband node in his family tree
        husband_family_tree_id: ID of the husband's family tree
        
    Returns:
        Dict with success status, message and family tree ID
    """
    try:
        print(f"husband_family_tree_id: {husband_family_tree_id}")
        print(f"husband_node_id: {husband_node_id}")
        print(f"wife_node: {wife_node}")
        # Validate husband's family tree
        husband_family_tree_doc = family_tree_ref.document(husband_family_tree_id).get()
        if not husband_family_tree_doc.exists:
            return {
                "success": False,
                "message": f"Husband's family tree not found: {husband_family_tree_id}"
            }
            
        husband_family_tree = husband_family_tree_doc.to_dict()
        husband_members_list = husband_family_tree.get('familyMembers', [])
        husband_members_dict = {member.get('id'): member for member in husband_members_list}
        
        if husband_node_id not in husband_members_dict:
            return {
                "success": False,
                "message": f"Husband node ID {husband_node_id} not found in family tree"
            }
            
        husband_details = husband_members_dict[husband_node_id]
        
        # Extract wife details from wife_node
        wife_email = wife_node.get('email')
        wife_name = wife_node.get('name', 'Unknown')
        print(f"wife_name: {wife_name}")
        wife_name_parts = wife_name.split()
        wife_first_name = wife_name_parts[0] if wife_name_parts else 'Unknown'
        print(f"wife_first_name: {wife_first_name}")
        wife_image_data = wife_node.get('profileImage')
        
        # Use husband's last name for wife
        husband_name = husband_details.get('name', 'Unknown')
        husband_name_parts = husband_name.split()
        husband_last_name = husband_name_parts[-1] if len(husband_name_parts) > 1 else husband_name
        
        # Create wife's updated name with husband's last name
        wife_updated_name_parts = wife_name_parts[:-1] if len(wife_name_parts) > 1 else [wife_first_name]
        wife_updated_name_parts.append(husband_last_name)
        wife_updated_name = ' '.join(wife_updated_name_parts)
        
        # Create timestamp-based ID for wife
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        wife_node_id = f"{timestamp}-{wife_updated_name.replace(' ', '')}"
        
        # Check if wife profile exists
        wife_profile_exists = wife_email is not None
        
        # Create wife details with spouse ID pointing to husband
        wife_details = {
            "id": wife_node_id,
            "name": wife_updated_name,
            "gender": "female",
            "generation": husband_details.get('generation', 0),
            "parentId": None,
            "spouse": husband_node_id,  # Set wife's spouse to husband's node ID
            "email": wife_email,
            "phone": wife_node.get('phone', ''),
            "profileImage": wife_image_data,
            "birthOrder": 1,
            "isSelf": False,
            "userProfileExists": wife_profile_exists
        }
        
        # Update husband's spouse reference
        for i, member in enumerate(husband_members_list):
            if member.get('id') == husband_node_id:
                husband_members_list[i]['spouse'] = wife_node_id
                break
                
        # Add wife to husband's family members
        husband_members_list.append(wife_details)
        
        # Update husband's family tree
        family_tree_ref.document(husband_family_tree_id).update({
            "familyMembers": husband_members_list,
            "updatedAt": datetime.now().isoformat()
        })
        
        # # Update wife's profile
        # user_profiles_ref.document(wife_email).set({
        #     "familyTreeId": husband_family_tree_id,
        #     "name": wife_updated_name,
        #     "lastName": husband_last_name,
        #     "MARITAL_STATUS": "Married",
        #     "updatedAt": datetime.now().isoformat()
        # }, merge=True)
            
        return {
            "success": True,
            "message": "Wife added successfully to husband's family tree",
            "familyTreeId": husband_family_tree_id,
            "husbandNodeId": husband_node_id,
            "wifeNodeId": wife_node_id
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Error adding wife to family tree: {str(e)}"
        } 

def create_family_tree_with_husband_email(
    family_tree_ref,
    user_profiles_ref,
    husband_email,
    wife_email
) -> Dict[str, Any]:
    """
    Creates a new family tree with a husband and wife using their emails.
    Fetches both user profiles, creates a family tree for husband,
    and adds wife to it or handles existing trees as needed.
    
    Args:
        family_tree_ref: Firestore reference for family trees
        user_profiles_ref: Firestore reference for user profiles
        husband_email: Email of the husband
        wife_email: Email of the wife
        
    Returns:
        Dict with success status, message and family tree ID
    """
    try:
        logger.info(f"Starting create_family_tree_with_husband_email for husband: {husband_email} and wife: {wife_email}")
        
        # Get husband profile data
        husband_profile_doc = user_profiles_ref.document(husband_email).get()
        if not husband_profile_doc or not husband_profile_doc.exists:
            logger.warning(f"Husband profile not found for email {husband_email}")
            return {
                "success": False, 
                "message": f"Husband profile not found for email {husband_email}"
            }
        husband_profile = husband_profile_doc.to_dict()
        logger.info("Successfully retrieved husband profile")
        
        # Get wife profile data
        wife_profile_doc = user_profiles_ref.document(wife_email).get()
        if not wife_profile_doc or not wife_profile_doc.exists:
            logger.warning(f"Wife profile not found for email {wife_email}")
            return {
                "success": False, 
                "message": f"Wife profile not found for email {wife_email}"
            }
        wife_profile = wife_profile_doc.to_dict()
        logger.info("Successfully retrieved wife profile")
        
        # Extract names and images
        husband_first_name = husband_profile.get('firstName', 'Unknown')
        husband_last_name = husband_profile.get('lastName', 'Unknown')
        husband_name = f"{husband_first_name} {husband_last_name}"
        logger.info(f"Husband name: {husband_name}")
        
        wife_first_name = wife_profile.get('firstName', 'Unknown')
        wife_last_name = wife_profile.get('lastName', 'Unknown')
        wife_name = f"{wife_first_name} {wife_last_name}"
        logger.info(f"Wife name: {wife_name}")
        
        # Get husband's profile image
        husband_image_data = None
        husband_current_image_id = husband_profile.get('currentProfileImageId')
        if husband_current_image_id:
            try:
                husband_profile_img = user_profiles_ref.document(husband_email)\
                          .collection('profileImages')\
                          .document(husband_current_image_id)\
                          .get()
                if husband_profile_img and husband_profile_img.exists:
                    image_data = husband_profile_img.to_dict().get('imageData')
                    if image_data:
                        husband_image_data = f"data:image/jpeg;base64,{image_data}"
                        logger.info("Successfully retrieved husband's profile image")
            except Exception as img_error:
                logger.warning(f"Could not fetch husband's profile image: {img_error}")
        
        # Get wife's profile image
        wife_image_data = None
        wife_current_image_id = wife_profile.get('currentProfileImageId')
        if wife_current_image_id:
            try:
                wife_profile_img = user_profiles_ref.document(wife_email)\
                          .collection('profileImages')\
                          .document(wife_current_image_id)\
                          .get()
                if wife_profile_img and wife_profile_img.exists:
                    image_data = wife_profile_img.to_dict().get('imageData')
                    if image_data:
                        wife_image_data = f"data:image/jpeg;base64,{image_data}"
                        logger.info("Successfully retrieved wife's profile image")
            except Exception as img_error:
                logger.warning(f"Could not fetch wife's profile image: {img_error}")
        
        # Update wife's name with husband's last name
        wife_updated_name = f"{wife_first_name} {husband_last_name}"
        logger.info(f"Updated wife name: {wife_updated_name}")
        
        # Create a new family tree for husband
        new_family_tree_id = str(uuid.uuid4())
        logger.info(f"Generated new family tree ID: {new_family_tree_id}")
        
        # Create timestamp-based IDs for husband and wife
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        husband_node_id = f"{timestamp}-{husband_name.replace(' ', '')}"
        wife_node_id = f"{timestamp}-{wife_updated_name.replace(' ', '')}"
        logger.info(f"Generated node IDs - Husband: {husband_node_id}, Wife: {wife_node_id}")
        
        # Create husband details
        husband_details = {
            "id": husband_node_id,
            "name": husband_name,
            "gender": "male",
            "generation": 0,
            "parentId": None,
            "spouse": wife_node_id,
            "email": husband_email,
            "phone": husband_profile.get('phone', ''),
            "profileImage": husband_image_data,
            "birthOrder": 1,
            "isSelf": True,
            "userProfileExists": True
        }
        logger.info("Created husband details")
        
        # Check if wife already has a family tree
        wife_family_tree_id = wife_profile.get('familyTreeId')
        logger.info(f"Wife's existing family tree ID: {wife_family_tree_id}")
        
        if wife_family_tree_id:
            # Wife has an existing family tree - fetch it
            wife_family_tree_doc = family_tree_ref.document(wife_family_tree_id).get()
            if not wife_family_tree_doc.exists:
                logger.warning(f"Wife's family tree not found: {wife_family_tree_id}")
                return {
                    "success": False,
                    "message": f"Wife's family tree not found: {wife_family_tree_id}"
                }
                
            wife_family_tree = wife_family_tree_doc.to_dict()
            wife_members_list = wife_family_tree.get('familyMembers', [])
            logger.info(f"Found {len(wife_members_list)} members in wife's family tree")
            
            # Find wife's node in her family tree
            wife_node = None
            wife_node_original_id = None
            for member in wife_members_list:
                if member.get('email') == wife_email:
                    wife_node = member
                    wife_node_original_id = member.get('id')
                    break
            
            if not wife_node_original_id:
                logger.warning("Wife node not found in her family tree")
                return {
                    "success": False,
                    "message": f"Wife node not found in her family tree"
                }
            
            logger.info(f"Found wife's original node ID: {wife_node_original_id}")
            
            # Step 1: Create wife node for husband's family tree
            wife_details = {
                "id": wife_node_id,
                "name": wife_updated_name,
                "gender": "female",
                "generation": 0,
                "parentId": None,
                "spouse": husband_node_id,
                "email": wife_email,
                "phone": wife_profile.get('phone', ''),
                "profileImage": wife_image_data,
                "birthOrder": 1,
                "isSelf": False,
                "userProfileExists": True,
                "originalFamilyTreeId": wife_family_tree_id,
                "originalNodeId": wife_node_original_id
            }
            logger.info("Created wife details for husband's tree")
            
            # Step 2: Create husband node for wife's family tree
            husband_node_in_wife_tree = {
                "id": f"husband_{wife_node_original_id}",
                "name": husband_name,
                "gender": "male",
                "generation": wife_node.get('generation', 0),
                "parentId": None,
                "spouse": wife_node_original_id,
                "email": husband_email,
                "phone": husband_profile.get('phone', ''),
                "profileImage": husband_image_data,
                "birthOrder": 1,
                "isSelf": False,
                "userProfileExists": True,
                "originalFamilyTreeId": new_family_tree_id,
                "originalNodeId": husband_node_id
            }
            logger.info("Created husband node for wife's tree")
            
            # Update wife's node in her tree to reference husband
            for i, member in enumerate(wife_members_list):
                if member.get('id') == wife_node_original_id:
                    wife_members_list[i]['spouse'] = husband_node_in_wife_tree['id']
                    wife_members_list[i]['name'] = wife_updated_name
                    wife_members_list[i]['originalFamilyTreeId'] = new_family_tree_id
                    wife_members_list[i]['originalNodeId'] = wife_node_id
                    break
            
            # Add husband to wife's family tree
            wife_members_list.append(husband_node_in_wife_tree)
            logger.info("Added husband to wife's family tree")
            
            # Step 3: Create relatives reference for wife's tree in husband's tree
            relatives = {
                wife_node_id: {
                    "name": wife_updated_name,
                    "email": wife_email,
                    "familyTreeId": wife_family_tree_id,
                    "originalNodeId": wife_node_original_id
                }
            }
            logger.info("Created relatives reference for wife's tree")
            
            # Step 4: Save both family trees
            family_tree_ref.document(new_family_tree_id).set({
                "familyMembers": [husband_details, wife_details],
                "relatives": relatives,
                "createdAt": datetime.now().isoformat(),
                "updatedAt": datetime.now().isoformat()
            })
            logger.info("Saved husband's family tree")
            
            # Update wife's family tree with husband reference
            wife_relatives = wife_family_tree.get('relatives', {})
            wife_relatives[husband_node_in_wife_tree['id']] = {
                "name": husband_name,
                "email": husband_email,
                "familyTreeId": new_family_tree_id,
                "originalNodeId": husband_node_id
            }
            
            family_tree_ref.document(wife_family_tree_id).update({
                "familyMembers": wife_members_list,
                "relatives": wife_relatives,
                "updatedAt": datetime.now().isoformat()
            })
            logger.info("Updated wife's family tree")
            
        else:
            # Wife doesn't have a family tree - simply add her to husband's tree
            wife_details = {
                "id": wife_node_id,
                "name": wife_updated_name,
                "gender": "female",
                "generation": 0,
                "parentId": None,
                "spouse": husband_node_id,
                "email": wife_email,
                "phone": wife_profile.get('phone', ''),
                "profileImage": wife_image_data,
                "birthOrder": 1,
                "isSelf": False,
                "userProfileExists": True
            }
            logger.info("Created wife details for new tree")
            
            # Create simple relative reference structure
            relatives = {
                wife_node_id: {
                    "name": wife_updated_name,
                    "email": wife_email
                }
            }
            logger.info("Created relatives reference")
            
            # Save the new family tree
            family_tree_ref.document(new_family_tree_id).set({
                "familyMembers": [husband_details, wife_details],
                "relatives": relatives,
                "createdAt": datetime.now().isoformat(),
                "updatedAt": datetime.now().isoformat()
            })
            logger.info("Saved new family tree")
        
        # Update husband's profile with family tree ID and marital status
        user_profiles_ref.document(husband_email).set({
            "familyTreeId": new_family_tree_id,
            "MARITAL_STATUS": "Married",
            "updatedAt": datetime.now().isoformat()
        }, merge=True)
        logger.info("Updated husband's profile")
        
        # Update wife's profile with husband's family tree ID, last name and marital status
        wife_profile_update = {
            "familyTreeId": new_family_tree_id,
            "name": wife_updated_name,
            "lastName": husband_last_name,
            "MARITAL_STATUS": "Married",
            "updatedAt": datetime.now().isoformat()
        }
        
        # If wife had a previous family tree, save it as oldFamilyTreeId
        if wife_family_tree_id:
            wife_profile_update["oldFamilyTreeId"] = wife_family_tree_id
        
        user_profiles_ref.document(wife_email).set(wife_profile_update, merge=True)
        logger.info("Updated wife's profile")
        
        logger.info("Successfully completed family tree creation")
        return {
            "success": True,
            "message": "Family tree created for husband with wife",
            "familyTreeId": new_family_tree_id,
            "husbandNodeId": husband_node_id,
            "wifeNodeId": wife_node_id
        }
        
    except Exception as e:
        logger.error(f"Error creating family tree with husband email: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"Error creating family tree with husband email: {str(e)}"
        }

def create_family_tree_with_wife_email(
    family_tree_ref,
    user_profiles_ref,
    wife_email,
    husband_email
) -> Dict[str, Any]:
    """
    Creates a new family tree with a wife and husband using their emails.
    Fetches both user profiles, creates a family tree for wife,
    and adds husband to it or handles existing trees as needed.
    
    Args:
        family_tree_ref: Firestore reference for family trees
        user_profiles_ref: Firestore reference for user profiles
        wife_email: Email of the wife
        husband_email: Email of the husband
        
    Returns:
        Dict with success status, message and family tree ID
    """
    try:
        logger.info(f"Starting create_family_tree_with_wife_email for wife: {wife_email} and husband: {husband_email}")
        
        # Get wife profile data
        wife_profile_doc = user_profiles_ref.document(wife_email).get()
        if not wife_profile_doc or not wife_profile_doc.exists:
            logger.warning(f"Wife profile not found for email {wife_email}")
            return {
                "success": False, 
                "message": f"Wife profile not found for email {wife_email}"
            }
        wife_profile = wife_profile_doc.to_dict()
        logger.info("Successfully retrieved wife profile")
        
        # Get husband profile data
        husband_profile_doc = user_profiles_ref.document(husband_email).get()
        if not husband_profile_doc or not husband_profile_doc.exists:
            logger.warning(f"Husband profile not found for email {husband_email}")
            return {
                "success": False, 
                "message": f"Husband profile not found for email {husband_email}"
            }
        husband_profile = husband_profile_doc.to_dict()
        logger.info("Successfully retrieved husband profile")
        
        # Check if husband already has a family tree
        husband_family_tree_id = husband_profile.get('familyTreeId')
        logger.info(f"Husband's existing family tree ID: {husband_family_tree_id}")
         
        # Extract names and images
        husband_first_name = husband_profile.get('firstName', 'Unknown')
        husband_last_name = husband_profile.get('lastName', 'Unknown')
        husband_name = f"{husband_first_name} {husband_last_name}"
        logger.info(f"Husband name: {husband_name}")
        
        wife_first_name = wife_profile.get('firstName', 'Unknown')
        wife_last_name = wife_profile.get('lastName', 'Unknown')
        wife_name = f"{wife_first_name} {wife_last_name}"
        logger.info(f"Wife name: {wife_name}")
        
        # Get husband's profile image
        husband_image_data = None
        husband_current_image_id = husband_profile.get('currentProfileImageId')
        if husband_current_image_id:
            try:
                husband_profile_img = user_profiles_ref.document(husband_email)\
                          .collection('profileImages')\
                          .document(husband_current_image_id)\
                          .get()
                if husband_profile_img and husband_profile_img.exists:
                    image_data = husband_profile_img.to_dict().get('imageData')
                    if image_data:
                        husband_image_data = f"data:image/jpeg;base64,{image_data}"
                        logger.info("Successfully retrieved husband's profile image")
            except Exception as img_error:
                logger.warning(f"Could not fetch husband's profile image: {img_error}")
        
        # Get wife's profile image
        wife_image_data = None
        wife_current_image_id = wife_profile.get('currentProfileImageId')
        if wife_current_image_id:
            try:
                wife_profile_img = user_profiles_ref.document(wife_email)\
                          .collection('profileImages')\
                          .document(wife_current_image_id)\
                          .get()
                if wife_profile_img and wife_profile_img.exists:
                    image_data = wife_profile_img.to_dict().get('imageData')
                    if image_data:
                        wife_image_data = f"data:image/jpeg;base64,{image_data}"
                        logger.info("Successfully retrieved wife's profile image")
            except Exception as img_error:
                logger.warning(f"Could not fetch wife's profile image: {img_error}")
        
        # Update wife's name with husband's last name
        wife_updated_name = f"{wife_first_name} {husband_last_name}"
        logger.info(f"Updated wife name: {wife_updated_name}")
        
        # If husband has no family tree, create a new one for wife and add husband
        if not husband_family_tree_id:
            logger.info("Creating new family tree as husband has no existing tree")
            # Create a new family tree
            new_family_tree_id = str(uuid.uuid4())
            logger.info(f"Generated new family tree ID: {new_family_tree_id}")
            
            # Create timestamp-based IDs for husband and wife
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            husband_node_id = f"{timestamp}-{husband_name.replace(' ', '')}"
            wife_node_id = f"{timestamp}-{wife_updated_name.replace(' ', '')}"
            logger.info(f"Generated node IDs - Husband: {husband_node_id}, Wife: {wife_node_id}")
            
            # Create husband details
            husband_details = {
                "id": husband_node_id,
                "name": husband_name,
                "gender": "male",
                "generation": 0,
                "parentId": None,
                "spouse": wife_node_id,
                "email": husband_email,
                "phone": husband_profile.get('phone', ''),
                "profileImage": husband_image_data,
                "birthOrder": 1,
                "isSelf": True,
                "userProfileExists": True
            }
            logger.info("Created husband details")
            
            # Create wife details
            wife_details = {
                "id": wife_node_id,
                "name": wife_updated_name,
                "gender": "female",
                "generation": 0,
                "parentId": None,
                "spouse": husband_node_id,
                "email": wife_email,
                "phone": wife_profile.get('phone', ''),
                "profileImage": wife_image_data,
                "birthOrder": 1,
                "isSelf": False,
                "userProfileExists": True
            }
            logger.info("Created wife details")
            
            # Save the new family tree
            family_tree_ref.document(new_family_tree_id).set({
                "familyMembers": [husband_details, wife_details],
                "createdAt": datetime.now().isoformat(),
                "updatedAt": datetime.now().isoformat()
            })
            logger.info("Saved new family tree")
            
            # Update husband's profile
            user_profiles_ref.document(husband_email).set({
                "familyTreeId": new_family_tree_id,
                "oldFamilyTreeId": None,
                "MARITAL_STATUS": "Married",
                "updatedAt": datetime.now().isoformat()
            }, merge=True)
            logger.info("Updated husband's profile")
            
            # Update wife's profile
            user_profiles_ref.document(wife_email).set({
                "familyTreeId": new_family_tree_id,
                "oldFamilyTreeId": None,
                "name": wife_updated_name,
                "lastName": husband_last_name,
                "MARITAL_STATUS": "Married",
                "updatedAt": datetime.now().isoformat()
            }, merge=True)
            logger.info("Updated wife's profile")
            
            logger.info("Successfully completed new family tree creation")
            return {
                "success": True,
                "message": "New family tree created for wife with husband",
                "familyTreeId": new_family_tree_id,
                "husbandNodeId": husband_node_id,
                "wifeNodeId": wife_node_id
            }
        
        # If husband already has a family tree, add wife to it
        else:
            logger.info("Adding wife to husband's existing family tree")
            # Fetch husband's family tree
            husband_family_tree_doc = family_tree_ref.document(husband_family_tree_id).get()
            if not husband_family_tree_doc.exists:
                logger.warning(f"Husband's family tree not found: {husband_family_tree_id}")
                return {
                    "success": False,
                    "message": f"Husband's family tree not found: {husband_family_tree_id}"
                }
                
            husband_family_tree = husband_family_tree_doc.to_dict()
            husband_members_list = husband_family_tree.get('familyMembers', [])
            logger.info(f"Found {len(husband_members_list)} members in husband's family tree")
            
            # Find husband's node in his family tree
            husband_node = None
            husband_node_id = None
            for member in husband_members_list:
                if member.get('email') == husband_email:
                    husband_node = member
                    husband_node_id = member.get('id')
                    break
            
            if not husband_node_id:
                logger.warning("Husband node not found in his family tree")
                return {
                    "success": False,
                    "message": f"Husband node not found in his family tree"
                }
            
            logger.info(f"Found husband's node ID: {husband_node_id}")
            
            # Create timestamp-based ID for wife
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            wife_node_id = f"{timestamp}-{wife_updated_name.replace(' ', '')}"
            logger.info(f"Generated wife node ID: {wife_node_id}")
            
            # Create wife details
            wife_details = {
                "id": wife_node_id,
                "name": wife_updated_name,
                "gender": "female",
                "generation": husband_node.get('generation', 0),
                "parentId": None,
                "spouse": husband_node_id,
                "email": wife_email,
                "phone": wife_profile.get('phone', ''),
                "profileImage": wife_image_data,
                "birthOrder": 1,
                "isSelf": False,
                "userProfileExists": True
            }
            logger.info("Created wife details")
            
            # Update husband's spouse reference
            for i, member in enumerate(husband_members_list):
                if member.get('id') == husband_node_id:
                    husband_members_list[i]['spouse'] = wife_node_id
                    break
            
            # Add wife to husband's family members
            husband_members_list.append(wife_details)
            logger.info("Added wife to husband's family members")
            
            # Update or create relatives section
            relatives = husband_family_tree.get('relatives', {})
            relatives[wife_node_id] = {
                "name": wife_updated_name,
                "email": wife_email
            }
            logger.info("Updated relatives section")
            
            # Update husband's family tree
            family_tree_ref.document(husband_family_tree_id).update({
                "familyMembers": husband_members_list,
                "relatives": relatives,
                "updatedAt": datetime.now().isoformat()
            })
            logger.info("Updated husband's family tree")
            
            # Update wife's profile
            user_profiles_ref.document(wife_email).set({
                "familyTreeId": husband_family_tree_id,
                "name": wife_updated_name,
                "lastName": husband_last_name,
                "MARITAL_STATUS": "Married",
                "updatedAt": datetime.now().isoformat()
            }, merge=True)
            logger.info("Updated wife's profile")
            
            logger.info("Successfully completed adding wife to husband's family tree")
            return {
                "success": True,
                "message": "Wife added to husband's existing family tree",
                "familyTreeId": husband_family_tree_id,
                "husbandNodeId": husband_node_id,
                "wifeNodeId": wife_node_id
            }
        
    except Exception as e:
        logger.error(f"Error creating family tree with wife email: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"Error creating family tree with wife email: {str(e)}"
        }

def handle_both_spouses_have_trees(
    family_tree_ref,
    user_profiles_ref,
    husband_email,
    husband_family_tree_id,
    wife_email,
    wife_family_tree_id
) -> Dict[str, Any]:
    """
    Handle scenario where both husband and wife have their own family trees.
    Links both trees by updating the user profiles and creating cross-references.
    
    Args:
        family_tree_ref: Firestore reference for family trees
        user_profiles_ref: Firestore reference for user profiles
        husband_email: Email of the husband
        husband_family_tree_id: ID of the husband's family tree
        wife_email: Email of the wife
        wife_family_tree_id: ID of the wife's family tree
        
    Returns:
        Dict with success status, message and family tree IDs
    """
    try:
        # Fetch both family trees
        husband_family_tree_doc = family_tree_ref.document(husband_family_tree_id).get()
        wife_family_tree_doc = family_tree_ref.document(wife_family_tree_id).get()
        
        if not husband_family_tree_doc.exists:
            return {
                "success": False,
                "message": f"Husband's family tree not found: {husband_family_tree_id}"
            }
            
        if not wife_family_tree_doc.exists:
            return {
                "success": False,
                "message": f"Wife's family tree not found: {wife_family_tree_id}"
            }
            
        husband_family_tree = husband_family_tree_doc.to_dict()
        wife_family_tree = wife_family_tree_doc.to_dict()
        
        # Get family members lists
        husband_members_list = husband_family_tree.get('familyMembers', [])
        wife_members_list = wife_family_tree.get('familyMembers', [])
        
        # Find husband and wife nodes in their respective trees
        husband_node = None
        husband_node_id = None
        for member in husband_members_list:
            if member.get('email') == husband_email:
                husband_node = member
                husband_node_id = member.get('id')
                break
                
        wife_node = None
        wife_node_id = None
        for member in wife_members_list:
            if member.get('email') == wife_email:
                wife_node = member
                wife_node_id = member.get('id')
                break
                
        if not husband_node_id:
            return {
                "success": False,
                "message": f"Husband node not found in his family tree"
            }
            
        if not wife_node_id:
            return {
                "success": False,
                "message": f"Wife node not found in her family tree"
            }
        
        # Get user profiles for additional details
        husband_profile_doc = user_profiles_ref.document(husband_email).get()
        wife_profile_doc = user_profiles_ref.document(wife_email).get()
        husband_profile = husband_profile_doc.to_dict()
        wife_profile = wife_profile_doc.to_dict()
        
        # Extract names and necessary details
        wife_first_name = wife_profile.get('firstName', wife_node.get('firstName', 'Unknown'))
        wife_last_name = wife_profile.get('lastName', wife_node.get('lastName', 'Unknown'))
        wife_name = f"{wife_first_name} {wife_last_name}"
        
        husband_first_name = husband_profile.get('firstName', 'Unknown')
        husband_last_name = husband_profile.get('lastName', 'Unknown')
        husband_name = f"{husband_first_name} {husband_last_name}"
        
        # Get profile images
        wife_image_data = wife_node.get('profileImage')
        husband_image_data = husband_profile.get('profileImage')
        
        # 1. Create wife's representation in husband's tree
        wife_in_husband_tree_id = f"wife_{husband_node_id}"
        
        # Update wife's name to take husband's last name
        wife_updated_name_parts = wife_name.split()[:-1] if len(wife_name.split()) > 1 else [wife_first_name]
        wife_updated_name_parts.append(husband_last_name)
        wife_updated_name = ' '.join(wife_updated_name_parts)
        
        wife_in_husband_tree = {
            "id": wife_in_husband_tree_id,
            "name": wife_updated_name,
            "firstName": wife_first_name,
            "lastName": husband_last_name,
            "email": wife_email,
            "phone": wife_node.get('phone', wife_profile.get('phone', '')),
            "gender": "female",
            "generation": husband_node.get('generation', 0),
            "parentId": None,
            "spouse": husband_node_id,
            "profileImage": wife_image_data,
            "birthOrder": wife_node.get('birthOrder', 1),
            "isSelf": False,
            "userProfileExists": True,
            "originalFamilyTreeId": wife_family_tree_id,
            "originalNodeId": wife_node_id
        }
        
        # 2. Create husband's representation in wife's tree
        husband_in_wife_tree_id = f"husband_{wife_node_id}"
        husband_in_wife_tree = {
            "id": husband_in_wife_tree_id,
            "name": husband_name,
            "firstName": husband_first_name,
            "lastName": husband_last_name,
            "email": husband_email,
            "phone": husband_node.get('phone', husband_profile.get('phone', '')),
            "gender": "male",
            "generation": wife_node.get('generation', 0),
            "parentId": None,
            "spouse": wife_node_id,
            "profileImage": husband_image_data,
            "birthOrder": husband_node.get('birthOrder', 1),
            "isSelf": False,
            "userProfileExists": True,
            "originalFamilyTreeId": husband_family_tree_id,
            "originalNodeId": husband_node_id
        }
        
        # 3. Update husband's spouse in his tree
        for i, member in enumerate(husband_members_list):
            if member.get('id') == husband_node_id:
                husband_members_list[i]['spouse'] = wife_in_husband_tree_id
                break
                
        # 4. Update wife's spouse and name in her tree
        for i, member in enumerate(wife_members_list):
            if member.get('id') == wife_node_id:
                wife_members_list[i]['spouse'] = husband_in_wife_tree_id
                wife_members_list[i]['name'] = wife_updated_name
                wife_members_list[i]['lastName'] = husband_last_name
                wife_members_list[i]['originalFamilyTreeId'] = husband_family_tree_id
                wife_members_list[i]['originalNodeId'] = wife_in_husband_tree_id
                break
                
        # 5. Add wife to husband's tree
        husband_members_list.append(wife_in_husband_tree)
        
        # 6. Add husband to wife's tree
        wife_members_list.append(husband_in_wife_tree)
        
        # 7. Update relatives mappings
        husband_relatives = husband_family_tree.get('relatives', {})
        husband_relatives[wife_in_husband_tree_id] = {
            "name": wife_updated_name,
            "email": wife_email,
            "familyTreeId": wife_family_tree_id,
            "originalNodeId": wife_node_id
        }
        
        wife_relatives = wife_family_tree.get('relatives', {})
        wife_relatives[husband_in_wife_tree_id] = {
            "name": husband_name,
            "email": husband_email,
            "familyTreeId": husband_family_tree_id,
            "originalNodeId": husband_node_id
        }
        
        # 8. Update both family trees
        family_tree_ref.document(husband_family_tree_id).update({
            "familyMembers": husband_members_list,
            "relatives": husband_relatives,
            "updatedAt": datetime.now().isoformat()
        })
        
        family_tree_ref.document(wife_family_tree_id).update({
            "familyMembers": wife_members_list,
            "relatives": wife_relatives,
            "updatedAt": datetime.now().isoformat()
        })
        
        # 9. Update user profiles
        # Set husband's family tree as primary for wife
        user_profiles_ref.document(wife_email).set({
            "familyTreeId": husband_family_tree_id,
            "oldFamilyTreeId": wife_family_tree_id,
            "name": wife_updated_name,
            "lastName": husband_last_name,
            "MARITAL_STATUS": "Married",
            "updatedAt": datetime.now().isoformat()
        }, merge=True)
        
        user_profiles_ref.document(husband_email).set({
            "MARITAL_STATUS": "Married",
            "updatedAt": datetime.now().isoformat()
        }, merge=True)
        
        return {
            "success": True,
            "message": "Both family trees linked successfully",
            "husbandFamilyTreeId": husband_family_tree_id,
            "wifeFamilyTreeId": wife_family_tree_id,
            "husbandNodeId": husband_node_id,
            "wifeNodeId": wife_node_id
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Error linking family trees: {str(e)}"
        } 

def adding_wife_to_family_tree(
    family_tree_ref,
    user_profiles_ref,
    husband_family_tree_id,
    husband_node_id,
    husband_email,
    wife_email
) -> Dict[str, Any]:
    """
    Add a wife to husband's family tree when isTreeFound is true and isAdding is 'wife'.
    
    Args:
        family_tree_ref: Firestore reference to family_tree collection
        user_profiles_ref: Firestore reference to user_profiles collection
        husband_family_tree_id: ID of husband's family tree
        husband_node_id: Node ID of husband in his family tree
        husband_email: Email of the husband
        wife_email: Email of the wife to be added
        
    Returns:
        Dictionary with success status and message
    """
    try:
        logger.info(f"Adding wife {wife_email} to husband's {husband_email} family tree")
        # Get husband's family tree
        husband_family_tree_doc = family_tree_ref.document(husband_family_tree_id).get()
        if not husband_family_tree_doc.exists:
            return {
                "success": False,
                "message": f"Husband's family tree not found: {husband_family_tree_id}"
            }
        
        # Get user profiles
        husband_profile_doc = user_profiles_ref.document(husband_email).get()
        wife_profile_doc = user_profiles_ref.document(wife_email).get()
        
 
            
        if not wife_profile_doc.exists:
            return {
                "success": False,
                "message": f"Wife profile not found for email {wife_email}"
            }
        
        husband_profile = husband_profile_doc.to_dict()
        wife_profile = wife_profile_doc.to_dict()
        
        # Get husband's family tree data
        husband_family_tree = husband_family_tree_doc.to_dict()
        husband_members_list = husband_family_tree.get('familyMembers', [])
        
        # Find husband node in his tree
        husband_node = None
        for member in husband_members_list:
            if member.get('id') == husband_node_id:
                husband_node = member
                break
                
        if not husband_node:
            return {
                "success": False,
                "message": f"Husband node not found in his family tree with ID {husband_node_id}"
            }
        
        # Check if wife already has a family tree
        wife_family_tree_id = wife_profile.get('familyTreeId')
        wife_family_tree = None
        wife_members_list = []
        wife_node = None
        wife_node_id = None
        
        if wife_family_tree_id:
            wife_family_tree_doc = family_tree_ref.document(wife_family_tree_id).get()
            if wife_family_tree_doc.exists:
                wife_family_tree = wife_family_tree_doc.to_dict()
                wife_members_list = wife_family_tree.get('familyMembers', [])
                
                # Find wife node in her tree
                for member in wife_members_list:
                    if member.get('email') == wife_email:
                        wife_node = member
                        wife_node_id = member.get('id')
                        break
        
        # Get names, preferring firstName/lastName fields in profiles
        # For husband
        husband_first_name = husband_profile.get('firstName', '')
        husband_last_name = husband_profile.get('lastName', '')
        
        # Fallback to husband node name if profile fields are missing
        if not husband_first_name or not husband_last_name:
            husband_name = husband_node.get('name', 'Unknown')
            logger.info(f"Using husband node name: {husband_name} for parsing")
        husband_name_parts = husband_name.split()
            
        if not husband_first_name:
            husband_first_name = husband_name_parts[0] if husband_name_parts else 'Unknown'
            logger.info(f"Extracted husband first name: {husband_first_name}")
                
        if not husband_last_name:
            husband_last_name = husband_name_parts[-1] if len(husband_name_parts) > 1 else husband_name
            logger.info(f"Extracted husband last name: {husband_last_name}")
        
        # For wife
        wife_first_name = wife_profile.get('firstName', '')
        wife_last_name = wife_profile.get('lastName', '')
        
        # Fallback to parsing name if profile fields are missing
        if not wife_first_name:
            wife_name = wife_profile.get('name', 'Unknown')
            logger.info(f"Using wife name: {wife_name} for parsing")
        wife_name_parts = wife_name.split()
        wife_first_name = wife_name_parts[0] if wife_name_parts else 'Unknown'
        logger.info(f"Extracted wife first name: {wife_first_name}")
        
        logger.info(f"Using names - Husband: {husband_first_name} {husband_last_name}, Wife: {wife_first_name}")
        
        # Get profile images
        husband_image_data = husband_node.get('profileImage')
        wife_image_data = None
        
        # Fetch wife's profile image from Firestore
        profile_image_id = wife_profile.get('currentProfileImageId')
        if profile_image_id:
            try:
                logger.info(f"Fetching profile image with ID: {profile_image_id} for wife: {wife_email}")
                profile_image_ref = user_profiles_ref.document(wife_email).collection('profileImages').document(profile_image_id)
                profile_image_doc = profile_image_ref.get()
                
                if profile_image_doc.exists:
                    logger.info(f"Profile image found for wife: {wife_email}")
                    profile_image_data = profile_image_doc.to_dict()
                    image_data = profile_image_data.get('imageData', '')
                    # Add base64 prefix if not already present
                    if image_data and not image_data.startswith('data:'):
                        logger.info(f"Adding base64 prefix to wife's profile image")
                        wife_image_data = 'data:image/jpeg;base64,' + image_data
                    else:
                        wife_image_data = image_data
            except Exception as img_error:
                logger.warning(f"Could not fetch wife's profile image: {img_error}")
        
        # Create wife's representation in husband's tree
        wife_in_husband_tree_id = f"wife_{husband_node_id}"
        
        # Wife takes husband's last name for the merged family
        wife_updated_name = f"{wife_first_name} {husband_last_name}"
        logger.info(f"Setting wife's name to: {wife_updated_name}")
        
        # Check if wife's profile actually exists in Firebase
        wife_profile_exists = wife_profile_doc.exists
        logger.info(f"Wife profile exists in Firebase: {wife_profile_exists}")
        
        wife_in_husband_tree = {
            "id": wife_in_husband_tree_id,
            "name": wife_updated_name,
            "firstName": wife_first_name,
            "lastName": husband_last_name,
            "email": wife_email,
            "phone": wife_profile.get('phone', ''),
            "gender": "female",
            "generation": husband_node.get('generation', 0),
            "parentId": None,
            "spouse": husband_node_id,
            "profileImage": wife_image_data,
            "birthOrder": 1,
            "isSelf": False,
            "userProfileExists": wife_profile_exists,
            "originalFamilyTreeId": wife_family_tree_id if wife_family_tree_id else None,
            "originalNodeId": wife_node_id if wife_node_id else None
        }
        
        # Update husband's spouse in his tree
        for i, member in enumerate(husband_members_list):
            if member.get('id') == husband_node_id:
                husband_members_list[i]['spouse'] = wife_in_husband_tree_id
                break
        
        # Add wife to husband's tree
        husband_members_list.append(wife_in_husband_tree)
        
        # Update relatives mappings in husband's tree
        husband_relatives = husband_family_tree.get('relatives', {})
        
        
        # Update husband's family tree
     
        
        # If wife has her own family tree, create husband's representation there
        if wife_family_tree and wife_node_id:
            husband_in_wife_tree_id = f"husband_{wife_node_id}"
            
            # Check if husband's profile actually exists in Firebase
            husband_profile_exists = husband_profile_doc.exists
            logger.info(f"Husband profile exists in Firebase: {husband_profile_exists}")
            
            husband_in_wife_tree = {
                "id": husband_in_wife_tree_id,
                "name": f"{husband_first_name} {husband_last_name}",
                "firstName": husband_first_name,
                "lastName": husband_last_name,
                "email": husband_email,
                "phone": husband_profile.get('phone', ''),
                "gender": "male",
                "generation": wife_node.get('generation', 0),
                "parentId": None,
                "spouse": wife_node_id,
                "profileImage": husband_image_data,
                "birthOrder": 1,
                "isSelf": False,
                "userProfileExists": husband_profile_exists,
                "originalFamilyTreeId": husband_family_tree_id,
                "originalNodeId": husband_node_id
            }
            
            # Update wife's name and spouse in her tree
            for i, member in enumerate(wife_members_list):
                if member.get('id') == wife_node_id:
                    wife_members_list[i]['spouse'] = husband_in_wife_tree_id
                    wife_members_list[i]['name'] = wife_updated_name
                    wife_members_list[i]['lastName'] = husband_last_name
                    wife_members_list[i]['originalFamilyTreeId'] = husband_family_tree_id
                    wife_members_list[i]['originalNodeId'] = wife_in_husband_tree_id
                    break
            
            # Add husband to wife's tree
            wife_members_list.append(husband_in_wife_tree)
            
            # Update relatives mappings in wife's tree
            wife_relatives = wife_family_tree.get('relatives', {})
            wife_relatives[husband_in_wife_tree_id] = {
                "name": husband_name,
                "email": husband_email,
                "familyTreeId": husband_family_tree_id,
                "originalNodeId": husband_node_id
            }
            
            # Update wife's family tree
            family_tree_ref.document(wife_family_tree_id).update({
                "familyMembers": wife_members_list,
                "relatives": wife_relatives,
                "updatedAt": datetime.now().isoformat()
            })
            husband_relatives[wife_in_husband_tree_id] = {
            "name": wife_updated_name,
            "email": wife_email,
            "familyTreeId": wife_family_tree_id if wife_family_tree_id else None,
            "originalNodeId": wife_node_id if wife_node_id else None
            }
            
        family_tree_ref.document(husband_family_tree_id).update({
            "familyMembers": husband_members_list,
            "relatives": husband_relatives,
            "updatedAt": datetime.now().isoformat()
        })
        # Update user profiles
        user_profiles_ref.document(wife_email).set({
            "familyTreeId": husband_family_tree_id,
            "oldFamilyTreeId": wife_family_tree_id if wife_family_tree_id else None,
            "name": wife_updated_name,
            "lastName": husband_last_name,
            "MARITAL_STATUS": "Married",
            "updatedAt": datetime.now().isoformat()
        }, merge=True)
        
        user_profiles_ref.document(husband_email).set({
            "MARITAL_STATUS": "Married",
            "updatedAt": datetime.now().isoformat()
        }, merge=True)
        
        return {
            "success": True,
            "message": "Wife added to husband's family tree successfully",
            "husbandFamilyTreeId": husband_family_tree_id,
            "wifeFamilyTreeId": wife_family_tree_id if wife_family_tree_id else None,
            "husbandNodeId": husband_node_id,
            "wifeNodeId": wife_in_husband_tree_id
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Error adding wife to family tree: {str(e)}"
        }

def adding_husband_to_family_tree(
    family_tree_ref,
    user_profiles_ref,
    wife_family_tree_id,
    wife_node_id,
    wife_email,
    husband_email
) -> Dict[str, Any]:
    """
    Add a husband to wife's family tree when isTreeFound is true and isAdding is 'husband'.
    
    Args:
        family_tree_ref: Firestore reference to family_tree collection
        user_profiles_ref: Firestore reference to user_profiles collection
        wife_family_tree_id: ID of wife's family tree
        wife_node_id: Node ID of wife in her family tree
        wife_email: Email of the wife
        husband_email: Email of the husband to be added
        
    Returns:
        Dictionary with success status and message
    """
    try:
        logger.info(f"Adding husband {husband_email} to wife's {wife_email} family tree")
        # Get wife's family tree
        wife_family_tree_doc = family_tree_ref.document(wife_family_tree_id).get()
        if not wife_family_tree_doc.exists:
            return {
                "success": False,
                "message": f"Wife's family tree not found: {wife_family_tree_id}"
            }
        
        # Get user profiles
        wife_profile_doc = user_profiles_ref.document(wife_email).get()
        husband_profile_doc = user_profiles_ref.document(husband_email).get()
        
     
            
        if not husband_profile_doc.exists:
            return {
                "success": False,
                "message": f"Husband profile not found for email {husband_email}"
            }
        
        wife_profile = wife_profile_doc.to_dict()
        husband_profile = husband_profile_doc.to_dict()
        
        # Get wife's family tree data
        wife_family_tree = wife_family_tree_doc.to_dict()
        wife_members_list = wife_family_tree.get('familyMembers', [])
        
        # Find wife node in her tree
        wife_node = None
        for member in wife_members_list:
            if member.get('id') == wife_node_id:
                wife_node = member
                break
                
        if not wife_node:
            return {
                "success": False,
                "message": f"Wife node not found in her family tree with ID {wife_node_id}"
            }
        
        # Check if husband already has a family tree
        husband_family_tree_id = husband_profile.get('familyTreeId')
        husband_family_tree = None
        husband_members_list = []
        husband_node = None
        husband_node_id = None
        
        if husband_family_tree_id:
            husband_family_tree_doc = family_tree_ref.document(husband_family_tree_id).get()
            if husband_family_tree_doc.exists:
                husband_family_tree = husband_family_tree_doc.to_dict()
                husband_members_list = husband_family_tree.get('familyMembers', [])
                
                # Find husband node in his tree
                for member in husband_members_list:
                    if member.get('email') == husband_email:
                        husband_node = member
                        husband_node_id = member.get('id')
                        break
        
        # Get names, preferring firstName/lastName fields in profiles
        # For wife
        wife_family_tree_doc=family_tree_ref.document(wife_family_tree_id).get()
        wife_family_tree=wife_family_tree_doc.to_dict()
        wife_members_list=wife_family_tree.get('familyMembers',[])
        wife_node=None
        for member in wife_members_list:
            if member.get('id')==wife_node_id:
                wife_node=member
                break
        wife_name=wife_node.get('name')
        wife_name_parts = wife_name.split()
        wife_first_name=wife_name_parts[:-1]
        wife_last_name=wife_name_parts[-1]
            
        if not wife_first_name:
            wife_first_name = wife_name_parts[0] if wife_name_parts else 'Unknown'
            logger.info(f"Extracted wife first name: {wife_first_name}")
                
        if not wife_last_name:
            wife_last_name = wife_name_parts[-1] if len(wife_name_parts) > 1 else wife_name
            logger.info(f"Extracted wife last name: {wife_last_name}")
        
        # For husband
        husband_first_name = husband_profile.get('firstName', '')
        husband_last_name = husband_profile.get('lastName', '')
        
        # Fallback to parsing name if profile fields are missing
        if not husband_first_name or not husband_last_name:
            husband_name = husband_profile.get('name', 'Unknown')
            logger.info(f"Using husband name: {husband_name} for parsing")
            husband_name_parts = husband_name.split()
            
            if not husband_first_name:
                husband_first_name = husband_name_parts[0] if husband_name_parts else 'Unknown'
                logger.info(f"Extracted husband first name: {husband_first_name}")
                
            if not husband_last_name:
                husband_last_name = husband_name_parts[-1] if len(husband_name_parts) > 1 else husband_name
                logger.info(f"Extracted husband last name: {husband_last_name}")
        
        logger.info(f"Using names - Wife: {wife_first_name} {wife_last_name}, Husband: {husband_first_name} {husband_last_name}")
        
        # Get profile images
        wife_image_data = wife_node.get('profileImage')
        husband_image_data = None
        
        # Fetch husband's profile image from Firestore
        profile_image_id = husband_profile.get('currentProfileImageId')
        if profile_image_id:
            try:
                logger.info(f"Fetching profile image with ID: {profile_image_id} for husband: {husband_email}")
                profile_image_ref = user_profiles_ref.document(husband_email).collection('profileImages').document(profile_image_id)
                profile_image_doc = profile_image_ref.get()
                
                if profile_image_doc.exists:
                    logger.info(f"Profile image found for husband: {husband_email}")
                    profile_image_data = profile_image_doc.to_dict()
                    image_data = profile_image_data.get('imageData', '')
                    # Add base64 prefix if not already present
                    if image_data and not image_data.startswith('data:'):
                        logger.info(f"Adding base64 prefix to husband's profile image")
                        husband_image_data = 'data:image/jpeg;base64,' + image_data
                    else:
                        husband_image_data = image_data
            except Exception as img_error:
                logger.warning(f"Could not fetch husband's profile image: {img_error}")
        
        # Create husband's representation in wife's tree
        husband_in_wife_tree_id = f"husband_{wife_node_id}"
        
        # Check if husband's profile actually exists in Firebase
        husband_profile_exists = husband_profile_doc.exists
        logger.info(f"Husband profile exists in Firebase: {husband_profile_exists}")
        
        husband_in_wife_tree = {
            "id": husband_in_wife_tree_id,
            "name": f"{husband_first_name} {husband_last_name}",
            "firstName": husband_first_name,
            "lastName": husband_last_name,
            "email": husband_email,
            "phone": husband_profile.get('phone', ''),
            "gender": "male",
            "generation": wife_node.get('generation', 0),
            "parentId": None,
            "spouse": wife_node_id,
            "profileImage": husband_image_data,
            "birthOrder": 1,
            "isSelf": False,
            "userProfileExists": husband_profile_exists,
            "originalFamilyTreeId": husband_family_tree_id if husband_family_tree_id else None,
            "originalNodeId": husband_node_id if husband_node_id else None
        }
        
        # Update wife's spouse in her tree
        for i, member in enumerate(wife_members_list):
            if member.get('id') == wife_node_id:
                wife_members_list[i]['spouse'] = husband_in_wife_tree_id
                break
        
        # Add husband to wife's tree
        wife_members_list.append(husband_in_wife_tree)
        
        # Update relatives mappings in wife's tree
        wife_relatives = wife_family_tree.get('relatives', {})
        
        
        # If husband has his own family tree, create wife's representation there
        if husband_family_tree and husband_node_id:
            wife_in_husband_tree_id = f"wife_{husband_node_id}"
            
            # husband_profile_doc=user_profiles_ref.document(husband_email).get()
            # husband_profile=husband_profile_doc.to_dict()
            # husband_family_tree_id=husband_profile.get('familyTreeId')
            # husband_family_tree_doc=family_tree_ref.document(husband_family_tree_id).get()
            # husband_family_tree=husband_family_tree_doc.to_dict()
            # husband_members_list=husband_family_tree.get('familyMembers',[])
            # husband_node=None
            # husband_node_id=None
            # for member in husband_members_list:
            #     if member.get('email')==husband_email:
            #         husband_node=member
            #         husband_node_id=member.get('id')
            #         break
            # husband_name=husband_node.get('name')
            # Check if wife's profile actually exists in Firebase
            
            
            husband_profile_doc=user_profiles_ref.document(husband_email).get()
            husband_profile=husband_profile_doc.to_dict()
            husband_first_name=husband_profile.get('firstName')
            husband_last_name=husband_profile.get('lastName')
            husband_name=f'{husband_first_name} {husband_last_name}'
            
            for member in wife_members_list:
                if member.get('id')==wife_node_id:
                    wife_node=member
                    break
            wife_name=wife_node.get('name')
            wife_name_parts=wife_name.split()
            wife_first_name=wife_name_parts[0]
            wife_last_name=wife_name_parts[-1]
            
            
            wife_profile_exists = wife_node.get('userProfileExists',False)
            logger.info(f"Wife profile exists in Firebase: {wife_profile_exists}")
            
            # Wife takes husband's last name
            husband_last_name =husband_last_name
            wife_updated_name = f"{wife_first_name} {husband_last_name}"
            logger.info(f"Setting wife's name to: {wife_updated_name}")
            
            # Fetch wife's profile image from Firestore
            wife_image_data = None
            wife_image_data=wife_node.get('profileImage')
            
            wife_in_husband_tree = {
                "id": wife_in_husband_tree_id,
                "name": wife_updated_name,
                "firstName": wife_first_name,
                "lastName": husband_last_name,
                "email": wife_email,
                "phone": wife_node.get('phone', ''),
                "gender": "female",
                "generation": husband_node.get('generation', 0),
                "parentId": None,
                "spouse": husband_node_id,
                "profileImage": wife_image_data,
                "birthOrder": 1,
                "isSelf": False,
                "userProfileExists": wife_profile_exists,
                "originalFamilyTreeId": wife_family_tree_id,
                "originalNodeId": wife_node_id
            }
            
            # Update husband's spouse in his tree
            for i, member in enumerate(husband_members_list):
                if member.get('id') == husband_node_id:
                    husband_members_list[i]['spouse'] = wife_in_husband_tree_id
                    break
            
            # Add wife to husband's tree
            husband_members_list.append(wife_in_husband_tree)
            
            # Update relatives mappings in husband's tree
            husband_relatives = husband_family_tree.get('relatives', {})
            husband_relatives[wife_in_husband_tree_id] = {
                "name": wife_updated_name,
                "email": wife_node.get('email',None),
                "familyTreeId": wife_family_tree_id,
                "originalNodeId": wife_node_id
            }
            
            # Update husband's family tree
            family_tree_ref.document(husband_family_tree_id).update({
                "familyMembers": husband_members_list,
                "relatives": husband_relatives,
                "updatedAt": datetime.now().isoformat()
            })
            
            # Also update wife's name in her own tree to match husband's last name
            for i, member in enumerate(wife_members_list):
                if member.get('id') == wife_node_id:
                    wife_members_list[i]['name'] = wife_updated_name
                    wife_members_list[i]['lastName'] = husband_last_name
                    break
            wife_relatives[husband_in_wife_tree_id] = {
            "name": husband_name,
            "email": husband_email,
            "familyTreeId": husband_family_tree_id if husband_family_tree_id else None,
            "originalNodeId": husband_node_id if husband_node_id else None
            }
        
        # Update wife's family tree
       
                    
            family_tree_ref.document(wife_family_tree_id).update({
                "familyMembers": wife_members_list,
                "relatives": wife_relatives,
                "updatedAt": datetime.now().isoformat()
            })
             
       
            if wife_profile_exists:
            # Update wife's profile with new name
                user_profiles_ref.document(wife_email).set({
                    "name": wife_updated_name,
                    "lastName": husband_last_name,
                    "MARITAL_STATUS": "Married",
                    "updatedAt": datetime.now().isoformat()
                }, merge=True)
        else:
            # If husband doesn't have a tree, update wife's profile
                   # Update husband's profile
            # If husband doesn't have a family tree, create a new one for both
            logger.info("Husband doesn't have a family tree - creating a new family tree for both spouses")
            
         
            wife_family_tree_doc=family_tree_ref.document(wife_family_tree_id).get()
            wife_family_tree=wife_family_tree_doc.to_dict()
            wife_members_list=wife_family_tree.get('familyMembers',[])
            wife_node=None
            
            for member in wife_members_list:
                if member.get('id')==wife_node_id:
                    wife_node=member
                    break
            wife_name=wife_node.get('name')
            wife_name_parts=wife_name.split()
            wife_first_name=wife_name_parts[0]
            wife_last_name=wife_name_parts[-1]
            
            # Make sure profile existence flags are set
           
            
            # Make sure we have profile images for both
            # Fetch husband's profile image if not already done
            if husband_image_data is None:
                profile_image_id = husband_profile.get('currentProfileImageId')
                if profile_image_id:
                    try:
                        logger.info(f"Fetching profile image with ID: {profile_image_id} for husband: {husband_email}")
                        profile_image_ref = user_profiles_ref.document(husband_email).collection('profileImages').document(profile_image_id)
                        profile_image_doc = profile_image_ref.get()
                        
                        if profile_image_doc.exists:
                            logger.info(f"Profile image found for husband: {husband_email}")
                            profile_image_data = profile_image_doc.to_dict()
                            image_data = profile_image_data.get('imageData', '')
                            # Add base64 prefix if not already present
                            if image_data and not image_data.startswith('data:'):
                                logger.info(f"Adding base64 prefix to husband's profile image")
                                husband_image_data = 'data:image/jpeg;base64,' + image_data
                            else:
                                husband_image_data = image_data
                    except Exception as img_error:
                        logger.warning(f"Could not fetch husband's profile image: {img_error}")
            
            # Fetch wife's profile image if not already done
    
            
            # Generate timestamp for IDs
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            logger.info(f"Generated timestamp for IDs: {timestamp}")
            
            # Generate new family tree ID
            new_family_tree_id = str(uuid.uuid4())
            logger.info(f"Generated new family tree ID: {new_family_tree_id}")
            
            # Create a combined family members list with both spouses
            combined_family_members = []
            
            # Add husband node to the new tree
            husband_full_name = f"{husband_first_name} {husband_last_name}"
            new_husband_node_id = f"{timestamp}-{husband_full_name.replace(' ', '')}"
            logger.info(f"Creating husband node with ID: {new_husband_node_id}")
            
            new_husband_node = {
                "id": new_husband_node_id,
                "name": husband_full_name,
                "firstName": husband_first_name,
                "lastName": husband_last_name,
                "email": husband_email,
                "phone": husband_profile.get('phone', ''),
                "gender": "male",
                "generation": 0,
                "parentId": None,
                "spouse": None,  # Will set this below
                "profileImage": husband_image_data,
                "birthOrder": 1,
                "isSelf": True,
                "userProfileExists": husband_profile_exists
            }
            
            # Add wife node to the new tree (with husband's last name)
            wife_updated_name = f"{wife_first_name} {husband_last_name}"
            new_wife_node_id = f"{timestamp}-{wife_updated_name.replace(' ', '')}"
            logger.info(f"Creating wife node with ID: {new_wife_node_id}")
            
            new_wife_node = {
                "id": new_wife_node_id,
                "name": wife_updated_name,
                "gender": "female",
                "generation": 0,
                "parentId": None,
                "spouse": new_husband_node_id,
                "email": wife_node.get('email',None),
                "phone": wife_node.get('phone', ''),
                "profileImage": wife_node.get('profileImage',None),
                "birthOrder": 1,
                "isSelf": False,
                "userProfileExists": wife_node.get('userProfileExists',False),
                "originalFamilyTreeId": wife_family_tree_id,
                "originalNodeId": wife_node_id
            }
            
            # Set husband's spouse to wife
            new_husband_node["spouse"] = new_wife_node_id
            
            # Add both to new family members list
            combined_family_members.append(new_husband_node)
            combined_family_members.append(new_wife_node)
            
           
            husband_relatives = {}
            
            # If wife has relatives in her old tree, copy them to the new tree
            husband_relatives[new_wife_node_id] = {
            "name": wife_updated_name,
            "email": wife_email,
            "familyTreeId": wife_family_tree_id if wife_family_tree_id else None,
            "originalNodeId": wife_node_id if wife_node_id else None
            }
            
            # Create the new family tree
            family_tree_ref.document(new_family_tree_id).set({ 
                "familyMembers": combined_family_members,
                "relatives": husband_relatives,
                "createdAt": datetime.now().isoformat(),
                "updatedAt": datetime.now().isoformat(),
                "name": f"{husband_first_name} and {wife_first_name}'s Family Tree"
            })
            
            logger.info(f"Created new family tree with ID: {new_family_tree_id}")
            
            
            
            husband_first_name = husband_profile.get('firstName', '')
            husband_last_name = husband_profile.get('lastName', '')
            
            # Fallback to parsing name if profile fields are missing
            if not husband_first_name or not husband_last_name:
                husband_name = husband_profile.get('name', 'Unknown')
                logger.info(f"Using husband name: {husband_name} for parsing")
                husband_name_parts = husband_name.split()
                
                if not husband_first_name:
                    husband_first_name = husband_name_parts[0] if husband_name_parts else 'Unknown'
                    logger.info(f"Extracted husband first name: {husband_first_name}")
                    
                if not husband_last_name:
                    husband_last_name = husband_name_parts[-1] if len(husband_name_parts) > 1 else husband_name
                    logger.info(f"Extracted husband last name: {husband_last_name}")
            
            logger.info(f"Using names - Wife: {wife_first_name} {wife_last_name}, Husband: {husband_first_name} {husband_last_name}")
            
            # Get profile images
          
            
            # Create husband's representation in wife's tree
            husband_in_wife_tree_id = f"husband_{wife_node_id}"
            
            # Check if husband's profile actually exists in Firebase
            husband_profile_exists = husband_profile_doc.exists
            logger.info(f"Husband profile exists in Firebase: {husband_profile_exists}")
            
            husband_in_wife_tree = {
                "id": husband_in_wife_tree_id,
                "name": f"{husband_first_name} {husband_last_name}",
                "firstName": husband_first_name,
                "lastName": husband_last_name,
                "email": husband_email,
                "phone": husband_profile.get('phone', ''),
                "gender": "male",
                "generation": wife_node.get('generation', 0),
                "parentId": None,
                "spouse": wife_node_id,
                "profileImage": husband_image_data,
                "birthOrder": 1,
                "isSelf": False,
                "userProfileExists": husband_profile_exists,
                "originalFamilyTreeId": husband_family_tree_id if husband_family_tree_id else None,
                "originalNodeId": husband_node_id if husband_node_id else None
            }
            
            # Update wife's spouse in her tree
            for i, member in enumerate(wife_members_list):
                if member.get('id') == wife_node_id:
                    wife_members_list[i]['spouse'] = husband_in_wife_tree_id
                    break
            
            # Add husband to wife's tree
            wife_members_list.append(husband_in_wife_tree)
            
            # Update relatives mappings in wife's tree
            wife_relatives = wife_family_tree.get('relatives', {})
            
            
            wife_relatives[husband_in_wife_tree_id] = {
            "name": husband_full_name,
            "email": husband_email,
            "familyTreeId": new_family_tree_id,
            "originalNodeId": new_husband_node_id 
            }
             
            family_tree_ref.document(wife_family_tree_id).set({
                "familyMembers": wife_members_list,
                "relatives": wife_relatives,
                "updatedAt": datetime.now().isoformat()
            },merge=True)
            
        # Update husband's profile
            user_profiles_ref.document(husband_email).set({
                "familyTreeId": new_family_tree_id,
                "MARITAL_STATUS": "Married",
                "updatedAt": datetime.now().isoformat()
            }, merge=True)
            
            # Update wife's profile
            user_profiles_ref.document(wife_email).set({
                "familyTreeId": new_family_tree_id,
                "oldFamilyTreeId": wife_family_tree_id,  # Store previous tree ID
                "name": wife_updated_name,
                "lastName": husband_last_name,
            "MARITAL_STATUS": "Married",
            "updatedAt": datetime.now().isoformat()
        }, merge=True)
            
            return {
                "success": True,
                "message": "Created new family tree for husband and wife with merged relatives",
                "newFamilyTreeId": new_family_tree_id,
                "wifeNodeId": new_wife_node_id,
                "husbandNodeId": new_husband_node_id,
                "previousWifeTreeId": wife_family_tree_id
            }
      
        
       
        
        # Update husband's profile
    
        
        return {
            "success": True,
            "message": "Husband added to wife's family tree successfully",
            "wifeFamilyTreeId": wife_family_tree_id,
            "husbandFamilyTreeId": husband_family_tree_id if husband_family_tree_id else None,
            "wifeNodeId": wife_node_id,
            "husbandNodeId": husband_in_wife_tree_id
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Error adding husband to family tree: {str(e)}"
        }
