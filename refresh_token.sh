#!/bin/bash

# Newly created Wazuh API user credentials
USER="signalbot"
PASS="SomethingStrong!"
API_URL="https://localhost:55000"

# Generate token
TOKEN=$(curl -sk -u $USER:$PASS -X POST "$API_URL/security/user/authenticate?raw=true")

# Save token to file (check file path to match your system)
echo "$TOKEN" > /home/user/wazuh_token.txt
chmod 600 /home/user/wazuh_token.txt
