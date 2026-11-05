"""Single owned sidechat outbox worker; does not touch approval state or Vibe agents."""
import fcntl
import os
import sys
import time
from pathlib import Path
sys.path.append("/home/mcp/code/vibe-dot-connector")
from approval_event_store import webhook
from connector import ROOT, opened, owner
from events import Events
from scope_rollout import readonly, reconcile_projects

def main():
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (ROOT/"publisher.lock").open("w") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        store=opened()
        try:
            events=Events(store,webhook)
            next_scan=0
            while True:
                if time.monotonic()>=next_scan:
                    try:
                        if store.db.execute('SELECT 1 FROM owner_project_policies WHERE enabled=1').fetchone():
                            with readonly(os.environ.get('VK_SIDECHAT_VIBE_DB','/home/mcp/.local/share/vibe-kanban-green-xdg/vibe-kanban/db.v2.sqlite')) as vibe:
                                reconcile_projects(store.db,vibe)
                    except Exception:
                        print('sidechat_project_scan_error; existing scopes retained',file=sys.stderr,flush=True)
                    try:
                        from dispatch_notes import recover_pending
                        recover_pending()
                    except Exception:
                        print('dispatch_note_recovery_unavailable; receipts retained',file=sys.stderr,flush=True)
                    next_scan=time.monotonic()+5
                try:
                    events.deliver_one(owner())
                except Exception:
                    print("sidechat_delivery_error; retained for retry",file=sys.stderr,flush=True)
                time.sleep(1)
        finally:
            store.close()

if __name__=="__main__":
    main()
