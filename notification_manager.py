from datetime import datetime
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

def get_user_notifications(
    user_email: str,
    db,
    filter_type: Optional[str] = None,
    is_read: Optional[bool] = None,
    is_archived: Optional[bool] = None,
    limit: int = 50,
    last_notification_id: Optional[str] = None
) -> Tuple[bool, Dict]:
    """
    Get notifications for a specific user with optional filtering and pagination.
    
    Args:
        user_email (str): Email of the user
        db: Firestore database instance
        filter_type (str, optional): Filter notifications by type (invitation, group_message, event, classified)
        is_read (bool, optional): Filter by read status
        is_archived (bool, optional): Filter by archive status
        limit (int): Maximum number of notifications to return (default: 50)
        last_notification_id (str, optional): Last notification ID for pagination
    
    Returns:
        Tuple[bool, Dict]: (success, result)
            - success (bool): Whether the operation was successful
            - result (Dict): Dictionary containing notifications or error message
    """
    try:
        # Get reference to user's notifications collection
        notifications_ref = db.collection('user_profiles').document(user_email).collection('notifications')
        
        # Start with base query ordered by creation time
        query = notifications_ref.order_by('createdAt', direction='DESCENDING')
        
        # Apply filters if provided
        if filter_type:
            query = query.where('type', '==', filter_type)
        
        if is_read is not None:
            query = query.where('isRead', '==', is_read)
            
        if is_archived is not None:
            query = query.where('isArchived', '==', is_archived)
        
        # Apply pagination if last_notification_id is provided
        if last_notification_id:
            last_doc = notifications_ref.document(last_notification_id).get()
            if last_doc.exists:
                query = query.start_after(last_doc)
        
        # Execute query with limit
        docs = query.limit(limit).stream()
        
        # Convert to list of notifications
        notifications = []
        for doc in docs:
            notification_data = doc.to_dict()
            notifications.append(notification_data)
        
        # Get unread count
        unread_count = len(list(notifications_ref.where('isRead', '==', False).get()))
        
        return True, {
            "notifications": notifications,
            "unread_count": unread_count,
            "has_more": len(notifications) == limit
        }
    
    except Exception as e:
        logger.error(f"Error getting notifications for user {user_email}: {str(e)}")
        return False, {"error": str(e)}

def mark_notifications_read(
    user_email: str,
    db,
    notification_ids: List[str]
) -> Tuple[bool, Dict]:
    """
    Mark specific notifications as read.
    
    Args:
        user_email (str): Email of the user
        db: Firestore database instance
        notification_ids (List[str]): List of notification IDs to mark as read
    
    Returns:
        Tuple[bool, Dict]: (success, result)
    """
    try:
        batch = db.batch()
        notifications_ref = db.collection('user_profiles').document(user_email).collection('notifications')
        
        for notification_id in notification_ids:
            doc_ref = notifications_ref.document(notification_id)
            batch.update(doc_ref, {
                'isRead': True,
                'updatedAt': datetime.now().isoformat()
            })
        
        batch.commit()
        return True, {"message": f"Successfully marked {len(notification_ids)} notifications as read"}
    
    except Exception as e:
        logger.error(f"Error marking notifications as read for user {user_email}: {str(e)}")
        return False, {"error": str(e)}

def archive_notifications(
    user_email: str,
    db,
    notification_ids: List[str]
) -> Tuple[bool, Dict]:
    """
    Archive specific notifications.
    
    Args:
        user_email (str): Email of the user
        db: Firestore database instance
        notification_ids (List[str]): List of notification IDs to archive
    
    Returns:
        Tuple[bool, Dict]: (success, result)
    """
    try:
        batch = db.batch()
        notifications_ref = db.collection('user_profiles').document(user_email).collection('notifications')
        
        for notification_id in notification_ids:
            doc_ref = notifications_ref.document(notification_id)
            batch.update(doc_ref, {
                'isArchived': True,
                'updatedAt': datetime.now().isoformat()
            })
        
        batch.commit()
        return True, {"message": f"Successfully archived {len(notification_ids)} notifications"}
    
    except Exception as e:
        logger.error(f"Error archiving notifications for user {user_email}: {str(e)}")
        return False, {"error": str(e)}

def mark_all_notifications_read(
    user_email: str,
    db
) -> Tuple[bool, Dict]:
    """
    Mark all notifications as read for a specific user.
    
    Args:
        user_email (str): Email of the user
        db: Firestore database instance
    
    Returns:
        Tuple[bool, Dict]: (success, result)
    """
    try:
        # Get reference to user's notifications collection
        notifications_ref = db.collection('user_profiles').document(user_email).collection('notifications')
        
        # Get all unread notifications
        unread_docs = notifications_ref.where('isRead', '==', False).stream()
        
        # Count documents before starting the update
        unread_ids = [doc.id for doc in unread_docs]
        count = len(unread_ids)
        
        if count == 0:
            return True, {"message": "No unread notifications found", "count": 0}
        
        # Update all unread notifications in a batch
        batch = db.batch()
        now = datetime.now().isoformat()
        
        for notification_id in unread_ids:
            doc_ref = notifications_ref.document(notification_id)
            batch.update(doc_ref, {
                'isRead': True,
                'updatedAt': now
            })
        
        # Commit the batch update
        batch.commit()
        
        # Now clean up old read notifications
        cleanup_read_notifications(user_email, db)
        
        return True, {"message": f"Successfully marked {count} notifications as read", "count": count}
    
    except Exception as e:
        logger.error(f"Error marking all notifications as read for user {user_email}: {str(e)}")
        return False, {"error": str(e)}

def cleanup_read_notifications(
    user_email: str,
    db,
    max_read_notifications: int = 20
) -> Tuple[bool, Dict]:
    """
    Clean up old read notifications, keeping only the most recent ones.
    
    Args:
        user_email (str): Email of the user
        db: Firestore database instance
        max_read_notifications (int): Maximum number of read notifications to keep
    
    Returns:
        Tuple[bool, Dict]: (success, result)
    """
    try:
        # Get reference to user's notifications collection
        notifications_ref = db.collection('user_profiles').document(user_email).collection('notifications')
        
        # Get all read notifications, ordered by timestamp (newest first)
        read_docs = notifications_ref.where('isRead', '==', True).order_by('createdAt', direction='DESCENDING').stream()
        
        # Convert to list to get the count
        read_docs_list = list(read_docs)
        total_read = len(read_docs_list)
        
        # If we have more than max_read_notifications, delete the oldest ones
        if total_read > max_read_notifications:
            # Get IDs to delete (all after max_read_notifications)
            to_delete = read_docs_list[max_read_notifications:]
            delete_count = len(to_delete)
            
            # Delete in batches (Firestore has a limit of 500 operations per batch)
            batch_size = 500
            for i in range(0, delete_count, batch_size):
                batch = db.batch()
                batch_to_delete = to_delete[i:i + batch_size]
                
                for doc in batch_to_delete:
                    doc_ref = notifications_ref.document(doc.id)
                    batch.delete(doc_ref)
                
                batch.commit()
                
            return True, {"message": f"Cleaned up {delete_count} old read notifications", "count": delete_count}
        else:
            return True, {"message": "No cleanup needed, read notifications within limit", "count": 0}
            
    except Exception as e:
        logger.error(f"Error cleaning up read notifications for user {user_email}: {str(e)}")
        return False, {"error": str(e)} 