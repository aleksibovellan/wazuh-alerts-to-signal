#!/bin/bash
# WAZUH API TOKEN REFRESHER

USER="signalbot"
PASS="SomethingStrong!"
API_URL="https://localhost:55000"

# Adjust path to where you want the token stored
OUTPUT_FILE="/home/user/wazuh_token.txt"

# Request Token
TOKEN=$(curl -sk -u $USER:$PASS -X POST "$API_URL/security/user/authenticate?raw=true")

# Validate
if [[ $TOKEN == eyJ* ]]; then
    echo "$TOKEN" > "$OUTPUT_FILE"
    chmod 600 "$OUTPUT_FILE"
else
    # Simple error logging (optional)
    echo "Failed to get Wazuh Token"
fi
