"""Closed-worktree Git graph and restored dependency qualification.

Shared repositories remain in place. Workspace-owned administrative metadata can
be archived with its worktree; the reachable objects are covered by a verified
shared dependency point. This verifier never resets branches, checks out over code, prunes, runs hooks or
changes common repository settings. Physical restoration belongs to the journaled
owner after it verifies this dependency closure.
"""
import os
from pathlib import Path
import re
import subprocess

from catalog import Conflict
import payloads

OID = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')
IN_PROGRESS = ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-apply',
               'rebase-merge', 'sequencer', 'BISECT_LOG')


def environment():
    # Ignore inherited Git placement/command overrides. Preserve authentication
    # settings in the environment but perform no network or credential action.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_OPTIONAL_LOCKS='0', GIT_CONFIG_NOSYSTEM='1',
               GIT_CONFIG_GLOBAL='/dev/null', GIT_TERMINAL_PROMPT='0', GIT_NO_LAZY_FETCH='1')
    return env


def git(root, *arguments, allowed=(0,), maximum=16 * 1024**2):
    result = subprocess.run(['git', '-C', str(root), '-c', 'core.hooksPath=/dev/null',
                             '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0', '-c', 'protocol.allow=never', *arguments],
                            env=environment(), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    if result.returncode not in allowed or len(result.stdout) > maximum:
        # Paths/private repository diagnostics stay out of public error strings.
        raise Conflict('Git dependency identity, integrity or bounded inspection failed')
    return result.stdout


def line(root, *arguments):
    raw = git(root, *arguments)
    if not raw.endswith(b'\n') or raw.count(b'\n') != 1:
        raise Conflict('Exact single Git identity required')
    return os.fsdecode(raw[:-1])


def object_id(value):
    if not isinstance(value, str) or not OID.fullmatch(value) or set(value) == {'0'}:
        raise Conflict('Exact Git object identity required')
    return value


def metadata_roots(admin, head):
    """Preserve commit roots referenced by private administrative recovery state."""
    roots = {object_id(head)}
    for path in (admin / 'ORIG_HEAD', admin / 'logs/HEAD'):
        if not os.path.lexists(path):
            continue
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024**2:
            raise Conflict('Unresolved Git administrative state is protected')
        before = payloads.signature(path.lstat())
        raw = path.read_bytes()
        if payloads.signature(path.lstat()) != before:
            raise Conflict('Git administrative state changed')
        for row in raw.splitlines():
            wanted = row.split(b' ', 2)[:2] if path.name == 'HEAD' else [row]
            if len(wanted) != (2 if path.name == 'HEAD' else 1):
                raise Conflict('Unresolved Git reflog entry is protected')
            for token in wanted:
                value = token.decode('ascii')
                if set(value) != {'0'}:
                    roots.add(object_id(value))
    return sorted(roots)


def inspect(worktree, repository, branch):
    worktree, repository = Path(worktree), Path(repository)
    payloads.parent_safe(worktree)
    if worktree.resolve(strict=True) != worktree or not worktree.is_dir():
        raise Conflict('Canonical existing workspace repository required')
    if line(worktree, 'rev-parse', '--show-toplevel') != str(worktree):
        raise Conflict('Workspace is not the exact registered repository root')
    common = Path(line(worktree, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve(strict=True)
    expected = Path(line(repository, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve(strict=True)
    admin = Path(line(worktree, 'rev-parse', '--absolute-git-dir')).resolve(strict=True)
    if common != expected or admin.parent != common / 'worktrees' or admin == common:
        raise Conflict('Workspace administrative metadata is not exclusively registered')
    # Shell and option injection are impossible: branch is data after --end-of-options.
    reference = 'refs/heads/' + branch
    git(repository, 'check-ref-format', reference)
    if line(worktree, 'symbolic-ref', '--quiet', 'HEAD') != reference:
        raise Conflict('Workspace branch differs from durable ownership')
    head = object_id(line(worktree, 'rev-parse', '--verify', 'HEAD^{commit}'))
    if any(os.path.lexists(admin / name) for name in IN_PROGRESS):
        raise Conflict('Unfinished Git operation is protected')
    if git(repository, 'config', '--local', '--get-regexp', r'^filter\..*\.(clean|smudge|process|required)$', allowed=(0, 1)):
        raise Conflict('Git filter programs require separate dependency qualification')
    if git(worktree, 'status', '--porcelain=v1', '-z', '--untracked-files=all'):
        raise Conflict('Dirty or untracked workspace work is protected')
    if any(row.startswith(b'160000 ') for row in git(worktree, 'ls-files', '--stage', '-z').split(b'\0')):
        raise Conflict('Submodule dependency ownership must be qualified separately')
    # Partial/promisor repositories and alternate object stores need their own
    # independently recoverable closure; do not assume an available checkout is it.
    if os.path.lexists(common / 'objects/info/alternates') or any((common / 'objects/pack').glob('*.promisor')):
        raise Conflict('External Git object dependencies are protected')
    registered = Path((admin / 'gitdir').read_text().strip())
    if registered.resolve(strict=True) != (worktree / '.git').resolve(strict=True):
        raise Conflict('Git registration points to a different workspace')
    roots = metadata_roots(admin, head)
    for root in roots:
        if line(repository, 'cat-file', '-t', root) not in ('commit', 'tag'):
            raise Conflict('Private Git recovery root has unexpected type')
    return dict(format='vk-workspace-git-dependency-v1', worktree=str(worktree),
                repository=str(repository.resolve(strict=True)), common=str(common), admin=str(admin),
                branch=reference, head=head, object_roots=roots)


def verify_shared_snapshot(common, roots):
    """Verify a separately restored common directory without external objects."""
    common = Path(common)
    if common.resolve(strict=True) != common or not common.is_dir():
        raise Conflict('Canonical restored Git dependency required')
    if os.path.lexists(common / 'objects/info/alternates'):
        raise Conflict('Restored Git dependency may not borrow another object store')
    env = environment()
    env['GIT_OBJECT_DIRECTORY'] = str(common / 'objects')
    command = ['git', '--git-dir=' + str(common), '-c', 'core.hooksPath=/dev/null',
               '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0', '-c', 'protocol.allow=never']
    for root in roots:
        result = subprocess.run(command + ['cat-file', '-e', object_id(root)], env=env,
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
        if result.returncode:
            raise Conflict('Restored Git graph is missing a required object root')
    result = subprocess.run(command + ['fsck', '--full', '--strict', '--no-dangling', '--no-reflogs'],
                            env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
    if result.returncode:
        raise Conflict('Independently restored Git dependency graph is incomplete')


def verify_live(spec):
    """Check live shared graph/branch after restoring exact private payloads."""
    if spec.get('format') != 'vk-workspace-git-dependency-v1':
        raise Conflict('Exact Git dependency ownership required')
    repository, common = Path(spec['repository']), Path(spec['common'])
    actual = Path(line(repository, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve(strict=True)
    if actual != common:
        raise Conflict('Shared Git repository identity changed')
    git(repository, 'check-ref-format', spec['branch'])
    head = line(repository, 'rev-parse', '--verify', '--end-of-options', spec['branch'] + '^{commit}')
    if head != spec['head']:
        raise Conflict('Archived branch changed; preserve the newer shared state')
    for root in spec['object_roots']:
        git(repository, 'cat-file', '-e', object_id(root))
    # Inspect both immutable graph and the restored administrative binding. No
    # checkout, branch reset, source overwrite or shared-repository cleanup.
    if inspect(spec['worktree'], spec['repository'], spec['branch'].removeprefix('refs/heads/')) != spec:
        raise Conflict('Restored worktree Git identity differs')
