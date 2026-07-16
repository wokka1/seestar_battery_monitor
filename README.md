# Seestar S50 Battery Monitor

Real battery/power telemetry for the ZWO Seestar S50, read directly over its
native protocol (the same one the official Seestar app uses) - not the
Alpaca/ASCOM layer, which has no battery data at all.

## How it works

The S50 speaks JSON-RPC over a plain TCP socket on port 4700. Before
`get_device_state` returns real data, it requires a challenge/response
handshake signed with an RSA private key:

1. `{"id":1,"method":"get_verify_str"}` -> device returns a random challenge
2. Sign the challenge (RSA, PKCS1v15 padding, SHA1), base64-encode it, send
   `{"id":2,"method":"verify_client","params":{"sign":...,"data":...}}`
3. `get_device_state` now returns the real payload, including a `pi_status`
   block: `battery_capacity`, `charger_status`, `charge_online`,
   `battery_temp`, `is_overtemp`.

The private key isn't something you generate - it's the same key the
official Seestar app itself uses to authenticate, and (at least as of this
writing) it ships as a plain file inside the app's own bundle. On macOS
(the app runs there via Apple's iOS-compatibility layer on Apple Silicon):

```
/Applications/Seestar.app/Wrapper/Seestar.app/my_private.pem
```

**This key is never included in this repo.** Point `private_key_path` in
your own `config.json` at wherever you find it.

## Setup

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp config.example.json config.json   # then edit config.json with your values
```

## Usage

One-off query:
```
.venv/bin/python3 seestar-battery-query.py /path/to/my_private.pem [host]
```

Recurring monitor (intended for cron):
```
.venv/bin/python3 monitor.py                # check + alert if below threshold
.venv/bin/python3 monitor.py --check-only   # print status only
```

Example cron entry (every 30 minutes):
```
*/30 * * * * /path/to/.venv/bin/python3 /path/to/monitor.py >> /path/to/monitor.log 2>&1
```

`monitor.py` only sends one Discord alert per low-battery "episode" - it
won't re-alert every cycle once you're already below the threshold, and
re-arms automatically once the battery recovers.

## Notes for other Seestar owners

The private key appears to be shared/non-device-specific (the same key
structure that the open-source `seestar_alp` project also uses via its own
`seestar_interop_pem` config, though that project doesn't publicly document
where to source it). If ZWO ever makes this device-specific or rotates it,
this will stop working and need re-investigation.

The same authenticated `get_device_state` call also returns quite a lot
more than battery data - mount state, balance/compass sensor readings, WiFi
AP credentials, storage info, etc. Treat the full response as sensitive if
you log or share it.
