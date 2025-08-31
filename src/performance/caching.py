#!/usr/bin/env python3
"""Intelligent caching system for query generation optimization"""
import time
import json
import hashlib
import base64
import threading
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import sqlite3
from enum import Enum

# Configure logging for cache operations
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class CacheLevel(Enum):
    """Cache levels with different TTL and policies"""
    MEMORY = "memory"         # Fast, temporary
    DISK = "disk"            # Persistent, slower
    DISTRIBUTED = "distributed"  # Shared across instances

@dataclass
class CacheEntry:
    """Cached query generation result"""
    key: str
    value: Dict[str, Any]
    created_at: float
    last_accessed: float
    access_count: int
    size_bytes: int
    ttl_seconds: int
    cache_level: CacheLevel
    metadata: Dict[str, Any]
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        return time.time() - self.created_at > self.ttl_seconds
    
    @property
    def age_seconds(self) -> int:
        """Get age of cache entry in seconds"""
        return int(time.time() - self.created_at)
    
    def update_access(self):
        """Update access statistics"""
        self.last_accessed = time.time()
        self.access_count += 1

class CacheStats:
    """Cache performance statistics"""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.size_bytes = 0
        self.entry_count = 0
        self.start_time = time.time()
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        return (self.hits / total) * 100 if total > 0 else 0
    
    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate"""
        return 100 - self.hit_rate
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "miss_rate": self.miss_rate,
            "evictions": self.evictions,
            "size_bytes": self.size_bytes,
            "entry_count": self.entry_count,
            "uptime_seconds": int(time.time() - self.start_time)
        }

class MemoryCache:
    """High-performance in-memory cache with LRU eviction"""
    
    def __init__(self, max_size_mb: int = 100, default_ttl: int = 3600):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: List[str] = []  # LRU tracking
        self.lock = threading.RLock()
        self.stats = CacheStats()
        
        logger.info(f"Initialized memory cache: {max_size_mb}MB max, {default_ttl}s TTL")
    
    def _generate_key(self, prompt: str, model: str, method: str, **kwargs) -> str:
        """Generate cache key from parameters"""
        key_data = {
            "prompt": prompt,
            "model": model,
            "method": method,
            **kwargs
        }
        
        # Create deterministic hash
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]
    
    def get(self, prompt: str, model: str, method: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Get cached result"""
        key = self._generate_key(prompt, model, method, **kwargs)
        
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                
                # Check if expired
                if entry.is_expired:
                    self._remove_entry(key)
                    self.stats.misses += 1
                    return None
                
                # Update access statistics
                entry.update_access()
                
                # Move to end of LRU list
                if key in self.access_order:
                    self.access_order.remove(key)
                self.access_order.append(key)
                
                self.stats.hits += 1
                return entry.value
            
            self.stats.misses += 1
            return None
    
    def put(self, prompt: str, model: str, method: str, value: Dict[str, Any], 
            ttl: Optional[int] = None, **kwargs) -> bool:
        """Cache a result"""
        key = self._generate_key(prompt, model, method, **kwargs)
        ttl = ttl or self.default_ttl
        
        # Calculate size and validate JSON serialization
        try:
            value_bytes = len(json.dumps(value).encode())
        except (TypeError, ValueError) as e:
            logger.error(f"Memory cache serialization error: {e}")
            return False
        
        with self.lock:
            # Check if we need to evict entries
            while (self.stats.size_bytes + value_bytes > self.max_size_bytes and 
                   self.access_order):
                self._evict_lru()
            
            # Create cache entry
            entry = CacheEntry(
                key=key,
                value=value.copy(),
                created_at=time.time(),
                last_accessed=time.time(),
                access_count=1,
                size_bytes=value_bytes,
                ttl_seconds=ttl,
                cache_level=CacheLevel.MEMORY,
                metadata={
                    "prompt_length": len(prompt),
                    "model": model,
                    "method": method
                }
            )
            
            # Remove existing entry if present
            if key in self.cache:
                self._remove_entry(key)
            
            # Add new entry
            self.cache[key] = entry
            self.access_order.append(key)
            self.stats.size_bytes += value_bytes
            self.stats.entry_count += 1
            
            return True
    
    def _evict_lru(self):
        """Evict least recently used entry"""
        if self.access_order:
            lru_key = self.access_order[0]
            self._remove_entry(lru_key)
            self.stats.evictions += 1
    
    def _remove_entry(self, key: str):
        """Remove entry from cache"""
        if key in self.cache:
            entry = self.cache[key]
            self.stats.size_bytes -= entry.size_bytes
            self.stats.entry_count -= 1
            del self.cache[key]
        
        if key in self.access_order:
            self.access_order.remove(key)
    
    def clear(self):
        """Clear all cache entries"""
        with self.lock:
            self.cache.clear()
            self.access_order.clear()
            self.stats.size_bytes = 0
            self.stats.entry_count = 0
    
    def cleanup_expired(self) -> int:
        """Remove expired entries"""
        removed_count = 0
        
        with self.lock:
            expired_keys = [
                key for key, entry in self.cache.items() 
                if entry.is_expired
            ]
            
            for key in expired_keys:
                self._remove_entry(key)
                removed_count += 1
        
        return removed_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            stats = self.stats.to_dict()
            stats["max_size_mb"] = self.max_size_bytes / 1024 / 1024
            stats["size_mb"] = self.stats.size_bytes / 1024 / 1024
            stats["utilization_percent"] = (self.stats.size_bytes / self.max_size_bytes) * 100
            return stats

