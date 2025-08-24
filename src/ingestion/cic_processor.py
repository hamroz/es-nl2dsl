#!/usr/bin/env python3
"""
Process CIC-IDS2017 CSV files and convert to Elasticsearch-compatible format
"""

import argparse
import csv
import json
import hashlib
from datetime import datetime, timedelta
import re
import sys
from pathlib import Path

def clean_field_name(field):
    """Clean and normalize field names for Elasticsearch"""
    field = field.strip().lower()
    field = re.sub(r'[^\w]+', '_', field)
    field = re.sub(r'_+', '_', field)
    field = field.strip('_')
    return field

def parse_timestamp(timestamp_str, filename):
    """Parse CIC timestamp format and add day info from filename"""
    try:
        # Parse date from timestamp (DD/MM/YYYY HH:MM:SS)
        dt = datetime.strptime(timestamp_str.strip(), '%d/%m/%Y %H:%M:%S')
        
        # Keep original timestamp - the data already has correct dates
        return dt.isoformat()
    except:
        # Fallback to a default timestamp if parsing fails
        return datetime(2017, 7, 3).isoformat()

def classify_attack(label):
    """Classify the attack type from the label"""
    label = label.strip()
    if label == 'BENIGN':
        return 'normal', 'BENIGN'
    elif 'DoS' in label or 'DDoS' in label:
        return 'dos', label
    elif 'PortScan' in label:
        return 'scan', label
    elif 'Web' in label or 'XSS' in label or 'Sql' in label:
        # Web attacks should be classified as web_attack even if they contain "Brute"
        return 'web_attack', label
    elif 'Patator' in label or ('Brute' in label and 'Web' not in label):
        return 'bruteforce', label
    elif 'Infiltration' in label or 'Infilteration' in label:
        return 'infiltration', label
    elif 'Bot' in label:
        return 'botnet', label
    elif 'Heartbleed' in label:
        return 'heartbleed', label
    else:
        return 'malicious', label

def process_row(row, headers, filename):
    """Process a single CSV row into Elasticsearch document"""
    doc = {}
    
    # Map CIC fields to our standard schema
    field_mapping = {
        'source_ip': 'src_ip',
        'destination_ip': 'dst_ip',
        'source_port': 'src_port',
        'destination_port': 'dst_port',
        'protocol': 'protocol',
        'timestamp': '@timestamp',
        'flow_duration': 'flow_duration',
        'total_fwd_packets': 'total_fwd_packets',
        'total_backward_packets': 'total_bwd_packets',
        'total_length_of_fwd_packets': 'bytes_out',
        'total_length_of_bwd_packets': 'bytes_in',
        'label': 'label'
    }
    
    # Process each field
    for i, header in enumerate(headers):
        clean_header = clean_field_name(header)
        value = row[i].strip() if i < len(row) else ''
        
        # Skip empty values
        if not value or value == 'NaN' or value == 'Infinity':
            continue
            
        # Handle special fields
        if clean_header in field_mapping:
            mapped_field = field_mapping[clean_header]
            
            if mapped_field == '@timestamp':
                doc[mapped_field] = parse_timestamp(value, filename)
            elif mapped_field == 'protocol':
                # Convert protocol number to name
                protocol_map = {'6': 'tcp', '17': 'udp', '1': 'icmp', '0': 'other'}
                doc[mapped_field] = protocol_map.get(value, 'other')
            elif mapped_field in ['src_port', 'dst_port', 'bytes_in', 'bytes_out', 
                                 'flow_duration', 'total_fwd_packets', 'total_bwd_packets']:
                try:
                    doc[mapped_field] = int(float(value))
                except:
                    doc[mapped_field] = 0
            elif mapped_field == 'label':
                attack_type, specific_label = classify_attack(value)
                doc['label'] = specific_label
                doc['attack_type'] = attack_type
            else:
                doc[mapped_field] = value
        
        # Include other important CIC fields
        elif clean_header in ['flow_bytes_s', 'flow_packets_s', 
                              'flow_iat_mean', 'flow_iat_std', 'flow_iat_max', 'flow_iat_min',
                              'fwd_iat_mean', 'fwd_iat_std', 'bwd_iat_mean', 'bwd_iat_std',
                              'fin_flag_count', 'syn_flag_count', 'rst_flag_count', 
                              'psh_flag_count', 'ack_flag_count', 'urg_flag_count',
                              'packet_length_min', 'packet_length_max', 'packet_length_mean',
                              'packet_length_std', 'avg_packet_size']:
            try:
                if 'flag_count' in clean_header:
                    doc[clean_header] = int(float(value))
                else:
                    doc[clean_header] = float(value)
            except:
                pass
    
    # Add derived fields
    if 'total_fwd_packets' in doc and 'total_bwd_packets' in doc:
        doc['total_packets'] = doc['total_fwd_packets'] + doc['total_bwd_packets']
    
    # Add temporal fields for easier querying
    if '@timestamp' in doc:
        dt = datetime.fromisoformat(doc['@timestamp'])
        doc['day_of_week'] = dt.strftime('%A')
        doc['hour_of_day'] = dt.hour
    
    # Generate a deterministic document ID
    id_str = f"{doc.get('src_ip', '')}-{doc.get('dst_ip', '')}-{doc.get('src_port', '')}-{doc.get('dst_port', '')}-{doc.get('@timestamp', '')}"
    doc_id = hashlib.sha1(id_str.encode()).hexdigest()
    
    return doc, doc_id

