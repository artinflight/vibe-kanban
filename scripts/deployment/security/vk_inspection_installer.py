"""Pinned administrator bootstrap template. Source only; main has no test root.

Builder replaces PAYLOAD with verified embedded bytes. No network, compilation,
repo imports, operational adoption, artifact byte reads, deletion or cutover.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import pwd
import signal
import stat
import subprocess
import sys
import sysconfig
import uuid

PLAN_HEAD = '29af1c33e029bc1fe9ef9467fd51a03eb586105d'
PLAN_SHA = 'a17d7f29b4b47c25811e8bf3d992f09ecd5084812d666dc761fbf4afff8a5357'
ANCHOR = '/mnt/vk-storage/vk-process-inspection-managed-v1'
GRANT = '/etc/sudoers.d/vk-process-inspection-v1'
EVIDENCE = ANCHOR + '/installation.safe.json'
PAYLOAD = None  # builder injects data, not executable imports


def require(value, reason='installation blocked'):
    if not value:
        raise ValueError(reason)


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def unpack(payload):
    require(type(payload) is dict and set(payload) == {'plan', 'sources', 'binaries'})
    raw = base64.b64decode(payload['plan'], validate=True)
    require(checksum(raw) == PLAN_SHA, 'plan pin mismatch')
    plan = json.loads(raw)
    sources = {p: base64.b64decode(data, validate=True) for p, data in payload['sources'].items()}
    require(set(sources) == set(plan['code_artifact_sha256']), 'source set mismatch')
    for path, digest in plan['code_artifact_sha256'].items():
        require(checksum(sources[path]) == digest, 'source pin mismatch')
    binaries = {p: base64.b64decode(data, validate=True) for p, data in payload['binaries'].items()}
    require(set(binaries) == {f['destination'] for f in plan['files'][:2]}, 'binary set mismatch')
    for entry in plan['files'][:2]:
        require(checksum(binaries[entry['destination']]) == entry['sha256'], 'binary pin mismatch')
    require(plan['grant_file_count'] == 1 and len(plan['exact_grants']) == 2)
    return plan, sources, binaries


class Host:
    """FD-relative no-follow operations. Fixture remapping exists only in tests."""
    def __init__(self, fixture=None, root_uid=0, root_gid=0, caller_uid=1000, caller_gid=1000):
        self.fixture = fixture
        self.root_uid, self.root_gid = root_uid, root_gid
        self.caller_uid, self.caller_gid = caller_uid, caller_gid

    def mapped(self, path):
        require(path.startswith('/') and '..' not in Path(path).parts)
        return str(Path(self.fixture) / path.lstrip('/')) if self.fixture else path

    def directory(self, path, immutable=False):
        fd = os.open(self.mapped('/'), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            for part in [None, *Path(path).parts[1:]]:
                if part is not None:
                    next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                    os.close(fd)
                    fd = next_fd
                info = os.fstat(fd)
                if immutable:
                    require(info.st_uid == self.root_uid and info.st_gid == self.root_gid
                            and not info.st_mode & 0o022, 'mutable privileged ancestor')
            return fd
        except BaseException:
            os.close(fd)
            raise

    def metadata(self, path):
        parent = self.directory(str(Path(path).parent))
        try:
            fd = os.open(Path(path).name, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
            try:
                info = os.fstat(fd)
                require(not stat.S_ISLNK(info.st_mode), 'symlink target')
                return info
            finally:
                os.close(fd)
        finally:
            os.close(parent)

    def absent(self, path):
        try:
            self.metadata(path)
        except FileNotFoundError:
            return
        raise ValueError('unexpected existing destination')

    def mkdir(self, path, mode, caller=False):
        parent = self.directory(str(Path(path).parent), immutable=not path.startswith('/mnt/'))
        try:
            os.mkdir(Path(path).name, 0o700, dir_fd=parent)
            fd = os.open(Path(path).name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            try:
                os.fchown(fd, self.caller_uid if caller else self.root_uid,
                          self.caller_gid if caller else self.root_gid)
                os.fchmod(fd, mode)
                os.fsync(fd)
                return os.fstat(fd)
            finally:
                os.close(fd)
        finally:
            os.close(parent)

    def create(self, path, data, mode):
        # Only fixed privileged/evidence destinations chosen by Installer.
        parent = self.directory(str(Path(path).parent), immutable=not path.startswith('/mnt/'))
        try:
            parent_info = os.fstat(parent)
            require(parent_info.st_uid == self.root_uid and not parent_info.st_mode & 0o022)
            fd = os.open(Path(path).name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=parent)
            try:
                os.fchown(fd, self.root_uid, self.root_gid)
                os.fchmod(fd, mode)
                with os.fdopen(os.dup(fd), 'wb') as stream:
                    stream.write(data)
                    stream.flush()
                os.fsync(fd)
                info = os.fstat(fd)
            finally:
                os.close(fd)
            os.fsync(parent)
            return info
        finally:
            os.close(parent)

    def read(self, path, mode=None, link_limit=1):
        parent = self.directory(str(Path(path).parent), immutable=not path.startswith('/mnt/'))
        try:
            fd = os.open(Path(path).name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=parent)
            try:
                info = os.fstat(fd)
                require(stat.S_ISREG(info.st_mode) and 1 <= info.st_nlink <= link_limit
                        and info.st_uid == self.root_uid and info.st_gid == self.root_gid
                        and not info.st_mode & 0o022 and (mode is None or stat.S_IMODE(info.st_mode) == mode))
                with os.fdopen(os.dup(fd), 'rb') as stream:
                    data = stream.read(2 * 1024 * 1024 + 1)
                require(len(data) <= 2 * 1024 * 1024)
                return data, info
            finally:
                os.close(fd)
        finally:
            os.close(parent)

    def publish_grant(self, staged):
        parent = self.directory('/etc/sudoers.d', immutable=True)
        try:
            # Atomic, no-replace publication. Both names are in a protected dir.
            os.link(Path(staged).name, Path(GRANT).name, src_dir_fd=parent, dst_dir_fd=parent,
                    follow_symlinks=False)
            os.unlink(Path(staged).name, dir_fd=parent)
            os.fsync(parent)
        finally:
            os.close(parent)

    def remove_own_grant(self, expected):
        raw, info = self.read(GRANT, 0o440, link_limit=2)
        require((info.st_dev, info.st_ino) == tuple(expected['identity'])
                and checksum(raw) == expected['sha256'], 'refuse changed grant')
        parent = self.directory('/etc/sudoers.d', immutable=True)
        try:
            os.unlink(Path(GRANT).name, dir_fd=parent)
            os.fsync(parent)
        finally:
            os.close(parent)

    def run(self, *argv):
        subprocess.run(argv, check=True, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C'},
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def platform(self, plan):
        require(os.uname().machine == 'x86_64' and sys.flags.isolated and sys.flags.no_site
                and sys.flags.dont_write_bytecode, 'isolated x86_64 OS interpreter required')
        user = pwd.getpwnam('mcp')
        require((user.pw_uid, user.pw_gid) == (1000, 1000))
        paths = [os.path.realpath('/usr/bin/python3'), '/usr/bin/findmnt',
                 '/usr/sbin/visudo', sysconfig.get_path('stdlib')]
        for path in paths:
            fd = self.directory(path if Path(path).is_dir() else str(Path(path).parent), immutable=True)
            os.close(fd)
            info = os.stat(path, follow_symlinks=False)
            require(info.st_uid == 0 and not info.st_mode & 0o022)
        for current, dirs, files in os.walk(sysconfig.get_path('stdlib'), followlinks=False):
            for name in dirs + files:
                info = os.lstat(os.path.join(current, name))
                require(info.st_uid == 0 and (stat.S_ISLNK(info.st_mode) or not info.st_mode & 0o022), 'mutable stdlib input')
                if stat.S_ISLNK(info.st_mode):
                    real = os.path.realpath(os.path.join(current, name))
                    info = os.stat(real)
                    require(info.st_uid == 0 and not info.st_mode & 0o022, 'mutable stdlib link')
                    fd = self.directory(str(Path(real).parent), immutable=True)
                    os.close(fd)
        result = subprocess.check_output(['/usr/bin/findmnt', '-n', '-o', 'UUID', '--mountpoint', '/mnt/vk-storage'],
                                         env={'PATH': '/usr/bin:/bin', 'LANG': 'C'}, stdin=subprocess.DEVNULL)
        require(result.decode().strip() == plan['policy_scopes']['historical']['control_scope']['filesystem_uuid'],
                'SSD not mounted with pinned UUID')
        require(os.stat('/proc/1/ns/pid').st_ino == os.stat('/proc/self/ns/pid').st_ino,
                'not full host PID namespace')
        # Real protected coverage/performance is a separate installed acceptance.
        self.run('/usr/sbin/visudo', '-c')


class Installer:
    def __init__(self, host, payload):
        self.host = host
        self.plan, self.sources, self.binaries = unpack(payload)
        self.state = {'schema': 1, 'approved_plan_head': PLAN_HEAD, 'plan_sha256': PLAN_SHA,
                      'adoption_enabled': False, 'action_authorized': False, 'created': [], 'installed_files': {}}
        self.grant = None
        self.anchor_identity = None

    def historical_metadata(self):
        target = self.plan['policy_scopes']['historical']['target']
        info = self.host.metadata(target['path'])  # O_PATH only, never bytes
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        require({k: getattr(info, 'st_' + k) for k in target['identity']} == target['identity'],
                'historical metadata pin mismatch')

    def preflight(self, installed=False):
        self.host.platform(self.plan)
        self.historical_metadata()
        for entry in self.plan['directories'][:4]:
            try:
                fd = self.host.directory(entry['path'], immutable=True)
                os.close(fd)
            except FileNotFoundError:
                require(entry['path'] != '/etc/sudoers.d')
                fd = self.host.directory(str(Path(entry['path']).parent), immutable=True)
                os.close(fd)
        fd = self.host.directory('/mnt/vk-storage')  # writable parent expressly allowed
        os.close(fd)
        if not installed:
            self.host.absent(ANCHOR)
            for entry in self.plan['files']:
                self.host.absent(entry['destination'])
        return {'preflight_passed': True, 'writes_performed': False, 'adoption_enabled': False}

    def enrolled(self, entry, inode):
        if entry['destination'] in self.binaries:
            return self.binaries[entry['destination']]
        data = self.sources[entry['source']]
        if entry['destination'].endswith('inspection-v1.json'):
            policy = json.loads(data)
            if 'scopes' in policy:
                policy['scopes']['managed-artifacts-v1']['anchor_inode'] = inode
            else:
                policy['control_scope']['anchor_inode'] = inode
            data = (json.dumps(policy, indent=2, sort_keys=True) + '\n').encode()
        return data

    def verify_anchor(self):
        fd = self.host.directory(ANCHOR)
        try:
            info = os.fstat(fd)
            require(info.st_uid == self.host.root_uid and info.st_gid == self.host.root_gid
                    and stat.S_IMODE(info.st_mode) == 0o755)
            require((info.st_dev, info.st_ino) == tuple(self.anchor_identity), 'scope replaced')
        finally:
            os.close(fd)

    def evidence(self, suffix):
        # Preserve progress/failure as distinct O_EXCL root-owned evidence files.
        self.verify_anchor()
        path = EVIDENCE if suffix == 'complete' else ANCHOR + '/installation.' + suffix + '.safe.json'
        self.host.create(path, (json.dumps(self.state, indent=2, sort_keys=True) + '\n').encode(), 0o600)

    def install(self):
        self.preflight()
        try:
            for entry in self.plan['directories']:
                if entry['path'] in [d['path'] for d in self.plan['directories'][:4]]:
                    try:
                        fd = self.host.directory(entry['path'], immutable=True)
                        os.close(fd)
                        continue
                    except FileNotFoundError:
                        pass
                info = self.host.mkdir(entry['path'], int(entry['mode'], 8), caller=entry['owner'] == 'mcp:mcp')
                self.state['created'].append(entry['path'])
                if entry['path'] == ANCHOR:
                    self.anchor_identity = (info.st_dev, info.st_ino)
                    self.state['anchor_identity'] = list(self.anchor_identity)
                    require(info.st_dev == self.host.metadata('/mnt/vk-storage').st_dev)
                    self.evidence('started')
            self.verify_anchor()
            for entry in self.plan['files'][:-1]:
                data = self.enrolled(entry, self.anchor_identity[1])
                self.host.create(entry['destination'], data, int(entry['mode'], 8))
                raw, _ = self.host.read(entry['destination'], int(entry['mode'], 8))
                require(raw == data)
                self.state['installed_files'][entry['destination']] = checksum(data)
            token = uuid.uuid4().hex
            staged = '/etc/sudoers.d/.vk-process-inspection-v1.' + token
            wrapper = staged + '.validation'
            grant_entry = self.plan['files'][-1]
            grant_data = self.sources[grant_entry['source']]
            info = self.host.create(staged, grant_data, 0o440)
            self.grant = {'identity': [info.st_dev, info.st_ino], 'sha256': checksum(grant_data)}
            self.state['grant'] = self.grant
            # Dotted staging/wrapper names are excluded by sudo includedir.
            self.host.create(wrapper, ('@include /etc/sudoers\n@include ' + staged + '\n').encode(), 0o600)
            self.host.run('/usr/sbin/visudo', '-cf', staged)
            self.host.run('/usr/sbin/visudo', '-c')
            self.host.run('/usr/sbin/visudo', '-cf', wrapper)  # complete prospective policy
            self.verify_anchor()
            self.historical_metadata()
            self.evidence('validated')  # durable exact grant provenance BEFORE publication
            self.host.publish_grant(staged)  # atomic no-overwrite; privilege enabled LAST
            self.host.run('/usr/sbin/visudo', '-c')
            self.state['installed_files'][GRANT] = checksum(grant_data)
            self.state['phase'] = 'installed-awaiting-read-only-acceptance; adoption disabled'
            self.verify_installed()
            self.evidence('complete')
            return self.state
        except BaseException as error:
            self.state['phase'] = 'failed; adoption disabled'
            self.state['error_type'] = type(error).__name__
            if self.grant:
                try:
                    self.host.remove_own_grant(self.grant)
                    self.state['new_grant_removed'] = True
                except FileNotFoundError:
                    self.state['new_grant_removed'] = True
                except Exception as cleanup:
                    self.state['cleanup_blocked'] = type(cleanup).__name__
            if self.anchor_identity:
                try:
                    self.evidence('failed')
                except Exception:
                    pass  # stdout below retains evidence even if anchor is replaced
            print(json.dumps(self.state, sort_keys=True))
            raise

    def verify_installed(self):
        if self.anchor_identity is None:
            raw, _ = self.host.read(EVIDENCE, 0o600)
            prior = json.loads(raw)
            require(prior['approved_plan_head'] == PLAN_HEAD and prior['plan_sha256'] == PLAN_SHA
                    and prior['adoption_enabled'] is False)
            self.anchor_identity = prior['anchor_identity']
            self.grant = prior['grant']
        self.verify_anchor()
        for entry in self.plan['files']:
            raw, _ = self.host.read(entry['destination'], int(entry['mode'], 8))
            require(raw == self.enrolled(entry, self.anchor_identity[1]), 'installed pin mismatch')
        self.host.platform(self.plan)
        self.historical_metadata()
        return {'installed_metadata_verified': True, 'root_consumer_acceptance_performed': False,
                'adoption_enabled': False, 'action_authorized': False}

    def rollback(self):
        raw = None
        for path in (EVIDENCE, ANCHOR + '/installation.failed.safe.json',
                     ANCHOR + '/installation.validated.safe.json'):
            try:
                raw, _ = self.host.read(path, 0o600)
                break
            except FileNotFoundError:
                pass
        require(raw is not None, 'no authenticated grant provenance; administrator review required')
        prior = json.loads(raw)
        require(prior['approved_plan_head'] == PLAN_HEAD and prior['plan_sha256'] == PLAN_SHA)
        self.anchor_identity = prior['anchor_identity']
        self.verify_anchor()
        try:
            self.host.remove_own_grant(prior['grant'])  # ONLY this exact include
        except FileNotFoundError:
            pass  # already withdrawn; preserve evidence and all remaining files
        self.host.run('/usr/sbin/visudo', '-c')
        return {'grant_removed': GRANT, 'adoption_enabled': False, 'artifacts_and_evidence_preserved': True}


def main():
    parser = argparse.ArgumentParser(description='Pinned two-profile administrator installation; no adoption')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--install', action='store_true')
    mode.add_argument('--verify-installed', action='store_true')
    mode.add_argument('--rollback', action='store_true')
    parser.add_argument('--approved-plan')
    parser.add_argument('--drained', action='store_true')
    args = parser.parse_args()
    try:
        require(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode)
        if not args.dry_run:
            require(os.geteuid() == 0, 'administrator authentication required')
        if args.install or args.rollback:
            require(args.approved_plan == PLAN_HEAD, 'explicit exact reviewed plan identifier required')
        if args.rollback:
            require(args.drained, 'administrator must first disable/disarm/drain both adapters')
        def interrupted(_signal, _frame):
            raise RuntimeError('installation interrupted; no adoption')
        if args.install:
            signal.signal(signal.SIGTERM, interrupted)
            signal.signal(signal.SIGHUP, interrupted)
        installer = Installer(Host(), PAYLOAD)
        result = installer.preflight() if args.dry_run else installer.install() if args.install else \
                 installer.rollback() if args.rollback else installer.verify_installed()
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps({'passed': False, 'reason': str(error), 'adoption_enabled': False}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
