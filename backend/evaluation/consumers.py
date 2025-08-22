import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import EvaluationRun, EvaluationBatch

class EvaluationProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.run_id = self.scope['url_route']['kwargs']['run_id']
        self.group_name = f'evaluation_{self.run_id}'
        
        # Join group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send current status
        try:
            run = await self.get_evaluation_run(self.run_id)
            if run:
                await self.send(text_data=json.dumps({
                    'type': 'status_update',
                    'run_id': run.run_id,
                    'status': run.status,
                    'scenario_id': run.scenario.scenario_id,
                    'method': run.method,
                    'progress': self.calculate_progress(run),
                    'message': f'Evaluation {run.status}'
                }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Failed to get evaluation status: {str(e)}'
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
        
    async def metrics_update(self, event):
        await self.send(text_data=json.dumps(event))
        
    async def error_update(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def get_evaluation_run(self, run_id):
        try:
            return EvaluationRun.objects.select_related('scenario').get(run_id=run_id)
        except EvaluationRun.DoesNotExist:
            return None
    
    def calculate_progress(self, run):
        """Calculate progress based on evaluation status"""
        if run.status == 'pending':
            return 0
        elif run.status == 'running':
            return 50  # Mid-progress
        elif run.status in ['completed', 'failed']:
            return 100
        return 0