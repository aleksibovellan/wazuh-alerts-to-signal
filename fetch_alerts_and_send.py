#!/usr/bin/env python3
import requests
import subprocess
import json
import time
import os
from requests.auth import HTTPBasicAuth
import urllib3
urllib3.disable_warnings()

# --- CONFIGURATION ---
# Signal-CLI Path
SIGNAL_CLI = "/usr/local/bin/signal-cli"
# SENDER Phone Number (Must be registered/linked in signal-cli)
SIGNAL_NUMBER = "+44XXXXXXXXXXX" 

# Signal Group IDs (Run 'signal-cli -u +44... listGroups' to get these)
GROUP_GENERAL = "YOUR_BASE64_GROUP_ID_HERE"
GROUP_PORTSCAN = "YOUR_BASE64_GROUP_ID_HERE"
GROUP_LOGIN = "YOUR_BASE64_GROUP_ID_HERE"

# Elasticsearch Credentials
ES_USER = "admin"
ES_PASS = "SecretPassword"
URL = "https://localhost:9200/wazuh-alerts-*/_search"
HEADERS = {"Content-Type": "application/json"}

# File to store throttling timestamps (Auto-created in the same folder)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, "throttle_state.json")

# Throttling Settings (Seconds) - Anti-Spam
THROTTLE_LIMITS = {
    GROUP_PORTSCAN: 180,  # 3 Minutes silence between Port Scan alerts
    GROUP_LOGIN: 60,      # 1 Minute silence between Login alerts
    GROUP_GENERAL: 60     # 1 Minute silence for others
}

# --- 1. HEARTBEAT (ANTI-EXPIRY) ---
# Critical: Sync receive queue to prevent session expiry (The "68 days ago" bug)
try:
    subprocess.run(
        [SIGNAL_CLI, "-u", SIGNAL_NUMBER, "receive"], 
        timeout=10, 
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.DEVNULL
    )
except Exception:
    pass

# --- 2. LOAD THROTTLE STATE ---
if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, 'r') as f:
            throttle_state = json.load(f)
    except:
        throttle_state = {}
else:
    throttle_state = {}

# --- 3. QUERY WAZUH ---
# We look back 1 minute. Cron should run this script every minute.
QUERY = {
    "query": {
        "range": {
            "@timestamp": {
                "gte": "now-1m",
                "lte": "now"
            }
        }
    },
    "sort": [{"@timestamp": {"order": "desc"}}],
    "size": 50 
}

response = requests.post(
    URL,
    auth=HTTPBasicAuth(ES_USER, ES_PASS),
    headers=HEADERS,
    json=QUERY,
    verify=False
)

try:
    alerts = response.json().get("hits", {}).get("hits", [])
except Exception:
    # Fail silently or log error
    exit(1)

# --- 4. CLASSIFICATION & PROCESSING ---
def classify_group(description):
    desc = description.lower()
    if "port scan" in desc:
        return GROUP_PORTSCAN
    elif "brute" in desc or "login" in desc or "authentication" in desc:
        return GROUP_LOGIN
    else:
        return GROUP_GENERAL

def severity_emoji(level):
    level = int(level)
    if level >= 13: return "🆘 Level 13–14"
    elif level >= 10: return "🔥 Level 10–12"
    elif level >= 8: return "⚠️ Level 8–9"
    elif level >= 5: return "🔷 Level 5–7"
    elif level >= 1: return "ℹ️ Level 1–4"
    else: return "✅ Informational"

current_time = time.time()

for alert in alerts:
    src = alert["_source"]
    rule = src.get("rule", {})
    description = rule.get("description", "No description")
    
    group_id = classify_group(description)
    
    # CHECK THROTTLE
    last_sent = throttle_state.get(group_id, 0)
    if (current_time - last_sent) < THROTTLE_LIMITS.get(group_id, 60):
        continue 
        
    throttle_state[group_id] = current_time
    
    data = src.get("data", {})
    timestamp = src.get("@timestamp", "unknown")
    level = rule.get("level", 0)
    agent_name = src.get("agent", {}).get("name", "unknown")
    
    if group_id == GROUP_LOGIN:
        srcuser = data.get("srcuser", "-")
        dstuser = data.get("dstuser", "-")
        hostname = src.get("predecoder", {}).get("hostname", "-")
        message = (
            f"🔐 *{description}*\n"
            f"User: `{srcuser}` ➔ `{dstuser}`\n"
            f"Host: `{hostname}`\n"
            f"Time: {timestamp}"
        )
    else:
        src_ip = data.get("src_ip", "-")
        dst_ip = data.get("dest_ip", "-")
        dst_port = data.get("dest_port", "-")
        message = (
            f"{severity_emoji(level)}\n"
            f"📢 *{description}*\n"
            f"Agent: `{agent_name}`\n"
            f"IP: `{src_ip}` ➔ `{dst_ip}`:`{dst_port}`"
        )

    # Send via Signal-CLI
    subprocess.run([
        SIGNAL_CLI, "-u", SIGNAL_NUMBER, "send", "-g", group_id, "-m", message
    ])

# --- 5. SAVE STATE ---
with open(STATE_FILE, 'w') as f:
    json.dump(throttle_state, f)
