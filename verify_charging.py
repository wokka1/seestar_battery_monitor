#!/usr/bin/env python3
"""
Polls the Seestar for charger_status == "Charging", used right after a
charger power-cycle to confirm the outlet coming back on actually resulted
in real charging (not just proof the smart plug itself is on).

Must run somewhere that can reach the Seestar's own network (e.g. on
stargazer) - this is intentionally separate from the Kasa outlet control,
which runs wherever has internet access to TP-Link's cloud (not
necessarily the same place).

Exit code 0 if charging resumed within the timeout, 1 otherwise.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from seestar_battery import SeestarAuthError, get_pi_status  # noqa: E402

POLL_INTERVAL_SECONDS = 5
DEFAULT_TIMEOUT_SECONDS = 60


def main() -> None:
    timeout = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TIMEOUT_SECONDS
    config = json.loads((Path(__file__).parent / "config.json").read_text())

    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        try:
            last_status = get_pi_status(config["private_key_path"], config["seestar_host"])
        except (OSError, SeestarAuthError) as e:
            print(f"Query failed: {e}")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        print(f"charger_status={last_status['charger_status']} charge_online={last_status['charge_online']} battery={last_status['battery_capacity']}%")
        if last_status["charger_status"] == "Charging":
            print("Charging resumed.")
            sys.exit(0)
        time.sleep(POLL_INTERVAL_SECONDS)

    print(f"Timed out after {timeout}s - charging did not resume. Last status: {last_status}")
    sys.exit(1)


if __name__ == "__main__":
    main()
