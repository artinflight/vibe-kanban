import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch
import uuid

import fast_online as fast
import online_owner
import test_scoped_fence


class FreshFenceTests(test_scoped_fence.ScopedTests):
    def make_fence(self, **overrides):
        values = dict(root=self.root, database=self.db, workspace_id=self.workspace,
                      plan=self.plan, roster=self.roster)
        values.update(overrides)
        return fast.FreshClosedLogFence(**values)

    def test_changes_committed_by_another_connection_are_seen_while_held(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
        with self.assertRaisesRegex(ValueError, 'terminal execution'):
            with self.fence.held():
                self.fence.check()
                with sqlite3.connect(self.db) as conn:
                    conn.execute("UPDATE execution_processes SET status='running' WHERE id=?",
                                 (uuid.UUID(Path(self.names[0]).stem).bytes,))
                self.fence.check()
        self.assertIsNone(self.fence.connection)
        self.assertFalse(self.fence.locks)

    def test_replaced_database_is_not_hidden_by_reused_connection(self):
        replacement = self.db.with_suffix('.other')
        replacement.write_bytes(self.db.read_bytes())
        with self.assertRaisesRegex(ValueError, 'database'):
            with self.fence.held():
                replacement.replace(self.db)
                self.fence.validate_entry(self.plan['files'][0])
        self.assertIsNone(self.fence.connection)

    def test_connection_is_read_only_and_no_transaction_is_retained(self):
        with self.fence.held():
            for _ in range(3):
                self.fence.check()
                self.assertFalse(self.fence.connection.in_transaction)
            with self.assertRaises(sqlite3.OperationalError):
                self.fence.connection.execute('DELETE FROM saved_inputs')
        self.assertIsNone(self.fence.connection)


class FastChecksTests(unittest.TestCase):
    def test_unit_properties_are_read_fresh_and_only_exact_fields(self):
        class Properties:
            def __init__(self): self.calls=[];self.pid=1
            def Get(self, interface, key, timeout):
                self.calls.append((interface,key,timeout))
                return b'1'*16 if key=='InvocationID' else self.pid if key=='MainPID' else 'active'
        properties=Properties();reader=fast.FreshUnits.__new__(fast.FreshUnits)
        reader.objects={'owned':properties}
        self.assertEqual(reader('owned')['MainPID'],'1')
        properties.pid=2
        self.assertEqual(reader('owned')['MainPID'],'2')
        self.assertEqual(len(properties.calls),10)
        self.assertEqual({x[1] for x in properties.calls},set(fast.FreshUnits.FIELDS))
        with self.assertRaises(KeyError):reader('foreign')

    def test_mount_checks_match_existing_semantics_including_nested_overrides(self):
        cases=[
            ('/ rw\n/data ro', '/data/sessions'),
            ('/ ro\n/data rw', '/data/sessions'),
            ('/ rw\n/data ro\n/data/sessions/sub rw', '/data/sessions'),
            ('/ rw\n/data ro\n/data/sessions-extra rw', '/data/sessions'),
            ('/ rw\n/data ro\n/data/sessions ro\n/data/sessions/x ro', '/data/sessions'),
            ('/ rw\n/data\\040store ro', '/data store/sessions'),
            ('/ ro\n/other rw', '/'),
        ]
        for mounts,inside in cases:
            raw='\n'.join('1 2 0:1 / '+line.replace(' ', ' ',1)+' - ext4 dev rw' for line in mounts.splitlines())
            outcomes=[]
            for fn in [online_owner.readonly_mount,fast.readonly_mount]:
                try:
                    with patch.object(Path,'read_text',return_value=raw):fn(123,inside)
                    outcomes.append(True)
                except ValueError:outcomes.append(False)
            self.assertEqual(outcomes[0],outcomes[1],mounts)

    def test_directory_groups_flush_before_completion_and_retain_failed_flush(self):
        calls=[];group=fast.DirectorySyncGroup(calls.append,limit=3)
        group.removed(Path('/a'));group.removed(Path('/b'))
        self.assertEqual(calls,[])
        group.removed(Path('/a'))
        self.assertEqual(calls,[Path('/a'),Path('/b')])
        group.removed(Path('/b'));group.flush()
        self.assertEqual(calls[-1],Path('/b'));self.assertFalse(group.pending)
        def fail(_):raise OSError('flush failed')
        group=fast.DirectorySyncGroup(fail);group.removed(Path('/a'))
        with self.assertRaises(OSError):group.flush()
        self.assertEqual(group.pending,{Path('/a')})


if __name__=='__main__':unittest.main()
