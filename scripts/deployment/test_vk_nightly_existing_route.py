import copy
import unittest
from vk_nightly_desktop_objects import ssh_command


class ExistingRouteTests(unittest.TestCase):
    def setUp(self):
        self.route=dict(format='vk-nightly-existing-Desktop-LAN-route-v1',hostname='10.0.0.109',
            host_key_alias='100.70.23.123',identity_probe_sha256='a'*64)

    def test_default_still_uses_existing_Desktop_with_strict_keys_and_no_key_updates(self):
        command=ssh_command({},'fixed command')
        self.assertEqual(command[-2:],['desktop','fixed command'])
        self.assertIn('StrictHostKeyChecking=yes',command);self.assertIn('UpdateHostKeys=no',command)
        self.assertFalse(any(c.startswith('Hostname=') for c in command))

    def test_explicit_verified_LAN_reuses_same_Desktop_alias_identity_and_command(self):
        command=ssh_command({'verified_SSH_route':self.route},'fixed command')
        self.assertIn('Hostname=10.0.0.109',command)
        self.assertIn('HostKeyAlias=100.70.23.123',command)
        self.assertEqual(command[-2:],['desktop','fixed command'])
        self.assertFalse(any('StrictHostKeyChecking=no' in c or 'known_hosts=/dev/null' in c for c in command))

    def test_unknown_key_route_shell_injection_public_or_missing_proof_refuses(self):
        bad=[]
        for key,value in [('hostname','10.0.0.109;touch /tmp/no'),('hostname','8.8.8.8'),
                          ('hostname','127.0.0.1'),('hostname','169.254.2.1'),('hostname','0.0.0.0'),
                          ('host_key_alias','other-server'),('identity_probe_sha256','unverified')]:
            route=copy.deepcopy(self.route);route[key]=value;bad.append(route)
        route=copy.deepcopy(self.route);route['command']='other command';bad.append(route)
        for route in bad:
            with self.subTest(route=route),self.assertRaises(ValueError):ssh_command({'verified_SSH_route':route},'fixed command')


if __name__=='__main__':unittest.main()
