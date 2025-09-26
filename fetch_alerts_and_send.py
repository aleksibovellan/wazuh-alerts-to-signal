#!/usr/bin/env python3
import requests
import subprocess
import json
from requests.auth import HTTPBasicAuth
import urllib3
urllib3.disable_warnings()

from datetime import datetime
from collections import defaultdict

# Signal CLI settings
SIGNAL_CLI = "/usr/local/bin/signal-cli"
SIGNAL_NUMBER = "+44XXXXXXXXXXX"
GROUP_GENERAL = "sg/RLEuR+XVrVAu1pGPFvebbOKzTxXigD1Dn6P6cKKQ="
GROUP_PORTSCAN = "TjDAf4veRMdBFaFKbGiHnva3mnYP7TMBINdAVv2A1t4="
GROUP_LOGIN = "UaBtwaJWvkEWEKEbG16Qm99I4oyQPc/mpua40nJ3rv0="

# Elasticsearch API auth (Basic Auth) <-- Replace with your actual username/password if different
ES_USER = "admin"
ES_PASS = "SecretPassword"

# Elasticsearch query endpoint
URL = "https://localhost:9200/wazuh-alerts-*/_search"
HEADERS = {"Content-Type": "application/json"}

QUERY = {
    "query": {
        "range": {
            "@timestamp": {
                "gte": "now-1m",
                "lte": "now"
            }
        }
    },
    "sort": [{ "@timestamp": { "order": "desc" }}],
    "size": 20
}

# Send request
response = requests.post(
    URL,
    auth=HTTPBasicAuth(ES_USER, ES_PASS),
    headers=HEADERS,
    json=QUERY,
    verify=False
)

# Try decoding JSON safely
try:
    alerts = response.json().get("hits", {}).get("hits", [])
except Exception as e:
    print("ERROR: Failed to parse JSON response from Elasticsearch.")
    print("Response text:", response.text)
    exit(1)

# Group classifier
def classify_group(description):
    desc = description.lower()
    if "port scan" in desc:
        return GROUP_PORTSCAN
    elif "brute" in desc or "login" in desc or "authentication" in desc:
        return GROUP_LOGIN
    else:
        return GROUP_GENERAL

# Emoji map for severity
def severity_emoji(level):
    level = int(level)
    if level >= 13:
        return "🆘 Level 13–14"
    elif level >= 10:
        return "🔥 Level 10–12"
    elif level >= 8:
        return "⚠️ Level 8–9"
    elif level >= 5:
        return "🔷 Level 5–7"
    elif level >= 1:
        return "ℹ️ Level 1–4"
    else:
        return "✅ Informational"

# Iterate alerts
for alert in alerts:
    src = alert["_source"]
    data = src.get("data", {})
    rule = src.get("rule", {})
    timestamp = src.get("@timestamp", "unknown")

    level = rule.get("level", 0)
    description = rule.get("description", "No description")
    category = data.get("alert", {}).get("category", "-")
    action = data.get("alert", {}).get("action", "-")
    src_ip = data.get("src_ip", "-")
    src_port = data.get("src_port", "-")
    dst_ip = data.get("dest_ip", "-")
    dst_port = data.get("dest_port", "-")
    proto = data.get("proto", "-")
    firedtimes = rule.get("firedtimes", 1)
    agent_name = src.get("agent", {}).get("name", "unknown")

    # Authentication-specific details
    srcuser = data.get("srcuser", "-")
    dstuser = data.get("dstuser", "-")
    full_log = src.get("full_log", "-")
    hostname = src.get("predecoder", {}).get("hostname", "-")
    program = src.get("predecoder", {}).get("program_name", "-")

    group_id = classify_group(description)

    if group_id == GROUP_LOGIN:
        message_lines = [
            f"🔐 *{description}*",
            f"Source User: `{srcuser}`",
            f"Target User: `{dstuser}`",
            f"Agent: `{agent_name}`",
            f"Hostname: `{hostname}`",
            f"Program: `{program}`",
            f"Time: {timestamp}",
            f"Log: `{full_log}`"
        ]
    else:
        message_lines = [
            f"{severity_emoji(level)}",
            f"📢 *{description}*",
            f"Agent: `{agent_name}`",
            f"Category: _{category}_",
            f"Action: `{action}`",
            f"From: `{src_ip}`:`{src_port}`",
            f"To: `{dst_ip}`:`{dst_port}` ({proto})",
            f"Count: {firedtimes}x",
            f"Time:\n{timestamp}"
        ]

    message = "\n".join(message_lines)

    # Send via Signal CLI
    subprocess.run([
        SIGNAL_CLI,
        "-u", SIGNAL_NUMBER,
        "send",
        "-g", group_id,
        "-m", message
    ])
