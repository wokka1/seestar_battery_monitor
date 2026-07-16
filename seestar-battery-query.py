#!/usr/bin/env python3
"""One-off CLI query of Seestar S50 battery/power telemetry. See README.md."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from seestar_battery import DEFAULT_HOST, get_device_state  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: seestar-battery-query.py /path/to/my_private.pem [host]")
    key_path = sys.argv[1]
    host = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_HOST

    result = get_device_state(key_path, host)

    print("Full get_device_state response:")
    print(json.dumps(result, indent=2))

    pi_status = result.get("pi_status")
    if pi_status:
        print("\npi_status (battery/power telemetry):")
        print(json.dumps(pi_status, indent=2))


if __name__ == "__main__":
    main()
