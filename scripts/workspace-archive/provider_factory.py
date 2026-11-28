"""Construct normal B using the maintained Nightly owner's pinned modules.

Existing logical roots, connection settings, immutable seed index and leases
are supplied by release qualification. No controller/schedule is started here.
"""
from contextlib import contextmanager
import importlib
import importlib.util
import json
from pathlib import Path
import sys

from catalog import Conflict
from host import pinned
from normal_b import NormalB


def create(config, guard):
    folder = Path(config['folder'])
    manifest = json.loads(pinned(config['manifest']))
    for name, sha in manifest['source_sha256'].items():
        if Path(name).name != name:
            raise Conflict('Invalid Nightly source closure member')
        pinned(dict(path=str(folder / name), sha256=sha))
    sys.path.insert(0, str(folder))
    modules = []
    for name in ('vk_nightly_owned_context', 'vk_nightly_selected_factory',
                 'vk_nightly_selected_recovery', 'vk_nightly_owner_controls'):
        if name + '.py' not in manifest['source_sha256']:
            raise Conflict('Nightly module missing from qualified closure')
        module = importlib.import_module(name)
        if Path(module.__file__) != folder / (name + '.py'):
            raise Conflict('Foreign Nightly module was loaded')
        modules.append(module)
    owned, factory, selected, controls = modules
    raw = pinned(config['bridge'])
    bridge = importlib.util.module_from_spec(importlib.util.spec_from_loader('workspace_nightly_bridge', loader=None))
    bridge.__file__ = config['bridge']['path']
    exec(compile(raw, bridge.__file__, 'exec'), bridge.__dict__)
    legacy_manifest = json.loads(pinned(config['legacy_manifest']))
    template = json.loads(pinned(config['template']))
    seed = json.loads(pinned(config['seed_config']))
    plan = json.loads(pinned(config['seed_plan']))
    if (template['source_folder'] != str(folder)
            or template['source_sha256'] != manifest['source_sha256']
            or seed['dependencies'] != template['dependencies']
            or seed['B_controls']['B_root'] != template['B_controls']['B_root']):
        raise Conflict('Qualified Nightly source/provider seed differs from current archive template')

    @contextmanager
    def context():
        guard()
        # Existing ordinary leases are reacquired per finite capture/reopen,
        # never held across the population or across another provider context.
        with bridge.pinned_modules(legacy_manifest) as legacy:
            with owned.open_recovery(config['seed_config']['path'], plan, legacy=legacy,
                                     legacy_sha256=config['legacy_factory_sha256']) as recovery:
                guard()
                class Guarded:
                    original = recovery
                    def __getattr__(self, name):
                        return getattr(recovery, name)
                    def check(self):
                        guard()
                        recovery.check()
                yield Guarded()
                guard()
    return NormalB(context, factory, selected, controls, template, config['work_root'], guard)
