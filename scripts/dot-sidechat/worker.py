"""Single owned sidechat outbox worker; does not touch approval state or Vibe agents."""
import fcntl
import sys
import time
from pathlib import Path
sys.path.append("/home/mcp/code/vibe-dot-connector")
from approval_event_store import webhook
from connector import ROOT, opened, owner
from events import Events

def main():
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (ROOT/"publisher.lock").open("w") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        store=opened()
        try:
            events=Events(store,webhook)
            while True:
                try:
                    events.deliver_one(owner())
                except Exception:
                    print("sidechat_delivery_error; retained for retry",file=sys.stderr,flush=True)
                time.sleep(1)
        finally:
            store.close()

if __name__=="__main__":
    main()
