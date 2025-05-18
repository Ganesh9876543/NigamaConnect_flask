from datetime import datetime
import uuid
import logging
import json
from firebase_admin import firestore
from socket_manager import notify_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Invitation status constants
STATUS_PENDING = 'pending'
STATUS_ACCEPTED = 'accepted'
STATUS_REJECTED = 'rejected'
STATUS_EXPIRED = 'expired'

# Invitation types
TYPE_FRIEND = 'friend'
TYPE_FAMILY = 'family'
TYPE_RELATIVE = 'relative'
TYPE_EVENT = 'event'
TYPE_OTHER = 'other'

def generate_invite_code():
    """Generate a unique invitation code"""
    print("[DEBUG] Generating unique invitation code")
    invite_code = str(uuid.uuid4())[:8].upper()
    print(f"[DEBUG] Generated invite code: {invite_code}")
    return invite_code

def create_invitation(sender_email, recipient_email, invitation_type, data=None):
    """
    Create a new invitation
    
    Args:
        sender_email (str): Email of the sender
        recipient_email (str): Email of the recipient
        invitation_type (str): Type of invitation (friend, family, etc.)
        data (dict): Additional data for the invitation
        
    Returns:
        dict: The created invitation object
    """
    print(f"\n[DEBUG] Creating invitation - Sender: {sender_email}, Recipient: {recipient_email}, Type: {invitation_type}")
    logger.info(f"Creating new {invitation_type} invitation from {sender_email} to {recipient_email}")
    
    current_time = datetime.now().isoformat()
    invite_code = generate_invite_code()
    
    # Base invitation object
    invitation = {
        'senderEmail': sender_email,
        'recipientEmail': recipient_email,
        'inviteCode': invite_code,
        'type': invitation_type,
        'status': STATUS_PENDING,
        'time': current_time,
        'valid': True,
        'createdAt': current_time,
        'updatedAt': current_time
    }
    
    # Add additional data if provided
    if data:
        print(f"[DEBUG] Adding additional data to invitation: {data}")
        invitation.update(data)
    
    print(f"[DEBUG] Created invitation object: {invitation}")
    return invitation

def save_invitation(invitation, db):
    """
    Save an invitation to the appropriate collections in Firestore
    
    Args:
        invitation (dict): The invitation to save
        db: Firestore database instance
        
    Returns:
        tuple: (success, error_message)
    """
    try:
        print("\n[DEBUG] Starting to save invitation")
        logger.info("Attempting to save invitation to Firestore")
        
        # Extract necessary data
        sender_email = invitation['senderEmail']
        recipient_email = invitation['recipientEmail']
        current_time = datetime.now()
        
        # Generate document ID (same for both sent and received records)
        timestamp = current_time.strftime('%Y%m%d%H%M%S%f')
        doc_id = f"{timestamp}_{invitation['inviteCode']}"
        print(f"[DEBUG] Generated document ID: {doc_id}")
        
        # Transaction to ensure both records are saved
        transaction = db.transaction()
        print("[DEBUG] Created database transaction")
        
        @firestore.transactional
        def save_invitation_transaction(transaction):
            print("[DEBUG] Starting transaction to save invitation")
            # Save to sender's sent_invitations collection
            sender_ref = db.collection('user_profiles').document(sender_email)
            sent_invitation_ref = sender_ref.collection('sent_invitations').document(doc_id)
            
            # Save to recipient's received_invitations collection
            recipient_ref = db.collection('user_profiles').document(recipient_email)
            received_invitation_ref = recipient_ref.collection('received_invitations').document(doc_id)
            
            # Create sent invitation record (include all original data)
            sent_data = invitation.copy()
            sent_data['documentId'] = doc_id
            sent_data['direction'] = 'sent'
            print(f"[DEBUG] Created sent invitation data with ID: {doc_id}")
            
            # Create received invitation record (include all original data)
            received_data = invitation.copy()
            received_data['documentId'] = doc_id
            received_data['direction'] = 'received'
            print(f"[DEBUG] Created received invitation data with ID: {doc_id}")
            
            # Save both records in the transaction
            print("[DEBUG] Saving both sent and received records in transaction")
            transaction.set(sent_invitation_ref, sent_data)
            transaction.set(received_invitation_ref, received_data)
            
            return doc_id
        
        # Execute the transaction
        invitation_id = save_invitation_transaction(transaction)
        print(f"[DEBUG] Successfully executed transaction. Invitation ID: {invitation_id}")
        
        logger.info(f"Invitation saved with ID: {invitation_id}")
        return True, invitation_id
    
    except Exception as e:
        print(f"[DEBUG] Error saving invitation: {str(e)}")
        logger.error(f"Error saving invitation: {str(e)}")
        return False, str(e)

