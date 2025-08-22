from django.db import models
from django.utils import timezone
import uuid

class DataIngestionTask(models.Model):
    """
    Represents a data ingestion task for processing datasets
    """
    task_id = models.CharField(max_length=50, unique=True, default=uuid.uuid4)
    task_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # File information
    source_file = models.CharField(max_length=500)
    file_size = models.BigIntegerField(null=True, blank=True)  # bytes
    dataset_type = models.CharField(max_length=50, choices=[
        ('cic_ids2017', 'CIC-IDS2017 Dataset'),
        ('general_csv', 'General CSV'),
        ('network_logs', 'Network Logs'),
        ('other', 'Other')
    ], default='general_csv')
    
    # Processing configuration
    target_index = models.CharField(max_length=100)
    chunk_size = models.IntegerField(default=5000)
    sample_size = models.IntegerField(null=True, blank=True)  # for limiting large files
    create_index = models.BooleanField(default=False)
    
    # Processing status
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], default='pending')
    
    # Progress tracking
    total_records = models.IntegerField(null=True, blank=True)
    processed_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    progress_percentage = models.FloatField(default=0.0)
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    processing_time_seconds = models.IntegerField(null=True, blank=True)
    
    # Results
    success_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    error_messages = models.JSONField(default=list)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Ingestion Task {self.task_id}: {self.task_name}"


class ElasticsearchIndex(models.Model):
    """
    Represents an Elasticsearch index for tracking and management
    """
    index_name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Index configuration
    mapping_file = models.CharField(max_length=500, blank=True)
    index_type = models.CharField(max_length=50, choices=[
        ('logs_net', 'Standard Network Logs'),
        ('logs_cic_ids2017', 'CIC-IDS2017 Logs'),
        ('logs_dp', 'Differential Privacy Logs'),
        ('custom', 'Custom Index')
    ], default='custom')
    
    # Index stats (updated periodically)
    document_count = models.BigIntegerField(default=0)
    index_size_bytes = models.BigIntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['index_name']
    
    def __str__(self):
        return f"Index: {self.index_name} ({self.display_name})"


class FileUpload(models.Model):
    """
    Represents an uploaded file for processing
    """
    upload_id = models.CharField(max_length=50, unique=True, default=uuid.uuid4)
    original_filename = models.CharField(max_length=500)
    file_path = models.CharField(max_length=1000)
    file_size = models.BigIntegerField()
    content_type = models.CharField(max_length=100)
    
    # File analysis
    file_type = models.CharField(max_length=50, choices=[
        ('csv', 'CSV File'),
        ('json', 'JSON File'),
        ('jsonl', 'JSONL File'),
        ('pcap', 'PCAP File'),
        ('other', 'Other')
    ], default='csv')
    
    # Preview data
    sample_data = models.JSONField(null=True, blank=True)
    column_names = models.JSONField(default=list)
    estimated_records = models.IntegerField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('uploaded', 'Uploaded'),
        ('analyzed', 'Analyzed'),
        ('processed', 'Processed'),
        ('failed', 'Failed')
    ], default='uploaded')
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"Upload {self.upload_id}: {self.original_filename}"


class CICDatasetFile(models.Model):
    """
    Represents a CIC-IDS2017 dataset file for tracking
    """
    file_id = models.CharField(max_length=50, unique=True)
    filename = models.CharField(max_length=200)
    file_path = models.CharField(max_length=1000)
    
    # CIC-specific metadata
    day_of_week = models.CharField(max_length=20, blank=True)
    time_period = models.CharField(max_length=50, blank=True)  # e.g., "WorkingHours", "AfterHours"
    attack_types = models.JSONField(default=list)  # list of attack types in this file
    
    # File stats
    original_size = models.BigIntegerField(null=True, blank=True)
    record_count = models.IntegerField(null=True, blank=True)
    processed_record_count = models.IntegerField(null=True, blank=True)
    
    # Processing status
    is_processed = models.BooleanField(default=False)
    is_ingested = models.BooleanField(default=False)
    processed_file_path = models.CharField(max_length=1000, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['filename']
    
    def __str__(self):
        return f"CIC File: {self.filename}"
