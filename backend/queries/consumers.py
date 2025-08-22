import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import QueryTask

class QueryProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.task_id = self.scope['url_route']['kwargs']['task_id']
        self.group_name = f'query_{self.task_id}'
        
        # Join group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send current status immediately
        try:
            task = await self.get_query_task(self.task_id)
            if task:
                await self.send(text_data=json.dumps({
                    'type': 'status_update',
                    'task_id': task.task_id,
                    'status': task.status,
                    'progress': 0,  # Will be enhanced with actual progress tracking
                    'message': f'Query task {task.status}'
                }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Failed to get task status: {str(e)}'
            }))

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            # Handle any client messages if needed
            if data.get('type') == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong'
                }))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))

    # Receive message from group
    async def status_update(self, event):
        await self.send(text_data=json.dumps(event))
    
    async def progress_update(self, event):
        await self.send(text_data=json.dumps(event))
        
    async def error_update(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def get_query_task(self, task_id):
        try:
            return QueryTask.objects.get(task_id=task_id)
        except QueryTask.DoesNotExist:
            return None