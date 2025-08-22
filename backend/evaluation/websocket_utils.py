from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_evaluation_progress_update(run_id, status=None, progress=None, message=None, **kwargs):
    """Send evaluation progress update to WebSocket clients"""
    channel_layer = get_channel_layer()
    group_name = f'evaluation_{run_id}'
    
    update_data = {
        'type': 'progress_update',
        'run_id': run_id,
    }
    
    if status is not None:
        update_data['status'] = status
    if progress is not None:
        update_data['progress'] = progress
    if message is not None:
        update_data['message'] = message
    
    update_data.update(kwargs)
    
    async_to_sync(channel_layer.group_send)(group_name, update_data)

def send_evaluation_metrics_update(run_id, metrics):
    """Send evaluation metrics update to WebSocket clients"""
    channel_layer = get_channel_layer()
    group_name = f'evaluation_{run_id}'
    
    update_data = {
        'type': 'metrics_update',
        'run_id': run_id,
        'metrics': metrics
    }
    
    async_to_sync(channel_layer.group_send)(group_name, update_data)

def send_evaluation_status_update(run_id, status, message=None):
    """Send evaluation status update to WebSocket clients"""
    channel_layer = get_channel_layer()
    group_name = f'evaluation_{run_id}'
    
    update_data = {
        'type': 'status_update',
        'run_id': run_id,
        'status': status,
    }
    
    if message:
        update_data['message'] = message
    
    async_to_sync(channel_layer.group_send)(group_name, update_data)