def process_cic_csv(input_file, output_file, sample_size=None):
    """Process CIC-IDS2017 CSV file and convert to JSONL format"""
    
    print(f"Processing {input_file}...")
    
    total_rows = 0
    malicious_count = 0
    benign_count = 0
    
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as infile:
        with open(output_file, 'w') as outfile:
            reader = csv.reader(infile)
            
            # Read and clean headers
            headers = next(reader)
            headers = [clean_field_name(h) for h in headers]
            
            for row_num, row in enumerate(reader):
                if sample_size and row_num >= sample_size:
                    break
                    
                try:
                    doc, doc_id = process_row(row, headers, input_file)
                    
                    # Write as JSONL with document ID for bulk indexing
                    action = {"index": {"_id": doc_id}}
                    outfile.write(json.dumps(action) + '\n')
                    outfile.write(json.dumps(doc) + '\n')
                    
                    # Count statistics
                    total_rows += 1
                    if doc.get('attack_type') == 'normal':
                        benign_count += 1
                    else:
                        malicious_count += 1
                    
                    # Progress indicator
                    if total_rows % 10000 == 0:
                        print(f"  Processed {total_rows:,} rows...")
                        
                except Exception as e:
                    print(f"  Error processing row {row_num}: {e}")
                    continue
    
    print(f"\nProcessing complete:")
    print(f"  Total rows: {total_rows:,}")
    print(f"  Benign: {benign_count:,} ({benign_count*100/max(total_rows,1):.1f}%)")
    print(f"  Malicious: {malicious_count:,} ({malicious_count*100/max(total_rows,1):.1f}%)")
    print(f"  Output written to: {output_file}")
    
    return total_rows

def main():
    parser = argparse.ArgumentParser(description='Process CIC-IDS2017 CSV files for Elasticsearch')
    parser.add_argument('--input', '-i', required=True, help='Input CSV file')
    parser.add_argument('--output', '-o', required=True, help='Output JSONL file')
    parser.add_argument('--sample', '-s', type=int, help='Sample size (number of rows to process)')
    
    args = parser.parse_args()
    
    if not Path(args.input).exists():
        print(f"Error: Input file {args.input} not found")
        sys.exit(1)
    
    process_cic_csv(args.input, args.output, args.sample)

if __name__ == '__main__':
    main()