def send_invitation(sender_email, recipient_email, invitation_type, data, db, user_profiles_ref):
    """
    Send an invitation from one user to another
    
    Args:
        sender_email (str): Email of the sender
        recipient_email (str): Email of the recipient
        invitation_type (str): Type of invitation
        data (dict): Additional data for the invitation
        db: Firestore database instance
        user_profiles_ref: Reference to user_profiles collection
        
    Returns:
        tuple: (success, result)
    """
    try:
        print(f"\n[DEBUG] Starting to send invitation from {sender_email} to {recipient_email}")
        logger.info(f"Attempting to send {invitation_type} invitation from {sender_email} to {recipient_email}")
        
        # Validate user existence
        sender_doc = user_profiles_ref.document(sender_email).get()
        if not sender_doc.exists:
            print(f"[DEBUG] Error: Sender profile not found - {sender_email}")
            return False, "Sender profile not found"
        
        # Check if recipient exists (we allow sending even if they don't, but flag it)
        recipient_doc = user_profiles_ref.document(recipient_email).get()
        recipient_exists = recipient_doc.exists
        print(f"[DEBUG] Recipient exists: {recipient_exists}")
        
        # Create the invitation
        print("[DEBUG] Creating invitation object")
        invitation = create_invitation(sender_email, recipient_email, invitation_type, data)
        
        # Add sender details
        sender_data = sender_doc.to_dict()
        sender_name = f"{sender_data.get('firstName', '')} {sender_data.get('lastName', '')}".strip()
        invitation['senderFullName'] = sender_name
        print(f"[DEBUG] Added sender full name: {sender_name}")
        
        # Save the invitation
        print("[DEBUG] Saving invitation")
        success, result = save_invitation(invitation, db)
        
        if success:
            print("[DEBUG] Invitation saved successfully")
            # Send real-time notification if recipient exists
            if recipient_exists:
                print("[DEBUG] Sending real-time notification to recipient")
                notification_data = {
                    'invitationId': result,
                    'senderEmail': sender_email,
                    'senderName': sender_name,
                    'type': invitation_type,
                    'message': f"You have received a new {invitation_type} invitation from {sender_name}"
                }
                notify_user(recipient_email, {
                    'type': 'new_invitation',
                    'data': notification_data
                })
            
            return True, {
                'invitationId': result,
                'recipientExists': recipient_exists,
                'invitation': invitation
            }
        else:
            print(f"[DEBUG] Failed to save invitation: {result}")
            return False, result
    
    except Exception as e:
        print(f"[DEBUG] Error sending invitation: {str(e)}")
        logger.error(f"Error sending invitation: {str(e)}")
        return False, str(e)

