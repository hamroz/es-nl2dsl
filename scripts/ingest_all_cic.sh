#!/bin/bash
# Ingest exactly 50k records from each CIC-IDS2017 file

echo "========================================="
echo "CIC-IDS2017 Complete Dataset Ingestion"
echo "Processing 50k records from each file"
echo "========================================="

SAMPLE_SIZE=50000
CHUNK_SIZE=5000
INDEX="logs_cic_ids2017"

# Process a single file
process_file() {
    local csv_file=$1
    local name=$2
    
    if [ ! -f "$csv_file" ]; then
        echo "⚠️  Skipping $name - file not found"
        return 1
    fi
    
    echo ""
    echo "📁 Processing: $name"
    echo "   File: $(basename $csv_file)"
    
    # Create temp JSONL file
    local temp_jsonl="data_raw/temp_${name}.jsonl"
    
    # Process CSV to JSONL
    echo "   Converting CSV to JSONL (50k records)..."
    python src/process_cic_ids2017.py \
        --input "$csv_file" \
        --output "$temp_jsonl" \
        --sample $SAMPLE_SIZE
    
    if [ $? -ne 0 ]; then
        echo "   ❌ Error processing CSV"
        return 1
    fi
    
    # Ingest into Elasticsearch
    echo "   Ingesting into Elasticsearch..."
    python src/ingest_large.py \
        --file "$temp_jsonl" \
        --index "$INDEX" \
        --chunk-size $CHUNK_SIZE \
        --user elastic \
        --password ChangeMe_123 2>/dev/null
    
    if [ $? -ne 0 ]; then
        echo "   ❌ Error ingesting data"
        rm -f "$temp_jsonl"
        return 1
    fi
    
    # Clean up
    rm -f "$temp_jsonl"
    echo "   ✅ Complete!"
    
    return 0
}

# Start processing
echo ""
echo "Starting batch ingestion..."
echo ""

# Process all files in order
process_file "data_raw/Monday-WorkingHours.pcap_ISCX.csv" "Monday"
process_file "data_raw/Tuesday-WorkingHours.pcap_ISCX.csv" "Tuesday"
process_file "data_raw/Wednesday-workingHours.pcap_ISCX.csv" "Wednesday"
process_file "data_raw/Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv" "Thursday-WebAttacks"
process_file "data_raw/Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv" "Thursday-Infiltration"
process_file "data_raw/Friday-WorkingHours-Morning.pcap_ISCX.csv" "Friday-Morning"
process_file "data_raw/Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv" "Friday-PortScan"
process_file "data_raw/Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv" "Friday-DDoS"

# Final statistics
echo ""
echo "========================================="
echo "📊 Final Statistics"
echo "========================================="

# Total documents
echo ""
echo "Total documents indexed:"
curl -s -u elastic:ChangeMe_123 \
    "http://localhost:9200/$INDEX/_count" 2>/dev/null | jq '.count'

# Attack type distribution
echo ""
echo "Attack type distribution:"
curl -s -u elastic:ChangeMe_123 \
    "http://localhost:9200/$INDEX/_search?size=0" \
    -H "Content-Type: application/json" \
    -d '{"aggs": {"types": {"terms": {"field": "attack_type", "size": 20}}}}' 2>/dev/null \
    | jq '.aggregations.types.buckets[] | "\(.key): \(.doc_count)"' -r

# Label distribution
echo ""
echo "Specific attack labels:"
curl -s -u elastic:ChangeMe_123 \
    "http://localhost:9200/$INDEX/_search?size=0" \
    -H "Content-Type: application/json" \
    -d '{"aggs": {"labels": {"terms": {"field": "label", "size": 30}}}}' 2>/dev/null \
    | jq '.aggregations.labels.buckets[] | "\(.key): \(.doc_count)"' -r

# Day distribution
echo ""
echo "Day of week distribution:"
curl -s -u elastic:ChangeMe_123 \
    "http://localhost:9200/$INDEX/_search?size=0" \
    -H "Content-Type: application/json" \
    -d '{"aggs": {"days": {"terms": {"field": "day_of_week", "size": 10}}}}' 2>/dev/null \
    | jq '.aggregations.days.buckets[] | "\(.key): \(.doc_count)"' -r

echo ""
echo "========================================="
echo "✅ Ingestion Complete!"
echo "========================================="