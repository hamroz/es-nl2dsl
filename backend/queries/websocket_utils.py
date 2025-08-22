from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_query_progress_update(task_id, status=None, progress=None, message=None, **kwargs):
    """Send progress update to WebSocket clients"""
    channel_layer = get_channel_layer()
    group_name = f'query_{task_id}'
    
    update_data = {
        'type': 'progress_update',
        'task_id': task_id,
    }
    
    if status is not None:
        update_data['status'] = status
    if progress is not None:
        update_data['progress'] = progress
    if message is not None:
        update_data['message'] = message
    
    # Add any additional data
    update_data.update(kwargs)
    
    async_to_sync(channel_layer.group_send)(group_name, update_data)

def send_query_status_update(task_id, status, message=None):
    """Send status update to WebSocket clients"""
    channel_layer = get_channel_layer()
    group_name = f'query_{task_id}'
    
    update_data = {
        'type': 'status_update',
        'task_id': task_id,
        'status': status,
    }
    
    if message:
        update_data['message'] = message
    
    async_to_sync(channel_layer.group_send)(group_name, update_data)

def send_query_error(task_id, error_message):
    """Send error message to WebSocket clients"""
    channel_layer = get_channel_layer()
    group_name = f'query_{task_id}'
    
    update_data = {
        'type': 'error_update',
        'task_id': task_id,
        'error': error_message,
    }
    
    async_to_sync(channel_layer.group_send)(group_name, update_data)