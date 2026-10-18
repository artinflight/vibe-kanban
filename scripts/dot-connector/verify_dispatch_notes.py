"""Offline full private-adapter note dispatch checks; no live calls or agents."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import Mock, patch


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adapter',type=Path,required=True)
    p.add_argument('--sha256',required=True)
    p.add_argument('--dependencies',type=Path,required=True)
    a=p.parse_args()
    if hashlib.sha256(a.adapter.read_bytes()).hexdigest()!=a.sha256:raise SystemExit('Candidate changed')
    sys.path[:0]=[str(a.adapter.parent),str(a.dependencies),str(Path(__file__).parent)]
    spec=importlib.util.spec_from_file_location('adapter',a.adapter)
    adapter=importlib.util.module_from_spec(spec);sys.modules['adapter']=adapter;spec.loader.exec_module(adapter)
    import dispatch_notes
    from test_dispatch_notes import DispatchNoteTests
    from workspace_issue_context import IssueContextError
    for kind,handler in [('start_workspace','local_start'),('run_session_prompt','local_followup')]:
        test=DispatchNoteTests();test.setUp()
        try:
            data=test.result if kind=='start_workspace' else {'isError':False,'content':[{'type':'text','text':json.dumps({
                'session_id':test.session,'execution_id':test.execution,
                'execution':{'id':test.execution,'session_id':test.session}})}]}
            args=test.args if kind=='start_workspace' else {'session_id':test.session,'prompt':'SENSITIVE_PRIVATE_PROMPT_NEVER_COPY'}
            upstream=Mock();facade=adapter.Adapter(upstream)
            request={'jsonrpc':'2.0','id':7,'method':'tools/call','params':{'name':kind,'arguments':args}}
            with patch.object(adapter,handler,return_value=data) as invoke,patch.object(dispatch_notes,'Runtime',test.factory),\
                 patch.object(adapter.urllib.request,'build_opener',side_effect=AssertionError('No network in fixture')):
                result=facade.handle(request)['result']
                note=test.receipt(result);assert note['state']=='noted'
                assert facade.handle(request)['result']==result
                assert test.counts()==(1,0,1)
                assert invoke.call_count==2
            # Original errors are exact; dispatch failure never reaches the note hook.
            error=IssueContextError('workspace_issue_ids_missing').tool_result()
            with patch.object(adapter,handler,return_value=error),patch.object(dispatch_notes,'Runtime') as runtime:
                assert facade.handle(request)['result'] is error;runtime.assert_not_called()
            with patch.object(adapter,handler,side_effect=TimeoutError('Unknown dispatch')),patch.object(dispatch_notes,'Runtime') as runtime:
                try:facade.handle(request);raise AssertionError('Unknown dispatch swallowed')
                except TimeoutError:pass
                runtime.assert_not_called()
            upstream.request.assert_not_called()
        finally:test.tearDown()
    print(json.dumps({'fullPrivateAdapterMockDispatch':True,'newWorkspaceAndExistingSession':True,
        'acceptedExecutionNoteAndRetryIdempotence':True,'originalPR271ErrorResultExact':True,
        'unknownDispatchNoNoteHook':True,'realNetworkOrStartPosts':0,'realAgentsCreated':0,'adapterSha256':a.sha256}))


if __name__=='__main__':main()
