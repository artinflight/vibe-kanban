"""Fixture-only tests against a prepared exact-live Store/adapter overlay."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest


def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--store-sha',required=True)
    p.add_argument('--adapter-sha',required=True)
    p.add_argument('--dependencies',type=Path,required=True)
    a=p.parse_args()
    for name,digest in [('sidechat.py',a.store_sha),('adapter.py',a.adapter_sha)]:
        if hashlib.sha256((a.candidate/name).read_bytes()).hexdigest()!=digest:
            raise SystemExit('Candidate changed; verify again before testing')
    sys.path[:0]=[str(a.candidate),str(a.dependencies),str(Path(__file__).parent),
                  str(Path(__file__).resolve().parents[1]/'dot-sidechat')]
    load('sidechat',a.candidate/'sidechat.py')
    import test_dispatch_caller
    suite=unittest.defaultTestLoader.loadTestsFromModule(test_dispatch_caller)
    result=unittest.TextTestRunner(verbosity=0).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
    import verify_dispatch_notes
    sys.argv=[sys.argv[0],'--adapter',str(a.candidate/'adapter.py'),'--sha256',a.adapter_sha,
              '--dependencies',str(a.dependencies)]
    verify_dispatch_notes.main()
