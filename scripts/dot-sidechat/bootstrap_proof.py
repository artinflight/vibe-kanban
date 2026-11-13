"""Create only an empty private disposable proof thread, never an event or reply."""
from connector import opened, owner
from sidechat import Principal, Rejected

THREAD="22222222-2222-4222-8222-222222222222"
PROJECT="sidechat-proof-project"
ISSUE="sidechat-proof-issue"
WORKSPACE="sidechat-proof-workspace"

def main():
    store=opened()
    try:
        principal=Principal(owner(),"owner")
        store.register_scope(principal.owner,PROJECT,ISSUE,WORKSPACE)
        with store.transaction():
            row=store.db.execute("SELECT * FROM threads WHERE id=?",(THREAD,)).fetchone()
            if row and (row["owner"],row["project"],row["issue"])!=(principal.owner,PROJECT,ISSUE):
                raise Rejected("Proof thread ID collision")
            store.db.execute("INSERT OR IGNORE INTO threads VALUES (?,?,?,?,?)",
                (THREAD,principal.owner,PROJECT,ISSUE,store.clock()))
        print("Empty private proof thread ready: "+THREAD)
    finally:
        store.close()

if __name__=="__main__": main()
