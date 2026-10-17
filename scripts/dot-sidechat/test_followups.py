"""Existing conversation recovery, explicit later updates and lost-ACK safety."""
import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import sqlite3
import sys
import types
import unittest
from unittest.mock import patch
import uuid

import test_sidechat
from sidechat import Principal, Rejected, Store
from prepare_context_status import prepare


class Followups(unittest.TestCase):
    setUp = test_sidechat.Contracts.setUp
    tearDown = test_sidechat.Contracts.tearDown
    send = test_sidechat.Contracts.send
    reply = test_sidechat.Contracts.reply

    def test_answered_thread_recovery_is_read_only_and_owner_scoped(self):
        m = self.send()
        self.reply(m)
        before = self.s.db.total_changes
        with_reader = Store.reader(self.path)
        try:
            context = with_reader.workspace_context(self.dot, 'w')
            self.assertEqual(self.t, context['thread_id'])
            self.assertEqual('not_found', with_reader.workspace_context(Principal('bob', 'dot'), 'w')['status'])
            self.assertEqual('not_found', with_reader.workspace_context(self.dot, 'unknown')['status'])
            with self.assertRaises(sqlite3.OperationalError):
                with_reader.db.execute('DELETE FROM messages')
        finally:
            with_reader.close()
        self.assertEqual(before, self.s.db.total_changes)
        self.assertEqual([], self.s.pending(self.dot)['items'])
        self.assertEqual(2, len(self.s.read(self.dot, self.t)['messages']))

    def test_exact_followup_lost_ack_restart_and_original_receipt(self):
        owner = self.send()
        ack = self.reply(owner)
        before = self.s.receipt(self.dot, self.t, owner['id'])
        context = self.s.read(self.dot, self.t)['messages'][0]['reply_context']
        self.assertEqual(ack['id'], context['reply_to'])
        args = dict(thread=self.t, workspace='w', request=context['reply_request'],
                    reply_to=context['reply_to'], event_id=context['event_id'], body='Completed result')
        update = self.s.tool(self.dot, 'append_dot_reply', args)
        self.s.close()
        self.s = Store(self.path)
        self.assertEqual(update, self.s.tool(self.dot, 'append_dot_reply', args))
        after = self.s.receipt(self.dot, self.t, owner['id'])
        for key in before:
            if key != 'continuation': self.assertEqual(before[key], after[key])
        self.assertEqual(2, after['continuation']['reply_count'])
        self.assertEqual(update['id'], after['continuation']['latest_reply']['id'])
        self.assertEqual(1, self.s.db.execute('SELECT count(*) FROM outbox').fetchone()[0])
        self.assertEqual(2, self.s.notifications(self.owner, ['p'])['issues'][0]['unread_count'])
        for changes in ({'workspace': 'w2'}, {'event_id': 'wrong'},
                        {'request': str(uuid.uuid4())}, {'body': 'different'}):
            with self.assertRaises(Rejected):
                self.s.tool(self.dot, 'append_dot_reply', dict(args, **changes))

    def test_snapshot_context_does_not_jump_to_later_reply(self):
        m = self.send()
        ack = self.reply(m)
        snap = self.s.read(self.dot, self.t, limit=1)
        self.reply(ack, event_id="sidechat_"+m["id"])
        frozen = self.s.read(self.dot, self.t, through=snap['through'])
        self.assertEqual(ack['id'], frozen['messages'][0]['reply_context']['reply_to'])

    def test_concurrent_continuation_retries_have_one_successor(self):
        m = self.send()
        ack = self.reply(m)
        key = str(uuid.uuid4())
        def write(_):
            store = Store(self.path)
            try:
                return store.append(self.dot, self.t, 'w', key, 'Later result', ack['id'], 'sidechat_'+m['id'])['id']
            finally: store.close()
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(1, len(set(pool.map(write, range(8)))))
        self.assertEqual(3, len(self.s.read(self.dot, self.t)['messages']))

    def test_continuation_cannot_cross_thread_or_event(self):
        m = self.send()
        ack = self.reply(m)
        self.s.register_scope('alice', 'p', 'other', 'other-w')
        other = self.s.resolve(self.owner, 'p', 'other', 'other-w')['id']
        for thread, workspace, event in [(other, 'other-w', 'sidechat_'+m['id']),
                                          (self.t, 'w', 'sidechat_'+ack['id'])]:
            with self.assertRaises(Rejected):
                self.s.append(self.dot, thread, workspace, str(uuid.uuid4()), 'Bad', ack['id'], event)


class StatusCompatibility(unittest.TestCase):
    def test_only_status_changes_and_original_fields_survive(self):
        source = b'''TOOLS = [{"unchanged": True}]
def untouched(): return 42
def status(api, args, store=None):
    if set(args) != {"workspace_id"}: raise ValueError("invalid")
    wid = args["workspace_id"]
    result = store.status(wid)
    return result
'''
        candidate = prepare(source, hashlib.sha256(source).hexdigest())
        original = {'readback_fresh': False, 'holds': ['hold'], 'delivery': {'status': 'unknown'},
                    'credit_budget': {'status': 'stale'}, 'usage_report': {'status': 'recorded'}}
        ns = {}
        exec(candidate, ns)
        fake = types.SimpleNamespace(workspace_context=lambda wid: {'status': 'available', 'thread_id': 'private'})
        with patch.dict(sys.modules, {'sidechat_connector': fake}):
            result = ns['status'](None, {'workspace_id': 'w'}, types.SimpleNamespace(status=lambda wid: original))
        self.assertEqual(original, {k: result[k] for k in original})
        self.assertNotIn('sidechat', original)
        self.assertEqual('private', result['sidechat']['thread_id'])
        with patch.dict(sys.modules, {'sidechat_connector': types.SimpleNamespace()}):
            result = ns['status'](None, {'workspace_id': 'other'}, types.SimpleNamespace(status=lambda wid: original))
        self.assertEqual('unavailable', result['sidechat']['status'])
        self.assertEqual(original, {k: result[k] for k in original})
        with self.assertRaises(ValueError): prepare(source, '0'*64)


if __name__ == '__main__': unittest.main()