def get_invitations(email, status=None, direction=None, db=None):
    """
    Get invitations for a user
    
    Args:
        email (str): User's email
        status (str, optional): Filter by status (pending, accepted, etc.)
        direction (str, optional): Filter by direction (sent or received)
        db: Firestore database instance
        
    Returns:
        tuple: (success, result)
    """
    try:
        print(f"\n[DEBUG] Starting get_invitations for email: {email}")
        print(f"[DEBUG] Parameters - status: {status}, direction: {direction}")
        
        if not db:
            print("[DEBUG] Error: Database instance is required")
            return False, "Database instance is required"
        
        user_ref = db.collection('user_profiles').document(email)
        print(f"[DEBUG] Created user reference for: {email}")
        
        # Determine which collection to query
        if direction == 'sent':
            print("[DEBUG] Querying sent invitations")
            collection_ref = user_ref.collection('sent_invitations')
        elif direction == 'received':
            print("[DEBUG] Querying received invitations")
            collection_ref = user_ref.collection('received_invitations')
        else:
            print("[DEBUG] Querying both sent and received invitations")
            # If no direction specified, return both sent and received
            sent_ref = user_ref.collection('sent_invitations')
            received_ref = user_ref.collection('received_invitations')
            
            # Build query for sent invitations
            sent_query = sent_ref
            if status:
                print(f"[DEBUG] Filtering sent invitations by status: {status}")
                sent_query = sent_query.where('status', '==', status)
            sent_query = sent_query.order_by('createdAt', direction=firestore.Query.DESCENDING)
            
            # Build query for received invitations
            received_query = received_ref
            if status:
                print(f"[DEBUG] Filtering received invitations by status: {status}")
                received_query = received_query.where('status', '==', status)
            received_query = received_query.order_by('createdAt', direction=firestore.Query.DESCENDING)
            
            # Execute both queries
            print("[DEBUG] Executing queries for both sent and received invitations")
            sent_docs = sent_query.stream()
            received_docs = received_query.stream()
            
            # Convert to list of dicts
            sent_invitations = [doc.to_dict() for doc in sent_docs]
            received_invitations = [doc.to_dict() for doc in received_docs]
            
            print(f"[DEBUG] Found {len(sent_invitations)} sent invitations")
            print(f"[DEBUG] Found {len(received_invitations)} received invitations")
            
            return True, {
                'sent': sent_invitations,
                'received': received_invitations,
                'totalSent': len(sent_invitations),
                'totalReceived': len(received_invitations)
            }
        
        # Build query for single direction
        query = collection_ref
        if status:
            print(f"[DEBUG] Filtering {direction} invitations by status: {status}")
            query = query.where('status', '==', status)
        query = query.order_by('createdAt', direction=firestore.Query.DESCENDING)
        
        # Execute query
        print(f"[DEBUG] Executing query for {direction} invitations")
        docs = query.stream()
        invitations = [doc.to_dict() for doc in docs]
        print(f"[DEBUG] Found {len(invitations)} {direction} invitations")
        
        return True, invitations
    
    except Exception as e:
        print(f"[DEBUG] Error in get_invitations: {str(e)}")
        logger.error(f"Error getting invitations: {str(e)}")
        return False, str(e)

def update_invitation_status(invitation_id, recipient_email, status, db, custom_handler=None):
    """
    Update the status of an invitation
    
    Args:
        invitation_id (str): ID of the invitation
        recipient_email (str): Email of the recipient
        status (str): New status (accepted, rejected, etc.)
        db: Firestore database instance
        custom_handler (function, optional): Custom handler for accepted invitations
        
    Returns:
        tuple: (success, result)
    """
    try:
        print(f"\n[DEBUG] Starting to update invitation status - ID: {invitation_id}, Status: {status}")
        logger.info(f"Updating invitation status for ID: {invitation_id} to {status}")
        
        # Start a transaction to update both sent and received records
        transaction = db.transaction()
        current_time = datetime.now().isoformat()
        print("[DEBUG] Created database transaction")
        
        @firestore.transactional
        def update_status_transaction(transaction):
            print("[DEBUG] Starting status update transaction")
            # Get the invitation from recipient's received_invitations
            recipient_ref = db.collection('user_profiles').document(recipient_email)
            received_ref = recipient_ref.collection('received_invitations').document(invitation_id)
            received_doc = received_ref.get(transaction=transaction)
            
            if not received_doc.exists:
                print(f"[DEBUG] Error: Invitation not found - {invitation_id}")
                raise ValueError(f"Invitation not found: {invitation_id}")
            
            # Get invitation data
            invitation = received_doc.to_dict()
            sender_email = invitation.get('senderEmail')
            invitation_type = invitation.get('type')
            print(f"[DEBUG] Retrieved invitation data - Type: {invitation_type}, Sender: {sender_email}")
            
            # Check if invitation is still valid
            if not invitation.get('valid', True):
                print("[DEBUG] Error: Invitation is no longer valid")
                raise ValueError("This invitation is no longer valid")
            
            # Update received invitation
            print("[DEBUG] Updating received invitation status")
            transaction.update(received_ref, {
                'status': status,
                'updatedAt': current_time,
                'responseTime': current_time
            })
            
            # Update sent invitation in sender's collection
            print("[DEBUG] Updating sent invitation status")
            sender_ref = db.collection('user_profiles').document(sender_email)
            sent_ref = sender_ref.collection('sent_invitations').document(invitation_id)
            transaction.update(sent_ref, {
                'status': status,
                'updatedAt': current_time,
                'responseTime': current_time
            })
            
            return invitation
        
        # Execute the transaction
        invitation = update_status_transaction(transaction)
        print("[DEBUG] Successfully executed status update transaction")
        
        # If invitation was accepted and there's a custom handler, call it
        if status == STATUS_ACCEPTED and custom_handler:
            print("[DEBUG] Invitation accepted, executing custom handler")
            try:
                custom_result = custom_handler(invitation, db)
                print("[DEBUG] Custom handler executed successfully")
                logger.info(f"Custom handler executed for invitation {invitation_id}")
                return True, {
                    'updatedInvitation': invitation,
                    'status': status,
                    'customResult': custom_result
                }
            except Exception as handler_error:
                print(f"[DEBUG] Error in custom handler: {str(handler_error)}")
                logger.error(f"Error in custom handler: {str(handler_error)}")
                return True, {
                    'updatedInvitation': invitation,
                    'status': status,
                    'handlerError': str(handler_error)
                }
        
        print("[DEBUG] Status update completed successfully")
        return True, {
            'updatedInvitation': invitation,
            'status': status
        }
    
    except ValueError as ve:
        print(f"[DEBUG] Validation error: {str(ve)}")
        logger.error(f"Validation error: {str(ve)}")
        return False, str(ve)
    
    except Exception as e:
        print(f"[DEBUG] Error updating invitation status: {str(e)}")
        logger.error(f"Error updating invitation status: {str(e)}")
        return False, str(e)

