"""Pinned native B control-plane transport, independent per-index leases.

Control transactions do not hold the body-writer lane forever. Each native
index has its own kernel lease and SQLite locking; capture still holds the
existing global body-writer lease. A tracker cannot collide with a map writer.
"""
import ast
import base64
import hashlib
import json
from pathlib import Path
import select
import subprocess

from vk_nightly_b_controls import Client,send,recv
from vk_nightly_desktop_objects import NATIVE,validate,ssh_command
from vk_nightly_objects import read_control
from vk_nightly_transport_diagnostics import Diagnostics,finish


def validate_control(config,folder):
    folder=Path(folder)
    if type(config['maximum_index_bytes']) is not int or config['maximum_index_bytes']<65536:
        raise ValueError('finite native B index budget required')
    source=(folder/'vk_nightly_b_controls.py').read_text()
    if hashlib.sha256(source.encode()).hexdigest()!=config['control_module_sha256']:
        raise ValueError('native B control module pin changed')
    portable={}
    modules=('vk_nightly_control_format','vk_nightly_file_version','vk_nightly_checkpoints',
             'vk_nightly_qualification','vk_nightly_current_map')
    descriptor=('vk_typed_recovery','vk_nightly_recovery_descriptor')
    declared=set(config['portable_source_sha256'])
    if declared-set(modules)-set(descriptor) or bool(declared&set(descriptor)) and not set(descriptor)<=declared:
        raise ValueError('exact fixed portable descriptor source closure required')
    if set(descriptor)<=declared:modules+=descriptor
    for module in modules:
        code=(folder/(module+'.py')).read_text()
        if hashlib.sha256(code.encode()).hexdigest()!=config['portable_source_sha256'][module]:
            raise ValueError('native B portable source pin changed: '+module)
        portable[module]=code
    return source,portable


class DesktopControls:
    def __init__(self,config,*,guard):self.config=config;self.guard=guard;self.process=None
    def __enter__(self):
        self.guard();config=self.config
        folder=Path(__file__).parent
        objects=(folder/'vk_nightly_objects.py').read_text();validate(config,objects)
        source,portable=validate_control(config,folder)
        mm=Path(config['MM_source']).read_text()
        if hashlib.sha256(mm.encode()).hexdigest()!=config['MM_sha256']:raise ValueError('MM control source changed')
        tree=ast.parse(NATIVE)
        receiver=next(n for n in tree.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
            and isinstance(n.value.func,ast.Attribute) and isinstance(n.value.func.value,ast.Name)
            and n.value.func.value.id=='objects' and n.value.func.attr=='receive')
        setup='\n'.join(NATIVE.splitlines()[:receiver.lineno-1])+'\n'
        program=('CONFIG='+repr(config)+'\nMM_SOURCE='+repr(mm)+'\nOBJECT_SOURCE='+repr(objects)+
            '\nCONTROL_SOURCE='+repr(source)+'\nPORTABLE='+repr(portable)+'\n'+setup+
            "assert hashlib.sha256(CONTROL_SOURCE.encode()).hexdigest()==CONFIG['control_module_sha256']\n"+
            "for name,code in PORTABLE.items():\n assert hashlib.sha256(code.encode()).hexdigest()==CONFIG['portable_source_sha256'][name]\n module=types.ModuleType(name);sys.modules[name]=module;exec(code,module.__dict__)\n"+
            "controls=types.ModuleType('native_controls');exec(CONTROL_SOURCE,controls.__dict__)\n"+
            "controls.serve(job,sys.stdin.buffer,sys.stdout.buffer,objects=objects,guard=progress_guard,maximum_index_bytes=CONFIG['maximum_index_bytes'])\n"+
            'final_guard(0)\n')
        self.process=subprocess.Popen(ssh_command(config,
            'python -B -u -c "import sys,base64;exec(base64.b64decode(sys.stdin.buffer.readline()))"'),
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.diagnostics=Diagnostics(self.process.stderr)
        try:
            p=self.process;p.stdin.write(base64.b64encode(program.encode())+b'\n');p.stdin.flush()
            if not select.select([p.stdout],[],[],90)[0]:raise TimeoutError('native B control readiness')
            self.ready=read_control(p.stdout)
            if not self.ready or self.ready.get('status')!='ready':raise ValueError('native B control readiness unavailable')
            self.client=Client(p.stdout,p.stdin,guard=self.guard);return self
        except BaseException:
            self.__exit__(*__import__('sys').exc_info());raise
    def __exit__(self,kind,value,tb):
        p=self.process
        if p is None:return
        try:
            if kind is None:
                send(p.stdin,dict(op='bye'))
                if recv(p.stdout)!={'closed':True}:raise ValueError('native B control close differs')
        except BaseException as error:
            finish(p,original=error,diagnostics=getattr(self,'diagnostics',None));raise
        finish(p,original=value,diagnostics=getattr(self,'diagnostics',None))
