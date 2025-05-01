from typing import List, Dict, Any

def determine_relationship(member: Dict[str, Any], target_node: Dict[str, Any], members_dict: Dict[str, Dict[str, Any]]) -> str:
    """
    Determine the relationship between a member and the target node.
    
    Args:
        member (Dict[str, Any]): The family member to determine relationship for
        target_node (Dict[str, Any]): The central node
        members_dict (Dict[str, Dict[str, Any]]): Dictionary of all family members
        
    Returns:
        str: The relationship label
    """
    # First check if member is the target node itself
    if member.get('id') == target_node.get('id'):
        return "Myself"
    
    # Check if member is target's parent
    parent_id = target_node.get('parentId')
    if parent_id and parent_id == member.get('id'):
        gender = member.get('gender', '').lower()
        if gender == 'male':
            return "Father"
        elif gender == 'female':
            return "Mother"
        else:
            return "Parent"
    
    # Check if member is the spouse of the parent (other parent)
    if parent_id and parent_id in members_dict:
        parent = members_dict[parent_id]
        if parent.get('spouse') == member.get('id'):
            gender = member.get('gender', '').lower()
            if gender == 'male':
                return "Father"
            elif gender == 'female':
                return "Mother"
            else:
                return "Parent"
    
    # Check if member is target's child
    if member.get('parentId') == target_node.get('id'):
        gender = member.get('gender', '').lower()
        return "Son" if gender == 'male' else "Daughter"
    
    # Check if member is target's spouse
    if target_node.get('spouse') == member.get('id') or member.get('spouse') == target_node.get('id'):
        gender = member.get('gender', '').lower()
        return "Husband" if gender == 'male' else "Wife"
    
    # Check if member is sibling (shares same parent)
    target_parent_id = target_node.get('parentId')
    print("target_parent_id",target_parent_id,"member_parent_id",member.get('parentId'))
    if target_parent_id and member.get('parentId') == target_parent_id and member.get('id') != target_node.get('id'):
        gender = member.get('gender', '').lower()
        return "Brother" if gender == 'male' else "Sister"
    
    # Check if member is sibling's spouse
    if target_parent_id:
        for potential_sibling_id, potential_sibling in members_dict.items():
            if (potential_sibling.get('parentId') == target_parent_id and 
                potential_sibling.get('id') != target_node.get('id') and 
                potential_sibling.get('spouse') == member.get('id')):
                gender = member.get('gender', '').lower()
                return "Brother-in-law" if gender == 'male' else "Sister-in-law"
    
    # Check if member is sibling's child (niece/nephew)
    if target_parent_id:
        for potential_sibling_id, potential_sibling in members_dict.items():
            if (potential_sibling.get('parentId') == target_parent_id and 
                potential_sibling.get('id') != target_node.get('id') and 
                member.get('parentId') == potential_sibling.get('id')):
                gender = member.get('gender', '').lower()
                return "Nephew" if gender == 'male' else "Niece"
    
    # Check if parent's sibling (aunt/uncle)
    if target_parent_id and target_parent_id in members_dict:
        parent = members_dict[target_parent_id]
        parent_parent_id = parent.get('parentId')
        if parent_parent_id and member.get('parentId') == parent_parent_id and member.get('id') != parent.get('id'):
            gender = member.get('gender', '').lower()
            return "Uncle" if gender == 'male' else "Aunt"
    
    # Parent's sibling's child (cousin)
    if target_parent_id and target_parent_id in members_dict:
        parent = members_dict[target_parent_id]
        parent_parent_id = parent.get('parentId')
        if parent_parent_id:
            for potential_uncle_id, potential_uncle in members_dict.items():
                if (potential_uncle.get('parentId') == parent_parent_id and 
                    potential_uncle.get('id') != parent.get('id') and 
                    member.get('parentId') == potential_uncle.get('id')):
                    return "Cousin"
    
    # Default
    return "Relative"

