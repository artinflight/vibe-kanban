#!/usr/bin/env python3
"""Use the existing TurnSteer connector without refreshing a caller's tool catalog."""
import argparse
import json
from pathlib import Path
import sys

CONNECTOR = Path('/home/mcp/code/vibe-dot-connector')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    target = sub.add_parser('target', help='Read current steering readiness without sending')
    target.add_argument('--session-id', required=True); target.add_argument('--execution-id', required=True)
    receipt = sub.add_parser('receipt', help='Read one exact retained request receipt')
    receipt.add_argument('--session-id', required=True); receipt.add_argument('--request-id', required=True)
    send = sub.add_parser('send', help='Send one explicit correction; bounded prompt comes from stdin')
    send.add_argument('--session-id', required=True); send.add_argument('--execution-id', required=True)
    send.add_argument('--request-id', required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(CONNECTOR))
    import adapter as api
    import steering
    sid = api.valid_uuid(args.session_id)
    if args.action == 'target':
        eid = api.valid_uuid(args.execution_id)
        data = steering.unwrap(api.http_get('/api/sessions/'+sid+'/steer/target?execution_id='+eid))
        print(json.dumps({k: data.get(k) for k in ('session_id','execution_id','status','thread_id','turn_id','queue_pending')}))
        return
    rid = api.valid_uuid(args.request_id)
    if args.action == 'receipt':
        result = steering.get_receipt(api, {'session_id':sid,'request_id':rid})
    else:
        prompt = sys.stdin.read(60001)
        result = steering.steer(api, {'session_id':sid, 'execution_id':api.valid_uuid(args.execution_id),
                                      'request_id':rid, 'prompt':prompt})
    # Existing adapter results contain bounded admission metadata, never prompt text.
    print(json.dumps(result))
    if result.get('isError'):raise SystemExit(2)

if __name__ == '__main__':
    try:main()
    except Exception:
        print(json.dumps({'status':'held','reason':'invalid_request_or_steering_unavailable','automatic_retry':False}))
        raise SystemExit(1)
