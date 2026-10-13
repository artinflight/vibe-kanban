#!/usr/bin/env python3
"""Opt-in turn preservation and a read-only, fail-closed cutover check.

No configuration means no publication permission. See VK_TURN_GIT_PRESERVATION.md.
Subprocess output is never included in errors (Git/scanners may print secrets).
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import time

VERSION = 2
DENIED = re.compile(
    r"(^|/)(\.env(?:\..*)?|\.git|\.ssh|credentials?|secrets?|runtime|"
    r"dev_assets|attachments?|uploads?|customer[s_-]?|client[s_-]?|"
    r"invoices?|financial|account[s_-]?|private|transcripts?|rollouts?|node_modules|target)(/|$)|"
    r"(^|/)[^/]*\.private(?:\.|$)|"
    r"\.(pem|key|p12|pfx|sqlite(?:3)?|db|zip|pdf|xlsx?|csv|exe|dll|so)$", re.I
)
IDENT = re.compile(r"^[A-Za-z0-9_-]+$")
CHECKPOINT_DEADLINE = None


class Blocked(Exception):
    pass


def require(ok, reason):
    if not ok:
        raise Blocked(reason)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def run(args, cwd=None, env=None, data=None):
    budget = 60 if CHECKPOINT_DEADLINE is None else min(60, CHECKPOINT_DEADLINE - time.monotonic())
    require(budget > 0, 'checkpoint time budget exhausted; retry remains pending')
    try:
        result = subprocess.run(args, cwd=cwd, env=env, input=data,
                                capture_output=True, timeout=budget)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked(f"{Path(args[0]).name} unavailable or timed out") from None
    require(result.returncode == 0, f"{Path(args[0]).name} {args[1]} failed")
    return result.stdout


def sanitized_env():
    # Git subprocesses and the scanner must see the same original objects.
    clean = {k: v for k, v in os.environ.items()
             if not k.startswith(('GIT_', 'GITLEAKS_'))}
    clean.update(GIT_TERMINAL_PROMPT='0', GIT_NO_REPLACE_OBJECTS='1', GIT_GRAFT_FILE='/dev/null',
                 GIT_LITERAL_PATHSPECS='1')
    return clean


def git(repo, *args, env=None, data=None):
    clean = sanitized_env()
    if env:
        clean.update(env)
    try:
        return run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
                    '-c', 'diff.external=', *args], repo, clean, data)
    except Blocked:
        raise Blocked(f'git {args[0]} failed or timed out') from None


def line(repo, *args):
    return git(repo, *args).decode().strip()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        os.chmod(tmp.name, 0o600)
        tmp.write(json.dumps(value, sort_keys=True).encode())
        tmp.flush()
        os.fsync(tmp.fileno())
    os.replace(tmp.name, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        raise Blocked('missing or malformed preservation state') from None


def file_state(path, algorithm):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    require(stat.S_ISREG(info.st_mode), 'symlink, submodule or special file requires review')
    require(info.st_size <= 5 * 1024 * 1024, 'large file requires separate review')
    content = path.read_bytes()
    blob = hashlib.new(algorithm, b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
    return [hashlib.sha256(content).hexdigest(),
            '100755' if info.st_mode & 0o111 else '100644', blob]


def snapshot(repo):
    require(Path(line(repo, 'rev-parse', '--show-toplevel')).resolve() == repo,
            'repository root mismatch')
    require(line(repo, 'rev-parse', '--is-shallow-repository') == 'false',
            'shallow history cannot prove exact commit coverage')
    require(not git(repo, 'ls-files', '-u', '-z'), 'unresolved index conflicts')
    flags = git(repo, 'ls-files', '-v', '-z').split(b'\0')
    require(all(not x or x[:1] == b'H' for x in flags),
            'hidden index flags or sparse checkout requires review')
    tracked = git(repo, 'ls-files', '--cached', '-z') + git(repo, 'ls-tree', '-r', '--name-only', '-z', 'HEAD')
    untracked = git(repo, 'ls-files', '--others', '--exclude-standard', '-z')
    paths = sorted(set(os.fsdecode(p) for p in (tracked + untracked).split(b'\0') if p))
    algorithm = line(repo, 'rev-parse', '--show-object-format')
    require(algorithm in ['sha1', 'sha256'], 'unsupported repository object format')
    files = {p: file_state(repo / p, algorithm) for p in paths}
    ignored = {}
    for raw in git(repo, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z').split(b'\0'):
        if raw:
            p = os.fsdecode(raw)
            s = (repo / p).lstat()
            ignored[p] = [s.st_size, s.st_mtime_ns, s.st_mode]
    index = Path(line(repo, 'rev-parse', '--path-format=absolute', '--git-path', 'index'))
    return dict(head=line(repo, 'rev-parse', 'HEAD'),
                branch=line(repo, 'symbolic-ref', '--short', 'HEAD'),
                files=files, ignored=ignored,
                status=git(repo, 'status', '--porcelain=v1', '-z', '--no-renames',
                           '--untracked-files=all').hex(),
                index=hashlib.sha256(index.read_bytes()).hexdigest() if index.exists() else None)


def require_tree_bytes(repo, snap):
    # Clean porcelain is insufficient: clean filters, CRLF conversion and disabled
    # filemode can hide worktree bytes/modes that differ from the original tree.
    tree = {}
    for raw in git(repo, 'ls-tree', '-r', '-z', snap['head']).split(b'\0'):
        if raw:
            meta, path = raw.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            require(kind == 'blob' and mode in ['100644', '100755'],
                    'non-source tree requires review')
            tree[os.fsdecode(path)] = [mode, oid]
    actual = {p: value[1:] for p, value in snap['files'].items() if value is not None}
    require(actual == tree, 'working bytes or modes differ from preserved original tree')


def eligible(paths, policy):
    excluded = [p for p in paths if DENIED.search(p) or
                p not in policy['allowed']]
    require(not excluded, 'excluded or unreviewed changed paths: ' + ', '.join(excluded))


def workflows(repo, commit):
    # Policy review covers automation dependencies, not merely workflow filenames.
    return hashlib.sha256(git(repo, 'ls-tree', '-r', commit, '--', '.github')).hexdigest()


@contextlib.contextmanager
def repo_lock(repo):
    import fcntl
    common = Path(line(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    with (common / 'vk-preservation.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Blocked('another preservation writer holds repository lock') from None
        yield


class Engine:
    def __init__(self, config, gh='gh'):
        self.config = config
        self.gh = gh
        self.root = Path(config['state_root']).resolve()
        require(self.root.is_dir(), 'state root must already exist on approved storage')
        mount = Path(config['storage_mount']).resolve()
        require(mount.is_mount() and self.root.is_relative_to(mount) and
                self.root.stat().st_dev == mount.stat().st_dev,
                'approved receipt storage is not mounted or filesystem identity differs')

    def state_path(self, request):
        require(IDENT.fullmatch(request['workspace']) and IDENT.fullmatch(request['turn']),
                'invalid workspace or turn identifier')
        return self.root / request['workspace'] / (request['turn'] + '.json')

    def policy(self, item):
        policy = self.config['repositories'].get(item['id'])
        require(policy is not None, 'repository has no approved publication policy')
        require(isinstance(policy.get('allowed'), list) and bool(policy['allowed']) and
                all(isinstance(p, str) and p and not p.startswith('/') and
                    '..' not in p.split('/') and not any(c in p for c in '*?[]\\')
                    for p in policy['allowed']),
                'publication requires an explicit reviewed file allowlist; globs are unsupported')
        repo = Path(item['path']).resolve()
        common = line(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir')
        require(Path(common).resolve() == Path(policy['common_dir']).resolve(),
                'repository identity differs from approved policy')
        require(not self.root.is_relative_to(repo), 'receipt storage must be outside source')
        return repo, policy

    def observe(self, record, item, head=None):
        repo = Path(item['path']).resolve()
        obligations = record['obligations']
        obligation = obligations.setdefault(item['id'], dict(path=str(repo), commits=[]))
        require(obligation['path'] == str(repo), 'original repository identity changed')
        # Persist HEAD before policy/snapshot admission: a later failure cannot forget it.
        try:
            if head is None:
                head = line(repo, 'rev-parse', '--verify', 'HEAD^{commit}')
        except Blocked:
            obligation['unverifiable'] = True
            raise
        obligation['commits'] = sorted(set([*obligation['commits'], head,
                                            *item.get('required_commits', [])]))
        return obligation['commits']

    def require_obligations(self, record):
        require(record.get('version') == VERSION, 'unsupported preservation contract')
        obligations = record.get('obligations')
        require(isinstance(obligations, dict) and bool(obligations),
                'missing original preservation obligations')
        entries = {e['id']: e for e in record['repositories']}
        require(set(entries) == set(obligations), 'affected original repository inventory omitted')
        for ident, obligation in obligations.items():
            entry = entries[ident]
            require(all(isinstance(c, str) and re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', c)
                        for c in obligation['commits']), 'required original commit must be a full ID')
            require(not obligation.get('unverifiable'), 'original history observation was unverifiable')
            require(obligation['path'] == entry['path'] and obligation['commits'] and
                    set(obligation['commits']) == set(entry.get('original_commits', [])) and
                    entry['before']['head'] in obligation['commits'] and
                    set(entry.get('required_commits', [])).issubset(obligation['commits']) and
                    (not entry.get('receipt') or entry['receipt']['commit'] in obligation['commits']),
                    'original preservation obligations are missing or inconsistent')

    def begin(self, request):
        path = self.state_path(request)
        require(not path.exists(), 'turn already registered; do not overwrite prior evidence')
        previous = None
        if (path.parent / 'latest.json').exists():
            latest = read_json(path.parent / 'latest.json')
            previous = read_json(path.parent / (latest['turn'] + '.json'))
            require(previous.get('version') == VERSION and isinstance(previous.get('obligations'), dict),
                    'earlier turn has unsupported provenance; originals need explicit reconciliation')
        record = dict(version=VERSION, workspace=request['workspace'], turn=request['turn'],
                      state='pending', reason='turn has not reached verified preservation',
                      config=digest(self.config), repositories=[],
                      obligations=previous['obligations'] if previous else {})
        atomic_json(path.parent / 'latest.json', dict(turn=request['turn']))
        atomic_json(path, record)
        try:
            require(bool(request['repositories']), 'empty affected repository inventory')
            require(len({i['id'] for i in request['repositories']}) == len(request['repositories']),
                    'duplicate repository inventory')
            # Observe every affected original before admitting any repository. Continue
            # capture after an error so a failed multi-repository admission loses no heads.
            errors = []
            for item in request['repositories']:
                try:
                    self.observe(record, item)
                except Blocked as error:
                    errors.append(str(error))
                finally:
                    atomic_json(path, record)
            require(not errors, errors[0] if errors else '')
            for item in request['repositories']:
                repo, _ = self.policy(item)
                with repo_lock(repo):
                    before = snapshot(repo)
                    originals = self.observe(record, item)
                    require(before['head'] in originals, 'head changed during admission')
                    record['repositories'].append(dict(id=item['id'], path=str(repo),
                                                       original_commits=list(originals), before=before,
                                                       required_commits=item.get('required_commits', []),
                                                       required_files=item.get('required_files', [])))
                    atomic_json(path, record)
            self.require_obligations(record)
        except (Blocked, OSError, KeyError, ValueError) as error:
            record.update(state='blocked', reason=str(error) if isinstance(error, Blocked)
                          else 'preservation IO or contract failure')
            atomic_json(path, record)
        return record

    def remote(self, repo, policy):
        remote = policy['remote']
        require(IDENT.fullmatch(remote) is not None, 'invalid remote name')
        require(line(repo, 'remote', 'get-url', remote) == policy['url'] and
                line(repo, 'remote', 'get-url', '--all', '--push', remote) == policy['url'],
                'missing, ambiguous or changed remote destination')
        repository = policy['repository']
        require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository),
                'invalid GitHub repository')
        require(policy['url'] in [f'git@github.com:{repository}.git',
                                 f'https://github.com/{repository}.git'],
                'publication requires a reviewed GitHub destination')
        return remote

    def witness(self, repo, remote, branch, expected):
        raw = git(repo, 'ls-remote', '--exit-code', remote, 'refs/heads/' + branch)
        require(raw.decode().split() == [expected, 'refs/heads/' + branch],
                'remote branch does not equal preserved commit')
        with tempfile.TemporaryDirectory(dir=self.root, prefix='verify-') as folder:
            git(folder, 'init', '--bare', '--quiet', folder)
            # Independent object store: no local remote-tracking refs or objects as evidence.
            git(folder, 'fetch', '--quiet', '--no-tags', '--no-write-fetch-head',
                remote, '--recurse-submodules=no',
                f'refs/heads/{branch}:refs/heads/witness')
            require(line(folder, 'rev-parse', 'refs/heads/witness') == expected,
                    'fresh remote fetch differs from preserved commit')
            tree = line(folder, 'rev-parse', expected + '^{tree}')
            require(tree == line(repo, 'rev-parse', expected + '^{tree}'),
                    'fresh remote tree differs from preserved tree')
            git(folder, 'fsck', '--no-dangling')
        return dict(commit=expected, tree=tree, ref='refs/heads/' + branch,
                    observed_at=time.time(), proof='exact-history-fresh-fetch')

    def prs(self, policy, branch):
        return json.loads(run([self.gh, 'pr', 'list', '--repo', policy['repository'],
                               '--head', branch, '--state', 'open', '--json',
                               'number,url,headRefName,headRefOid,baseRefName,isDraft']).decode())

    def verify_pr(self, policy, branch, head, number):
        pr = json.loads(run([self.gh, 'pr', 'view', str(number), '--repo', policy['repository'],
                             '--json', 'number,url,headRefName,headRefOid,baseRefName,state,isDraft,headRepository,headRepositoryOwner']).decode())
        require(pr['headRepository']['name'] == policy['repository'].split('/')[1] and
                pr['headRepositoryOwner']['login'].lower() == policy['repository'].split('/')[0].lower(),
                'PR head belongs to a different repository')
        require(pr['state'] == 'OPEN' and pr['headRefName'] == branch and
                pr['headRefOid'] == head and pr['baseRefName'] == policy['base_branch'],
                'PR does not cover the verified branch commit and base')
        return pr

    def outgoing_objects(self, repo, policy, head):
        base = policy['base_commit']
        git(repo, 'merge-base', '--is-ancestor', base, head)
        seen = set()
        for commit in line(repo, 'rev-list', base + '..' + head).splitlines():
            # Raw original commit messages are published too; scan them without log formatting.
            yield git(repo, 'cat-file', 'commit', commit)
            paths = [os.fsdecode(p) for p in git(repo, 'diff-tree', '--root', '-m',
                     '--no-commit-id', '--name-only', '-r', '-z', commit).split(b'\0') if p]
            eligible(paths, policy)
            if not paths:
                continue
            for raw in git(repo, 'ls-tree', '-r', '-z', commit, '--', *paths).split(b'\0'):
                if not raw:
                    continue
                meta, _ = raw.split(b'\t', 1)
                mode, kind, oid = meta.decode().split()
                require(mode in ['100644', '100755'] and kind == 'blob',
                        'outgoing symlink or submodule history requires review')
                require(int(line(repo, 'cat-file', '-s', oid)) <= 5 * 1024 * 1024,
                        'large outgoing blob requires review')
                if oid in seen:
                    continue
                seen.add(oid)
                content = git(repo, 'cat-file', 'blob', oid)
                require(b'\0' not in content, 'binary outgoing history requires review')
                try:
                    content.decode('utf-8')
                except UnicodeDecodeError:
                    raise Blocked('non-text outgoing history requires review') from None
                yield content

    def scan(self, repo, policy, head):
        scanner = Path(self.config['scanner'])
        require(scanner.is_absolute() and
                hashlib.sha256(scanner.read_bytes()).hexdigest() == self.config['scanner_sha256'],
                'approved secret scanner missing or changed')
        # No rendered diffs, filenames, local attributes/drivers, replacement refs or
        # repository scanner config participate. stdin scans complete original blobs,
        # including intermediate revisions and bytes inherited from an unchanged base.
        with tempfile.NamedTemporaryFile(dir=self.root, suffix='.toml') as config:
            config.write(b'[extend]\nuseDefault = true\n')
            config.flush()
            for content in self.outgoing_objects(repo, policy, head):
                run([str(scanner), 'stdin', '--config', config.name,
                     '--no-banner', '--redact', '--ignore-gitleaks-allow',
                     '--gitleaks-ignore-path', '/dev/null'],
                    cwd=self.root, env=sanitized_env(), data=content)

    def commit(self, repo, policy, snap, turn, remember):
        index = Path(line(repo, 'rev-parse', '--path-format=absolute', '--git-path', 'index'))
        lock = index.with_name(index.name + '.lock')
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise Blocked('Git index is locked by another writer') from None
        # Keep a kernel reference through pathname replacement and cleanup so
        # the owned inode cannot be freed/reused by a later writer.
        lock_lease = os.dup(fd)
        owned_lock = os.fstat(lock_lease)
        try:
            with os.fdopen(fd, 'wb') as output, tempfile.TemporaryDirectory(dir=self.root) as folder:
                env = {'GIT_INDEX_FILE': str(Path(folder) / 'index')}
                git(repo, 'read-tree', snap['head'], env=env)
                for p, value in snap['files'].items():
                    if value is None:
                        git(repo, 'update-index', '--force-remove', '--', p, env=env)
                    else:
                        content = (repo / p).read_bytes()
                        require(hashlib.sha256(content).hexdigest() == value[0],
                                'concurrent writer changed file bytes during snapshot')
                        require(b'\0' not in content, 'binary source requires separate review')
                        try:
                            content.decode('utf-8')
                        except UnicodeDecodeError:
                            raise Blocked('non-text source requires separate review') from None
                        blob = git(repo, 'hash-object', '-w', '--no-filters', '--stdin',
                                   data=content).decode().strip()
                        git(repo, 'update-index', '--add', '--cacheinfo', value[1], blob, p, env=env)
                tree = git(repo, 'write-tree', env=env).decode().strip()
                require(tree != line(repo, 'rev-parse', snap['head'] + '^{tree}'),
                        'index-only changes require review; no empty commit created')
                head = git(repo, 'commit-tree', tree, '-p', snap['head'],
                           data=f'Preserve agent turn {turn}\n'.encode()).decode().strip()
                self.scan(repo, policy, head)
                require(snapshot(repo) == snap, 'concurrent writer changed snapshot during commit')
                # Write-ahead original obligation precedes exposing the new branch head.
                remember(head)
                output.write(Path(env['GIT_INDEX_FILE']).read_bytes())
                output.flush()
                os.fsync(output.fileno())
                git(repo, 'update-ref', 'refs/heads/' + snap['branch'], head, snap['head'])
            os.replace(lock, index)
            return head
        finally:
            # os.replace releases our pathname. Another writer may already own
            # a new index.lock there; never delete its file during our cleanup.
            try:
                current_lock = lock.lstat() if lock.exists() else None
                if current_lock and (current_lock.st_dev, current_lock.st_ino) == (owned_lock.st_dev, owned_lock.st_ino):
                    lock.unlink()
            finally:
                os.close(lock_lease)

    def update_handoff(self, repo, policy, before, snap, turn):
        """Append bounded content metadata only to the explicitly reviewed document.

        User documentation is retained. Retries reuse the same content marker;
        the generated document cannot trigger a further changed-content handoff.
        """
        name = policy.get('handoff_file')
        if name is None:
            return snap
        require(isinstance(name, str) and name in policy['allowed'],
                'automatic handoff needs a literal reviewed destination')
        eligible([name], policy)
        require(not name.startswith('.github/'), 'automatic handoff cannot change publication automation')
        require(all(ord(c) >= 32 for c in name), 'invalid handoff destination')
        changes = {p: value for p, value in snap['files'].items()
                   if p != name and value != before['files'].get(p)}
        changes.update({p: None for p in before['files'] if p != name and p not in snap['files']})
        if not changes:
            return snap
        eligible(changes, policy)
        marker = '<!-- vk-github-sync ' + turn + ' ' + digest(changes) + ' -->'
        require(name not in snap['ignored'], 'handoff destination is ignored; excluded files are not Git-protected')
        target = repo / name
        # Parent traversal and symlinks cannot redirect this write outside the owner.
        require(target.parent.resolve().is_relative_to(repo) and target.parent.is_dir(),
                'handoff parent is unavailable or outside repository')
        old = target.read_bytes() if name in snap['files'] and snap['files'][name] is not None else b''
        require(len(old) <= 5 * 1024 * 1024 and b'\0' not in old, 'handoff must be bounded text')
        old.decode('utf-8')
        if marker.encode() in old:
            return snap
        lines = [marker, '## Automatic GitHub checkpoint', '', 'Turn: `' + turn + '`.',
                 'Changed eligible content since turn admission:', '']
        for path, value in sorted(changes.items()):
            status = 'deleted' if value is None else ('added' if not before['files'].get(path) else 'modified')
            lines.append('- ' + json.dumps(path, ensure_ascii=True) + ': ' + status +
                         ('.' if value is None else '; SHA-256 `' + value[0] + '`.'))
        lines += ['', 'Excluded files are not Git-protected. Merge requires explicit approval.', '']
        addition = ('\n\n' + '\n'.join(lines)).encode()
        require(len(old) + len(addition) <= 5 * 1024 * 1024, 'handoff exceeds bounded text limit')
        require(snapshot(repo) == snap, 'workspace changed before handoff update')
        flags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW
        if not old and not target.exists():
            flags |= os.O_CREAT | os.O_EXCL
        with os.fdopen(os.open(target, flags, 0o644), 'ab') as document:
            document.write(addition)
            document.flush()
            os.fsync(document.fileno())
        current = snapshot(repo)
        require({k: v for k, v in current['files'].items() if k != name} ==
                {k: v for k, v in snap['files'].items() if k != name} and
                all(current[k] == snap[k] for k in ['head', 'branch', 'ignored', 'index']) and
                target.read_bytes() == old + addition,
                'concurrent writer changed content during handoff update')
        return current

    def preserve_repo(self, entry, policy, request, remember):
        repo = Path(entry['path'])
        before = entry['before']
        snap = snapshot(repo)
        require(snap['branch'] == before['branch'], 'branch changed during turn')
        require(snap['branch'] not in ['main', 'staging'] and
                snap['branch'] not in policy.get('protected_branches', []),
                'protected branch is never automatically published')
        require(snap['ignored'] == before['ignored'],
                'ignored files changed; excluded work is not Git-protected')
        self.remote(repo, policy)
        remote = policy['url']
        eligible(entry.get('required_files', []), policy)
        require(all(p in snap['files'] and snap['files'][p] is not None
                    for p in entry.get('required_files', [])),
                'required affected file is missing, ignored or unverifiable')
        base = policy['base_commit']
        git(repo, 'merge-base', '--is-ancestor', base, snap['head'])
        git(repo, 'merge-base', '--is-ancestor', before['head'], snap['head'])
        for required in entry['original_commits']:
            require(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', required),
                    'required original commit must be a full ID')
            git(repo, 'merge-base', '--is-ancestor', required, snap['head'])
        require(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', base), 'reviewed base must be a full commit ID')
        status_paths = [os.fsdecode(p[3:]) for p in bytes.fromhex(snap['status']).split(b'\0') if p]
        eligible(status_paths, policy)
        # The configured review is an operator assessment of Actions and external automation.
        require(policy.get('publication_review') and policy.get('review_expires', 0) > time.time()
                and policy['workflow_digest'] == workflows(repo, base),
                'publication automation review absent or stale')
        require(workflows(repo, snap['head']) == policy['workflow_digest'] and
                not any(p.startswith('.github/') for p in status_paths),
                'automation changed since publication review')
        require(git(repo, 'ls-remote', '--exit-code', remote,
                    'refs/heads/' + policy['base_branch']).decode().split() ==
                [base, 'refs/heads/' + policy['base_branch']],
                'remote integration base moved since publication review')
        automation_branch = policy['automation_branch']
        require(git(repo, 'ls-remote', '--exit-code', remote,
                    'refs/heads/' + automation_branch).decode().split() ==
                [policy['automation_commit'], 'refs/heads/' + automation_branch],
                'remote automation source moved since publication review')
        require(workflows(repo, policy['automation_commit']) == policy['automation_workflow_digest'],
                'automation source digest differs from review')
        snap = self.update_handoff(repo, policy, before, snap, request['turn'])
        changed = bool(snap['status']) or snap['head'] != before['head']
        if snap['status']:
            head = self.commit(repo, policy, snap, request['turn'], remember)
        else:
            head = snap['head']
            self.scan(repo, policy, head)
        stable = snapshot(repo)
        index_path = Path(line(repo, 'rev-parse', '--path-format=absolute', '--git-path', 'index'))
        require(not index_path.with_name(index_path.name + '.lock').exists(),
                'Git index became locked by another writer; checkpoint remains pending')
        require(not stable['status'], 'worktree or index remains dirty after commit')
        require(stable['head'] == head, 'original head changed during preservation')
        require_tree_bytes(repo, stable)
        prs = self.prs(policy, stable['branch'])
        require(len(prs) <= 1, 'ambiguous existing pull requests')
        if prs:
            # Confirm destination/base before a push can trigger existing-PR automation.
            self.verify_pr(policy, stable['branch'], prs[0]['headRefOid'], prs[0]['number'])
        if changed:
            require(policy['review_expires'] > time.time(), 'publication review expired before push')
            for branch, reviewed in [(policy['base_branch'], base),
                                     (policy['automation_branch'], policy['automation_commit'])]:
                require(git(repo, 'ls-remote', '--exit-code', remote,
                            'refs/heads/' + branch).decode().split() == [reviewed, 'refs/heads/' + branch],
                        'reviewed automation or integration ref moved before push')
            require(snapshot(repo) == stable, 'workspace changed before publication')
            # Normal push only. Uncertain failure stays blocked and retry rechecks remote state.
            git(repo, 'push', '--porcelain', '--no-follow-tags', '--no-mirror',
                '--recurse-submodules=no', remote, f'{head}:refs/heads/{stable["branch"]}')
        # A fresh read-only branch at the reviewed base needs no new branch or PR.
        witness_branch = policy['base_branch'] if not changed and head == base and not prs else stable['branch']
        witness = self.witness(repo, remote, witness_branch, head)
        if changed and not prs:
            require(head != base, 'no changes against reviewed base; no PR created')
            run([self.gh, 'pr', 'create', '--repo', policy['repository'], '--draft',
                 '--base', policy['base_branch'], '--head', stable['branch'],
                 '--title', 'Preserve agent turn ' + request['turn'], '--body',
                 'Automatic eligible repository preservation. Exact remote coverage is verified '
                 'separately. Excluded files are not Git-protected. No merge or deployment approval.'])
            prs = self.prs(policy, stable['branch'])
            require(len(prs) == 1 and prs[0]['isDraft'], 'new draft PR not independently confirmed')
        if prs:
            witness['pr'] = self.verify_pr(policy, stable['branch'], head, prs[0]['number'])
        elif changed:
            raise Blocked('changed work has no covering PR')
        require(snapshot(repo) == stable, 'workspace changed after remote verification')
        return dict(**witness, after=stable, changed=changed,
                    ignored_not_git_protected=sorted(stable['ignored']))

    def observe_finished(self, request):
        """Record original heads before another admitted turn can rewrite ancestry.

        This records obligations only, never a writer fence or remote coverage.
        """
        path = self.state_path(request)
        record = read_json(path)
        require(record['config'] == digest(self.config), 'policy changed after turn admission')
        require([(e['id'], e['path']) for e in record['repositories']] ==
                [(i['id'], str(Path(i['path']).resolve())) for i in request['repositories']],
                'affected repository inventory differs from admitted turn')
        record['observation_complete'] = False
        try:
            for entry in record['repositories']:
                entry['original_commits'] = list(self.observe(record, entry))
                atomic_json(path, record)
            self.require_obligations(record)
            record['observation_complete'] = True
        except (Blocked, OSError, KeyError, ValueError):
            for entry in record['repositories']:
                record['obligations'][entry['id']]['unverifiable'] = True
            record.update(state='blocked', reason='completed original history observation failed')
        atomic_json(path, record)
        return record

    def checkpoint(self, request):
        # Queued turns get scoped coverage at a later idle boundary. This does
        # not certify the latest workspace/controller boundary.
        global CHECKPOINT_DEADLINE
        CHECKPOINT_DEADLINE = time.monotonic() + 90
        try:
            return self.end(request, checkpoint=True)
        finally:
            CHECKPOINT_DEADLINE = None

    def end(self, request, checkpoint=False):
        path = self.state_path(request)
        record = read_json(path)
        self.require_obligations(record)
        require(bool(request['repositories']) and bool(record['repositories']),
                'empty affected repository inventory')
        require(checkpoint or read_json(path.parent / 'latest.json')['turn'] == request['turn'],
                'a newer turn is pending; earlier turn cannot certify the workspace')
        require(record['config'] == digest(self.config), 'policy changed after turn admission')
        require([(e['id'], e['path'], e.get('required_commits', []), e.get('required_files', [])) for e in record['repositories']] ==
                [(i['id'], str(Path(i['path']).resolve()), i.get('required_commits', []), i.get('required_files', [])) for i in request['repositories']],
                'affected repository inventory differs from admitted turn')
        record.update(state='pending', reason='preservation in progress', checkpoint_only=checkpoint)
        atomic_json(path, record)
        try:
            require(request.get('writers_fenced') is True, 'writers are not fenced')
            errors = []
            for entry in record['repositories']:
                try:
                    entry['original_commits'] = list(self.observe(record, entry))
                except (Blocked, OSError, KeyError, ValueError) as error:
                    errors.append(str(error) if isinstance(error, Blocked)
                                  else 'original history observation was unverifiable')
                finally:
                    atomic_json(path, record)
            require(not errors, errors[0] if errors else '')
            for entry in record['repositories']:
                repo, policy = self.policy(entry)
                with repo_lock(repo):
                    def remember(head):
                        entry['original_commits'] = list(self.observe(record, entry, head))
                        atomic_json(path, record)

                    # Verify prior success first on retry; no duplicate commits or PR creation.
                    if checkpoint and entry.get('receipt') and snapshot(repo) != entry['receipt']['after']:
                        # Retain the prior proof. preserve_repo still requires every
                        # observed original as ancestry before refreshing coverage.
                        entry.setdefault('receipt_history', []).append(entry.pop('receipt'))
                        atomic_json(path, record)
                    if entry.get('receipt'):
                        self.check_repo(entry, policy)
                    else:
                        entry['receipt'] = self.preserve_repo(entry, policy, request, remember)
                    entry['original_commits'] = list(self.observe(record, entry))
                    atomic_json(path, record)
            self.require_obligations(record)
            for entry in record['repositories']:
                require(snapshot(Path(entry['path'])) == entry['receipt']['after'],
                        'earlier repository changed while another repository was preserved')
            require(checkpoint or read_json(path.parent / 'latest.json')['turn'] == request['turn'],
                    'newer turn admitted during preservation')
            record.update(state='verified', reason='eligible work has exact remote commit coverage',
                          outcome=request.get('outcome', 'unknown'))
        except (Blocked, OSError, KeyError, ValueError) as error:
            record.update(state='blocked', reason=str(error) if isinstance(error, Blocked)
                          else 'preservation IO or contract failure')
        if record['state'] == 'blocked':
            for entry in record['repositories']:
                try:
                    entry['original_commits'] = list(self.observe(record, entry))
                except (Blocked, OSError, KeyError, ValueError):
                    record.update(state='blocked', reason='original history observation was unverifiable')
        atomic_json(path, record)
        return record

    def check_repo(self, entry, policy):
        repo = Path(entry['path'])
        receipt = entry['receipt']
        require(isinstance(receipt.get('changed'), bool) and
                (not receipt['changed'] or 'pr' in receipt),
                'changed preservation receipt has no covering PR')
        eligible(entry.get('required_files', []), policy)
        require(all(p in receipt['after']['files'] and receipt['after']['files'][p] is not None
                    for p in entry.get('required_files', [])),
                'required affected file is missing, ignored or unverifiable')
        require(snapshot(repo) == receipt['after'], 'workspace changed after earlier receipt')
        require_tree_bytes(repo, receipt['after'])
        require(receipt.get('proof') == 'exact-history-fresh-fetch',
                'source-only checkpoint is not an exact-history preservation receipt')
        for required in entry['original_commits']:
            git(repo, 'merge-base', '--is-ancestor', required, receipt['commit'])
        self.scan(repo, policy, receipt['commit'])
        self.remote(repo, policy)
        remote = policy['url']
        self.witness(repo, remote, receipt['ref'].removeprefix('refs/heads/'), receipt['commit'])
        if 'pr' in receipt:
            self.verify_pr(policy, receipt['after']['branch'], receipt['commit'], receipt['pr']['number'])
        require(snapshot(repo) == receipt['after'], 'workspace changed during fresh verification')

    def check(self, request):
        # Never repairs or publishes. Caller supplies the full expected affected-work inventory.
        require(request.get('writers_fenced') is True, 'writers are not fenced')
        require(request.get('repositories'), 'empty affected repository inventory')
        path = self.state_path(request)
        record = read_json(path)
        require(read_json(path.parent / 'latest.json')['turn'] == request['turn'],
                'newer turn has invalidated the earlier receipt')
        require(record['version'] == VERSION and record['workspace'] == request['workspace'] and
                record['turn'] == request['turn'] and record['state'] == 'verified',
                'turn preservation is pending, blocked or unsupported')
        self.require_obligations(record)
        require(record['config'] == digest(self.config), 'policy differs from preservation receipt')
        require([(e['id'], e['path'], e.get('required_commits', []), e.get('required_files', [])) for e in record['repositories']] ==
                [(i['id'], str(Path(i['path']).resolve()), i.get('required_commits', []), i.get('required_files', [])) for i in request['repositories']],
                'affected repository inventory differs from receipt')
        for entry in record['repositories']:
            repo, policy = self.policy(entry)
            with repo_lock(repo):
                try:
                    self.check_repo(entry, policy)
                except Blocked as error:
                    raise Blocked(f"workspace {request['workspace']}, repository {repo}: {error}") from None
        for entry in record['repositories']:
            require(snapshot(Path(entry['path'])) == entry['receipt']['after'],
                    'earlier repository changed while another repository was checked')
        require(read_json(path.parent / 'latest.json')['turn'] == request['turn'],
                'newer turn admitted during verification')
        require(read_json(self.state_path(request)) == record,
                'preservation state changed during verification')
        return dict(version=VERSION, state='verified', workspace=request['workspace'],
                    turn=request['turn'], scope='eligible-repository-work-only',
                    checked_at=time.time(), receipt_digest=digest(record),
                    repositories=record['repositories'])


    def block(self, request):
        # Runtime visibility/persistence failure must not leave a green controller receipt.
        path = self.state_path(request)
        record = read_json(path)
        require(record['workspace'] == request['workspace'] and record['turn'] == request['turn'],
                'receipt identity mismatch')
        record.update(state='blocked', reason=request.get('reason', 'runtime could not persist preservation status'))
        atomic_json(path, record)
        return record

    def check_all(self, request):
        require(request.get('writers_fenced') is True, 'controller writers are not fenced')
        require(bool(request.get('turns')), 'empty affected turn inventory')
        results = []
        for turn in request['turns']:
            results.append(self.check(dict(turn, writers_fenced=True)))
        for result in results:
            current = read_json(self.state_path(result))
            require(read_json(self.state_path(result).parent / 'latest.json')['turn'] == result['turn'] and
                    current['state'] == 'verified' and digest(current) == result['receipt_digest'],
                    f"workspace {result['workspace']} preservation changed during batch check")
            for entry in result['repositories']:
                require(snapshot(Path(entry['path'])) == entry['receipt']['after'],
                        'affected workspace changed during controller batch check')
        return dict(version=VERSION, state='verified', scope='eligible-repository-work-only',
                    checked_at=time.time(), turns=results)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['begin', 'end', 'checkpoint', 'observe-finished', 'check', 'check-all', 'block'])
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    request = {}
    try:
        request = json.load(__import__('sys').stdin)
        config = read_json(Path(args.config))
        inventory = request.get('turns', [request]) if args.action == 'check-all' else [request]
        for item in [repo for turn in inventory for repo in turn['repositories']]:
            require(not Path(args.config).resolve().is_relative_to(Path(item['path']).resolve()),
                    'policy must be outside agent repository')
        result = getattr(Engine(config), args.action.replace('-', '_'))(request)
    except (Blocked, OSError, KeyError, ValueError) as error:
        result = dict(version=VERSION, state='blocked', workspace=request.get('workspace'),
                      turn=request.get('turn'), repositories=request.get('repositories', []), reason=str(error) if isinstance(error, Blocked)
                      else 'preservation IO or contract failure')
    print(json.dumps(result, sort_keys=True))
    return 0 if ((args.action == 'observe-finished' and result.get('observation_complete') is True)
                 or (result['state'] in ['verified', 'pending'] and args.action == 'begin')
                 or result['state'] == 'verified') else 2


if __name__ == '__main__':
    raise SystemExit(main())