def get_related_nodes(family_members: List[Dict[str, Any]], node_id: str) -> List[Dict[str, Any]]:
    """
    Get related nodes for a specific node in a family tree.
    Returns a unified family tree structure containing parents, siblings, siblings' spouses and children,
    with relationship labels for each node.
    
    Args:
        family_members (List[Dict[str, Any]]): List of family tree members
        node_id (str): ID of the node to find related members for
        
    Returns:
        List[Dict[str, Any]]: List of related nodes in a unified family tree structure with relationship labels
    """
    # Create a dictionary for quick lookup
    members_dict = {member.get('id'): member for member in family_members}
    
    # Get the target node
    target_node = members_dict.get(node_id)
    if not target_node:
        return []  # Node not found
    
    # Create a set to track related node IDs
    related_node_ids = set()
    
    # Get parent ID
    parent_id = target_node.get('parentId')
    if parent_id and parent_id in members_dict:
        related_node_ids.add(parent_id)
        
        # Add parent's spouse
        parent = members_dict[parent_id]
        parent_spouse_id = parent.get('spouse')
        if parent_spouse_id and parent_spouse_id in members_dict:
            related_node_ids.add(parent_spouse_id)
    
    # Get siblings (nodes with same parent)
    if parent_id:
        for member_id, member in members_dict.items():
            # Skip self
            if member_id == node_id:
                continue
                
            # Check if this is a sibling (has same parent)
            if member.get('parentId') == parent_id:
                # Add sibling
                related_node_ids.add(member_id)
                
                # Add sibling's spouse
                sibling_spouse_id = member.get('spouse')
                if sibling_spouse_id and sibling_spouse_id in members_dict:
                    related_node_ids.add(sibling_spouse_id)
                
                # Add sibling's children (nieces/nephews)
                for potential_child_id, potential_child in members_dict.items():
                    if potential_child.get('parentId') == member_id:
                        related_node_ids.add(potential_child_id)
    
    # Add spouse
    spouse_id = target_node.get('spouse')
    if spouse_id and spouse_id in members_dict:
        related_node_ids.add(spouse_id)
        
        # Add spouse's parents
        spouse = members_dict[spouse_id]
        spouse_parent_id = spouse.get('parentId')
        if spouse_parent_id and spouse_parent_id in members_dict:
            related_node_ids.add(spouse_parent_id)
            
            # Add spouse's parent's spouse
            spouse_parent = members_dict[spouse_parent_id]
            spouse_parent_spouse_id = spouse_parent.get('spouse')
            if spouse_parent_spouse_id and spouse_parent_spouse_id in members_dict:
                related_node_ids.add(spouse_parent_spouse_id)
    
    # Add children
    for member_id, member in members_dict.items():
        if member.get('parentId') == node_id:
            related_node_ids.add(member_id)
            
            # Add children's spouses
            child_spouse_id = member.get('spouse')
            if child_spouse_id and child_spouse_id in members_dict:
                related_node_ids.add(child_spouse_id)
    
    # Convert set of IDs to list of nodes with relationship labels
    related_nodes = []
    for node_id_rel in related_node_ids:
        if node_id_rel in members_dict:
            # Create a copy of the member to avoid modifying the original
            member = members_dict[node_id_rel].copy()
            
            # Determine relationship to the target node
            relation = determine_relationship(member, target_node, members_dict)
            
            # Add relationship attributes
            member['relation'] = relation
            member['isSelf'] = False
            
            # Ensure spouse reference is preserved
            spouse_node_id = member.get('spouse')
            if spouse_node_id:
                member['spouse'] = spouse_node_id
                
                # If spouse exists in our data, add spouse's name for convenience
                if spouse_node_id in members_dict:
                    spouse_name = members_dict[spouse_node_id].get('name')
                    if spouse_name:
                        member['spouseName'] = spouse_name
            
            related_nodes.append(member)
    
    # Include the target node itself
    if node_id in members_dict:
        self_node = members_dict[node_id].copy()
        self_node['relation'] = "Myself"
        self_node['isSelf'] = True
        
        # Ensure spouse reference is preserved for self node too
        spouse_node_id = self_node.get('spouse')
        if spouse_node_id:
            if spouse_node_id in members_dict:
                spouse_name = members_dict[spouse_node_id].get('name')
                if spouse_name:
                    self_node['spouseName'] = spouse_name
        
        related_nodes.append(self_node)
    
    return related_nodes