def handle_friend_invitation_acceptance(invitation, db):
    """
    Handle additional actions when a friend invitation is accepted
    
    Args:
        invitation (dict): The accepted invitation
        db: Firestore database instance
        
    Returns:
        dict: Result of the handling
    """
    try:
        print("\n[DEBUG] Starting to handle friend invitation acceptance")
        sender_email = invitation.get('senderEmail')
        recipient_email = invitation.get('recipientEmail')
        print(f"[DEBUG] Processing friendship between {sender_email} and {recipient_email}")
        
        # Extract data from the invitation
        additional_data = invitation.get('additionalData', {})
        print(f"[DEBUG] Additional data from invitation: {additional_data}")
        
        # Get the category/relationship selected by the sender for the recipient
        sender_category = invitation.get('category', 'Friends')
        recipient_category = sender_category
        print(f"[DEBUG] Categories - Sender: {sender_category}, Recipient: {recipient_category}")
        
        # Use the new mutual friends function
        print("[DEBUG] Adding mutual friends relationship")
        from friend_manager import add_mutual_friends
        result = add_mutual_friends(
            db=db,
            user1_email=sender_email,
            user2_email=recipient_email,
            user1_category=sender_category,
            user2_category=recipient_category
        )
        
        print(f"[DEBUG] Mutual friends addition result: {result}")
        logger.info(f"Friendship established between {sender_email} and {recipient_email} with result: {result}")
        
        return result
    
    except Exception as e:
        print(f"[DEBUG] Error handling friend invitation: {str(e)}")
        logger.error(f"Error handling friend invitation: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise e

def handle_family_invitation_acceptance(invitation, db):
    """
    Handle additional actions when a family invitation is accepted
    
    Args:
        invitation (dict): The accepted invitation
        db: Firestore database instance
        
    Returns:
        dict: Result of the handling
    """
    try:
        logger.info("Starting to handle family invitation acceptance")
        logger.info(f"Invitation data: {invitation}")
        
        # Extract relationship type and other relevant data
        relationship_type = invitation.get('relationship')
        sender_email = invitation.get('senderEmail')
        recipient_email = invitation.get('recipientEmail')
        is_tree_found = invitation.get('isTreeFound', False)
        member_type = invitation.get('memberType')
        
        # Extract selected member data
        selected_member = invitation.get('selectedMember', {})
        selected_match_profile = invitation.get('selectedMatchProfile', {})
        
        logger.info(f"Processing {relationship_type} relationship between {sender_email} and {recipient_email}")
        logger.info(f"Member type: {member_type}, Tree found: {is_tree_found}")
        logger.info(f"Selected member: {selected_member}")
        logger.info(f"Selected match profile: {selected_match_profile}")
        
        # Handle 'spouse' relationship type
        if relationship_type == 'spouse':
            logger.info("Processing spouse relationship")
            # Get references to required collections
            family_tree_ref = db.collection('family_tree')
            user_profiles_ref = db.collection('user_profiles')
            
            # Handle spouse relationship based on tree existence and who is being added
            if is_tree_found:
                logger.info("Adding to existing family tree")
                if selected_member.get('gender') == 'male':
                    logger.info("Adding wife to husband's tree")
                    print("husband_family_tree_id",invitation.get('husbandFamilyTreeId'))
                    print("husband_node_id",selected_member.get('id'))
                    print("husband_email",sender_email)
                    print("wife_email",recipient_email)
                    from family_spouse_manager import adding_wife_to_family_tree
                    
                    result = adding_wife_to_family_tree(
                        family_tree_ref=family_tree_ref,
                        user_profiles_ref=user_profiles_ref,
                        husband_family_tree_id=invitation.get('husbandFamilyTreeId'),
                        husband_node_id=selected_member.get('id'),
                        husband_email=selected_member.get('email'),
                        wife_email=recipient_email
                    )
                    
                    logger.info(f"Added wife to husband's family tree: {result}")
                    
                    return {
                        'success': result.get('success', False),
                        'message': result.get('message', 'Failed to add wife to family tree'),
                        'husbandFamilyTreeId': result.get('husbandFamilyTreeId'),
                        'wifeNodeId': result.get('wifeNodeId')
                    }
                    
                elif selected_member.get('gender') == 'female':
                    logger.info("Adding husband to wife's tree")
                    print("wife_family_tree_id",invitation.get('wifeFamilyTreeId'))
                    print("wife_node_id",selected_member.get('id'))
                    print("wife_email",sender_email)
                    print("husband_email",recipient_email)
                    from family_spouse_manager import adding_husband_to_family_tree
                    
                    result = adding_husband_to_family_tree(
                        family_tree_ref=family_tree_ref,
                        user_profiles_ref=user_profiles_ref,
                        wife_family_tree_id=invitation.get('wifeFamilyTreeId'),
                        wife_node_id=selected_member.get('id'),
                        wife_email=selected_member.get('email'),
                        husband_email=recipient_email
                    )
                    
                    logger.info(f"Added husband to wife's family tree: {result}")
                    
                    return {
                        'success': result.get('success', False),
                        'message': result.get('message', 'Failed to add husband to family tree'),
                        'wifeFamilyTreeId': result.get('wifeFamilyTreeId'),
                        'husbandNodeId': result.get('husbandNodeId')
                    }
                    
                else:
                    error_msg = f"Invalid gender value: {selected_member.get('gender')}. Must be 'male' or 'female'."
                    logger.error(error_msg)
                    return {
                        'success': False,
                        'message': error_msg
                    }
                    
            else:
                logger.info("Creating new family tree")
                if selected_member.get('gender') == 'male':
                    logger.info("Creating new family tree with husband email")
                    from family_spouse_manager import create_family_tree_with_husband_email
                    
                    result = create_family_tree_with_husband_email(
                        family_tree_ref=family_tree_ref,
                        user_profiles_ref=user_profiles_ref,
                        husband_email=sender_email,
                        wife_email=recipient_email
                    )
                    
                    logger.info(f"Created family tree with husband email: {result}")
                    
                    return {
                        'success': result.get('success', False),
                        'message': result.get('message', 'Failed to create family tree with husband'),
                        'familyTreeId': result.get('familyTreeId')
                    }
                    
                elif selected_member.get('gender') == 'female':
                    logger.info("Creating new family tree with wife email")
                    from family_spouse_manager import create_family_tree_with_wife_email
                    
                    result = create_family_tree_with_wife_email(
                        family_tree_ref=family_tree_ref,
                        user_profiles_ref=user_profiles_ref,
                        wife_email=sender_email,
                        husband_email=recipient_email
                    )
                    
                    logger.info(f"Created family tree with wife email: {result}")
                    
                    return {
                        'success': result.get('success', False),
                        'message': result.get('message', 'Failed to create family tree with wife'),
                        'familyTreeId': result.get('familyTreeId')
                    }
                    
                else:
                    error_msg = f"Invalid gender value: {selected_member.get('gender')}. Must be 'male' or 'female'."
                    logger.error(error_msg)
                    return {
                        'success': False,
                        'message': error_msg
                    }
        
        # Extract family tree data for other relationship types
        logger.info("Processing other relationship types")
        child_email = recipient_email
        parent_email = sender_email
        parent_type = member_type
        child_birth_order = invitation.get('birthOrder', 1)
        family_tree_id = invitation.get('fatherFamilyTreeId')
        child_node_id = selected_match_profile.get('id')
        
        logger.info(f"Family tree data - Tree ID: {family_tree_id}, Child Node ID: {child_node_id}")
        logger.info(f"Parent type: {parent_type}, Parent email: {parent_email}")
        
        # Different handling based on relationship type
        if relationship_type == 'parent':
            logger.info("Processing parent relationship")
            
            # Check if parent has a family tree
            parent_profile = db.collection('user_profiles').document(parent_email).get()
            parent_has_tree = False
            if parent_profile.exists:
                parent_data = parent_profile.to_dict()
                parent_has_tree = bool(parent_data.get('familyTreeId'))
                logger.info(f"Parent {parent_email} has family tree: {parent_has_tree}")
            
            # Check if child has a family tree
            child_profile = db.collection('user_profiles').document(child_email).get()
            child_has_tree = False
            if child_profile.exists:
                child_data = child_profile.to_dict()
                child_has_tree = bool(child_data.get('familyTreeId'))
                logger.info(f"Child {child_email} has family tree: {child_has_tree}")
            
            # Handle different scenarios based on family tree existence
            if not parent_has_tree and not child_has_tree:
                logger.error("Neither parent nor child has a family tree")
                return {
                    'success': False,
                    'message': 'Cannot establish family relationship: neither parent nor child has a family tree'
                }
            
            # If either has a tree, proceed with merge
            try:
                # Get references to required collections
                family_tree_ref = db.collection('family_tree')
                user_profiles_ref = db.collection('user_profiles')
                
                # Import the function here to avoid circular imports
                from family_parent_manager import merge_family_trees
                
                # Call the function to merge family trees
                result = merge_family_trees(
                    family_tree_ref,
                    user_profiles_ref,
                   
                    parent_email,
                    child_email,
                    family_tree_id,
                    child_node_id
                )
                
                logger.info(f"Created new parent relationship: {result}")
                
                if result.get('success'):
                    return {
                        'success': True,
                        'message': 'Family relationship established as parent',
                        'familyTreeId': result.get('familyTreeId'),
                        'childNodeId': result.get('childNodeId'),
                        'mergeResult': result
                    }
                else:
                    error_msg = result.get('message') or result.get('error')
                    logger.error(f"Failed to create parent relationship: {error_msg}")
                    return {
                        'success': True,
                        'message': 'Family relationship established but failed to create parent relationship',
                        'mergeError': error_msg
                    }
            except Exception as e:
                logger.error(f"Error creating parent relationship: {str(e)}", exc_info=True)
                return {
                    'success': True,
                    'message': 'Family relationship established but error occurred creating parent relationship',
                    'error': str(e)
                }
        elif relationship_type == 'child':
            logger.info("Processing child relationship")
            if not is_tree_found:
                logger.info("Processing new child connection")
                try:
                    
                    logger.info(f"Created new child relationship: {result}")
                    
                    return {
                        'success': result.get('success', False),
                        'message': result.get('message', 'Failed to create child relationship'),
                        'familyTreeId': result.get('familyTreeId'),
                        'childNodeId': result.get('childNodeId')
                    }
                except Exception as e:
                    logger.error(f"Error creating child relationship: {str(e)}", exc_info=True)
                    return {
                        'success': False,
                        'message': f'Failed to create child relationship: {str(e)}'
                    }
            else:
                # If relationship is 'child' with existing tree, use add_child_with_subtree
                logger.info("Adding child to existing tree")
                family_tree_ref = db.collection('family_tree')
                user_profiles_ref = db.collection('user_profiles')
                father_node_id=invitation.get('fatherNodeId')
                father_family_tree_id=invitation.get('fatherFamilyTreeId')
                
                if all([father_family_tree_id, father_node_id, child_email]):
                    try:
                        
                        
                        print("father_node_id",father_node_id)
                        print("father_family_tree_id",father_family_tree_id)    
                        print("family_tree_id",family_tree_id)
                        print("child_node_id",child_node_id)
                        print("child_email",child_email)
                        print("child_birth_order",child_birth_order)
                        
                        
                        
                        from family_child_manager import add_child_with_subtree
                        
                        result = add_child_with_subtree(
                            family_tree_ref,
                            user_profiles_ref,
                            family_tree_id,
                            father_node_id,
                            child_email,
                            child_birth_order
                        )
                        
                        logger.info(f"Added child to existing tree: {result}")
                        
                        if result.get('success'):
                            return {
                                'success': True,
                                'message': 'Family relationship established and child added to family tree',
                                'familyTreeId': family_tree_id,
                                'childNodeId': result.get('childNodeId'),
                                'addChildResult': result
                            }
                        else:
                            error_msg = result.get('message') or result.get('error')
                            logger.error(f"Failed to add child to family tree: {error_msg}")
                            return {
                                'success': True,
                                'message': 'Family relationship established but failed to add child to family tree',
                                'familyTreeId': family_tree_id,
                                'addChildError': error_msg
                            }
                    except Exception as e:
                        logger.error(f"Error adding child to family tree: {str(e)}", exc_info=True)
                        return {
                            'success': True,
                            'message': 'Family relationship established but error occurred adding child to family tree',
                            'error': str(e)
                        }
        else:
            # Generic family relationship without specific tree operations
            logger.info(f"Generic family relationship established: {relationship_type}")
        
        # Default return for when we don't have family tree data or relationship type
        return {
            'success': True,
            'message': f'Family relationship established: {relationship_type}'
        }
    
    except Exception as e:
        logger.error(f"Error handling family invitation: {str(e)}", exc_info=True)
        raise e

# Map of invitation types to their acceptance handlers
invitation_acceptance_handlers = {
    TYPE_FRIEND: handle_friend_invitation_acceptance,
    TYPE_FAMILY: handle_family_invitation_acceptance,
    # Add other handlers as needed
}

def send_family_invitation(
    sender_email,
    recipient_email,
    relationship_type,
    db,
    father_family_tree_id=None,
    father_node_id=None,
    child_email=None,
    child_birth_order=None,
    family_tree_id=None,
    child_node_id=None,
    father_node=None,
    mother_node=None,
    # Spouse relationship parameters
    is_tree_found=None,
    is_adding=None,
    husband_family_tree_id=None,
    husband_node_id=None,
    husband_email=None,
    wife_family_tree_id=None,
    wife_node_id=None,
    wife_email=None
):
    """
    Send a family relationship invitation
    
    Args:
        sender_email: Email of the sender
        recipient_email: Email of the recipient
        relationship_type: Type of relationship (e.g., 'parent', 'child', 'sibling', 'spouse')
        db: Firestore database instance
        father_family_tree_id: ID of father's family tree (for 'child' relationship)
        father_node_id: ID of father's node in the tree (for 'child' relationship)
        child_email: Email of the child (for 'child' or 'parent' relationship)
        child_birth_order: Birth order of the child (for 'child' relationship)
        family_tree_id: ID of the existing family tree (for 'parent' relationship)
        child_node_id: ID of child's node (for 'parent' relationship)
        father_node: Father's node data (for 'parent' relationship)
        mother_node: Mother's node data (for 'parent' relationship)
        is_tree_found: Whether a family tree exists (for 'spouse' relationship)
        is_adding: Which spouse is being added ('husband' or 'wife') (for 'spouse' relationship)
        husband_family_tree_id: ID of husband's family tree (for 'spouse' relationship when adding wife)
        husband_node_id: ID of husband's node (for 'spouse' relationship when adding wife)
        husband_email: Email of the husband (for 'spouse' relationship)
        wife_family_tree_id: ID of wife's family tree (for 'spouse' relationship when adding husband)
        wife_node_id: ID of wife's node (for 'spouse' relationship when adding husband)
        wife_email: Email of the wife (for 'spouse' relationship)
        
    Returns:
        dict: Result of the invitation sending
    """
    try:
        print(f"\n[DEBUG] Starting to send family invitation - Type: {relationship_type}")
        logger.info(f"Sending family invitation from {sender_email} to {recipient_email} - Type: {relationship_type}")
        
        # Validate sender and recipient emails
        if not sender_email or not recipient_email:
            print("[DEBUG] Error: Missing sender or recipient email")
            return {
                "success": False,
                "message": "Sender and recipient emails are required"
            }
        
        # Validate relationship type
        if not relationship_type:
            print("[DEBUG] Error: Missing relationship type")
            return {
                "success": False,
                "message": "Relationship type is required"
            }
        
        # Get sender's profile
        print(f"[DEBUG] Getting sender's profile: {sender_email}")
        sender_doc = db.collection('user_profiles').document(sender_email).get()
        if not sender_doc.exists:
            print(f"[DEBUG] Error: Sender profile not found - {sender_email}")
            return {
                "success": False,
                "message": f"Sender profile not found: {sender_email}"
            }
        
        # Get sender's profile data
        sender_profile = sender_doc.to_dict()
        sender_name = f"{sender_profile.get('firstName', '')} {sender_profile.get('lastName', '')}".strip()
        print(f"[DEBUG] Sender name: {sender_name}")
        
        # Validate recipient's profile
        print(f"[DEBUG] Getting recipient's profile: {recipient_email}")
        recipient_doc = db.collection('user_profiles').document(recipient_email).get()
        if not recipient_doc.exists:
            print(f"[DEBUG] Error: Recipient profile not found - {recipient_email}")
            return {
                "success": False,
                "message": f"Recipient profile not found: {recipient_email}"
            }
        
        # Get recipient's profile data
        recipient_profile = recipient_doc.to_dict()
        recipient_name = f"{recipient_profile.get('firstName', '')} {recipient_profile.get('lastName', '')}".strip()
        print(f"[DEBUG] Recipient name: {recipient_name}")
        
        # Check for existing invitations between sender and recipient
        print("[DEBUG] Checking for existing invitations")
        invitations_query = db.collection('invitations').where(
            'senderEmail', '==', sender_email
        ).where(
            'recipientEmail', '==', recipient_email
        ).where(
            'status', '==', 'pending'
        ).where(
            'invitationType', '==', 'family'
        )
        
        # Check if an invitation already exists
        existing_invitations = list(invitations_query.stream())
        if existing_invitations:
            print("[DEBUG] Error: Found existing pending invitation")
            return {
                "success": False,
                "message": "An invitation already exists between sender and recipient"
            }
        
        # Create invitation data
        print("[DEBUG] Creating invitation data")
        timestamp = datetime.now().isoformat()
        invite_token = str(uuid.uuid4())
        
        invitation_data = {
            'invitationType': 'family',
            'relationshipType': relationship_type,
            'senderEmail': sender_email,
            'senderName': sender_name,
            'recipientEmail': recipient_email,
            'recipientName': recipient_name,
            'status': 'pending',
            'token': invite_token,
            'createdAt': timestamp,
            'updatedAt': timestamp
        }
        
        # Add family tree data for 'child' relationship type
        if relationship_type == 'child' and all([father_family_tree_id, father_node_id, child_email]):
            print("[DEBUG] Adding child relationship data")
            invitation_data.update({
                'fatherFamilyTreeId': father_family_tree_id,
                'fatherNodeId': father_node_id,
                'childEmail': child_email,
                'childBirthOrder': child_birth_order or 1
            })
        
        # Add family tree data for 'parent' relationship type
        if relationship_type == 'parent' and child_email:
            print("[DEBUG] Adding parent relationship data")
            invitation_data.update({
                'childEmail': child_email,
                'familyTreeId': family_tree_id,
                'childNodeId': child_node_id
            })
            
            # Add parent nodes if provided
            if father_node:
                print("[DEBUG] Adding father node data")
                invitation_data['fatherNode'] = father_node
            if mother_node:
                print("[DEBUG] Adding mother node data")
                invitation_data['motherNode'] = mother_node
        
        # Add data for 'spouse' relationship type
        if relationship_type == 'spouse':
            print("[DEBUG] Adding spouse relationship data")
            # Add isTreeFound and isAdding flags
            if is_tree_found is not None:
                invitation_data['isTreeFound'] = is_tree_found
            if is_adding:
                invitation_data['isAdding'] = is_adding
                
            # Add appropriate data based on which spouse is being added
            if is_adding == 'wife' and husband_email:
                print("[DEBUG] Adding wife to husband data")
                invitation_data['husbandEmail'] = husband_email
                invitation_data['wifeEmail'] = wife_email or recipient_email
                
                # Add tree data if it exists
                if is_tree_found and husband_family_tree_id and husband_node_id:
                    print("[DEBUG] Adding existing husband's tree data")
                    invitation_data['husbandFamilyTreeId'] = husband_family_tree_id
                    invitation_data['husbandNodeId'] = husband_node_id
                    
            elif is_adding == 'husband' and wife_email:
                print("[DEBUG] Adding husband to wife data")
                invitation_data['wifeEmail'] = wife_email
                invitation_data['husbandEmail'] = husband_email or recipient_email
                
                # Add tree data if it exists
                if is_tree_found and wife_family_tree_id and wife_node_id:
                    print("[DEBUG] Adding existing wife's tree data")
                    invitation_data['wifeFamilyTreeId'] = wife_family_tree_id
                    invitation_data['wifeNodeId'] = wife_node_id
        
        # Save invitation to database
        print(f"[DEBUG] Saving invitation to database with token: {invite_token}")
        db.collection('invitations').document(invite_token).set(invitation_data)
        
        print("[DEBUG] Family invitation sent successfully")
        return {
            "success": True,
            "message": "Family invitation sent successfully",
            "token": invite_token
        }
    
    except Exception as e:
        print(f"[DEBUG] Error sending family invitation: {str(e)}")
        logger.error(f"Error sending family invitation: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        } 
