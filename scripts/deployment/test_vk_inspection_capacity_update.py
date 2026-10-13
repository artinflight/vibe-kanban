"""Unprivileged disposable replacement models; no live files/sudo/root actions."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import test_vk_inspection_installer as fixtures
install,load=fixtures.install,fixtures.load
update=load('vk_inspection_capacity_update')
packager=load('build_capacity_update')


class UpdateTests(fixtures.InstallerTests):
    # Inherit setup only, not duplicate installer tests discovered here.
    def setUp(self):
        super().setUp()
        self.initial=self.actor.install()
        namespace={'__name__':'unprivileged_update_fixture'}
        exec(compile(packager.build(),'<pinned package fixture>','exec'),namespace)
        _,files=update.load(namespace['PAYLOAD'])
        self.updater=update.Update(self.host,files)

    def retained(self):
        excluded=set(update.PINS)
        return {entry['destination']:self.path(entry['destination']).read_bytes()
                for entry in self.actor.plan['files'] if entry['destination'] not in excluded}

    def test_dry_run_preserves_exact_installed_ids_and_bytes(self):
        before={str(p):p.stat().st_ino for p in self.base.rglob('*')}
        self.updater.preflight()
        self.assertEqual(before,{str(p):p.stat().st_ino for p in self.base.rglob('*')})

    def test_exact_apply_preserves_anchor_policy_grant_binary_identities(self):
        before=self.retained()
        identities={p:self.path(p).stat().st_ino for p in before}
        anchor=self.path(update.ANCHOR).stat().st_ino
        result=self.updater.apply()
        self.assertEqual(self.retained(),before)
        self.assertEqual({p:self.path(p).stat().st_ino for p in before},identities)
        self.assertEqual(anchor,self.path(update.ANCHOR).stat().st_ino)
        self.assertFalse(result['operational_adoption_changed'])
        for path,pins in update.PINS.items():
            self.assertEqual(update.digest(self.path(path).read_bytes()),pins[1])
        self.assertTrue(self.path(update.UPDATE_EVIDENCE).exists())

    def test_unexpected_code_or_policy_refuses_overwrite(self):
        path=next(iter(update.PINS))
        self.path(path).write_bytes(b'unexpected administrator code')
        with self.assertRaises(ValueError):self.updater.apply()
        self.assertEqual(self.path(path).read_bytes(),b'unexpected administrator code')

    def test_partial_failure_after_rename_restores_both_original_files(self):
        original=self.updater.replace
        calls=0
        def interrupted(path,data,expected):
            nonlocal calls
            calls+=1
            original(path,data,expected)
            if calls==1:raise OSError('fixture fsync failure after rename')
        with patch.object(self.updater,'replace',side_effect=interrupted),self.assertRaises(OSError):
            self.updater.apply()
        for path,pins in update.PINS.items():
            self.assertEqual(update.digest(self.path(path).read_bytes()),pins[0])

    def test_mixed_version_crash_rollback_is_bounded_to_two_code_files(self):
        before=self.retained()
        path=next(iter(update.PINS))
        self.updater.replace(path,self.updater.files[path][1],update.PINS[path][0])
        self.updater.rollback()
        self.assertEqual(before,self.retained())
        for path,pins in update.PINS.items():
            self.assertEqual(update.digest(self.path(path).read_bytes()),pins[0])


# Do not inherit parent TestCase test methods: retain its shared fixture lifecycle.
for name in list(dir(UpdateTests)):
    if name.startswith('test_') and name not in UpdateTests.__dict__:
        setattr(UpdateTests,name,None)


if __name__=='__main__': unittest.main()
