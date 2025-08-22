import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import SecurityTest, SecurityTestResult

class SecurityTestProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.test_id = self.scope['url_route']['kwargs']['test_id']
        self.group_name = f'security_{self.test_id}'
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send current status
        try:
            test = await self.get_security_test(self.test_id)
            if test:
                progress = await self.calculate_progress(test)
                await self.send(text_data=json.dumps({
                    'type': 'status_update',
                    'test_id': test.test_id,
                    'status': test.status,
                    'method': test.method,
                    'total_prompts': test.total_prompts,
                    'progress': progress,
                    'abstain_count': test.abstain_count,
                    'malicious_count': test.malicious_count,
                    'message': f'Security test {test.status}'
                }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Failed to get security test status: {str(e)}'
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
        
    async def prompt_tested(self, event):
        await self.send(text_data=json.dumps(event))
        
    async def security_metrics_update(self, event):
        await self.send(text_data=json.dumps(event))
        
    async def error_update(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def get_security_test(self, test_id):
        try:
            return SecurityTest.objects.get(test_id=test_id)
        except SecurityTest.DoesNotExist:
            return None
    
    @database_sync_to_async
    def calculate_progress(self, test):
        """Calculate progress based on completed test results"""
        if test.status == 'pending':
            return 0
        elif test.status == 'running':
            completed_results = SecurityTestResult.objects.filter(
                test=test, 
                status__in=['completed', 'failed']
            ).count()
            if test.total_prompts > 0:
                return int((completed_results / test.total_prompts) * 100)
            return 50
        elif test.status in ['completed', 'failed']:
            return 100
        return 0