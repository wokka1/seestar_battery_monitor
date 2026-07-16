"""
Real Seestar S50 battery/power telemetry, over its native JSON-RPC-over-TCP
protocol (port 4700) - the same protocol/port the official Seestar app
itself uses. Confirmed via a live packet capture of the real app's traffic
(2026-07-16). This is separate from (and has data the Alpaca API used by
NINA/ASCOM does not expose at all).

Requires a real auth handshake before get_device_state returns real data:
  1. send {"id":N,"method":"get_verify_str"} -> get back a random challenge
  2. sign the challenge (RSA private key, PKCS1v15 padding, SHA1 hash),
     base64-encode it, send {"id":N,"method":"verify_client",
     "params":{"sign":<sig>,"data":<challenge>}}
  3. only then does get_device_state return the real pi_status block
     (battery_capacity, charger_status, charge_online, battery_temp, etc)

The private key is never bundled with this project - it must be supplied
by the user, read from wherever the official Seestar app is installed,
e.g. on macOS:
  /Applications/Seestar.app/Wrapper/Seestar.app/my_private.pem
"""

from __future__ import annotations

import base64
import json
import socket

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

DEFAULT_HOST = "10.0.0.1"
DEFAULT_PORT = 4700
DEFAULT_TIMEOUT_SECONDS = 5


class SeestarAuthError(Exception):
    """Raised when the challenge/response handshake is rejected."""


def _send_recv(sock: socket.socket, payload: dict, timeout: float) -> dict:
    sock.sendall((json.dumps(payload) + "\r\n").encode("utf-8"))
    buf = b""
    sock.settimeout(timeout)
    while b"\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buf += chunk
    line = buf.splitlines()[0]
    return json.loads(line)


def get_device_state(
    key_path: str,
    host: str,
    port: int = DEFAULT_PORT,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """Authenticate and return the full get_device_state result dict."""
    with open(key_path, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))

        challenge_resp = _send_recv(s, {"id": 1, "method": "get_verify_str"}, timeout)
        challenge = challenge_resp["result"]["str"]

        signature = private_key.sign(challenge.encode("utf-8"), padding.PKCS1v15(), hashes.SHA1())
        sign_b64 = base64.b64encode(signature).decode("ascii")

        verify_resp = _send_recv(s, {
            "id": 2,
            "method": "verify_client",
            "params": {"sign": sign_b64, "data": challenge},
        }, timeout)
        if verify_resp.get("result") != 0:
            raise SeestarAuthError(f"verify_client rejected: {verify_resp}")

        state_resp = _send_recv(s, {"id": 3, "method": "get_device_state", "params": {}}, timeout)
        return state_resp["result"]
    finally:
        s.close()


def get_pi_status(key_path: str, host: str, port: int = DEFAULT_PORT, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict:
    """Return just the pi_status block (battery/power telemetry)."""
    return get_device_state(key_path, host, port, timeout)["pi_status"]
