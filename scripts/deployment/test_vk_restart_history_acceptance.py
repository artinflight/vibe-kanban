import unittest
from vk_restart_history_acceptance import bind_summary, checkpoint_message, verify_history, digest, MARKER, OBSERVATION_REASON

class HistoryAcceptance(unittest.TestCase):
    def test_generated_notice_is_separate_but_summary_hash_is_preserved(self):
        report=dict(state='blocked',workspace='w',turn='e',reason=OBSERVATION_REASON)
        summary='The exact reply.'+MARKER+checkpoint_message(report)
        b=bind_summary(summary,execution='e',workspace='w',observation_state='failed')
        self.assertEqual(b['selected_final_sha256'],digest('The exact reply.'))
        self.assertEqual(b['summary_sha256'],digest(summary))
        self.assertEqual(len(b['checkpoint_annotation_sha256']),1)

    def test_user_marker_and_unbound_notice_are_not_stripped(self):
        for summary in ('Reply'+MARKER+'user content', 'Reply'+MARKER+checkpoint_message(dict(state='blocked',workspace='other',turn='e',reason=OBSERVATION_REASON))):
            b=bind_summary(summary,execution='e',workspace='w',observation_state='failed')
            self.assertEqual(b['selected_final_sha256'],digest(summary))
            self.assertEqual(b['checkpoint_annotation_sha256'],[])

    def test_observed_turn_does_not_authenticate_blocked_observation_notice(self):
        s='Reply'+MARKER+checkpoint_message(dict(state='blocked',workspace='w',turn='e',reason=OBSERVATION_REASON))
        self.assertEqual(bind_summary(s,execution='e',workspace='w',observation_state='observed')['selected_final_sha256'],digest(s))

    def test_other_turn_receipt_refuses(self):
        with self.assertRaises(ValueError):
            bind_summary('Reply',execution='e',workspace='w',report=dict(turn='other',workspace='w'))

    def test_pagination_finds_exact_final_and_rejects_missing_or_corrupt(self):
        def page(text,cursor=None,error=None):
            return dict(success=True,data=dict(entries=[dict(entry=dict(content=dict(entry_type=dict(type='assistant_message'),content=text)))],next_before=cursor,capture_error=error,capture_pending=False))
        expected=dict(execution='e',selected_final_sha256=digest('final'))
        pages=iter([page('earlier',12),page('final')])
        self.assertEqual(verify_history(lambda _:next(pages),expected)['pages'],2)
        for p in [page('missing'),page('final',error='damaged')]:
            with self.assertRaises(ValueError):verify_history(lambda _:p,expected)
        with self.assertRaisesRegex(ValueError,'did not advance'):
            verify_history(lambda _:page('earlier',12),expected)

if __name__=='__main__':unittest.main()
