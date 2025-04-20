import uuid
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional

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
        "isSelf": True
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
        "isSelf": False
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
        "isSelf": True
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
        "isSelf": False
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
        "isSelf": False
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
        "isSelf": False
    }
    
    # Update husband's spouse reference
    for i, member in enumerate(husband_members_list):
        if member.get('id') == husband_node_id:
            husband_members_list[i]['spouse'] = new_wife_node_id
            break
            
    # Add wife to husband's family members
    husband_members_list.append(new_wife_details)
    wife_last_name=wife_details.get('lastName')
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
        "isSelf": False
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