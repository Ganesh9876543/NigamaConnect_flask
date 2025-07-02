import uuid
from datetime import datetime
import logging
import requests

logger = logging.getLogger(__name__)

def add_child_to_family_tree(
    family_tree_ref,
    user_profiles_ref,
    family_tree_id: str,
    father_node_id: str,
    child_data: dict
):
    """
    Add a child to a parent in the family tree.
    
    Args:
        family_tree_ref: Firestore reference for family trees
        user_profiles_ref: Firestore reference for user profiles
        family_tree_id: ID of the family tree
        father_node_id: ID of the father node
        child_data: Dictionary containing child data
        
    Returns:
        dict: Result of the operation with success status and message
    """
    try:
        # Get the family tree document
        family_tree_doc = family_tree_ref.document(family_tree_id).get()
        
        if not family_tree_doc.exists:
            return {
                "success": False,
                "message": f"Family tree not found: {family_tree_id}"
            }

        family_tree = family_tree_doc.to_dict()
        family_members = family_tree.get('familyMembers', [])
        
        # Check if father exists in the family tree
        father_exists = False
        for member in family_members:
            if member.get('id') == father_node_id:
                father_exists = True
                break
                
        if not father_exists:
            return {
                "success": False,
                "message": f"Father node with ID {father_node_id} not found in the family tree"
            }
            
        # Add parentId to the child data
        child_data['parentId'] = father_node_id
        
       
            
        # Add the child to the family members list
        family_members.append(child_data)
        
        # Update the family tree document
        family_tree_ref.document(family_tree_id).update({
            'familyMembers': family_members,
            'updatedAt': datetime.now().isoformat()
        })
        
        # # If the child has an email, update their profile with the family tree ID
        # child_email = child_data.get('email')
        # if child_email:
        #     user_profiles_ref.document(child_email).set({
        #         'familyTreeId': family_tree_id,
        #         'updatedAt': datetime.now().isoformat()
        #     }, merge=True)

        return {
            "success": True,
            "message": "Child added successfully to the family tree",
            "familyTreeId": family_tree_id,
            "childNodeId": child_data['id']
        }

    except Exception as e:
        logger.error(f"Error adding child to family tree: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def create_family_tree_with_father_child(
    family_tree_ref,
    user_profiles_ref,
    father_email: str,
    child_data: dict
):
    """
    Create a new family tree with a father and child.
    Fetches father's details from their profile using the email.
    
    Args:
        family_tree_ref: Firestore reference for family trees
        user_profiles_ref: Firestore reference for user profiles
        father_email: Email of the father
        child_data: Dictionary containing child data
        
    Returns:
        dict: Result of the operation with success status and message
    """
    try:
        # Fetch father's profile to check if it exists
        father_profile_doc = user_profiles_ref.document(father_email).get()
        
        if not father_profile_doc.exists:
            return {
                "success": False,
                "message": f"Father profile not found with email: {father_email}"
            }
        
        # Get father's profile data
        father_profile = father_profile_doc.to_dict()
        
        # Generate timestamp for father node ID
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        father_full_name = f"{father_profile.get('firstName', '')} {father_profile.get('lastName', '')}"
        
        # Create father node data from profile with timestamp-fullname ID
        father_data = {
            'id': f"{timestamp}-{father_full_name.replace(' ', '')}",
            'name': father_full_name,
            'gender': father_profile.get('gender', 'male'),
            'email': father_email,
            'phone': father_profile.get('phone', ''),
            'isSelf': True,
            "generation": 1,
            'userProfileExists': True,
            'aliveStatus': True,
            'dateOfBirth': father_profile.get('DOB', ''),
            'deathDate': father_profile.get('deathDate', '')
        }
        
        # Try to get father's profile image
        profile_image_id = father_profile.get('dashboardImageId')
        if profile_image_id:
            try:
                profile_image_ref = user_profiles_ref.document(father_email).collection('profileImages').document(profile_image_id)
                profile_image_doc = profile_image_ref.get()
                
                if profile_image_doc.exists:
                    profile_image_data = profile_image_doc.to_dict()
                    father_data['profileImage'] = profile_image_data.get('imageData', '')
            except Exception as img_error:
                logger.warning(f"Could not fetch father's profile image: {img_error}")
            
        # Generate a new family tree ID
        new_family_tree_id = str(uuid.uuid4())
            
        # Generate timestamp-based ID for child
        child_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        if 'name' in child_data:
            child_name = child_data['name']
            child_data['id'] = f"{child_timestamp}-{child_name.replace(' ', '')}"
        else:
            child_data['id'] = f"{child_timestamp}-child"
            
        # Set child's parentId to father's ID
        child_data['parentId'] = father_data['id']
        
        # Create the family members list with father and child
        family_members = [father_data, child_data]
        
        # Create the new family tree
        family_tree_ref.document(new_family_tree_id).set({
            'familyMembers': family_members,
            'createdAt': datetime.now().isoformat(),
            'updatedAt': datetime.now().isoformat()
        })
        
        # Update father's profile with family tree ID
        user_profiles_ref.document(father_email).set({
            'familyTreeId': new_family_tree_id,
            'updatedAt': datetime.now().isoformat()
        }, merge=True)
        
        # If child has an email, update their profile with family tree ID
        child_email = child_data.get('email')
        if child_email:
            user_profiles_ref.document(child_email).set({
                'familyTreeId': new_family_tree_id,
                'updatedAt': datetime.now().isoformat()
            }, merge=True)
            
        return {
            "success": True,
            "message": "Family tree created successfully with father and child",
            "familyTreeId": new_family_tree_id,
            "fatherNodeId": father_data['id'],
            "childNodeId": child_data['id']
        }
        
    except Exception as e:
        logger.error(f"Error creating family tree with father and child: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def add_child_with_subtree(
    family_tree_ref,
    user_profiles_ref,
    father_family_tree_id: str,
    father_node_id: str,
    child_email: str,
    child_birth_order: int
):
    """
    Add a child to a father's family tree, handling various scenarios:
    1. If child has no family tree: Create a node for the child in father's tree
    2. If child has own family tree: Merge only the child's subtree (child, spouse, descendants)
       into father's tree without modifying existing IDs
    
    Child generation is set as father's generation + 1 and all descendants' generations
    are adjusted accordingly.
    
    Args:
        family_tree_ref: Firestore reference for family trees
        user_profiles_ref: Firestore reference for user profiles
        father_family_tree_id: ID of the father's family tree
        father_node_id: ID of the father node in the family tree
        child_email: Email of the child
        child_birth_order: Birth order of the child
        
    Returns:
        dict: Result of the operation with success status and message
    """
    try:
        logger.info(f"Starting add_child_with_subtree for child: {child_email} to father's tree: {father_family_tree_id}")
        
        # Get the father's family tree
        father_tree_doc = family_tree_ref.document(father_family_tree_id).get()
        
        if not father_tree_doc.exists:
            logger.warning(f"Father's family tree not found: {father_family_tree_id}")
            return {
                "success": False,
                "message": f"Father's family tree not found: {father_family_tree_id}"
            }
        
        # Get the child's profile
        child_profile_doc = user_profiles_ref.document(child_email).get()
        
        if not child_profile_doc.exists:
            logger.warning(f"Child profile not found with email: {child_email}")
            return {
                "success": False,
                "message": f"Child profile not found with email: {child_email}"
            }
        
        # Get father's family tree data
        father_tree = father_tree_doc.to_dict()
        father_family_members = father_tree.get('familyMembers', [])
        father_relatives = father_tree.get('relatives', {})
        logger.info(f"Found {len(father_family_members)} members in father's family tree")
        
        # Check if father exists in the family tree and get his generation
        father_exists = False
        father_generation = 0  # Default if not set
        for member in father_family_members:
            if member.get('id') == father_node_id:
                father_exists = True
                father_generation = member.get('generation', 0)
                break
                
        if not father_exists:
            logger.warning(f"Father node with ID {father_node_id} not found in the family tree")
            return {
                "success": False,
                "message": f"Father node with ID {father_node_id} not found in the family tree"
            }
        
        # Child's generation is father's generation + 1
        child_generation = father_generation - 1
        logger.info(f"Setting child generation to {child_generation} (father's generation + 1)")
        
        # Get child's profile data
        child_profile = child_profile_doc.to_dict()
        child_family_tree_id = child_profile.get('familyTreeId')
        logger.info(f"Child's existing family tree ID: {child_family_tree_id}")
        
        # Generate timestamp for child node ID (only for new nodes)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        child_full_name = f"{child_profile.get('firstName', '')} {child_profile.get('lastName', '')}"
        child_node_id = f"{timestamp}-{child_full_name.replace(' ', '')}"
        logger.info(f"Generated child node ID: {child_node_id}")
        
        
        email1=None
        
        for member in father_family_members:
                if member.get('email') and member.get('userProfileExists') == True:
                    email1 = member.get('email')
                    break
        
        # SCENARIO 1: Child has no family tree
        if not child_family_tree_id:
            logger.info("Scenario 1: Child has no family tree - creating new node")
            # Create child node from profile
            child_node = {
                'id': child_node_id,
                'name': child_full_name,
                'gender': child_profile.get('GENDER', '').lower(),
                'email': child_email,
                'phone': child_profile.get('phone', ''),
                'birthOrder': child_birth_order,
                'parentId': father_node_id,
                'userProfileExists': True,
                'isSelf':False,
                'generation': child_generation,  # Add generation information
                'aliveStatus': True,
                'dateOfBirth': child_profile.get('DOB', ''),
                'deathDate': child_profile.get('deathDate', '')
            }
            
            # Try to get child's profile image
            profile_image_id = child_profile.get('currentProfileImageId')
            if profile_image_id:
                try:
                    logger.info(f"Fetching profile image with ID: {profile_image_id} for child: {child_email}")
                    profile_image_ref = user_profiles_ref.document(child_email).collection('profileImages').document(profile_image_id)
                    profile_image_doc = profile_image_ref.get()
                    
                    if profile_image_doc.exists:
                        logger.info(f"Profile image found for child: {child_email}")
                        profile_image_data = profile_image_doc.to_dict()
                        image_data = profile_image_data.get('imageData', '')
                        # Add base64 prefix if not already present
                        if image_data and not image_data.startswith('data:'):
                            logger.info(f"Adding base64 prefix to child's profile image")
                            child_node['profileImage'] = 'data:image/jpeg;base64,' + image_data
                        else:
                            child_node['profileImage'] = image_data
                        logger.info("Successfully added child's profile image")
                except Exception as img_error:
                    logger.warning(f"Could not fetch child's profile image: {img_error}")
            
            # Add child to father's family tree
            father_family_members.append(child_node)
            logger.info("Added child node to father's family tree")
            
            # Update father's family tree
            family_tree_ref.document(father_family_tree_id).update({
                'familyMembers': father_family_members,
                'updatedAt': datetime.now().isoformat()
            })
            logger.info("Updated father's family tree")
            
            # Update child's profile with father's family tree ID
            user_profiles_ref.document(child_email).update({
                'familyTreeId': father_family_tree_id,
                'updatedAt': datetime.now().isoformat()
            })
            logger.info("Updated child's profile with father's family tree ID")
            
            # get any one userprofile exits email from the family tree id
            
            
            # call an api  to update in otehr backent
            if email1:  
                http_request = requests.post(
                    f"https://9b38g2lm-5001.inc1.devtunnels.ms//api/users/share-items",
                    json={
                        "email1": email1,
                        "email2": child_email
                    }
                )
                logger.info(f"Successfully completed adding new child to father's family tree: {http_request.json()}")
            else:
                logger.warning("No userprofile exits email from the family tree id")
                
            logger.info("Successfully completed adding new child to father's family tree")
            return {
                "success": True,
                "message": "Child added successfully to father's family tree",
                "scenario": "new_child",
                "familyTreeId": father_family_tree_id,
                "childNodeId": child_node_id,
                "childGeneration": child_generation,
                "fatherGeneration": father_generation
            }
        
        # SCENARIO 2: Child has own family tree - merge only child's subtree
        else:
            
            logger.info("Scenario 2: Child has existing family tree - merging subtree")
            # Get child's family tree
            child_tree_doc = family_tree_ref.document(child_family_tree_id).get()
            
            if not child_tree_doc.exists:
                logger.warning(f"Child's family tree not found: {child_family_tree_id}")
                return {
                    "success": False,
                    "message": f"Child's family tree not found: {child_family_tree_id}"
                }
             
            # Get child's family tree data
            child_tree = child_tree_doc.to_dict()
            child_family_members = child_tree.get('familyMembers', [])
            child_relatives = child_tree.get('relatives', {})
            logger.info(f"Found {len(child_family_members)} members in child's family tree")
            
            # Find child's node in their family tree
            child_node = None
            original_child_generation = 0  # Default if not set
            
            # Look for the child by email first
            logger.info(f"Looking for child node with email: {child_email} in child's family tree")
            for member in child_family_members:
                if member.get('email') == child_email:
                    logger.info(f"Found child node by email with ID: {member.get('id')}")
                    child_node = member
                    # Keep the original ID
                    child_node_id = member.get('id')
                    # Get original generation for calculating generation difference
                    original_child_generation = member.get('generation', 0)
                    # Update parent ID to point to father
                    member['parentId'] = father_node_id
                    # Update generation to be father's generation + 1
                    member['generation'] = child_generation
                    # Add birth order
                    member['birthOrder'] = child_birth_order
                    break
            
            # If we didn't find the child by email, try to find the self-marked node
            if not child_node:
                logger.info("Child not found by email, looking for node marked as 'self'")
                for member in child_family_members:
                    if member.get('isSelf') == True:
                        logger.info(f"Found child node marked as 'self' with ID: {member.get('id')}")
                        child_node = member
                        # Keep the original ID
                        child_node_id = member.get('id')
                        # Get original generation for calculating generation difference
                        original_child_generation = member.get('generation', 0)
                        # Update parent ID to point to father
                        member['parentId'] = father_node_id
                        # Update generation to be father's generation + 1
                        member['generation'] = child_generation
                        # Add birth order
                        member['birthOrder'] = child_birth_order
                        # Ensure email is set correctly
                        member['email'] = child_email
                        break
                        
            # If still not found, try to find the root node or central node
            if not child_node:
                logger.info("Child not found by email or self flag, looking for root/central node")
                
                # Try to find a node without a parentId that might be the root
                for member in child_family_members:
                    if not member.get('parentId'):
                        # This might be the root node - especially if others have this as their parent
                        child_count = 0
                        for other in child_family_members:
                            if other.get('parentId') == member.get('id'):
                                child_count += 1
                                
                        if child_count > 0:
                            logger.info(f"Found potential root node with ID: {member.get('id')} with {child_count} children")
                            child_node = member
                            # Keep the original ID
                            child_node_id = member.get('id')
                            # Get original generation for calculating generation difference
                            original_child_generation = member.get('generation', 0)
                            # Update parent ID to point to father
                            member['parentId'] = father_node_id
                            # Update generation to be father's generation + 1
                            member['generation'] = child_generation
                            # Add birth order
                            member['birthOrder'] = child_birth_order
                            # Ensure email is set correctly
                            member['email'] = child_email
                            break
            
            logger.info(f"Found child's original generation: {original_child_generation}")
            
            # Calculate generation difference to adjust descendants
            generation_diff = child_generation - original_child_generation
            logger.info(f"Generation difference for descendants: {generation_diff}")
            
            # If child node not found in their family tree, create it
            if not child_node:
                logger.warning("Child node not found in their family tree - creating new node")
                child_node = {
                    'id': child_node_id,
                    'name': child_full_name,
                    'gender': child_profile.get('GENDER', '').lower(),
                    'email': child_email,
                    'phone': child_profile.get('phone', ''),
                    'birthOrder': child_birth_order,
                    'parentId': father_node_id,
                    'userProfileExists': True,
                    'isSelf': True,  # Mark as self for future reference
                    'generation': child_generation,  # Add generation information
                    'aliveStatus': True,
                    'dateOfBirth': child_profile.get('DOB', ''),
                    'deathDate': child_profile.get('deathDate', '')
                }
                
                # Try to get child's profile image
                profile_image_id = child_profile.get('currentProfileImageId')
                if profile_image_id:
                    try:
                        logger.info(f"Fetching profile image with ID: {profile_image_id} for child: {child_email}")
                        profile_image_ref = user_profiles_ref.document(child_email).collection('profileImages').document(profile_image_id)
                        profile_image_doc = profile_image_ref.get()
                        
                        if profile_image_doc.exists:
                            logger.info(f"Profile image found for child: {child_email}")
                            profile_image_data = profile_image_doc.to_dict()
                            image_data = profile_image_data.get('imageData', '')
                            # Add base64 prefix if not already present
                            if image_data and not image_data.startswith('data:'):
                                logger.info(f"Adding base64 prefix to child's profile image")
                                child_node['profileImage'] = 'data:image/jpeg;base64,' + image_data
                            else:
                                child_node['profileImage'] = image_data
                            logger.info("Successfully added child's profile image")
                    except Exception as img_error:
                        logger.warning(f"Could not fetch child's profile image: {img_error}")
                
                child_family_members.append(child_node)
                logger.info("Added new child node to child's family tree")
            
            # Function to recursively collect child's descendants and adjust generations
            def collect_descendants(member_id, members_dict, generation_adjustment):
                """
                Recursively collect all descendants of a member including spouse, children, and their descendants.
                
                Args:
                    member_id: ID of the member to collect descendants for
                    members_dict: Dictionary of all family members keyed by ID
                    generation_adjustment: Value to adjust generations by
                    
                Returns:
                    List of descendant members with adjusted generations
                """
                logger.info(f"Collecting descendants for member_id: {member_id}")
                descendants = []
                member = members_dict.get(member_id)
                if not member:
                    logger.warning(f"Member {member_id} not found in members_dict")
                    return []
                    
                # Find member's spouse
                spouse = None
                spouse_id = member.get('spouse')
                
                # First try to find spouse through direct reference
                if spouse_id and spouse_id in members_dict:
                    logger.info(f"Found spouse {spouse_id} through direct reference")
                    spouse = members_dict[spouse_id]
                    spouse = spouse.copy()  # Create copy to avoid modifying original
                    
                    # Set spouse generation same as member
                    if 'generation' in member:
                        spouse['generation'] = member['generation']
                    
                    descendants.append(spouse)
                else:
                    # Try to find spouse through alternative means - same generation and opposite gender
                    member_gender = member.get('gender', '').lower() if member.get('gender') else None
                    member_gen = member.get('generation', 0)
                    
                    logger.info(f"Looking for implicit spouse for {member_id} (gender: {member_gender}, gen: {member_gen})")
                    
                    for potential_id, potential_spouse in members_dict.items():
                        if potential_id == member_id:
                            continue  # Skip the member itself
                        
                        potential_gen = potential_spouse.get('generation', 0)
                        potential_gender = potential_spouse.get('gender', '').lower() if potential_spouse.get('gender') else None
                        
                        # Consider as spouse if:
                        # 1. Same generation and opposite gender, or
                        # 2. Has a parentId that matches member's parentId (siblings)
                        if ((potential_gen == member_gen) and 
                            (member_gender and potential_gender) and
                            (member_gender != potential_gender)):
                            
                            logger.info(f"Found implicit spouse {potential_id} with opposite gender and same generation")
                            spouse = potential_spouse.copy()  # Create a copy
                            spouse['generation'] = member['generation']  # Ensure same generation
                            descendants.append(spouse)
                            break
                
                # Find all direct children - multiple approaches
                children = []
                
                # Method 1: Using parentId field
                direct_children = [m.copy() for m in members_dict.values() 
                                 if m.get('parentId') == member_id]
                
                if direct_children:
                    logger.info(f"Found {len(direct_children)} children using parentId reference")
                    children.extend(direct_children)
                
                # Method 2: Check generation compared to member
                if not children:
                    member_gen = member.get('generation', 0)
                    potential_children = []
                    
                    # Look for nodes that are one generation lower
                    for potential_id, potential_child in members_dict.items():
                        potential_gen = potential_child.get('generation', None)
                        
                        # Skip if:
                        # - It's the same as the current member
                        # - It's the spouse we just found
                        # - It already has a different parentId
                        if (potential_id == member_id or 
                            (spouse and potential_id == spouse.get('id')) or
                            (potential_child.get('parentId') and potential_child.get('parentId') != member_id)):
                            continue
                        
                        # Consider as child if one generation below
                        if potential_gen is not None and potential_gen == member_gen - 1:
                            logger.info(f"Found potential child {potential_id} by generation comparison")
                            child = potential_child.copy()
                            child['parentId'] = member_id  # Ensure proper parent linkage
                            potential_children.append(child)
                    
                    children.extend(potential_children)
                
                logger.info(f"Found total of {len(children)} children for member {member_id}")
                
                # Adjust generations for children
                for child in children:
                    # Adjust generation
                    if 'generation' in child:
                        original_gen = child['generation']
                        child['generation'] = child['generation'] + generation_adjustment
                        logger.info(f"Adjusted child {child.get('id')} generation from {original_gen} to {child['generation']}")
                    else:
                        # If generation doesn't exist, set it based on parent - 1
                        child['generation'] = member['generation'] - 1
                    
                    descendants.append(child)
                    
                    # Recursively process this child's descendants
                    child_descendants = collect_descendants(child.get('id'), members_dict, generation_adjustment)
                    if child_descendants:
                        logger.info(f"Adding {len(child_descendants)} descendants from child {child.get('id')}")
                        descendants.extend(child_descendants)
                
                return descendants
            
            # Create a dictionary of child's family members for easy lookup
            child_members_dict = {member.get('id'): member for member in child_family_members if member.get('id')}
            
            # Log child members dict for debugging
            logger.info(f"Created members dictionary with {len(child_members_dict)} entries")
            for member_id, member in child_members_dict.items():
                logger.info(f"Member ID: {member_id}, Name: {member.get('name')}, Gen: {member.get('generation')}, Email: {member.get('email')}")
                if member.get('parentId'):
                    logger.info(f"  - Has parentId: {member.get('parentId')}")
                if member.get('spouse'):
                    logger.info(f"  - Has spouse: {member.get('spouse')}")
            
            # Collect the child's subtree (the child, spouse, and all descendants)
            subtree_to_merge = [child_node]
            if child_node_id and child_node_id in child_members_dict:
                logger.info(f"Starting collection of descendants for child node: {child_node_id}")
                descendants = collect_descendants(child_node_id, child_members_dict, generation_diff)
                
                #get all the emil from decendants where userprofile exitts true and add to a list
                email_list = []
                for member in descendants:
                    if member.get('email') and member.get('userProfileExists') == True:
                        email_list.append(member.get('email'))
                
                # call an api  to update in otehr backent   
                http_request = requests.post(
                    f"https://9b38g2lm-5001.inc1.devtunnels.ms//api/users/share-items-multiple",
                    json={
                        "email1": email1,
                        "targetEmails": email_list
                    }
                )
                
                subtree_to_merge.extend(descendants)
                logger.info(f"Collected {len(descendants)} descendants for child's subtree")
            else:
                logger.warning(f"Child node ID ({child_node_id}) not found in members dictionary, cannot collect descendants")
            
            # Add only the child's subtree to the father's family tree
            updated_family_members = father_family_members.copy()
            for member in subtree_to_merge:
                # Check if member already exists in father's tree (by email or ID)
                exists = False
                for father_member in updated_family_members:
                    if (member.get('email') and member.get('email') == father_member.get('email')) or \
                       (member.get('id') and member.get('id') == father_member.get('id')):
                        exists = True
                        # If exists, update the generation
                        if 'generation' in member:
                            father_member['generation'] = member['generation']
                        break
                
                # Add member if not exists
                if not exists:
                    updated_family_members.append(member)
            
            logger.info(f"Added {len(subtree_to_merge)} members to father's family tree")
            
            # Collect IDs of members in the subtree for filtering relatives
            subtree_member_ids = [member.get('id') for member in subtree_to_merge if member.get('id')]
            
            # Only merge relatives related to members in the subtree
            updated_relatives = father_relatives.copy()
            for node_id, relative_data in child_relatives.items():
                # Only include relatives for members in the subtree
                if node_id in subtree_member_ids:
                    # If the node already has relatives in father's tree, merge them
                    if node_id in updated_relatives:
                        # Merge the relative data, but don't overwrite existing values
                        for key, value in relative_data.items():
                            if key not in updated_relatives[node_id]:
                                updated_relatives[node_id][key] = value
                    else:
                        # Add the entire relative entry
                        updated_relatives[node_id] = relative_data
            
            logger.info("Merged relatives data for subtree members")
            
            # Update father's family tree with merged data
            family_tree_ref.document(father_family_tree_id).update({
                'familyMembers': updated_family_members,
                'relatives': updated_relatives,
                'updatedAt': datetime.now().isoformat()
            })
            logger.info("Updated father's family tree with merged data")
            
            # Update family tree ID for all members with profiles in the subtree
            members_updated = []
            for member in subtree_to_merge:
                member_email = member.get('email')
                member_profile_doc = user_profiles_ref.document(member_email).get()
                if member_email and member_profile_doc.exists:
                    # Update member's profile with father's family tree ID
                    user_profiles_ref.document(member_email).update({
                        'familyTreeId': father_family_tree_id,
                        'updatedAt': datetime.now().isoformat()
                    })
                    members_updated.append(member_email)
            
            logger.info(f"Updated {len(members_updated)} member profiles with new family tree ID")
            logger.info("Successfully completed merging child's subtree into father's family tree")
            
            return {
                "success": True,
                "message": "Child and direct family subtree merged into father's family tree with updated generations",
                "scenario": "merged_subtree",
                "familyTreeId": father_family_tree_id,
                "childNodeId": child_node_id,
                "childFamilyTreeId": child_family_tree_id,
                "childGeneration": child_generation,
                "fatherGeneration": father_generation,
                "generationOffset": generation_diff,
                "membersUpdated": members_updated
            }
    
    except Exception as e:
        logger.error(f"Error adding child with subtree: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        } 
