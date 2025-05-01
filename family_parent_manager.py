from datetime import datetime
import logging
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_parents_to_family_tree(
    family_tree_ref,
    user_profiles_ref,
    child_family_tree_id: str,
    child_node_id: str,
    father_node=None,
    mother_node=None
):
    """
    Add parents (father and/or mother) to a child's family tree.
    
    Child is set as generation 0, and parents are set as generation 1 (child's generation + 1).
    All nodes in the subtree are updated with appropriate generation values.
    
    Args:
        family_tree_ref: Firestore reference for family trees
        user_profiles_ref: Firestore reference for user profiles
        child_family_tree_id: ID of the child's family tree
        child_node_id: ID of the child node in the family tree
        father_node: Data for the father node (optional)
        mother_node: Data for the mother node (optional)
        
    Returns:
        dict: Result of the operation with success status and message
    """
    try:
        # Validate input: at least one parent must be provided
        if not father_node and not mother_node:
            return {
                "success": False,
                "message": "At least one parent (father or mother) data must be provided"
            }
        
        # Get the child's family tree
        child_tree_doc = family_tree_ref.document(child_family_tree_id).get()
        
        if not child_tree_doc.exists:
            return {
                "success": False,
                "message": f"Child's family tree not found: {child_family_tree_id}"
            }
        
        # Get child's family tree data
        child_tree = child_tree_doc.to_dict()
        child_family_members = child_tree.get('familyMembers', [])
        
        # Check if child exists in the family tree
        child_node = None
        child_generation = 0
        for member in child_family_members:
            if member.get('id') == child_node_id:
                child_node = member
                child_generation = member.get('generation', 0)
                # Ensure child has generation set
                if 'generation' not in member:
                    member['generation'] = 0
                    child_generation = 0
                break
                
        if not child_node:
            return {
                "success": False,
                "message": f"Child node with ID {child_node_id} not found in the family tree"
            }
        
        # Parent generation should be child generation + 1
        parent_generation = child_generation + 1
        
        # Generate timestamp for node IDs 
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Prepare parents data and add to family members
        added_parents = []
        
        # Add father if provided
        if father_node:
            # If father doesn't have an ID, generate one
            if 'id' not in father_node:
                father_name = father_node.get('name', 'Father').replace(' ', '')
                father_node['id'] = f"{timestamp}-{father_name}"
            
            # Set generation for father (child gen + 1)
            father_node['generation'] = parent_generation
            
            # Add father to family members
            father_node_id = father_node['id']
            child_family_members.append(father_node)
            added_parents.append({
                "type": "father",
                "nodeId": father_node_id,
                "name": father_node.get('name', ''),
                "generation": parent_generation
            })
            
            # Update father's profile if email is provided
            father_email = father_node.get('email')
            if father_email and father_node.get('userProfileExists', False):
                user_profiles_ref.document(father_email).update({
                    'familyTreeId': child_family_tree_id,
                    'updatedAt': datetime.now().isoformat()
                })
        
        # Add mother if provided
        if mother_node:
            # If mother doesn't have an ID, generate one
            if 'id' not in mother_node:
                mother_name = mother_node.get('name', 'Mother').replace(' ', '')
                mother_node['id'] = f"{timestamp}-{mother_name}"
            
            # Set generation for mother (child gen + 1)
            mother_node['generation'] = parent_generation
            
            # Add mother to family members
            mother_node_id = mother_node['id']
            child_family_members.append(mother_node)
            added_parents.append({
                "type": "mother",
                "nodeId": mother_node_id,
                "name": mother_node.get('name', ''),
                "generation": parent_generation
            })
            
            # Update mother's profile if email is provided
            mother_email = mother_node.get('email')
            if mother_email and mother_node.get('userProfileExists', False):
                user_profiles_ref.document(mother_email).update({
                    'familyTreeId': child_family_tree_id,
                    'updatedAt': datetime.now().isoformat()
                })
        
        # Set up spouse relationship between father and mother if both are provided
        if father_node and mother_node:
            father_node_id = father_node['id']
            mother_node_id = mother_node['id']
            
            # Update father with spouse reference
            for member in child_family_members:
                if member.get('id') == father_node_id:
                    member['spouse'] = mother_node_id
                    break
                    
            # Update mother with spouse reference
            for member in child_family_members:
                if member.get('id') == mother_node_id:
                    member['spouse'] = father_node_id
                    break
        
        # Update child's parentId to father's ID if father provided, otherwise to mother's ID
        parent_id = father_node['id'] if father_node else mother_node['id']
        for member in child_family_members:
            if member.get('id') == child_node_id:
                member['parentId'] = parent_id
                break
        
        # Update all generations in the subtree
        # # For each child of the current child, update their generation and their descendants
        # child_descendants = []
        # for member in child_family_members:
        #     if member.get('parentId') == child_node_id:
        #         child_descendants.append(member.get('id'))
        
        # # If there are descendants, update their generations and their subtrees
        # for descendant_id in child_descendants:
        #     child_family_members = update_subtree_generations(child_family_members, descendant_id, child_generation - 1)
        
        # Update the family tree document
        family_tree_ref.document(child_family_tree_id).update({
            'familyMembers': child_family_members,
            'updatedAt': datetime.now().isoformat()
        })
        
        return {
            "success": True,
            "message": "Parents added successfully to the child's family tree with updated generations",
            "familyTreeId": child_family_tree_id,
            "childNodeId": child_node_id,
            "childGeneration": child_generation,
            "parentGeneration": parent_generation,
            "addedParents": added_parents
        }
    
    except Exception as e:
        logger.error(f"Error adding parents to family tree: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def create_family_tree_with_parents(
    family_tree_ref,
    user_profiles_ref,
    child_email: str,
    father_node=None,
    mother_node=None
):
    """
    Create a new family tree for a child and add parents (father and mother).
    
    Child is set as generation 0, and parents are set as generation 1 (child's generation + 1).
    If parent nodes already have generation values, they are respected and child's generation is adjusted accordingly.
    
    Args:
        family_tree_ref: Firestore reference for family trees
        user_profiles_ref: Firestore reference for user profiles
        child_email: Email of the child
        father_node: Data for the father node (optional)
        mother_node: Data for the mother node (optional)
        
    Returns:
        dict: Result of the operation with success status and message
    """
    try:
        # Validate input: at least one parent must be provided
        if not father_node and not mother_node:
            return {
                "success": False,
                "message": "At least one parent (father or mother) data must be provided"
            }
        
        # Validate child email
        if not child_email:
            return {
                "success": False,
                "message": "Child email is required"
            }
        
        # Get child's profile
        child_profile_doc = user_profiles_ref.document(child_email).get()
        
        if not child_profile_doc.exists:
            return {
                "success": False,
                "message": f"Child profile not found with email: {child_email}"
            }
        
        # Get child's profile data
        child_profile = child_profile_doc.to_dict()
        
        # Check if child already has a family tree
        existing_family_tree_id = child_profile.get('familyTreeId')
        if existing_family_tree_id:
            # If child already has a family tree, you might want to just add parents to that tree
            # or return an error. For now, we'll return an error.
            return {
                "success": False,
                "message": f"Child already has a family tree with ID: {existing_family_tree_id}. Use add_parents_to_family_tree or merge_family_trees instead."
            }
        
        # Generate timestamp for IDs
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Determine parent generation
        # If father_node already has generation set, use that as reference
        if father_node and 'generation' in father_node:
            parent_generation = father_node['generation']
        # If mother_node already has generation set, use that as reference
        elif mother_node and 'generation' in mother_node:
            parent_generation = mother_node['generation']
        else:
            # Default: parent is generation 1
            parent_generation = 1
        
        # Child generation is always one below parent
        child_generation = parent_generation - 1
        
        # Create child node from profile
        child_full_name = f"{child_profile.get('firstName', '')} {child_profile.get('lastName', '')}".strip()
        child_node_id = f"{timestamp}-{child_full_name.replace(' ', '')}"
        
        child_node = {
            'id': child_node_id,
            'name': child_full_name,
            'gender': child_profile.get('GENDER', '').lower(),
            'email': child_email,
            'phone': child_profile.get('phone', ''),
            'userProfileExists': True,
            'generation': child_generation  # Child generation is based on parent's generation
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
            except Exception as img_error:
                logger.warning(f"Could not fetch child's profile image: {img_error}")
        
        # Prepare family members array
        family_members = [child_node]
        
        # Add father if provided and generate ID if not present
        father_node_id = None
        if father_node:
            if 'id' not in father_node:
                father_name = father_node.get('name', 'Father').replace(' ', '')
                father_node['id'] = f"{timestamp}-{father_name}"
            
            # Set generation for father if not already present
            if 'generation' not in father_node:
                father_node['generation'] = parent_generation
            
            father_node_id = father_node['id']
            family_members.append(father_node)
        
        # Add mother if provided and generate ID if not present
        mother_node_id = None
        if mother_node:
            if 'id' not in mother_node:
                mother_name = mother_node.get('name', 'Mother').replace(' ', '')
                mother_node['id'] = f"{timestamp}-{mother_name}"
            
            # Set generation for mother if not already present
            if 'generation' not in mother_node:
                mother_node['generation'] = parent_generation
            
            mother_node_id = mother_node['id']
            family_members.append(mother_node)
        
        # Set up spouse relationship between father and mother if both are provided
        if father_node and mother_node:
            # Update father with spouse reference
            for member in family_members:
                if member.get('id') == father_node_id:
                    member['spouse'] = mother_node_id
                    break
                    
            # Update mother with spouse reference
            for member in family_members:
                if member.get('id') == mother_node_id:
                    member['spouse'] = father_node_id
                    break
        
        # Set parent-child relationship
        if father_node:
            # If father is provided, set child's parentId to father's ID
            for member in family_members:
                if member.get('id') == child_node_id:
                    member['parentId'] = father_node_id
                    break
        elif mother_node:
            # If only mother is provided, set child's parentId to mother's ID
            for member in family_members:
                if member.get('id') == child_node_id:
                    member['parentId'] = mother_node_id
                    break
        
        # Generate family tree ID
        family_tree_id = f"family-tree-{timestamp}"
        
        # Create family tree document
        family_tree_data = {
            'createdAt': datetime.now().isoformat(),
            'updatedAt': datetime.now().isoformat(),
            'familyMembers': family_members,
            'rootMember': child_node_id,  # Set child as root member
            'createdBy': child_email,
            'name': f"{child_full_name}'s Family Tree",
            'relatives': {}  # Initialize empty relatives object
        }
        
        # Save family tree to database
        family_tree_ref.document(family_tree_id).set(family_tree_data)
        
        # Update child's profile with family tree ID
        user_profiles_ref.document(child_email).update({
            'familyTreeId': family_tree_id,
            'updatedAt': datetime.now().isoformat()
        })
        
        # Update parent profiles if they have emails
        added_parents = []
        
        if father_node:
            added_parents.append({
                "type": "father",
                "nodeId": father_node_id,
                "name": father_node.get('name', ''),
                "generation": father_node.get('generation', parent_generation)
            })
            
            father_email = father_node.get('email')
            if father_email and father_node.get('userProfileExists', False):
                user_profiles_ref.document(father_email).update({
                    'familyTreeId': family_tree_id,
                    'updatedAt': datetime.now().isoformat()
                })
        
        if mother_node:
            added_parents.append({
                "type": "mother",
                "nodeId": mother_node_id,
                "name": mother_node.get('name', ''),
                "generation": mother_node.get('generation', parent_generation)
            })
            
            mother_email = mother_node.get('email')
            if mother_email and mother_node.get('userProfileExists', False):
                user_profiles_ref.document(mother_email).update({
                    'familyTreeId': family_tree_id,
                    'updatedAt': datetime.now().isoformat()
                })
        
        return {
            "success": True,
            "message": "Family tree created successfully with child and parents",
            "familyTreeId": family_tree_id,
            "childNodeId": child_node_id,
            "childName": child_full_name,
            "childGeneration": child_generation,
            "parentGeneration": parent_generation,
            "addedParents": added_parents
        }
    
    except Exception as e:
        logger.error(f"Error creating family tree with parents: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def update_subtree_generations(family_members, node_id, current_generation):
    """
    Helper function to recursively update generations for a node and all its descendants
    
    Args:
        family_members: List of family members in the tree
        node_id: ID of the node to start updating from
        current_generation: Generation value for the current node
        
    Returns:
        Updated family_members list
    """
    # Find and update the current node
    for member in family_members:
        if member.get('id') == node_id:
            # Update generation for this node
            old_generation = member.get('generation', None)
            member['generation'] = current_generation
            
            # Find all children of this node
            children = []
            for potential_child in family_members:
                if potential_child.get('parentId') == node_id:
                    children.append(potential_child)
            
            # Recursively update children (one generation down)
            for child in children:
                update_subtree_generations(family_members, child.get('id'), current_generation - 1)
            
            break
    
    return family_members

def merge_family_trees(
    family_tree_ref,
    user_profiles_ref,
    child_email: str,
    father_email: str,
    child_family_tree_id=None,
    child_node_id=None
):
    """
    Merge child's subtree into father's family tree.
    Only merges the child's spouse, children, and all descendants.
    
    Scenarios:
    1. If child has no tree and father has no tree: Return error
    2. If child has tree and father has no tree: Return error (no spouse)
    3. If child has no tree and father has tree: Add child to father's tree
    4. If both have trees: Merge child's subtree into father's tree
    """
    try:
        logger.info(f"Starting merge_family_trees operation for child: {child_email} and father: {father_email}, child_family_tree_id: {child_family_tree_id}, child_node_id: {child_node_id}")
        
        # Validate inputs
        if not child_email or not father_email:
            logger.warning("Missing required email parameters")
            return {
                "success": False,
                "message": "Both child and father email are required"
            }
        
        # Get child's profile and tree info
        logger.info(f"Fetching child profile for: {child_email}")
        child_profile_doc = user_profiles_ref.document(child_email).get()
        if not child_profile_doc.exists:
            logger.warning(f"Child profile not found: {child_email}")
            return {
                "success": False,
                "message": f"Child profile not found with email: {child_email}"
            }
        
        child_profile = child_profile_doc.to_dict()
        child_tree_id = child_profile.get('familyTreeId')
        logger.info(f"Child tree ID: {child_tree_id}")
        
        # Get father's profile and tree info
        logger.info(f"Fetching father profile for: {father_email}")
        father_profile_doc = user_profiles_ref.document(father_email).get()
        if not father_profile_doc.exists:
            logger.warning(f"Father profile not found: {father_email}")
            return {
                "success": False,
                "message": f"Father profile not found with email: {father_email}"
            }
        
        father_profile = father_profile_doc.to_dict()
        father_tree_id = father_profile.get('familyTreeId')
        logger.info(f"Father tree ID: {father_tree_id}")
        
        # Create father node data
        father_full_name = f"{father_profile.get('firstName', '')} {father_profile.get('lastName', '')}".strip()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        father_node = {
            'id': f"{timestamp}-{father_full_name.replace(' ', '')}",
            'name': father_full_name,
            'gender': 'male',
            'email': father_email,
            'phone': father_profile.get('phone', ''),
            'userProfileExists': True,
            'nodeType': 'father'
        }
        
        # Add father's profile image if available
        profile_image_id = father_profile.get('currentProfileImageId')
        if profile_image_id:
            try:
                profile_image_ref = user_profiles_ref.document(father_email).collection('profileImages').document(profile_image_id)
                profile_image_doc = profile_image_ref.get()
                if profile_image_doc.exists:
                    profile_image_data = profile_image_doc.to_dict()
                    image_data = profile_image_data.get('imageData', '')
                    # Add base64 prefix if not already present
                    if image_data and not image_data.startswith('data:'):
                        father_node['profileImage'] = 'data:image/jpeg;base64,' + image_data
                    else:
                        father_node['profileImage'] = image_data
                    logger.info("Successfully added father's profile image")
            except Exception as img_error:
                logger.warning(f"Could not fetch father's profile image: {img_error}")
        
        # SCENARIO 1: Neither has a tree
        if not child_tree_id and not father_tree_id:
            logger.warning("Neither child nor father has a family tree")
            return {
                "success": False,
                "message": "Unable to create family tree - neither child nor father has an existing tree"
            }
        
        # SCENARIO 2: Child has tree but father doesn't
        if child_tree_id and not father_tree_id:
            logger.warning("Child has tree but father doesn't")
            return {
                "success": False,
                "message": "Unable to create family tree - father has no family tree with spouse"
            }
        
        # SCENARIO 3: Child has no tree but father has tree
        if not child_tree_id and father_tree_id:
            logger.info("Scenario 3: Adding child to father's existing tree")
            # Get father's tree
            father_tree_doc = family_tree_ref.document(father_tree_id).get()
            if not father_tree_doc.exists:
                logger.error(f"Father's tree not found: {father_tree_id}")
                return {
                    "success": False,
                    "message": f"Father's family tree not found: {father_tree_id}"
                }
            
            father_tree = father_tree_doc.to_dict()
            family_members = father_tree.get('familyMembers', [])
            
            # Find father's node and generation
            father_node_id = None
            father_generation = None
            for member in family_members:
                if member.get('email') == father_email:
                    father_node_id = member.get('id')
                    father_generation = member.get('generation', 1)
                    break
                
            if not father_node_id:
                logger.error("Father not found in his own family tree")
                return {
                    "success": False,
                    "message": "Father not found in his own family tree"
                }
            
            logger.info(f"Found father node ID: {father_node_id} with generation: {father_generation}")
            
            # Create child node
            child_full_name = f"{child_profile.get('firstName', '')} {child_profile.get('lastName', '')}".strip()
            child_node_id = f"{timestamp}-{child_full_name.replace(' ', '')}"
            
            print(child_profile.get('GENDER', ''))
            
            child_node = {
                'id': child_node_id,
                'name': child_full_name,
                'gender': child_profile.get('GENDER', '').lower(),
                'email': child_email,
                'phone': child_profile.get('phone', ''),
                'userProfileExists': True,
                'generation': father_generation - 1,  # One generation below father
                'parentId': father_node_id
            }
            
            # Add profile image if available
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
                except Exception as img_error:
                    logger.warning(f"Could not fetch child's profile image: {img_error}")
            
            # Add child to family members
            family_members.append(child_node)
            logger.info(f"Added child node to family members. Total members: {len(family_members)}")
            
            # Update the tree
            family_tree_ref.document(father_tree_id).update({
                'familyMembers': family_members,
                'updatedAt': datetime.now().isoformat()
            })
            logger.info("Updated father's family tree with new child")
            
            # Update child's profile
            user_profiles_ref.document(child_email).update({
                'familyTreeId': father_tree_id,
                'updatedAt': datetime.now().isoformat()
            })
            logger.info("Updated child's profile with father's tree ID")
            
            return {
                "success": True,
                "message": "Child added to father's family tree successfully",
                "familyTreeId": father_tree_id,
                "childNodeId": child_node_id,
                "fatherNodeId": father_node_id,
                "childGeneration": father_generation - 1,
                "fatherGeneration": father_generation
            }
        
        # SCENARIO 4: Both have trees - Merge child's subtree into father's tree
        logger.info("Scenario 4: Merging child's subtree into father's tree")
        child_tree_doc = family_tree_ref.document(child_tree_id).get()
        father_tree_doc = family_tree_ref.document(father_tree_id).get()
        
        if not child_tree_doc.exists or not father_tree_doc.exists:
            logger.error("One or both family trees not found")
            return {
                "success": False,
                "message": "One or both family trees not found"
            }
        
        child_tree = child_tree_doc.to_dict()
        father_tree = father_tree_doc.to_dict()
        
        child_members = child_tree.get('familyMembers', [])
        father_members = father_tree.get('familyMembers', [])
        logger.info(f"Found {len(child_members)} members in child's tree and {len(father_members)} in father's tree")
        
        # Get relatives from both trees
        child_relatives = child_tree.get('relatives', {})
        father_relatives = father_tree.get('relatives', {})
        
        # Find child node in their tree
        child_node = None
        for member in child_members:
            if member.get('email') == child_email:
                child_node = member
                child_node_id = member.get('id')
                break
        
        if not child_node:
            logger.error("Child not found in their family tree")
            return {
                "success": False,
                "message": "Child not found in their family tree"
            }
        
        # Find father node in his tree
        father_node = None
        for member in father_members:
            if member.get('email') == father_email:
                father_node = member
                break
        
        if not father_node:
            logger.error("Father not found in his family tree")
            return {
                "success": False,
                "message": "Father not found in his family tree"
            }
        
        logger.info(f"Found child node ID: {child_node_id} and father node ID: {father_node.get('id')}")
        
        # Function to collect child's subtree members
        def collect_subtree_members(members, root_id, collected_members=None, processed_ids=None):
            if collected_members is None:
                collected_members = []
            if processed_ids is None:
                processed_ids = set()
            
            # Skip if we've already processed this node
            if root_id in processed_ids:
                return collected_members
            
            processed_ids.add(root_id)
            
            # Find the root member
            root_member = None
            for member in members:
                if member.get('id') == root_id:
                    root_member = member
                    break
            
            if not root_member:
                return collected_members
            
            # Add the root member
            collected_members.append(root_member)
            
            # Add spouse if exists
            spouse_id = root_member.get('spouse')
            if spouse_id:
                for member in members:
                    if member.get('id') == spouse_id and spouse_id not in processed_ids:
                        collected_members.append(member)
                        processed_ids.add(spouse_id)
            
            # Recursively add all children and their subtrees
            for member in members:
                if member.get('parentId') == root_id:
                    collect_subtree_members(members, member.get('id'), collected_members, processed_ids)
            
            return collected_members
        
        # Collect child's subtree (including spouse and all descendants)
        subtree_members = collect_subtree_members(child_members, child_node_id)
        logger.info(f"Collected {len(subtree_members)} members from child's subtree")
        
        # Calculate generation adjustment
        child_old_gen = child_node.get('generation', 0)
        child_new_gen = father_node.get('generation', 1) - 1
        gen_adjustment = child_new_gen - child_old_gen
        logger.info(f"Generation adjustment: {gen_adjustment} (old: {child_old_gen}, new: {child_new_gen})")
        
        # Create merged members list starting with father's tree
        merged_members = father_members.copy()
        
        # Update and add subtree members
        added_members = 0
        for member in subtree_members:
            # Skip if member already exists in father's tree
            if any(m.get('email') == member.get('email') for m in merged_members):
                continue
            
            # Adjust generation
            member['generation'] = member.get('generation', 0) + gen_adjustment
            
            # If this is the child node, update its parentId
            if member.get('id') == child_node_id:
                member['parentId'] = father_node.get('id')
            
            # Add base64 prefix to profile image if needed
            
            
            merged_members.append(member)
            added_members += 1
        
        logger.info(f"Added {added_members} new members to father's tree")
        
        # Merge relatives from child's subtree
        merged_relatives = father_relatives.copy()
        relatives_added = 0
        for member in subtree_members:
            member_email = member.get('email')
            if member_email and member_email in child_relatives:
                # If member already exists in father's relatives, merge their relatives
                if member_email in merged_relatives:
                    member_relatives = child_relatives[member_email]
                    existing_relatives = merged_relatives[member_email]
                    
                    # Merge each type of relative
                    for rel_type in ['children', 'parents', 'siblings', 'spouse']:
                        if rel_type in member_relatives:
                            if rel_type not in existing_relatives:
                                existing_relatives[rel_type] = []
                            # Add new relatives that don't already exist
                            existing_relatives[rel_type].extend([
                                rel for rel in member_relatives[rel_type]
                                if rel not in existing_relatives[rel_type]
                            ])
                else:
                    # If member doesn't exist in father's relatives, add all their relatives
                    merged_relatives[member_email] = child_relatives[member_email]
                    relatives_added += 1
        
        logger.info(f"Added {relatives_added} new relatives to father's tree")
        
        # Update the father's tree with merged members and relatives
        family_tree_ref.document(father_tree_id).update({
            'familyMembers': merged_members,
            'relatives': merged_relatives,
            'updatedAt': datetime.now().isoformat()
        })
        logger.info("Updated father's tree with merged members and relatives")
        
        # Update profiles for all subtree members to point to father's tree
        profiles_updated = 0
        for member in subtree_members:
            if member.get('userProfileExists') and member.get('email'):
                user_profiles_ref.document(member.get('email')).update({
                    'familyTreeId': father_tree_id,
                    'updatedAt': datetime.now().isoformat()
                })
                profiles_updated += 1
        
        logger.info(f"Updated {profiles_updated} user profiles with new tree ID")
        
        # Delete the child's tree as the subtree has been merged
        family_tree_ref.document(child_tree_id).delete()
        logger.info(f"Deleted child's tree: {child_tree_id}")
        
        logger.info("Successfully completed tree merge operation")
        return {
            "success": True,
            "message": "Child's subtree and relatives merged successfully into father's tree",
            "familyTreeId": father_tree_id,
            "childNodeId": child_node_id,
            "fatherNodeId": father_node.get('id'),
            "childGeneration": child_new_gen,
            "fatherGeneration": father_node.get('generation'),
            "mergedMembers": len(subtree_members),
            "mergedRelatives": len(merged_relatives) - len(father_relatives)
        }
    
    except Exception as e:
        logger.error(f"Error merging family trees: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        } 