class DiskCache:
    """Persistent disk cache using SQLite"""
    
    def __init__(self, db_path: str = "artifacts/cache/query_cache.db", 
                 max_size_mb: int = 1000, default_ttl: int = 86400):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl = default_ttl
        self.lock = threading.RLock()
        self.stats = CacheStats()
        
        self._init_database()
        self._load_stats()
        
        logger.info(f"Initialized disk cache: {max_size_mb}MB max, {default_ttl}s TTL, path: {self.db_path}")
    
    def _init_database(self):
        """Initialize SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    value BLOB,
                    created_at REAL,
                    last_accessed REAL,
                    access_count INTEGER,
                    size_bytes INTEGER,
                    ttl_seconds INTEGER,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at ON cache_entries(created_at)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_last_accessed ON cache_entries(last_accessed)
            """)
    
    def _load_stats(self):
        """Load cache statistics from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*), SUM(size_bytes) 
                FROM cache_entries 
                WHERE created_at + ttl_seconds > ?
            """, (time.time(),))
            
            count, total_size = cursor.fetchone()
            self.stats.entry_count = count or 0
            self.stats.size_bytes = total_size or 0
    
    def _generate_key(self, prompt: str, model: str, method: str, **kwargs) -> str:
        """Generate cache key from parameters"""
        key_data = {
            "prompt": prompt,
            "model": model,
            "method": method,
            **kwargs
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]
    
    def get(self, prompt: str, model: str, method: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Get cached result from disk"""
        key = self._generate_key(prompt, model, method, **kwargs)
        
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("""
                        SELECT value, created_at, ttl_seconds, access_count
                        FROM cache_entries 
                        WHERE key = ?
                    """, (key,))
                    
                    row = cursor.fetchone()
                    if not row:
                        self.stats.misses += 1
                        return None
                    
                    value_blob, created_at, ttl_seconds, access_count = row
                    
                    # Check if expired
                    if time.time() - created_at > ttl_seconds:
                        self._remove_entry(key)
                        self.stats.misses += 1
                        return None
                    
                    # Update access statistics
                    conn.execute("""
                        UPDATE cache_entries 
                        SET last_accessed = ?, access_count = access_count + 1
                        WHERE key = ?
                    """, (time.time(), key))
                    
                    # Deserialize value from JSON
                    try:
                        value = json.loads(value_blob.decode('utf-8'))
                        self.stats.hits += 1
                        return value
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        logger.error(f"Disk cache deserialization error for key {key[:8]}...: {e}")
                        # Remove corrupted entry
                        self._remove_entry(key)
                        self.stats.misses += 1
                        return None
                    
            except Exception as e:
                logger.error(f"Disk cache get error: {e}")
                self.stats.misses += 1
                return None
    
    def put(self, prompt: str, model: str, method: str, value: Dict[str, Any], 
            ttl: Optional[int] = None, **kwargs) -> bool:
        """Cache a result to disk"""
        key = self._generate_key(prompt, model, method, **kwargs)
        ttl = ttl or self.default_ttl
        
        try:
            # Serialize value to JSON
            try:
                value_json = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
                value_blob = value_json.encode('utf-8')
                value_size = len(value_blob)
            except (TypeError, ValueError) as e:
                logger.error(f"Disk cache serialization error: {e}")
                return False
            
            with self.lock:
                # Check if we need to evict entries
                self._ensure_space(value_size)
                
                with sqlite3.connect(self.db_path) as conn:
                    # Remove existing entry if present
                    cursor = conn.execute("SELECT size_bytes FROM cache_entries WHERE key = ?", (key,))
                    existing = cursor.fetchone()
                    if existing:
                        self.stats.size_bytes -= existing[0]
                        self.stats.entry_count -= 1
                    
                    # Insert/update entry
                    conn.execute("""
                        INSERT OR REPLACE INTO cache_entries 
                        (key, value, created_at, last_accessed, access_count, size_bytes, ttl_seconds, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        key, value_blob, time.time(), time.time(), 1, 
                        value_size, ttl, json.dumps({
                            "prompt_length": len(prompt),
                            "model": model,
                            "method": method
                        })
                    ))
                    
                    self.stats.size_bytes += value_size
                    self.stats.entry_count += 1
                
                return True
                
        except Exception as e:
            logger.error(f"Disk cache put error: {e}")
            return False
    
    def _ensure_space(self, required_bytes: int):
        """Ensure enough space by evicting old entries"""
        while self.stats.size_bytes + required_bytes > self.max_size_bytes:
            if not self._evict_lru():
                break  # No more entries to evict
    
    def _evict_lru(self) -> bool:
        """Evict least recently used entry (proper LRU)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # First try to evict expired entries
                cursor = conn.execute("""
                    SELECT key, size_bytes FROM cache_entries 
                    WHERE created_at + ttl_seconds <= ?
                    ORDER BY created_at ASC 
                    LIMIT 1
                """, (time.time(),))
                
                row = cursor.fetchone()
                if row:
                    key, size_bytes = row
                    conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                    self.stats.size_bytes -= size_bytes
                    self.stats.entry_count -= 1
                    self.stats.evictions += 1
                    return True
                
                # If no expired entries, evict LRU (least recently accessed)
                cursor = conn.execute("""
                    SELECT key, size_bytes FROM cache_entries 
                    ORDER BY last_accessed ASC 
                    LIMIT 1
                """)
                
                row = cursor.fetchone()
                if not row:
                    return False
                
                key, size_bytes = row
                conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                
                self.stats.size_bytes -= size_bytes
                self.stats.entry_count -= 1
                self.stats.evictions += 1
                
                return True
                
        except Exception as e:
            logger.error(f"Disk cache LRU eviction error: {e}")
            return False
    
    def _remove_entry(self, key: str):
        """Remove specific entry"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT size_bytes FROM cache_entries WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    size_bytes = row[0]
                    conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                    self.stats.size_bytes -= size_bytes
                    self.stats.entry_count -= 1
        except Exception as e:
            logger.error(f"Disk cache remove error: {e}")
    
    def cleanup_expired(self) -> int:
        """Remove expired entries"""
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("""
                        SELECT COUNT(*), SUM(size_bytes) FROM cache_entries 
                        WHERE created_at + ttl_seconds <= ?
                    """, (time.time(),))
                    
                    count, size_bytes = cursor.fetchone()
                    removed_count = count or 0
                    removed_size = size_bytes or 0
                    
                    if removed_count > 0:
                        conn.execute("""
                            DELETE FROM cache_entries 
                            WHERE created_at + ttl_seconds <= ?
                        """, (time.time(),))
                        
                        self.stats.entry_count -= removed_count
                        self.stats.size_bytes -= removed_size
                    
                    return removed_count
                    
        except Exception as e:
            logger.error(f"Disk cache cleanup error: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            stats = self.stats.to_dict()
            stats["max_size_mb"] = self.max_size_bytes / 1024 / 1024
            stats["size_mb"] = self.stats.size_bytes / 1024 / 1024
            stats["utilization_percent"] = (self.stats.size_bytes / self.max_size_bytes) * 100
            stats["db_path"] = str(self.db_path)
            return stats

class MultiLevelCache:
    """Multi-level cache with memory (L1) and disk (L2) tiers"""
    
    def __init__(self, 
                 memory_size_mb: int = 50,
                 disk_size_mb: int = 500,
                 memory_ttl: int = 1800,    # 30 minutes
                 disk_ttl: int = 86400):    # 24 hours
        
        self.memory_cache = MemoryCache(memory_size_mb, memory_ttl)
        self.disk_cache = DiskCache(max_size_mb=disk_size_mb, default_ttl=disk_ttl)
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._periodic_cleanup, daemon=True)
        self.cleanup_thread.start()
    
    def get(self, prompt: str, model: str, method: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Get from multi-level cache (L1 -> L2)"""
        
        # Try L1 (memory) first
        result = self.memory_cache.get(prompt, model, method, **kwargs)
        if result is not None:
            return result
        
        # Try L2 (disk)
        result = self.disk_cache.get(prompt, model, method, **kwargs)
        if result is not None:
            # Promote to L1 cache
            self.memory_cache.put(prompt, model, method, result, **kwargs)
            return result
        
        return None
    
    def put(self, prompt: str, model: str, method: str, value: Dict[str, Any], **kwargs):
        """Put to multi-level cache (L1 and L2)"""
        
        # Always cache in memory (L1)
        self.memory_cache.put(prompt, model, method, value, **kwargs)
        
        # Also cache to disk (L2) for persistence
        self.disk_cache.put(prompt, model, method, value, **kwargs)
    
    def _periodic_cleanup(self):
        """Periodic cleanup of expired entries"""
        while True:
            try:
                time.sleep(300)  # Cleanup every 5 minutes
                
                memory_cleaned = self.memory_cache.cleanup_expired()
                disk_cleaned = self.disk_cache.cleanup_expired()
                
                if memory_cleaned > 0 or disk_cleaned > 0:
                    logger.info(f"Cache cleanup: {memory_cleaned} memory + {disk_cleaned} disk entries removed")
                    
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        memory_stats = self.memory_cache.get_stats()
        disk_stats = self.disk_cache.get_stats()
        
        return {
            "memory_cache": memory_stats,
            "disk_cache": disk_stats,
            "total_hits": memory_stats["hits"] + disk_stats["hits"],
            "total_misses": memory_stats["misses"] + disk_stats["misses"],
            "overall_hit_rate": (
                (memory_stats["hits"] + disk_stats["hits"]) / 
                (memory_stats["hits"] + disk_stats["hits"] + memory_stats["misses"] + disk_stats["misses"])
            ) * 100 if (memory_stats["hits"] + disk_stats["hits"] + memory_stats["misses"] + disk_stats["misses"]) > 0 else 0
        }
    
    def clear_all(self):
        """Clear all cache levels"""
        self.memory_cache.clear()
        # Note: Disk cache clearing would require more careful implementation
    
    def warm_cache(self, warm_entries: List[Dict[str, Any]], max_warm_entries: int = 100) -> int:
        """Warm cache with frequently used queries"""
        warmed_count = 0
        
        logger.info(f"Starting cache warming with {len(warm_entries)} potential entries")
        
        for entry in warm_entries[:max_warm_entries]:
            try:
                prompt = entry.get('prompt', '')
                model = entry.get('model', '')
                method = entry.get('method', 'constrained')
                result = entry.get('result', {})
                
                if prompt and model and result:
                    self.put(prompt, model, method, result)
                    warmed_count += 1
                    
            except Exception as e:
                logger.warning(f"Failed to warm cache entry: {e}")
                continue
        
        logger.info(f"Cache warming completed: {warmed_count} entries loaded")
        return warmed_count
    
    def warm_from_history(self, history_file: str = "artifacts/cache/query_history.json", 
                         max_entries: int = 50) -> int:
        """Warm cache from historical queries"""
        try:
            history_path = Path(history_file)
            if not history_path.exists():
                logger.info(f"No history file found at {history_path}")
                return 0
            
            with open(history_path) as f:
                history = json.load(f)
            
            # Sort by frequency/recency and warm most common queries
            if isinstance(history, list):
                warm_entries = history
            elif isinstance(history, dict) and 'queries' in history:
                warm_entries = history['queries']
            else:
                logger.warning("Invalid history file format")
                return 0
            
            return self.warm_cache(warm_entries, max_entries)
            
        except Exception as e:
            logger.error(f"Failed to warm cache from history: {e}")
            return 0

# Global cache instance
_global_cache: Optional[MultiLevelCache] = None

def get_global_cache() -> MultiLevelCache:
    """Get or create global cache instance"""
    global _global_cache
    if _global_cache is None:
        _global_cache = MultiLevelCache()
    return _global_cache

def cached_query_generation(prompt: str, model: str, method: str = "constrained", **kwargs) -> Optional[Dict[str, Any]]:
    """Wrapper function for cached query generation"""
    cache = get_global_cache()
    return cache.get(prompt, model, method, **kwargs)

def cache_query_result(prompt: str, model: str, result: Dict[str, Any], method: str = "constrained", **kwargs):
    """Cache a query generation result"""
    cache = get_global_cache()
    cache.put(prompt, model, method, result, **kwargs)

def get_cache_stats() -> Dict[str, Any]:
    """Get global cache statistics"""
    cache = get_global_cache()
    return cache.get_stats()

def warm_global_cache(warm_entries: List[Dict[str, Any]] = None, from_history: bool = True) -> int:
    """Warm the global cache"""
    cache = get_global_cache()
    
    total_warmed = 0
    if from_history:
        total_warmed += cache.warm_from_history()
    
    if warm_entries:
        total_warmed += cache.warm_cache(warm_entries)
    
    return total_warmed

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cache management utilities")
    parser.add_argument("--stats", action="store_true", help="Show cache statistics")
    parser.add_argument("--clear", action="store_true", help="Clear all caches")
    parser.add_argument("--test", action="store_true", help="Run cache performance test")
    
    args = parser.parse_args()
    
    if args.stats:
        stats = get_cache_stats()
        print("Cache Statistics:")
        print(json.dumps(stats, indent=2))
    
    if args.clear:
        cache = get_global_cache()
        cache.clear_all()
        print("Cache cleared")
    
    if args.test:
        print("Running cache performance test...")
        cache = get_global_cache()
        
        # Test data
        test_prompt = "Find malicious events on July 4, 2017"
        test_model = "llama3.1:latest"
        test_result = {"query": {"term": {"label": "malicious"}}}
        
        # Test cache operations
        start_time = time.time()
        
        # Write test
        for i in range(100):
            cache.put(f"{test_prompt}_{i}", test_model, "constrained", test_result)
        
        write_time = time.time() - start_time
        
        # Read test
        start_time = time.time()
        hits = 0
        
        for i in range(100):
            result = cache.get(f"{test_prompt}_{i}", test_model, "constrained")
            if result:
                hits += 1
        
        read_time = time.time() - start_time
        
        print(f"Write performance: {100/write_time:.1f} ops/sec")
        print(f"Read performance: {100/read_time:.1f} ops/sec")
        print(f"Cache hits: {hits}/100")
        
        stats = cache.get_stats()
        print(f"Hit rate: {stats['overall_hit_rate']:.1f}%")
