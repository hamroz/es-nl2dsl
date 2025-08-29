#!/usr/bin/env python3
"""History management for multi-modal data adaptation"""
import json
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class AdaptationRecord:
    """Record of a data adaptation session"""
    id: str
    timestamp: float
    file_name: str
    file_format: str
    index_name: str
    status: str  # "analyzed", "ingested", "completed", "failed"
    schema: Dict[str, Any]
    ai_analysis: Dict[str, Any]
    elasticsearch_mapping: Dict[str, Any]
    document_count: int
    generated_queries: List[Dict[str, Any]]
    model_used: str
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AdaptationRecord':
        """Create from dictionary"""
        return cls(**data)
    
    def get_display_name(self) -> str:
        """Get a user-friendly display name"""
        return f"{self.file_name} → {self.index_name}"
    
    def get_status_emoji(self) -> str:
        """Get emoji for status"""
        status_emojis = {
            "analyzed": "🔍",
            "ingested": "📤", 
            "completed": "✅",
            "failed": "❌"
        }
        return status_emojis.get(self.status, "❓")
    
    def get_time_ago(self) -> str:
        """Get human-readable time since creation"""
        now = time.time()
        diff = now - self.timestamp
        
        if diff < 60:
            return "Just now"
        elif diff < 3600:
            minutes = int(diff / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif diff < 86400:
            hours = int(diff / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(diff / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"


class AdaptationHistory:
    """Manage history of data adaptation sessions"""
    
    def __init__(self, history_file: str = "artifacts/adaptation_history.json"):
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(exist_ok=True)
        self.records: Dict[str, AdaptationRecord] = {}
        self.load_history()
    
    def load_history(self) -> None:
        """Load history from file"""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    self.records = {
                        record_id: AdaptationRecord.from_dict(record_data)
                        for record_id, record_data in data.items()
                    }
                logger.info(f"Loaded {len(self.records)} adaptation records")
            else:
                self.records = {}
                logger.info("No existing history file found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading adaptation history: {e}")
            self.records = {}
    
    def save_history(self) -> bool:
        """Save history to file"""
        try:
            data = {
                record_id: record.to_dict()
                for record_id, record in self.records.items()
            }
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self.records)} adaptation records")
            return True
        except Exception as e:
            logger.error(f"Error saving adaptation history: {e}")
            return False
    
    def create_record(
        self,
        file_name: str,
        schema: Dict[str, Any],
        model_used: str = ""
    ) -> str:
        """Create a new adaptation record"""
        import uuid
        record_id = f"adapt_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        record = AdaptationRecord(
            id=record_id,
            timestamp=time.time(),
            file_name=file_name,
            file_format=schema.get('format', 'unknown'),
            index_name="",  # Will be set later
            status="analyzed",
            schema=schema,
            ai_analysis={},
            elasticsearch_mapping={},
            document_count=0,
            generated_queries=[],
            model_used=model_used
        )
        
        self.records[record_id] = record
        self.save_history()
        logger.info(f"Created adaptation record {record_id} for {file_name}")
        return record_id
    
    def update_record(
        self,
        record_id: str,
        **updates
    ) -> bool:
        """Update an existing record"""
        if record_id not in self.records:
            logger.error(f"Adaptation record {record_id} not found")
            return False
        
        record = self.records[record_id]
        for key, value in updates.items():
            if hasattr(record, key):
                setattr(record, key, value)
            else:
                logger.warning(f"Unknown field {key} in adaptation record update")
        
        self.save_history()
        logger.info(f"Updated adaptation record {record_id}")
        return True
    
    def get_record(self, record_id: str) -> Optional[AdaptationRecord]:
        """Get a specific record"""
        return self.records.get(record_id)
    
    def list_records(self, limit: int = None) -> List[AdaptationRecord]:
        """List all records, sorted by timestamp (newest first)"""
        records = sorted(
            self.records.values(),
            key=lambda r: r.timestamp,
            reverse=True
        )
        if limit:
            records = records[:limit]
        return records
    
    def delete_record(self, record_id: str) -> bool:
        """Delete a record"""
        if record_id in self.records:
            del self.records[record_id]
            self.save_history()
            logger.info(f"Deleted adaptation record {record_id}")
            return True
        return False
    
    def get_records_by_status(self, status: str) -> List[AdaptationRecord]:
        """Get records with specific status"""
        return [record for record in self.records.values() if record.status == status]
    
    def get_records_by_index(self, index_name: str) -> List[AdaptationRecord]:
        """Get records for a specific index"""
        return [record for record in self.records.values() if record.index_name == index_name]
    
    def search_records(self, query: str) -> List[AdaptationRecord]:
        """Search records by file name or index name"""
        query_lower = query.lower()
        matching_records = []
        
        for record in self.records.values():
            if (query_lower in record.file_name.lower() or 
                query_lower in record.index_name.lower()):
                matching_records.append(record)
        
        return sorted(matching_records, key=lambda r: r.timestamp, reverse=True)
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics"""
        total_records = len(self.records)
        status_counts = {}
        format_counts = {}
        
        for record in self.records.values():
            status_counts[record.status] = status_counts.get(record.status, 0) + 1
            format_counts[record.file_format] = format_counts.get(record.file_format, 0) + 1
        
        return {
            "total_records": total_records,
            "status_counts": status_counts,
            "format_counts": format_counts,
            "total_documents": sum(record.document_count for record in self.records.values())
        }


# Singleton instance
_history_instance = None

def get_adaptation_history() -> AdaptationHistory:
    """Get singleton instance of AdaptationHistory"""
    global _history_instance
    if _history_instance is None:
        _history_instance = AdaptationHistory()
    return _history_instance
