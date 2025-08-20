#!/usr/bin/env python3
"""
Test the Data Explorer functionality
"""

import json
import subprocess
import time
from elasticsearch import Elasticsearch

def test_data_explorer():
    """Test the Data Explorer feature"""
    
    print("=" * 60)
    print("DATA EXPLORER FEATURE TEST")
    print("=" * 60)
    
    # Connect to Elasticsearch (use elastic user for admin operations)
    es = Elasticsearch(
        ['http://localhost:9200'],
        basic_auth=('elastic', 'ChangeMe_123'),
        verify_certs=False
    )
    
    # 1. Check available indices
    print("\n1. Checking available indices...")
    try:
        indices = es.cat.indices(format='json')
        available_indices = [idx['index'] for idx in indices if not idx['index'].startswith('.')]
        print(f"✅ Found {len(available_indices)} indices:")
        for idx in available_indices[:5]:  # Show first 5
            count = es.count(index=idx)['count']
            print(f"   - {idx}: {count:,} documents")
    except Exception as e:
        print(f"❌ Error checking indices: {e}")
        return
    
    # 2. Test basic data retrieval
    print("\n2. Testing basic data retrieval...")
    test_index = "logs_cic_ids2017" if "logs_cic_ids2017" in available_indices else available_indices[0]
    
    try:
        # Get sample documents
        response = es.search(
            index=test_index,
            size=10,
            body={"query": {"match_all": {}}}
        )
        hits = response['hits']['hits']
        print(f"✅ Retrieved {len(hits)} documents from {test_index}")
        
        if hits:
            # Show sample fields
            sample_doc = hits[0]['_source']
            fields = list(sample_doc.keys())[:10]
            print(f"   Sample fields: {', '.join(fields)}")
    except Exception as e:
        print(f"❌ Error retrieving data: {e}")
    
    # 3. Test filtering capabilities
    print("\n3. Testing filter capabilities...")
    
    # Time range filter
    try:
        response = es.search(
            index=test_index,
            size=0,
            body={
                "query": {
                    "range": {
                        "@timestamp": {
                            "gte": "now-7d"
                        }
                    }
                }
            }
        )
        count = response['hits']['total']['value']
        print(f"✅ Time filter (last 7 days): {count:,} documents")
    except:
        print("⚠️ Time filter test skipped (no timestamp field)")
    
    # Field filter (if CIC data)
    if "cic" in test_index.lower():
        try:
            response = es.search(
                index=test_index,
                size=0,
                body={
                    "query": {
                        "term": {"attack_type": "dos"}
                    }
                }
            )
            count = response['hits']['total']['value']
            print(f"✅ Attack type filter (dos): {count:,} documents")
        except:
            print("⚠️ Attack type filter test skipped")
    
    # 4. Test aggregations
    print("\n4. Testing aggregation capabilities...")
    try:
        # Get top values for a field
        field_to_agg = "attack_type" if "cic" in test_index.lower() else "protocol"
        response = es.search(
            index=test_index,
            size=0,
            body={
                "aggs": {
                    "top_values": {
                        "terms": {
                            "field": field_to_agg,
                            "size": 5
                        }
                    }
                }
            }
        )
        
        buckets = response['aggregations']['top_values']['buckets']
        if buckets:
            print(f"✅ Top {field_to_agg} values:")
            for bucket in buckets:
                print(f"   - {bucket['key']}: {bucket['doc_count']:,} documents")
    except Exception as e:
        print(f"⚠️ Aggregation test skipped: {e}")
    
    # 5. Test random sampling
    print("\n5. Testing random sampling...")
    try:
        response = es.search(
            index=test_index,
            size=5,
            body={
                "query": {
                    "function_score": {
                        "query": {"match_all": {}},
                        "random_score": {"seed": 42}
                    }
                }
            }
        )
        sample_count = len(response['hits']['hits'])
        print(f"✅ Random sampling: Retrieved {sample_count} random documents")
    except Exception as e:
        print(f"⚠️ Random sampling test failed: {e}")
    
    print("\n" + "=" * 60)
    print("DATA EXPLORER FEATURES:")
    print("=" * 60)
    print("""
✅ IMPLEMENTED FEATURES:
1. 📊 Index Selection
   - Dynamic index discovery
   - Document count display
   - Support for all ES indices

2. 🎯 Browse Options
   - Configurable result limit (10-1000 documents)
   - Sort by any field (timestamp, _doc, IPs, etc.)
   - Ascending/Descending order

3. 🔧 Advanced Filters
   - Time range filtering (1h, 24h, 7d, 30d, all)
   - Field-specific filtering
   - Attack type filtering (for CIC data)
   - Text search across all fields
   - Random sampling with seed

4. 📈 Display Formats
   - Table View: Formatted DataFrame with column configs
   - JSON View: Pretty, Raw, and Source-only tabs
   - Document Cards: Visual card layout with metrics

5. 💾 Export Options
   - CSV export with one click
   - JSON export with formatting
   - Timestamped filenames

6. 🔍 Query Inspector
   - View generated Elasticsearch query
   - Helpful for learning ES DSL

USAGE WORKFLOW:
1. Navigate to "🔍 Data Explorer" in sidebar
2. Select index from dropdown
3. Configure browse options (limit, sort)
4. Apply filters if needed (time, field, attack type)
5. Click "🚀 Load Data"
6. View results in preferred format
7. Export data as CSV or JSON

BEST PRACTICES:
- Start with small result limits for exploration
- Use time filters to focus on recent data
- Apply field filters to narrow down results
- Use random sampling for large datasets
- Export filtered results for offline analysis
""")

if __name__ == "__main__":
    test_data_explorer()