#!/bin/bash

# Helper script to grant reader access to new log indices
# Usage: ./grant_index_access.sh [index_name]

INDEX_NAME=${1:-logs_*}

echo "Granting reader access to index pattern: $INDEX_NAME"

# Update the reader role to include the specified index pattern
curl -X PUT "localhost:9200/_security/role/logs_net_reader" \
  -u elastic:ChangeMe_123 \
  -H 'Content-Type: application/json' \
  -d '{
    "cluster": ["monitor"],
    "indices": [
      {
        "names": ["logs_*"],
        "privileges": ["read", "view_index_metadata"]
      }
    ]
  }'

echo ""
echo "Access granted! Testing with reader user..."

# Test access
curl -X GET "localhost:9200/${INDEX_NAME}/_search?size=0" \
  -u reader:ReaderPwd_123 \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {
      "match_all": {}
    }
  }'

echo ""
echo "Done!"
