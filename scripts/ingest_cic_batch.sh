#!/bin/bash
# Batch process and ingest CIC-IDS2017 datasets

echo "CIC-IDS2017 Batch Ingestion Script"
echo "===================================="

# Configuration
INDEX="logs_cic_ids2017"
SAMPLE_SIZE=50000  # Adjust as needed
CHUNK_SIZE=5000

# Process and ingest each file
process_file() {
    local input_file=$1
    local day_name=$2
    
    echo ""
    echo "Processing $day_name..."
    echo "------------------------"
    
    # Generate temp file name
    temp_file="data_raw/temp_${day_name}.jsonl"
    
    # Process CSV to JSONL
    echo "Converting CSV to JSONL (sample: $SAMPLE_SIZE)..."
    python src/process_cic_ids2017.py \
        --input "$input_file" \
        --output "$temp_file" \
        --sample $SAMPLE_SIZE
    
    if [ $? -ne 0 ]; then
        echo "Error processing $input_file"
        return 1
    fi
    
    # Ingest into Elasticsearch
    echo "Ingesting into Elasticsearch..."
    python src/ingest_large.py \
        --file "$temp_file" \
        --index "$INDEX" \
        --chunk-size $CHUNK_SIZE
    
    if [ $? -ne 0 ]; then
        echo "Error ingesting $temp_file"
        rm -f "$temp_file"
        return 1
    fi
    
    # Clean up temp file
    rm -f "$temp_file"
    echo "✅ $day_name completed!"
    
    return 0
}

# Create index if needed
echo "Ensuring index exists..."
curl -s -X PUT "localhost:9200/$INDEX" \
    -H 'Content-Type: application/json' \
    -u elastic:ChangeMe_123 \
    -d @artifacts/mappings_cic_enhanced.json > /dev/null 2>&1

# Process files in recommended order
echo ""
echo "Starting batch processing..."

# Monday - baseline (already done, skip if needed)
# process_file "data_raw/Monday-WorkingHours.pcap_ISCX.csv" "Monday"

# Tuesday - Brute force attacks
if [ -f "data_raw/Tuesday-WorkingHours.pcap_ISCX.csv" ]; then
    process_file "data_raw/Tuesday-WorkingHours.pcap_ISCX.csv" "Tuesday"
fi

# Friday Morning - Botnet
if [ -f "data_raw/Friday-WorkingHours-Morning.pcap_ISCX.csv" ]; then
    process_file "data_raw/Friday-WorkingHours-Morning.pcap_ISCX.csv" "Friday-Morning"
fi

# Friday Afternoon - PortScan
if [ -f "data_raw/Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv" ]; then
    process_file "data_raw/Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv" "Friday-PortScan"
fi

# Thursday Morning - Web Attacks
if [ -f "data_raw/Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv" ]; then
    process_file "data_raw/Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv" "Thursday-WebAttacks"
fi

echo ""
echo "===================================="
echo "Batch processing complete!"

# Show final statistics
echo ""
echo "Index statistics:"
curl -s -u elastic:ChangeMe_123 \
    "http://localhost:9200/$INDEX/_count" | jq '.count'

echo ""
echo "Attack type distribution:"
curl -s -u elastic:ChangeMe_123 \
    "http://localhost:9200/$INDEX/_search?size=0" \
    -H "Content-Type: application/json" \
    -d '{"aggs": {"types": {"terms": {"field": "attack_type", "size": 20}}}}' \
    | jq '.aggregations.types.buckets'