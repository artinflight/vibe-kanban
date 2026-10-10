"""Disposable cron state only; never invokes live crontab installation."""
from types import SimpleNamespace
import re
import unittest

from vk_nightly_schedule import block, add_owned, remove_owned, apply


class Schedule(unittest.TestCase):
    def setUp(self):
        self.owned=block('/fixture/package','/fixture/config','a'*64,'/fixture/log',hour=2,minute=0)
        self.original='MAILTO=""\n15 3 * * * /fixture/unrelated-backup\n'
    def test_daily_script_no_llm_root_or_service_cutover(self):
        self.assertIn('0 2 * * * ',self.owned);self.assertIn('MemoryMax=3G',self.owned)
        self.assertIn('vk_nightly_supervisor.py',self.owned)
        for forbidden in ('sudo','codex','systemctl stop','rm '):self.assertNotIn(forbidden,self.owned)
    def test_cron_percent_does_not_split_command_or_create_stdin(self):
        command=self.owned.splitlines()[1].split(' ',5)[5]
        self.assertFalse(re.search(r'(?<!\\)%',command))
        shell_command=command.replace('\\%','%')
        self.assertIn('--property=CPUQuota=25% ',shell_command)
        self.assertIn('--config-sha256 '+'a'*64,shell_command)
    def test_rollback_preserves_all_other_lines(self):
        updated=add_owned(self.original,self.owned,timezone='Etc/UTC')
        self.assertEqual(remove_owned(updated,self.owned),self.original)
    def test_unknown_or_changed_block_cannot_be_replaced(self):
        with self.assertRaises(ValueError):add_owned(self.original+self.owned,self.owned,timezone='UTC')
        with self.assertRaises(ValueError):remove_owned(self.original+self.owned.replace('MemoryMax=3G','MemoryMax=4G'),self.owned)
    def test_timezone_does_not_silently_change_unrelated_jobs(self):
        for text,timezone in [(self.original,'Europe/London'),('CRON_TZ=UTC\n'+self.original,'UTC')]:
            with self.assertRaises(ValueError):add_owned(text,self.owned,timezone=timezone)
    def test_gate_failure_is_before_any_cron_access(self):
        def denied():raise ValueError('fixture acceptance missing')
        def unexpected(*a,**kw):self.fail('gate did not precede access')
        with self.assertRaises(ValueError):apply(self.owned,denied,timezone='UTC',runner=unexpected)
    def test_install_and_rollback_against_disposable_state(self):
        state=self.original
        def runner(argv,**kwargs):
            nonlocal state
            if argv==['crontab','-l']:return SimpleNamespace(returncode=0,stdout=state,stderr='')
            self.assertEqual(argv,['crontab','-']);state=kwargs['input']
            return SimpleNamespace(returncode=0,stdout='',stderr='')
        self.assertTrue(apply(self.owned,lambda:None,timezone='UTC',runner=runner)['own_nightly_enabled'])
        result=apply(self.owned,lambda:None,timezone='UTC',rollback=True,runner=runner)
        self.assertFalse(result['own_nightly_enabled']);self.assertEqual(state,self.original)
    def test_concurrent_change_rejects_before_write(self):
        reads=iter([self.original,self.original+'# concurrent\n'])
        def runner(argv,**kwargs):
            self.assertEqual(argv,['crontab','-l'])
            return SimpleNamespace(returncode=0,stdout=next(reads),stderr='')
        with self.assertRaises(ValueError):apply(self.owned,lambda:None,timezone='UTC',runner=runner)


if __name__=='__main__':unittest.main()
