"""Offline app-server peer. No connectors, credentials, network or model calls."""
import json
import sys

for line in sys.stdin:
    value = json.loads(line)
    if "fixture" in value:
        print(json.dumps(value["fixture"]), flush=True)
    else:
        # A response is the only dispatch gate in this fixture.
        value["fixtureDispatch"] = value.get("result", {}).get("action") == "accept"
        print(json.dumps(value), file=sys.stderr, flush=True)
