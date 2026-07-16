#!/usr/bin/env python3
"""
Recurring Seestar S50 battery check - queries real telemetry (see
seestar_battery.py) and sends a Discord webhook alert if the battery drops
below a configured threshold. Meant to run periodically via cron.

Only alerts once per low-battery "episode" (state.json tracks whether an
alert has already fired since the battery last dropped below the
threshold) - resets once the battery recovers back above it, so a 30-minute
cron cadence doesn't spam the same warning over and over.

Config (config.json, not committed - copy config.example.json and fill in
your own values):
  seestar_host          - IP of the Seestar's own network, e.g. "10.0.0.1"
  private_key_path       - path to the official app's bundled private key
  low_battery_threshold  - battery_capacity percent to alert below
  discord_webhook_url    - Discord webhook URL to POST alerts to

Usage:
  python3 monitor.py                 # run one check now (for cron)
  python3 monitor.py --check-only     # print status, don't alert or write state
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from seestar_battery import SeestarAuthError, get_pi_status

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
STATE_PATH = BASE_DIR / "state.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(f"Missing {CONFIG_PATH} - copy config.example.json and fill in your values")
    return json.loads(CONFIG_PATH.read_text())


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"alert_sent_for_current_episode": False}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


def send_discord_alert(webhook_url: str, message: str) -> bool:
    data = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, data=data,
        headers={"Content-Type": "application/json", "User-Agent": "SeestarBatteryMonitor/1.0"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Discord alert failed to send: {e}", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Print status only, don't alert or persist state")
    args = parser.parse_args()

    config = load_config()
    timestamp = datetime.now().isoformat()

    try:
        pi_status = get_pi_status(config["private_key_path"], config["seestar_host"])
    except (OSError, SeestarAuthError, KeyError) as e:
        print(f"[{timestamp}] Query failed: {e}")
        sys.exit(1)

    battery = pi_status["battery_capacity"]
    charging = pi_status["charger_status"]
    threshold = config["low_battery_threshold"]

    print(f"[{timestamp}] battery={battery}% charger_status={charging} charge_online={pi_status['charge_online']}")

    if args.check_only:
        return

    state = load_state()
    below_threshold = battery < threshold

    if below_threshold and not state["alert_sent_for_current_episode"]:
        message = (
            f"⚠️ Seestar S50 battery low: {battery}% (threshold {threshold}%). "
            f"Charger status: {charging}, charge_online: {pi_status['charge_online']}."
        )
        if send_discord_alert(config["discord_webhook_url"], message):
            state["alert_sent_for_current_episode"] = True
            print(f"[{timestamp}] Alert sent.")
    elif not below_threshold and state["alert_sent_for_current_episode"]:
        state["alert_sent_for_current_episode"] = False
        print(f"[{timestamp}] Battery recovered above threshold, alert re-armed.")

    save_state(state)


if __name__ == "__main__":
    main()
