import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import DataIngestionTask

class DataIngestionProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.task_id = self.scope['url_route']['kwargs']['task_id']
        self.group_name = f'data_ingestion_{self.task_id}'
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send current status
        try:
            task = await self.get_ingestion_task(self.task_id)
            if task:
                await self.send(text_data=json.dumps({
                    'type': 'status_update',
                    'task_id': task.task_id,
                    'status': task.status,
                    'dataset_type': task.dataset_type,
                    'target_index': task.target_index,
                    'total_records': task.total_records,
                    'processed_records': task.processed_records,
                    'progress_percentage': task.progress_percentage,
                    'success_count': task.success_count,
                    'error_count': task.error_count,
                    'message': f'Data ingestion {task.status}'
                }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Failed to get ingestion status: {str(e)}'
            }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data.get('type') == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))

    # Group message handlers
    async def status_update(self, event):
        await self.send(text_data=json.dumps(event))
    
    async def progress_update(self, event):
        await self.send(text_data=json.dumps(event))
        
    async def records_processed(self, event):
        await self.send(text_data=json.dumps(event))
        
    async def chunk_completed(self, event):
        await self.send(text_data=json.dumps(event))
        
    async def error_update(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def get_ingestion_task(self, task_id):
        try:
            return DataIngestionTask.objects.get(task_id=task_id)
        except DataIngestionTask.DoesNotExist:
            return None