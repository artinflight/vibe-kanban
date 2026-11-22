from datetime import datetime,timezone,timedelta
import copy
import unittest
import remote_dispatch as dispatch

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.job='test-id'
        self.status={'heartbeat':{'account':'vibeworker','administrator':False,'at':datetime.now(timezone.utc).isoformat()},
                     'jobs':[{'id':'dedup-'+self.job,'status':'completed','finished':'observed','exit':0}]}
    def test_exact_native_success(self):
        self.assertEqual(dispatch.queue_completion(self.status,self.job),self.status['jobs'][0])
    def test_missing_or_still_running_is_not_completion(self):
        self.assertIsNone(dispatch.queue_completion(self.status,'different-job'))
        self.status['jobs'][0]['status']='running'
        self.assertIsNone(dispatch.queue_completion(self.status,self.job))
    def test_failed_interrupted_and_nonzero_exit_are_refused(self):
        for key,value in [('status','failed'),('status','interrupted'),('exit',1),('finished',None),('exit',False)]:
            status=copy.deepcopy(self.status);status['jobs'][0][key]=value
            with self.assertRaises(ValueError):dispatch.queue_completion(status,self.job)
    def test_stale_or_admin_worker_is_refused(self):
        for key,value in [('administrator',True),('account','administrator'),('at',(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat())]:
            status=copy.deepcopy(self.status);status['heartbeat'][key]=value
            with self.assertRaises(ValueError):dispatch.queue_completion(status,self.job)

if __name__=='__main__':unittest.main()
