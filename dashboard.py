#!/usr/bin/env python3
"""
Small internal-only status dashboard for the Seestar S50 - deliberately NOT
auto-polling (real telemetry requires a live auth handshake against the
telescope, not something to hit on every page load/refresh). Shows the
last poll's results with a button to trigger a fresh one on demand.

Not internet-exposed by design - reachable only within the WireGuard mesh.
Run with:
  .venv/bin/python3 dashboard.py
Binds to 0.0.0.0:5056.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, redirect, render_template_string, url_for

sys.path.insert(0, str(Path(__file__).parent))
from seestar_battery import SeestarAuthError, get_device_state  # noqa: E402

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
LAST_POLL_PATH = BASE_DIR / "last_poll.json"

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Seestar S50 Status</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #f5f6f8; --card: #ffffff; --border: #e2e4e9; --text: #1a1d24;
    --muted: #6b7280; --accent: #3b6fd4; --accent-soft: #eaf0fd;
    --good: #1a8a4a; --warn: #b8860b; --bad: #b3261e;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #14161b; --card: #1c1f26; --border: #2b2f38; --text: #e8e9ec;
      --muted: #9aa1ac; --accent: #7ba2f0; --accent-soft: #1e2636;
      --good: #4ad080; --warn: #e0b64a; --bad: #f0847c;
    }
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    background: var(--bg); color: var(--text);
    max-width: 40rem; margin: 0 auto; padding: 2rem 1.25rem 4rem; line-height: 1.5;
  }
  h1 { font-size: 1.4rem; margin: 0 0 0.2rem; }
  .sub { color: var(--muted); font-size: 0.85rem; margin-bottom: 1.5rem; }
  .card {
    background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 1.1rem 1.3rem; margin-bottom: 1.2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }
  h2 { font-size: 1rem; margin: 0 0 0.8rem; }
  dl { display: grid; grid-template-columns: auto 1fr; gap: 0.35rem 1rem; margin: 0; }
  dt { color: var(--muted); font-size: 0.85rem; }
  dd { margin: 0; font-weight: 500; }
  button {
    background: var(--accent); color: white; border: none; border-radius: 6px;
    padding: 0.5rem 1.1rem; font-size: 0.9rem; font-weight: 500; cursor: pointer;
  }
  button:hover { filter: brightness(1.08); }
  .badge { display: inline-block; padding: 0.1rem 0.55rem; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }
  .badge.good { background: var(--accent-soft); color: var(--good); }
  .badge.warn { background: var(--accent-soft); color: var(--warn); }
  .badge.bad { background: var(--accent-soft); color: var(--bad); }
  .error { color: var(--bad); }
  .empty { color: var(--muted); font-style: italic; }
</style>
</head>
<body>
<h1>Seestar S50 Status</h1>
<p class="sub">On-demand only - polling this queries the live telescope, so nothing here auto-refreshes.</p>

<form method="post" action="{{ url_for('poll') }}">
  <button type="submit">Poll now</button>
</form>

{% if error %}
<div class="card"><p class="error">{{ error }}</p></div>
{% elif not data %}
<div class="card"><p class="empty">No data yet - click "Poll now".</p></div>
{% else %}
<div class="card">
  <h2>Last poll: {{ data.polled_at }}</h2>
  <dl>
    <dt>Battery</dt><dd>{{ data.pi_status.battery_capacity }}%</dd>
    <dt>Charger status</dt>
    <dd>
      <span class="badge {{ 'good' if data.pi_status.charger_status == 'Charging' else 'warn' }}">
        {{ data.pi_status.charger_status }}
      </span>
    </dd>
    <dt>Charge online</dt><dd>{{ data.pi_status.charge_online }}</dd>
    <dt>Battery temp</dt>
    <dd>{{ data.pi_status.battery_temp }}&deg;C ({{ data.pi_status.battery_temp_type }})</dd>
    <dt>Device temp</dt>
    <dd>
      {{ '%.1f'|format(data.pi_status.temp) }}&deg;C
      {% if data.pi_status.is_overtemp %}<span class="badge bad">OVERTEMP</span>{% endif %}
    </dd>
  </dl>
</div>

<div class="card">
  <h2>Mount</h2>
  <dl>
    <dt>Tracking</dt><dd>{{ data.mount.tracking }}</dd>
    <dt>Arm closed</dt><dd>{{ data.mount.close }}</dd>
    <dt>Move type</dt><dd>{{ data.mount.move_type }}</dd>
    <dt>EQ mode</dt><dd>{{ data.mount.equ_mode }}</dd>
  </dl>
</div>

<div class="card">
  <h2>Orientation</h2>
  <dl>
    <dt>Balance angle</dt><dd>{{ '%.1f'|format(data.balance_sensor.data.angle) }}&deg;</dd>
    <dt>Compass direction</dt><dd>{{ '%.1f'|format(data.compass_sensor.data.direction) }}&deg;</dd>
  </dl>
</div>

<div class="card">
  <h2>Storage</h2>
  <dl>
    <dt>Free</dt><dd>{{ data.storage.storage_volume[0].free_mb }} MB / {{ data.storage.storage_volume[0].total_mb }} MB</dd>
    <dt>Used</dt><dd>{{ data.storage.storage_volume[0].used_percent }}%</dd>
  </dl>
</div>

<div class="card">
  <h2>Device</h2>
  <dl>
    <dt>Model</dt><dd>{{ data.device.product_model }}</dd>
    <dt>Firmware</dt><dd>{{ data.device.firmware_ver_string }}</dd>
    <dt>Serial</dt><dd>{{ data.device.sn }}</dd>
  </dl>
</div>
{% endif %}
</body>
</html>
"""


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


@app.route("/")
def index():
    data = None
    if LAST_POLL_PATH.exists():
        data = json.loads(LAST_POLL_PATH.read_text())
    return render_template_string(TEMPLATE, data=data, error=None)


@app.route("/poll", methods=["POST"])
def poll():
    config = load_config()
    try:
        result = get_device_state(config["private_key_path"], config["seestar_host"])
    except (OSError, SeestarAuthError, KeyError) as e:
        return render_template_string(TEMPLATE, data=None, error=f"Poll failed: {e}")

    result["polled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LAST_POLL_PATH.write_text(json.dumps(result, indent=2))
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5056)
