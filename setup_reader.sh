#!/bin/bash

# Setup reader role and user in Elasticsearch

echo "Creating reader role and user..."

# Create the reader role
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

# Create the reader user
curl -X PUT "localhost:9200/_security/user/reader" \
  -u elastic:ChangeMe_123 \
  -H 'Content-Type: application/json' \
  -d '{
    "password": "ReaderPwd_123",
    "roles": ["logs_net_reader"],
    "full_name": "Read-only User"
  }'

echo ""
echo "Reader user created with role logs_net_reader"

# Test the reader user
echo ""
echo "Testing reader user access..."
curl -X GET "localhost:9200/logs_net/_search?size=0" \
  -u reader:ReaderPwd_123 \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {
      "match_all": {}
    }
  }'

echo ""
echo "Setup complete!"