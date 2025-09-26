# Wazuh Alerts to Signal via Signal-CLI
A system to extract, classify, and send Wazuh alerts to dedicated Signal Messenger groups using Signal-CLI.  This setup was built, tested, and deployed on an Ubuntu server running official Wazuh Docker installation.

## Overview

This system parses and classifies Wazuh alert JSONs into 3 alert categories, and then sends them into their relevant Signal chat groups automatically:

1. General Alerts
2. Portscans
3. Login Attempts

- Automatically refreshes Wazuh API tokens
- Queries Wazuh alert JSONs via Elasticsearch (on Wazuh Docker stack)
- Runs from cron every minute or can be triggered manually
- Included: optional NordVPN integration with autoconnect and LAN allow settings

### Alert Routing Logic

```
[Wazuh Docker] --> [Wazuh API Alert JSONs]
                               |
                       [Python parser script]
                               |
                  --> Signal Group: General
                  --> Signal Group: Port Scans
                  --> Signal Group: Login Attempts
```

## Prerequisites for this guide and scripts:

* Ubuntu 22.04.3 LTS (or similar)
* Python 3.10+
* Java Runtime (for Signal-CLI)
* Wazuh Docker deployment (with Elasticsearch API), using default port numbers, or edit them to taste in scripts. Do the same with all credentials and file paths mentioned.

## Signal-CLI Installation

```bash
sudo apt update && sudo apt install -y unzip curl jq default-jre qrencode

VERSION=$(curl -s https://api.github.com/repos/AsamK/signal-cli/releases/latest | jq -r .tag_name)
curl -LO https://github.com/AsamK/signal-cli/releases/download/$VERSION/signal-cli-$VERSION-Linux.tar.gz

sudo mkdir -p /opt/signal-cli && \
  sudo tar -xzf signal-cli-$VERSION-Linux.tar.gz -C /opt/signal-cli --strip-components=1

sudo ln -s /opt/signal-cli/bin/signal-cli /usr/local/bin/signal-cli
```

Use Signal's CAPTCHA generator (https://signalcaptchas.org/registration/generate), and copy the resulting url from the appearing "login/continue" button.

Copy-paste the resulted CAPTCHA url into the following terminal command to start phone number register process for the Signal-CLI, then check the phone number for SMS verification code, and use it:

```bash
signal-cli -a +44XXXXXXXXXXX register --captcha "signalcaptcha://..."
signal-cli -a +44XXXXXXXXXXX verify SMS-CODE
```

## Signal Account Setup (Mobile App)

1. Install Signal on a mobile phone, and login/register the device for that Signal account, as it automatically guides through.
2. Verify the phone number if needed, or otherwise - if so guided - ensure that the mobile device Signal login/registration is completed.
3. Create 3 Signal groups named:

   * Wazuh General Alerts
   * Wazuh Portscans
   * Wazuh Login Alerts

> Important: The Signal mobile app must be fully registered/logged in **before** starting the next linking process (Signal-CLI & Signal mobile app), or the following QR image reading will fail.

## Link Signal-CLI to Mobile App

```bash
signal-cli -u +44XXXXXXXXXXX link -n "Wazuh Server"
```

This command outputs a long URL starting with `tsdevice:/`. You can visualize that url into a QR code, in a web browser (https://www.qr-code-generator.com/), or in a terminal ASCII image using:

```bash
echo "YOUR_TSDEVICE_LINK" | qrencode -t ansiutf8
```

Then, on your Signal mobile app: Settings > Linked Devices > + > Scan the QR code.

Once linked:

```bash
signal-cli listAccounts
signal-cli -u +44XXXXXXXXXXX receive
signal-cli -u +44XXXXXXXXXXX listGroups
```

Copy the group ID numbers from there. Replace the group IDs in the Python script `fetch_alerts_and_send.py`.

## Optional: NordVPN Setup

NordVPN is optional. If you want to route alerts through a VPN, install and configure as desired:

```bash
sh <(curl -sSf https://downloads.nordcdn.com/apps/linux/install.sh)
sudo usermod -aG nordvpn $USER && newgrp nordvpn

nordvpn login

nordvpn set technology nordlynx && \
  nordvpn set killswitch on && \
  nordvpn set autoconnect on && \
  nordvpn set lan allow && \
  nordvpn set lan-discovery enabled && \
  nordvpn set routing enabled && \
  nordvpn set legacy_support enabled && \
  nordvpn set notify off

sudo reboot
```

After reboot, VPN should be connected automatically:

```bash
nordvpn status
curl ifconfig.me
```

And if not, use 'nordvpn connect estonia', etc.

## Wazuh API User Creation

We create and use a dedicated new Wazuh API user ("signalbot") to fetch alerts securely.

### Create Generic Admin Token into memory with Wazuh API credentials:

```bash
curl -k -u APIuser:APIpassword -X POST https://localhost:55000/security/user/authenticate?raw=true
```

### Create New User

```bash
curl -k -H "Authorization: Bearer ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -X POST https://localhost:55000/security/users \
     -d '{"username":"signalbot","password":"SomethingStrong!"}'
```

### Assign Admin Role

Find role ID for `administrator`:

```bash
curl -k -H "Authorization: Bearer ADMIN_TOKEN" https://localhost:55000/security/roles | jq
```

Assume it's ID 1.

Get user ID for signalbot:

```bash
curl -k -H "Authorization: Bearer ADMIN_TOKEN" https://localhost:55000/security/users | jq
```

Then assign role:

```bash
curl -k -H "Authorization: Bearer ADMIN_TOKEN" \
     -X PUT https://localhost:55000/security/users/user/3 \
     -d '{"roles":[1]}'
```

## Script Files
Save these two scripts into your local or other desired directory, and check in them all usernames, passwords and location paths to match your setup.

### \~/refresh\_token.sh

Bash script provided in the repo under `refresh_token.sh`. This refreshes the Wazuh API admin token into memory so that it doesn't suddenly expire - for the alert fetch python script to continue working automatically in the background.

### \~/fetch\_alerts\_and\_send.py

Python script provided in the repo under `fetch_alerts_and_send.py`. This fetches the last minute of alerts, parses them, deduplicates based on similarity, and sends a single message with alert count per match.

\(Uses `HTTPBasicAuth` for Elasticsearch API access and `signal-cli` subprocess call to send.\)

### Permissions (check file paths)

```bash
chmod +x ~/refresh_token.sh ~/fetch_alerts_and_send.py
```

## Cron Job Setup for both scripts to work automatically (check file paths):

```bash
crontab -e
```

Add:

```cron
* * * * * /home/user/refresh_token.sh && /usr/bin/python3 /home/user/fetch_alerts_and_send.py > /dev/null 2>&1
```

## Manual Test

```bash
bash ~/refresh_token.sh && python3 ~/fetch_alerts_and_send.py
```

## Debug Tools

```bash
signal-cli -u +44XXXXXXXXXXX listGroups
signal-cli -u +44XXXXXXXXXXX receive
```

