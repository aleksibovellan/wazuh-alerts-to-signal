# Wazuh Alerts to Signal via Signal-CLI
A mechanism to automatically extract, classify, and send Wazuh alerts to dedicated Signal Messenger groups using Signal-CLI on Ubuntu.  This setup was built, tested, and deployed on an Ubuntu server running official Wazuh Docker Single Node installation (https://documentation.wazuh.com/current/deployment-options/docker/index.html)

## Overview

These cron-repeated automatic scripts parse and classify Wazuh alert JSONs into 3 alert categories, and then automatically send them into their relevant Signal chat groups named:

1. General Alerts
2. Portscans
3. Login Attempts

- Automatically refreshes Wazuh API tokens to avoid token time-outs
- Queries Wazuh alert JSONs via Elasticsearch (on Wazuh Docker stack)
- Runs from cron every minute and/or can be triggered manually
- Included: optional NordVPN integration with autoconnect, killswitch and LAN allow settings

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
* Wazuh Docker Single Node deployment (with Elasticsearch API), using default config port numbers - or edit them to taste in these included scripts. Do the same with all credentials and file paths mentioned too.

## Install basic requirements

```bash
pip3 install -r requirements.txt
```

## Signal-CLI Installation (Ubuntu)

```bash
sudo apt update && sudo apt install -y unzip curl jq default-jre qrencode

VERSION=$(curl -s https://api.github.com/repos/AsamK/signal-cli/releases/latest | jq -r .tag_name)
curl -LO https://github.com/AsamK/signal-cli/releases/download/$VERSION/signal-cli-$VERSION-Linux.tar.gz

sudo mkdir -p /opt/signal-cli && \
  sudo tar -xzf signal-cli-$VERSION-Linux.tar.gz -C /opt/signal-cli --strip-components=1

sudo ln -s /opt/signal-cli/bin/signal-cli /usr/local/bin/signal-cli
```

1. Use browser to open Signal's CAPTCHA generator (https://signalcaptchas.org/registration/generate).
2. Copy the CAPTCHA URL link from the resulted "Continue/Login" button in your browser.
3. Paste the resulted URL into below command to start phone number registration process for the Signal-CLI:

```bash
signal-cli -a +44XXXXXXXXXXX register --captcha "signalcaptcha://..."
```

4. Then check the phone number for received SMS verification code.
5. Use the SMS verification code like below, and Signal-CLI should be accepted to work for that specific phone number:

```bash
signal-cli -a +44XXXXXXXXXXX verify SMS-CODE
```

## Signal Account Setup (in Mobile App)

1. Install Signal on a mobile phone, and login/register the device for that Signal account, as it usually automatically guides through.
2. Verify the phone number if needed, or otherwise - if so guided - ensure that the mobile device Signal login/registration is completed.
3. Create 3 x Signal groups named:

   * Wazuh General Alerts
   * Wazuh Portscans
   * Wazuh Login Alerts

> Important: The Signal mobile app must be fully registered/logged in **before** starting the next linking process between Signal-CLI and Signal mobile app, or the following QR image reading will not go through.

## Link Signal-CLI to Mobile App

```bash
signal-cli -u +44XXXXXXXXXXX link -n "Wazuh Server"
```

That command outputs a long URL starting with `tsdevice:/`. You can visualize that url into a QR code, in a web browser (https://www.qr-code-generator.com/), or in a terminal as an ASCII image using:

```bash
echo "YOUR_TSDEVICE_LINK" | qrencode -t ansiutf8
```

Then, on your Signal mobile app, go to: Settings > Linked Devices > + > Scan the previous QR code.

Once linked successfully, check the result in Ubuntu:

```bash
signal-cli listAccounts
signal-cli -u +44XXXXXXXXXXX receive
signal-cli -u +44XXXXXXXXXXX listGroups
```

Notice and copy the shown group ID numbers for your groups. Replace the group IDs in the included Python script: `fetch_alerts_and_send.py`.

## Optional: NordVPN Setup

NordVPN is optional. If you want to route alerts through a VPN, install and configure as desired:

```bash
sh <(curl -sSf https://downloads.nordcdn.com/apps/linux/install.sh)
sudo usermod -aG nordvpn $USER && newgrp nordvpn
```

The NordVPN login process will print an URL after running the following command:

```bash
nordvpn login
```

Use a browser to visit the URL to login into NordVPN. After successful login, the NordVPN-CLI will either:

1. update itself with the accepted login information, or
2. you cab use the browser's successful login page, to copy the url for the "Continue" kind-of button, and use it in the terminal like so:

```bash
nordvpn login --callback-url "https://api.nordvpn.com/..."
nordvpn account
nordvpn set technology nordlynx && \
  nordvpn set autoconnect on && \
  nordvpn set lan allow && \
  nordvpn set lan-discovery enabled && \
  nordvpn set routing enabled && \
  nordvpn set legacy_support enabled && \
  nordvpn set notify off
  nordvpn set killswitch on

sudo reboot
```

After reboot, VPN should be connected automatically from now on:

```bash
nordvpn status
curl ifconfig.me
```

And if not, use 'nordvpn connect estonia', etc.

## Wazuh API User Creation

We create and use a dedicated new Wazuh API user ("signalbot") to fetch alerts securely.

### Create Wazuh Admin Token into memory with Wazuh admin/Indexer credentials

Replace `admin` and `SecretPassword` with your actual Wazuh admin/Indexer credentials. If the second command returns user data, then the token is valid and stored in memory.

```bash
ADMIN_TOKEN=$(curl -sk -u admin:SecretPassword -X POST https://localhost:55000/security/user/authenticate?raw=true)
curl -sk -H "Authorization: Bearer $ADMIN_TOKEN" https://localhost:55000/security/user/me | jq
```

### Create New User

```bash
curl -sk -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -X POST https://localhost:55000/security/users \
     -d '{"username":"signalbot","password":"SomethingStrong!"}'
```

### Assign Admin Role

Find the role ID number for Wazuh's user level of `administrator`:

```bash
curl -sk -H "Authorization: Bearer $ADMIN_TOKEN" https://localhost:55000/security/roles | jq
```

Usually it's ID 1.

Then get user ID for the newly created user `signalbot`:

```bash
curl -sk -H "Authorization: Bearer $ADMIN_TOKEN" https://localhost:55000/security/users | jq
```

Then assign administrator role to the new user `signalbot`:

```bash
curl -sk -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -X PUT https://localhost:55000/security/users/user/3 \
     -d '{"roles":[1]}'
```

## Script Files
Save these included two scripts into your local or other desired directory, where they are allowed to run using cron, and check them for all mentioned usernames, passwords and location paths to match your own setup.

### \~/refresh\_token.sh

Bash script provided in the repo under `refresh_token.sh`. This script refreshes the Wazuh API admin token in memory in intervals, so that it doesn't suddenly expire and thus stop the alerts from transmitting into Signal.

### \~/fetch\_alerts\_and\_send.py

Python script provided in the repo under `fetch_alerts_and_send.py`. This fetches the last minute of alerts, parses them, deduplicates based on similarity, and sends a single message with alert count per match.

\(Uses `HTTPBasicAuth` for Elasticsearch API access and `signal-cli` subprocess call to send.\)

### Permissions (check file paths to match your setup)

```bash
chmod +x ~/refresh_token.sh ~/fetch_alerts_and_send.py
```

## Cron Setup for both scripts to work automatically (check file paths to match your system):

```bash
crontab -e
```

Add:

```cron
* * * * * /home/user/refresh_token.sh && /usr/bin/python3 /home/user/fetch_alerts_and_send.py > /dev/null 2>&1
```

## Manual Running & Testing

```bash
bash ~/refresh_token.sh && python3 ~/fetch_alerts_and_send.py
```

## Debug Tools

```bash
signal-cli -u +44XXXXXXXXXXX listGroups
signal-cli -u +44XXXXXXXXXXX receive
```