def get_extended_family(family_tree_id: str, node_id: str, db=None) -> List[Dict[str, Any]]:
    """
    Get extended family for a specific node in a family tree from Firestore.
    Returns a unified family tree structure with relationship labels.
    
    Args:
        family_tree_id (str): ID of the family tree
        node_id (str): ID of the node to find related members for
        db: Firestore database client (optional)
        
    Returns:
        List[Dict[str, Any]]: List of related nodes in a unified family tree structure with relationship labels
    """
    if db is None:
        from firebase_admin import firestore
        db = firestore.client()
    
    try:
        # Get family tree document
        tree_doc = db.collection('family_tree').document(family_tree_id).get()
        
        if not tree_doc.exists:
            return []
        
        # Extract family members
        tree_data = tree_doc.to_dict()
        family_members = tree_data.get('familyMembers', [])
        
        # Create a dictionary for quick lookup
        members_dict = {member.get('id'): member for member in family_members}
        
        # Get the target node
        target_node = members_dict.get(node_id)
        if not target_node:
            return []
        
        # Create a set to track related node IDs
        related_node_ids = set()
        
        # Get parent ID
        parent_id = target_node.get('parentId')
        if parent_id and parent_id in members_dict:
            related_node_ids.add(parent_id)
            
            # Add parent's spouse
            parent = members_dict[parent_id]
            parent_spouse_id = parent.get('spouse')
            if parent_spouse_id and parent_spouse_id in members_dict:
                related_node_ids.add(parent_spouse_id)
        
        # Get siblings (nodes with same parent)
        if parent_id:
            for member_id, member in members_dict.items():
                # Skip self
                if member_id == node_id:
                    continue
                    
                # Check if this is a sibling (has same parent)
                if member.get('parentId') == parent_id:
                    # Add sibling
                    related_node_ids.add(member_id)
                    
                    # Add sibling's spouse
                    sibling_spouse_id = member.get('spouse')
                    if sibling_spouse_id and sibling_spouse_id in members_dict:
                        related_node_ids.add(sibling_spouse_id)
                    
                    # Add sibling's children (nieces/nephews)
                    for potential_child_id, potential_child in members_dict.items():
                        if potential_child.get('parentId') == member_id:
                            related_node_ids.add(potential_child_id)
        
        # Add spouse
        spouse_id = target_node.get('spouse')
        if spouse_id and spouse_id in members_dict:
            related_node_ids.add(spouse_id)
            
            # Add spouse's parents
            spouse = members_dict[spouse_id]
            spouse_parent_id = spouse.get('parentId')
            if spouse_parent_id and spouse_parent_id in members_dict:
                related_node_ids.add(spouse_parent_id)
                
                # Add spouse's parent's spouse
                spouse_parent = members_dict[spouse_parent_id]
                spouse_parent_spouse_id = spouse_parent.get('spouse')
                if spouse_parent_spouse_id and spouse_parent_spouse_id in members_dict:
                    related_node_ids.add(spouse_parent_spouse_id)
        
        # Add children
        for member_id, member in members_dict.items():
            if member.get('parentId') == node_id:
                related_node_ids.add(member_id)
                
                # Add children's spouses
                child_spouse_id = member.get('spouse')
                if child_spouse_id and child_spouse_id in members_dict:
                    related_node_ids.add(child_spouse_id)
        
        # Convert set of IDs to list of nodes with relationship labels
        related_nodes = []
        for node_id_rel in related_node_ids:
            if node_id_rel in members_dict:
                # Create a copy of the member to avoid modifying the original
                member = members_dict[node_id_rel].copy()
                
                # Determine relationship to the target node
                relation = determine_relationship(member, target_node, members_dict)
                
                # Add relationship attributes
                member['relation'] = relation
                member['isSelf'] = False
                
                # Ensure spouse reference is preserved
                spouse_node_id = member.get('spouse')
                if spouse_node_id:
                    member['spouse'] = spouse_node_id
                    
                    # If spouse exists in our data, add spouse's name for convenience
                    if spouse_node_id in members_dict:
                        spouse_name = members_dict[spouse_node_id].get('name')
                        if spouse_name:
                            member['spouseName'] = spouse_name
                
                related_nodes.append(member)
        
        # Include the target node itself
        if node_id in members_dict:
            self_node = members_dict[node_id].copy()
            self_node['relation'] = "Myself"
            self_node['isSelf'] = True
            
            # Ensure spouse reference is preserved for self node too
            spouse_node_id = self_node.get('spouse')
            if spouse_node_id:
                if spouse_node_id in members_dict:
                    spouse_name = members_dict[spouse_node_id].get('name')
                    if spouse_name:
                        self_node['spouseName'] = spouse_name
            
            related_nodes.append(self_node)
        
        return related_nodes
        
    except Exception as e:
        return [] 
