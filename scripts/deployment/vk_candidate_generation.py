"""Candidate-state controller primitives. No production service/route entrypoint.

The sealed owning controller supplies its pinned backup reader and supervisor.
This module never captures production, connects to Desktop, runs a binary,
deletes files, or resumes the historical conversation. Tests retain their files.
"""
from contextlib import contextmanager, closing
from dataclasses import dataclass
import hashlib
import base64
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import stat


class Blocked(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Blocked(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def atime_binding(manifest_sha256, values):
    return digest({'order': 'sorted_manifest_names', 'manifest_sha256': manifest_sha256,
                   'nanoseconds': values})


def relative(name):
    p = PurePosixPath(name)
    require(isinstance(name, str) and name and not p.is_absolute()
            and all(x not in ("", ".", "..") for x in name.split("/")), "unsafe relative path")
    return p


def underneath(path, parent):
    return path == parent or path.is_relative_to(parent)


@dataclass(frozen=True)
class Layout:
    task: Path
    tree: Path
    evidence: Path
    protected: tuple

    def validate(self):
        task, tree, evidence = [Path(p).absolute() for p in (self.task, self.tree, self.evidence)]
        require(task.resolve() == task and tree.resolve() == tree and evidence.resolve() == evidence,
                "candidate layout has a host symlink alias")
        require(tree != task and evidence != task and tree.is_relative_to(task)
                and evidence.is_relative_to(task), "candidate/evidence must stay in their task")
        require(not underneath(tree, evidence) and not underneath(evidence, tree), "evidence overlaps candidate")
        require(bool(self.protected), "protected-root inventory is empty")
        for raw in self.protected:
            p = Path(raw).resolve()
            require(not underneath(task, p) and not underneath(p, task), "task overlaps protected root")
        if tree.exists():
            require(tree.is_dir() and not tree.is_symlink(), "candidate root is not an independent directory")
        return self

    def binding(self):
        self.validate()
        info = self.tree.stat()
        return digest({"tree": str(self.tree), "device": info.st_dev, "inode": info.st_ino,
                       "protected": sorted(str(Path(p).resolve()) for p in self.protected)})


@contextmanager
def open_regular(root, name):
    """Open without following any host symlink, including intermediate components."""
    parts = relative(name).parts
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        stream_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        info = os.fstat(stream_fd)
        require(stat.S_ISREG(info.st_mode), "source is not a regular file")
        with os.fdopen(stream_fd, "rb") as stream:
            yield stream
            after = os.fstat(stream.fileno())
            require((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                    == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                    "source changed during read")
    finally:
        os.close(fd)


def inventory(root):
    """Exact private tree inventory; links are recorded, never followed."""
    root = Path(root)
    require(root.resolve() == root.absolute() and root.is_dir(), "inventory root alias")
    rows, inodes = {}, {}

    def visit(directory):
        for path in sorted(directory.iterdir()):
            name = path.relative_to(root).as_posix()
            info = path.lstat()
            row = {"mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid, "gid": info.st_gid}
            row["mtime_ns"] = info.st_mtime_ns
            row["xattrs"] = {key: base64.b64encode(os.getxattr(path, key, follow_symlinks=False)).decode()
                             for key in sorted(os.listxattr(path, follow_symlinks=False))}
            if stat.S_ISDIR(info.st_mode):
                row["kind"] = "directory"
                rows[name] = row
                visit(path)
            elif stat.S_ISREG(info.st_mode):
                with open_regular(root, name) as stream:
                    sha = hashlib.file_digest(stream, "sha256").hexdigest()
                row.update(kind="file", sha256=sha, bytes=info.st_size)
                rows[name] = row
                inodes.setdefault((info.st_dev, info.st_ino), []).append((name, info.st_nlink))
            elif stat.S_ISLNK(info.st_mode):
                row.update(kind="symlink", target=os.readlink(path))
                rows[name] = row
            else:
                raise Blocked("unsupported special file: " + name)
    visit(root)
    for aliases in inodes.values():
        require(all(count == len(aliases) for _, count in aliases), "hardlink escapes candidate inventory")
        # Directory-first traversal is not lexical ordering of complete paths:
        # e.g. z/file is visited before z-/file, while z-/file sorts first.
        # Match the authenticated archive's canonical primary without changing
        # the actual inode relationships or any file metadata.
        aliases.sort(key=lambda alias: alias[0])
        first = aliases[0][0]
        for name, _ in aliases[1:]:
            rows[name]["kind"] = "hardlink"
            rows[name]["target"] = first
    return rows


def validate_manifest(rows, *, recorded_link_exceptions=None):
    """Validate preservation rows; exceptions never authorize a runtime selector.

    A bound capture may contain originally dangling/external links. Only their
    exact literal targets may be retained; host resolution is never consulted.
    Escape/cycle/type errors are not missing dependencies and remain blockers.
    """
    exceptions = {} if recorded_link_exceptions is None else recorded_link_exceptions
    require(type(exceptions) is dict, "invalid recorded link exception inventory")
    require(all(rows.get(name, {}).get("kind") == "symlink"
                and rows[name].get("target") == target for name, target in exceptions.items()),
            "recorded link exception changed or omitted")
    require(bool(rows), "empty candidate scope")
    for name, row in rows.items():
        p = relative(name)
        require(row.get("kind") in ("directory", "file", "hardlink", "symlink"), "unsupported manifest kind")
        require(isinstance(row.get("mode"), int) and 0 <= row["mode"] <= 0o7777, "invalid mode")
        require(not row["mode"] & 0o6000, "privileged mode needs separate reviewed ownership mapping")
        require(isinstance(row.get("mtime_ns"), int) and row["mtime_ns"] >= 0, "mtime proof missing")
        require(isinstance(row.get("xattrs"), dict), "extended metadata proof missing")
        for key, value in row["xattrs"].items():
            require(key.startswith("user.") or key in ("system.posix_acl_access", "system.posix_acl_default"),
                    "non-user extended metadata needs reviewed restore adapter")
            try:
                base64.b64decode(value, validate=True)
            except (ValueError, TypeError) as error:
                raise Blocked("invalid extended attribute encoding") from error
        require(row.get("uid") == os.getuid() and row.get("gid") == os.getgid(),
                "foreign owner requires explicit reviewed namespace mapping")
        for parent in p.parents:
            if str(parent) != ".":
                require(rows.get(str(parent), {}).get("kind") == "directory", "manifest parent is missing/not a directory")
        if row["kind"] in ("file", "hardlink"):
            require(isinstance(row.get("bytes"), int) and row["bytes"] >= 0
                    and isinstance(row.get("sha256"), str) and len(row["sha256"]) == 64
                    and all(c in "0123456789abcdef" for c in row["sha256"]), "file proof missing")
        if row["kind"] == "hardlink":
            relative(row["target"])
            target = rows.get(row["target"], {})
            require(target.get("kind") == "file" and all(row[k] == target.get(k)
                    for k in ("mode", "uid", "gid", "bytes", "sha256", "mtime_ns", "xattrs")), "hardlink relationship mismatch")
        if row["kind"] == "symlink":
            require(isinstance(row.get("target"), str) and row["target"] and "\x00" not in row["target"], "invalid link target")
            # Resolve in the future private root, not the host. No arbitrary host link is opened.
            target = PurePosixPath(row["target"])
            parts = list(target.parts[1:] if target.is_absolute() else p.parent.parts + target.parts)
            normalized = []
            for part in parts:
                if part in ("", "."):
                    continue
                if part == "..":
                    require(bool(normalized), "link escapes namespace")
                    normalized.pop()
                else:
                    normalized.append(part)
    for name, row in rows.items():
        if row["kind"] == "symlink":
            try:
                resolve_virtual(rows, "/" + name)
            except Blocked as error:
                require(str(error) == "namespace dependency missing" and name in exceptions,
                        str(error))
            else:
                require(name not in exceptions, "resolved link must not be an exception")
    return rows


def recorded_link_exceptions(rows):
    """Classify missing virtual dependencies, without reading any host target."""
    exceptions = {}
    for name, row in rows.items():
        if row.get("kind") == "symlink":
            try:
                resolve_virtual(rows, "/" + name)
            except Blocked as error:
                require(str(error) == "namespace dependency missing", str(error))
                exceptions[name] = row["target"]
    validate_manifest(rows, recorded_link_exceptions=exceptions)
    return exceptions


def capture_link_exceptions(verified):
    exceptions = verified.get("recorded_link_exceptions", {})
    if exceptions:
        require(verified.get("recorded_link_exceptions_sha256") == digest({
                    "manifest_sha256": verified["manifest_sha256"], "targets": exceptions}),
                "recorded link exception binding mismatch")
    return exceptions


def resolve_virtual(rows, path):
    """Resolve links inside the future namespace, never through the host filesystem."""
    require(path.startswith("/") and "\x00" not in path, "invalid virtual path")
    pending, resolved, traversed = list(PurePosixPath(path).parts[1:]), [], set()
    while pending:
        part = pending.pop(0)
        if part in ("", "."):
            continue
        if part == "..":
            require(bool(resolved), "link escapes namespace")
            resolved.pop()
            continue
        name = "/".join(resolved + [part])
        require(name in rows, "namespace dependency missing")
        row = rows[name]
        if row["kind"] == "symlink":
            require(name not in traversed, "namespace symlink cycle")
            traversed.add(name)
            target = PurePosixPath(row["target"])
            if target.is_absolute():
                resolved = []
                pending = list(target.parts[1:]) + pending
            else:
                pending = list(target.parts) + pending
        else:
            require(not pending or row["kind"] == "directory", "non-directory namespace ancestor")
            resolved.append(part)
    require(bool(resolved), "namespace root selector is forbidden")
    return "/" + "/".join(resolved)


def write_new_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def sync_tree_directories(root):
    # Do not follow virtual absolute links into the host while sealing restore.
    for directory, children, files in os.walk(root, followlinks=False, topdown=False):
        for name in files:
            path = Path(directory) / name
            if path.is_symlink():
                continue
            with open_regular(root, path.relative_to(root).as_posix()) as stream:
                os.fsync(stream.fileno())
        sync_directory(directory)


def verify_sqlite(tree, paths):
    for name in paths:
        relative(name)
        with open_regular(tree, name) as stream:
            require(stream.read(16) == b"SQLite format 3\0", "invalid SQLite snapshot")
        # Only the private, stopped, fully restored copy is opened immutable.
        with sqlite3.connect((Path(tree) / name).as_uri() + "?mode=ro&immutable=1", uri=True) as db:
            require(db.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "private database integrity failed")


def verify_tree(layout, rows, sqlite_paths, *, recorded_link_exceptions=None):
    layout.validate()
    validate_manifest(rows, recorded_link_exceptions=recorded_link_exceptions)
    require(inventory(layout.tree) == rows, "candidate content/type/mode/owner/link inventory differs")
    verify_sqlite(layout.tree, sqlite_paths)
    return {"root_binding": layout.binding(), "manifest_sha256": digest(rows), "sqlite_paths": sorted(sqlite_paths)}


def binding_environment(layout, selectors, *, preserved_capture=None):
    """Preserve virtual absolute selectors; return only independent backing paths.

    Root must give this mapping to the existing reviewed kernel boundary. These
    mappings do not authorize an environment-only launch on the host.
    """
    layout.validate()
    exceptions = {}
    if preserved_capture is not None:
        require(digest(preserved_capture["entries"]) == preserved_capture["manifest_sha256"],
                "preserved capture manifest binding mismatch")
        exceptions = capture_link_exceptions(preserved_capture)
    rows = validate_manifest(inventory(layout.tree), recorded_link_exceptions=exceptions)
    bindings = {}
    for key, virtual in selectors.items():
        require(isinstance(virtual, str) and virtual.startswith("/") and ".." not in virtual.split("/"),
                "selector must be an absolute namespace path")
        resolved = resolve_virtual(rows, virtual)
        backing = layout.tree / resolved.lstrip("/")
        require(backing.exists() and not backing.is_symlink() and backing.resolve() == backing,
                "selector backing missing/aliased; materialized namespace proof required")
        bindings[key] = {"virtual": virtual, "resolved_virtual": resolved, "backing": str(backing),
                         "device": backing.stat().st_dev, "inode": backing.stat().st_ino}
    return {"root_binding": layout.binding(), "selectors": bindings,
            "requires_reviewed_kernel_boundary": True, "host_launch_authorized": False}


def bind_reviewed_namespace(layout, argv, prefixes, selectors, *, preserved_capture=None):
    """Extend an already reviewed kernel command with candidate virtual roots.

    Never execute here. The supervisor must authenticate the boundary source and
    rerun its manager/socket and spawned-worker proofs with these mappings. Bind
    containing roots, rather than just environment variables, so absolute Git,
    history and attachment paths see the same candidate generation.
    """
    layout.validate()
    require(all(flag in argv for flag in ("--unshare-user", "--unshare-pid", "--unshare-net",
                "--new-session", "--die-with-parent", "--proc", "--dev", "--")), "kernel boundary incomplete")
    require(any(argv[i:i + 3] == ["--ro-bind", "/", "/"] for i in range(len(argv))),
            "host root must remain read-only")
    require(any(argv[i:i + 2] == ["--tmpfs", "/run"] for i in range(len(argv))),
            "host manager runtime must remain hidden")
    require(any(argv[i:i + 3] == ["--bind", str(layout.tree), str(layout.tree)] for i in range(len(argv))),
            "reviewed sole writable root differs from candidate")
    require(prefixes and len(set(prefixes)) == len(prefixes), "namespace prefixes missing/duplicated")
    normalized = [Path(p) for p in prefixes]
    require(all(p.is_absolute() and str(p) not in ("/", "/run", "/proc", "/dev", "/usr", "/etc")
                and ".." not in p.parts for p in normalized), "unsafe namespace prefix")
    require(all(not underneath(a, b) for a in normalized for b in normalized if a != b),
            "nested namespace prefixes need a separately reviewed mount order")
    bindings = binding_environment(layout, selectors, preserved_capture=preserved_capture)
    require(all(all(any(underneath(Path(row[key]), p) for p in normalized)
                    for key in ("virtual", "resolved_virtual")) for row in bindings["selectors"].values()),
            "namespace mounts do not cover every selector and its link backing")
    # Reject a command containing another writable host bind. The reviewed
    # sibling temporary mount is the only exception to the candidate root.
    for i, token in enumerate(argv[:argv.index("--")]):
        if token == "--bind":
            pair = argv[i + 1:i + 3]
            allowed = ([str(layout.tree), str(layout.tree)],
                       [str(layout.tree.with_name(layout.tree.name + "-private-tmp")), "/tmp"])
            require(pair in allowed, "unreviewed writable host bind")
        require(token not in ("--bind-try", "--bind-data", "--overlay", "--share-net", "--share-user"),
                "unreviewed boundary override")
    extra = []
    for prefix in sorted(prefixes):
        backing = layout.tree / prefix.lstrip("/")
        require(backing.is_dir() and not backing.is_symlink() and backing.resolve() == backing,
                "namespace prefix backing missing/aliased")
        extra += ["--bind", str(backing), prefix]
    end = argv.index("--")
    return {"argv": argv[:end] + extra + argv[end:], "bindings": bindings,
            "boundary_reacceptance_required": True, "operational_authorization": False}


def namespace_runtime_identity(layout, database_virtual, workspace_virtual, *, preserved_capture=None):
    """Produce PR153's inode receipt for this namespace, without enrolling a DB.

    Call again after catch-up replaces a DB/workspace inode. A missing persisted
    dataset identity blocks; it is never synthesized from a path or history claim.
    The supervisor mounts the resulting small receipt read-only outside data.
    """
    bindings = binding_environment(layout, {"database": database_virtual, "workspaces": workspace_virtual},
                                   preserved_capture=preserved_capture)
    database, workspaces = [bindings["selectors"][key] for key in ("database", "workspaces")]
    require(Path(workspaces["backing"]).is_dir(), "workspace selector is not a directory")
    relative_database = Path(database["backing"]).relative_to(layout.tree).as_posix()
    verify_sqlite(layout.tree, (relative_database,))
    try:
        with sqlite3.connect(Path(database["backing"]).as_uri() + "?mode=ro&immutable=1", uri=True) as db:
            identities = db.execute("SELECT dataset_id FROM vk_runtime_identity WHERE singleton = 1").fetchall()
    except sqlite3.Error as error:
        raise Blocked("persisted dataset identity missing; reviewed one-time enrollment remains required") from error
    require(len(identities) == 1 and isinstance(identities[0][0], str) and len(identities[0][0]) == 32
            and all(c in "0123456789abcdefABCDEF" for c in identities[0][0]), "persisted dataset identity invalid")
    text = ("vk-runtime-identity-v1\n"
            f"database={database['resolved_virtual']}\n"
            f"database_id={database['device']}:{database['inode']}\n"
            f"workspace_root={workspaces['resolved_virtual']}\n"
            f"workspace_root_id={workspaces['device']}:{workspaces['inode']}\n"
            f"dataset_id={identities[0][0]}\n")
    return {"root_binding": bindings["root_binding"], "text": text,
            "sha256": hashlib.sha256(text.encode()).hexdigest(), "enrollment_performed": False}


class CandidateController:
    """Fail-closed controller with pinned external provider/supervisor adapters.

    provider.verify(capture) must authenticate the complete B stream, full current
    inventory/SQLite snapshots, exact scope and frozen boundary when requested.
    It returns the authenticated manifest, not caller-provided success booleans.
    provider.open(capture, name) streams an authenticated member from that capture.
    supervisor.verify_stopped(binding) independently covers candidate/extra writers.
    supervisor.verify_fence(capture) binds fresh incumbent/all-writer fencing.
    supervisor.acceptance(...) binds real binary/module/scanner/boundary/controller
    checks and current report receipts to this exact source/root/data generation.
    Production adapters are supplied by a newly sealed approved owner, never old
    imported operational scripts. No adapter is constructed or invoked on import.
    """

    def __init__(self, layout, scope_sha256, source_sha256, provider, supervisor, sqlite_paths,
                 fallback_artifact_sha256=None, capacity_policy_sha256=None):
        self._configure(layout, scope_sha256, source_sha256, provider, supervisor, sqlite_paths,
                        fallback_artifact_sha256, capacity_policy_sha256)
        require(not self.layout.evidence.exists() or not any(self.layout.evidence.iterdir()),
                "retained controller journal needs explicit recovery; refusing a new owner")

    def _configure(self, layout, scope_sha256, source_sha256, provider, supervisor, sqlite_paths,
                   fallback_artifact_sha256, capacity_policy_sha256):
        self.layout = layout.validate()
        self.scope = scope_sha256
        self.source = source_sha256
        self.fallback_artifact = fallback_artifact_sha256
        self.capacity_policy = capacity_policy_sha256
        self.reserve_bytes = None
        self.provider, self.supervisor = provider, supervisor
        self.sqlite_paths = tuple(sqlite_paths)
        require(bool(self.sqlite_paths), "required database inventory is empty")
        require(all(isinstance(p, str) and len(p) == 64 and all(c in "0123456789abcdef" for c in p)
                    for p in (scope_sha256, source_sha256)), "source/scope digest is invalid")
        self.phase, self.sequence = "new", 0
        self.rows = None
        self.boundary = None
        self.test_receipt = None
        self.owner_receipt = None

    @classmethod
    def recover_initial_restore(cls, layout, scope_sha256, source_sha256, provider, supervisor,
                                sqlite_paths, *, prior_source_sha256,
                                fallback_artifact_sha256=None, capacity_policy_sha256=None):
        """Reverify one completed, never-accepted restore under a new held owner.

        No interrupted operation, test edit, rehearsal, activation or fence is
        reconstructed. The real supervisor must independently exclude writers
        and hold the new ownership lease before this method can append evidence.
        All prior evidence remains intact; recovery returns only `restored`.
        """
        self = cls.__new__(cls)
        self._configure(layout, scope_sha256, source_sha256, provider, supervisor, sqlite_paths,
                        fallback_artifact_sha256, capacity_policy_sha256)
        require(isinstance(prior_source_sha256, str) and len(prior_source_sha256) == 64
                and all(c in '0123456789abcdef' for c in prior_source_sha256),
                'prior controller source must be explicitly pinned')
        require(self.layout.evidence.is_dir() and not self.layout.evidence.is_symlink(),
                'completed restore journal missing or aliased')
        journals = list(self.layout.evidence.iterdir())
        allowed = ('0001-restored.json', '0001-initial-materialization-verified.json')
        require(len(journals) == 1 and journals[0].name in allowed,
                'only a single completed initial restore can be recovered; later operations remain held')
        with open_regular(self.layout.evidence, journals[0].name) as stream:
            require(os.fstat(stream.fileno()).st_nlink == 1, 'restore journal has an external hardlink')
            previous = json.load(stream)
        if journals[0].name == '0001-initial-materialization-verified.json':
            require(previous.get('scope') == self.scope
                    and previous.get('prior_attempt_reconstructed') is False
                    and previous.get('restored_again') is False
                    and previous.get('rehearsal_accepted') is False
                    and previous.get('activation_authorized') is False,
                    'initial materialization journal claims an unsupported operation')
        require(previous.get('source') == prior_source_sha256
                and previous.get('root_binding') == self.layout.binding(),
                'retained restore source/root binding differs')
        self.supervisor.verify_stopped(self.layout.binding())
        verified = self.authenticated(previous['capture_id'])
        require(previous.get('manifest_sha256') == verified['manifest_sha256'],
                'retained restore journal differs from authenticated B capture')
        proof = verify_tree(self.layout, verified['entries'], self.sqlite_paths,
                            recorded_link_exceptions=capture_link_exceptions(verified))
        proof.update(self.restore_atimes(verified))
        self.supervisor.verify_stopped(self.layout.binding())
        self.rows, self.boundary, self.sequence = verified['entries'], verified, 1
        self.checkpoint('initial-owner-recovered', {**proof, 'capture_id': verified['capture_id'],
            'prior_source': prior_source_sha256, 'source': self.source, 'scope': self.scope,
            'prior_journal': journals[0].name,
            'rehearsal_accepted': False, 'activation_authorized': False})
        self.phase = 'restored'
        return self

    def checkpoint(self, kind, value):
        self.sequence += 1
        write_new_json(self.layout.evidence / f"{self.sequence:04d}-{kind}.json", value)

    def authenticated(self, capture, frozen=False):
        verified = self.provider.verify(capture)
        require(verified["scope_sha256"] == self.scope, "backup scope mismatch")
        require(verified["capture_id"] == capture, "backup generation mismatch")
        require(verified["full_current_state"] is True and verified["provider"] == "desktop-B",
                "full authoritative B capture required")
        rows = validate_manifest(verified["entries"],
                                 recorded_link_exceptions=capture_link_exceptions(verified))
        require(verified["manifest_sha256"] == digest(rows), "backup manifest binding mismatch")
        if not verified.get('fixture_only'):
            require(verified.get('restore_archived_atime') is True,
                    'operational restore requires authenticated archived-atime policy')
            require(type(verified['archived_atime_ns']) is list
                    and len(verified['archived_atime_ns']) == len(rows)
                    and atime_binding(verified['manifest_sha256'], verified['archived_atime_ns'])
                    == verified['archived_atime_sha256'],
                    'operational archived-atime inventory binding mismatch')
        require(set(self.sqlite_paths) <= rows.keys(), "required database omitted")
        require(all(rows[p]["kind"] == "file" for p in self.sqlite_paths), "database must be a standalone snapshot")
        self.verify_suffix_files(capture, rows)
        if frozen:
            self.supervisor.verify_fence(verified)
        return verified

    def verify_suffix_files(self, capture, rows):
        """Distinguish an authenticated ELF executable from SQLite bookkeeping.

        Names alone cannot identify sidecars. Preserve suffix-named binaries only
        after hashing their complete archived bytes and checking their ELF header.
        A base in the archive/required DB inventory, links, data files and ambiguous
        bytes remain blocked. No caller-supplied exemption or live file is trusted.
        """
        selected = {p for p in rows if p.endswith(("-wal", "-shm"))}
        for name in selected:
            row = rows[name]
            require(name[:-4] not in rows and name[:-4] not in self.sqlite_paths
                    and row['kind'] == 'file' and row['mode'] & 0o111,
                    'SQLite sidecars require snapshot normalization')

        def check(name, stream):
            row = rows[name]
            header = stream.read(64)
            # Native ELF64 little-endian executable/shared-object header. SQLite
            # WAL/SHM contents cannot satisfy this distinct format signature.
            require(len(header) == 64 and header[:7] == b'\x7fELF\x02\x01\x01'
                    and int.from_bytes(header[16:18], 'little') in (2, 3)
                    and header[18:24] == b'\x3e\x00\x01\x00\x00\x00'
                    and int.from_bytes(header[52:54], 'little') == 64,
                    'SQLite sidecars require snapshot normalization; suffix file is not ELF')
            h, count = hashlib.sha256(header), len(header)
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                count += len(block)
                require(count <= row['bytes'], 'suffix file exceeds authenticated size')
                h.update(block)
            require(count == row['bytes'] and h.hexdigest() == row['sha256'],
                    'suffix file differs from authenticated archive')

        if not selected:
            return
        if callable(getattr(self.provider, 'file_members', None)):
            seen = set()
            with self.provider.file_members(capture, selected) as members:
                for name, stream in members:
                    require(name in selected and name not in seen, 'unexpected/duplicate suffix file')
                    check(name, stream)
                    seen.add(name)
            require(seen == selected, 'archive omitted suffix file')
        else:
            for name in sorted(selected):
                with self.provider.open(capture, name) as stream:
                    check(name, stream)

    def accepted(self, receipt, proof, stage, capture):
        require(receipt.get("root_binding") == proof["root_binding"]
                and receipt.get("source") == self.source and receipt.get("scope") == self.scope
                and receipt.get("capture_id") == capture and receipt.get("stage") == stage
                and receipt.get("manifest_sha256") == proof["manifest_sha256"],
                "acceptance receipt binding mismatch")
        checks = ("private_filesystem_pid_network_manager_boundary", "no_incumbent_write_access",
                  "binary_module_scanner_bound", "capacity_controller_ready",
                  "runtime_database_workspace_identity_bound",
                  "operational_dependency_closure_verified",
                  "whole_state_capacity_restore_verified",
                  "full_required_linux_metadata_verified",
                  "recommend_and_usage_controls_preserved", "consent_accepted",
                  "current_report_receipts_preserved", "cleanup_unavailable")
        if stage in ("activation", "latest-data-fallback"):
            checks += ("fallback_latest_data_compatible",)
            require(isinstance(self.fallback_artifact, str) and len(self.fallback_artifact) == 64
                    and all(c in "0123456789abcdef" for c in self.fallback_artifact)
                    and receipt.get("fallback_artifact_sha256") == self.fallback_artifact,
                    "protected compatible fallback artifact is not pinned")
        require(all(receipt.get("checks", {}).get(key) is True for key in checks),
                "required acceptance check absent or failed")
        return receipt

    def capacity(self, verified, stage, payload_bytes):
        require(isinstance(self.capacity_policy, str) and len(self.capacity_policy) == 64
                and all(c in "0123456789abcdef" for c in self.capacity_policy),
                "measured capacity policy is not pinned")
        receipt = self.supervisor.verify_capacity(verified, self.layout, stage, payload_bytes)
        require(receipt.get("policy_sha256") == self.capacity_policy
                and receipt.get("scope") == self.scope and receipt.get("source") == self.source
                and receipt.get("capture_id") == verified["capture_id"] and receipt.get("stage") == stage
                and receipt.get("payload_bytes") == payload_bytes, "capacity receipt binding mismatch")
        reserve = receipt.get("reserve_bytes")
        require(type(reserve) is int and reserve > 0, "proven working reserve missing")
        self.reserve_bytes = reserve
        self.room(payload_bytes)
        return receipt

    def room(self, next_bytes):
        require(type(self.reserve_bytes) is int, "capacity proof missing")
        parent = self.layout.task
        while not parent.exists():
            parent = parent.parent
        info = os.statvfs(parent)
        require(info.f_bavail * info.f_frsize >= next_bytes + self.reserve_bytes,
                "candidate working reserve insufficient; partial private state remains retained")

    def materialize(self, verified, changed):
        rows = verified["entries"]
        for name in sorted(changed, key=lambda p: (len(relative(p).parts), p)):
            row, target = rows.get(name), self.layout.tree / name
            if row is None:
                continue
            if row["kind"] == "directory":
                # New private directories stay writable until descendants are
                # restored; final metadata applies the recorded mode last.
                target.mkdir(mode=0o700)
        files = {p for p in changed if rows.get(p, {}).get("kind") == "file"}
        if callable(getattr(self.provider, "file_members", None)):
            seen = set()
            # One complete verified archive pass per selected chain member, not
            # one full B transfer per restored file. Hash errors at EOF still
            # fail this private materialization before links/acceptance.
            with self.provider.file_members(verified["capture_id"], files) as members:
                for name, source in members:
                    require(name in files and name not in seen, "unexpected/duplicate restore member")
                    self._write_member(name, rows[name], source)
                    seen.add(name)
            require(seen == files, "stream omitted required restore members")
        else:
            for name in sorted(files):
                with self.provider.open(verified["capture_id"], name) as source:
                    self._write_member(name, rows[name], source)
        # Links are last; their parents cannot redirect any preceding write.
        for name in sorted(changed):
            row = rows.get(name)
            if row and row["kind"] == "hardlink":
                os.link(self.layout.tree / row["target"], self.layout.tree / name, follow_symlinks=False)
            elif row and row["kind"] == "symlink":
                os.symlink(row["target"], self.layout.tree / name)
        # Directory timestamps are applied last, after all descendant creation.
        for name in sorted(rows, key=lambda p: (-len(relative(p).parts), p)):
            row, target = rows[name], self.layout.tree / name
            if name in changed:
                if row["kind"] != "symlink":
                    os.chmod(target, row["mode"])
                for key, value in row["xattrs"].items():
                    os.setxattr(target, key, base64.b64decode(value), follow_symlinks=False)
            if name in changed or row["kind"] == "directory":
                os.utime(target, ns=(row["mtime_ns"], row["mtime_ns"]), follow_symlinks=False)
        sync_tree_directories(self.layout.tree)
        sync_directory(self.layout.tree.parent)

    def _write_member(self, name, row, source):
        target = self.layout.tree / name
        require(not target.exists() and not target.is_symlink(), "restore would overwrite an unquarantined path")
        h, count = hashlib.sha256(), 0
        with target.open("xb") as out:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                self.room(len(block))
                count += len(block)
                require(count <= row["bytes"], "restore member longer than authenticated manifest")
                h.update(block)
                out.write(block)
            out.flush()
            os.fsync(out.fileno())
        require(count == row["bytes"] and h.hexdigest() == row["sha256"], "restored bytes mismatch")

    def restore_atimes(self, verified):
        """Restore authenticated archive timestamps after content verification.

        Reads on a relatime filesystem may change atime; apply after the last
        content traversal, then inspect using lstat only. Running application
        access may legitimately change timestamps after this stopped boundary.
        """
        if not verified.get('restore_archived_atime'):
            return {'archived_atime_restored': False}
        values, rows = verified['archived_atime_ns'], verified['entries']
        manifest_sha256 = digest(rows)
        require(type(values) is list and len(values) == len(rows)
                and manifest_sha256 == verified['manifest_sha256']
                and atime_binding(manifest_sha256, values) == verified['archived_atime_sha256'],
                'atime inventory binding mismatch')
        require(all(type(value) is int and value >= 0 for value in values),
                'atime inventory contains invalid nanoseconds')
        self.supervisor.verify_stopped(self.layout.binding())
        names = sorted(rows)
        # Reverse lexical order puts every descendant before its parent.
        for index in range(len(names) - 1, -1, -1):
            name, value = names[index], values[index]
            target = self.layout.tree / name
            os.utime(target, ns=(value, rows[name]['mtime_ns']), follow_symlinks=False)
            info = target.lstat()
            require(info.st_atime_ns == value and info.st_mtime_ns == rows[name]['mtime_ns'],
                    'filesystem cannot restore exact archived timestamps')
        return {'archived_atime_restored': True,
                'archived_atime_sha256': atime_binding(manifest_sha256, values),
                'original_source_atime_verified': False}

    def restore(self, capture):
        require(self.phase == "new" and not self.layout.tree.exists(), "initial restore needs a new empty generation")
        verified = self.authenticated(capture)
        self.supervisor.verify_stopped(None)
        self.capacity(verified, "initial-restore", sum(r["bytes"] for r in verified["entries"].values()
                                                      if r["kind"] == "file"))
        self.phase = "restoring"
        self.layout.tree.mkdir(parents=True, mode=0o700)
        self.materialize(verified, set(verified["entries"]))
        proof = verify_tree(self.layout, verified["entries"], self.sqlite_paths,
                            recorded_link_exceptions=capture_link_exceptions(verified))
        proof.update(self.restore_atimes(verified))
        self.rows, self.boundary = verified["entries"], verified
        self.checkpoint("restored", {**proof, "capture_id": capture, "source": self.source})
        self.phase = "restored"
        return proof

    def verify_initial_materialization(self, capture):
        """Adopt only a fully matching, stopped private tree without restoring it.

        A failed initial verifier can leave all bytes materialized without a
        completed journal. Do not reconstruct that attempt or trust its result.
        Authenticate B anew and verify every current file, database and metadata
        relationship under held ownership. Partial/corrupt data remain held;
        no file is repaired, overwritten, removed or chmodded here. This new
        verification journal confers no rehearsal or operational acceptance.
        """
        require(self.phase == 'new' and self.layout.tree.is_dir(),
                'initial materialization requires a new verifier and retained tree')
        require(not self.layout.evidence.exists() or not any(self.layout.evidence.iterdir()),
                'retained journal requires explicit completed-operation recovery')
        binding = self.layout.binding()
        self.supervisor.verify_stopped(binding)
        verified = self.authenticated(capture)
        self.capacity(verified, 'initial-materialization-verification', 0)
        proof = verify_tree(self.layout, verified['entries'], self.sqlite_paths,
                            recorded_link_exceptions=capture_link_exceptions(verified))
        require(self.layout.binding() == binding, 'materialized root changed during verification')
        proof.update(self.restore_atimes(verified))
        self.supervisor.verify_stopped(binding)
        self.rows, self.boundary = verified['entries'], verified
        self.checkpoint('initial-materialization-verified', {**proof,
            'capture_id': capture, 'source': self.source, 'scope': self.scope,
            'prior_attempt_reconstructed': False, 'restored_again': False,
            'rehearsal_accepted': False, 'activation_authorized': False})
        self.phase = 'restored'
        return proof

    def accept_rehearsal(self):
        require(self.phase == "restored", "candidate is not restored")
        self.supervisor.verify_stopped(self.layout.binding())
        test_rows = validate_manifest(inventory(self.layout.tree),
                                     recorded_link_exceptions=capture_link_exceptions(self.boundary))
        verify_sqlite(self.layout.tree, self.sqlite_paths)
        proof = {"root_binding": self.layout.binding(), "manifest_sha256": digest(test_rows)}
        receipt = self.supervisor.acceptance(self.layout.binding(), self.source, self.scope, "rehearsal")
        self.accepted(receipt, proof, "rehearsal", self.boundary["capture_id"])
        self.test_receipt = receipt
        self.checkpoint("rehearsal", receipt)
        self.phase = "tested"

    def bootstrap_identity(self, database_virtual, workspace_virtual, dataset_id):
        """Explicit candidate-only schema seed; never enroll the incumbent.

        Rehearsal enrollment is a test edit and final catch-up quarantines it.
        Enrollment after final catch-up blocks promotion until an authenticated
        fresh B capture contains this exact, stopped candidate generation.
        """
        require(self.phase in ("restored", "refreshed"), "identity bootstrap lacks a stopped prepared generation")
        prior_phase = self.phase
        self.supervisor.verify_stopped(self.layout.binding())
        if prior_phase == "refreshed":
            self.supervisor.verify_fence(self.boundary)
        require(isinstance(dataset_id, str) and len(dataset_id) == 32
                and all(c in "0123456789abcdef" for c in dataset_id), "invalid explicit dataset identity")
        bindings = binding_environment(self.layout, {"database": database_virtual, "workspaces": workspace_virtual},
                                       preserved_capture=self.boundary)
        name = bindings["selectors"]["database"]["resolved_virtual"].lstrip("/")
        require(name in self.sqlite_paths and self.rows[name]["kind"] == "file",
                "bootstrap database is outside authenticated required snapshots")
        path = Path(bindings["selectors"]["database"]["backing"])
        require(path.stat().st_nlink == 1, "bootstrap database has external/other aliases")
        with open_regular(self.layout.tree, name) as stream:
            require(hashlib.file_digest(stream, "sha256").hexdigest() == self.rows[name]["sha256"],
                    "bootstrap database changed since authenticated restore")
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
            require(not db.execute("SELECT 1 FROM sqlite_master WHERE name='vk_runtime_identity'").fetchall(),
                    "existing dataset identity must be retained, not replaced")
        require(not any(os.path.lexists(str(path) + s) for s in ("-wal", "-shm", "-journal")),
                "bootstrap database has live bookkeeping files")
        before = path.stat()
        self.checkpoint("identity-bootstrap-intent", {"root_binding": self.layout.binding(),
            "source": self.source, "capture_id": self.boundary["capture_id"],
            "prior_manifest_sha256": digest(self.rows), "database": name,
            "dataset_id_sha256": hashlib.sha256(dataset_id.encode()).hexdigest(),
            "original_source_enrolled": False})
        self.phase = "bootstrapping-identity"
        # Only this missing table is created. There is no startup auto-enrollment
        # or token overwrite path, and all original application tables survive.
        with closing(sqlite3.connect(path)) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE vk_runtime_identity (singleton INTEGER PRIMARY KEY CHECK (singleton = 1), "
                       "dataset_id TEXT NOT NULL UNIQUE)")
            db.execute("INSERT INTO vk_runtime_identity(singleton,dataset_id) VALUES(1,?)", (dataset_id,))
            db.commit()
        after = path.stat()
        require((before.st_dev, before.st_ino, before.st_uid, before.st_gid, before.st_mode)
                == (after.st_dev, after.st_ino, after.st_uid, after.st_gid, after.st_mode),
                "bootstrap changed database identity/ownership/mode")
        require(not any(os.path.lexists(str(path) + s) for s in ("-wal", "-shm", "-journal")),
                "bootstrap left unnormalized SQLite bookkeeping")
        self.supervisor.verify_stopped(self.layout.binding())
        if prior_phase == "refreshed":
            self.supervisor.verify_fence(self.boundary)
        identity = namespace_runtime_identity(self.layout, database_virtual, workspace_virtual,
                                               preserved_capture=self.boundary)
        self.bootstrap_rows = inventory(self.layout.tree)
        self.checkpoint("identity-bootstrap", {"root_binding": self.layout.binding(),
            "prior_capture_id": self.boundary["capture_id"], "database": name,
            "new_manifest_sha256": digest(self.bootstrap_rows), "runtime_identity_sha256": identity["sha256"],
            "original_source_enrolled": False, "fresh_B_capture_required_before_promotion": True})
        self.phase = "restored" if prior_phase == "restored" else "needs-bootstrap-backup"
        return identity

    def accept_bootstrap_capture(self, capture):
        require(self.phase == "needs-bootstrap-backup", "bootstrap backup lacks a pending tracked transformation")
        self.supervisor.verify_stopped(self.layout.binding())
        verified = self.authenticated(capture, frozen=True)
        require(capture != self.boundary["capture_id"]
                and verified["origin_root_binding"] == self.layout.binding(),
                "bootstrap backup is stale or from different roots")
        require(verified["entries"] == self.bootstrap_rows, "bootstrap capture differs from tracked candidate state")
        proof = verify_tree(self.layout, verified["entries"], self.sqlite_paths,
                            recorded_link_exceptions=capture_link_exceptions(verified))
        proof.update(self.restore_atimes(verified))
        self.rows, self.boundary = verified["entries"], verified
        self.checkpoint("identity-bootstrap-backed-up", {**proof, "capture_id": capture,
                        "source": self.source, "scope": self.scope})
        self.phase = "refreshed"
        return proof

    def catch_up(self, capture):
        require(self.phase == "tested", "final refresh requires accepted rehearsal")
        self.supervisor.verify_stopped(self.layout.binding())
        verified = self.authenticated(capture, frozen=True)
        require(capture != self.boundary["capture_id"], "stale initial capture cannot be promoted")
        return self._refresh(verified)

    def _refresh(self, verified):
        """Apply only an authenticated stopped/fenced generation; retain every displaced path."""
        require(self.phase in ("tested", "active"), "refresh lacks a tested/tracked owner")
        capture = verified["capture_id"]
        current, expected = inventory(self.layout.tree), verified["entries"]
        changed = {p for p in current.keys() | expected.keys() if current.get(p) != expected.get(p)}
        # Directory mtime alone does not require moving/restreaming an unchanged subtree.
        changed = {p for p in changed if not (current.get(p, {}).get("kind") == "directory"
                   and expected.get(p, {}).get("kind") == "directory"
                   and {k: v for k, v in current[p].items() if k != "mtime_ns"}
                   == {k: v for k, v in expected[p].items() if k != "mtime_ns"})}
        # Never leave an unchanged alias linked to quarantined historical bytes.
        groups = []
        for rows in (current, expected):
            linked = {}
            for p, row in rows.items():
                if row["kind"] in ("file", "hardlink"):
                    linked.setdefault(row.get("target", p), set()).add(p)
            groups.extend(linked.values())
        # Close directory moves and cross-subtree hardlinks together. A mode0555
        # child retains its inode, permissions and '..' inside a writable ancestor
        # moved as one unit. No denied child rename or chmod is attempted.
        previous = None
        while previous != changed:
            previous = set(changed)
            for name in list(changed):
                for parent in [relative(name), *relative(name).parents]:
                    p = str(parent)
                    row = current.get(p, {})
                    if row.get("kind") != "directory":
                        continue
                    writable = row["mode"] & 0o300 == 0o300 and os.access(
                        self.layout.tree / p, os.W_OK | os.X_OK, effective_ids=True)
                    if writable:
                        continue
                    ancestor = next((str(q) for q in parent.parents if str(q) != "."
                        and current.get(str(q), {}).get("kind") == "directory"
                        and current[str(q)]["mode"] & 0o300 == 0o300
                        and os.access(self.layout.tree / str(q), os.W_OK | os.X_OK, effective_ids=True)), None)
                    require(ancestor is not None,
                            "changed read-only directory has no writable ancestor below candidate root; approval/strategy required")
                    changed.add(ancestor)
            containers = {p for p in changed if current.get(p, {}).get("kind") == "directory"}
            tops = sorted(p for p in containers if not any(p.startswith(q + "/") for q in containers if q != p))
            for top in tops:
                changed.update(p for p in current.keys() | expected.keys() if p.startswith(top + "/"))
            for group in groups:
                if changed & group:
                    changed.update(group)
        self.capacity(verified, "fenced-refresh", sum(expected[p]["bytes"] for p in changed & expected.keys()
                                                     if expected[p]["kind"] == "file"))
        self.phase = "refreshing"
        quarantine = self.layout.evidence / f"{self.sequence + 1:04d}-test-and-prior-state"
        quarantine.mkdir()
        self.checkpoint("refresh-intent", {"capture_id": capture, "old_inventory": current,
                        "expected_manifest_sha256": digest(expected), "changed_paths": sorted(changed),
                        "quarantine": str(quarantine)})
        self.supervisor.verify_stopped(self.layout.binding())
        self.supervisor.verify_fence(verified)
        # Deepest files first, except complete containers which retain all descendants.
        moves = [p for p in changed & current.keys() if not any(p.startswith(q + "/") for q in tops)]
        for name in sorted(moves, key=lambda p: (-len(relative(p).parts), p)):
            destination = quarantine / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            require(not destination.exists() and not destination.is_symlink(), "quarantine collision")
            (self.layout.tree / name).rename(destination)
        sync_tree_directories(quarantine)
        sync_directory(quarantine.parent)
        self.materialize(verified, changed & expected.keys())
        self.supervisor.verify_fence(verified)
        proof = verify_tree(self.layout, expected, self.sqlite_paths,
                            recorded_link_exceptions=capture_link_exceptions(verified))
        proof.update(self.restore_atimes(verified))
        self.rows, self.boundary = expected, verified
        self.checkpoint("refreshed", {**proof, "capture_id": capture, "quarantine": str(quarantine)})
        self.phase = "refreshed"
        return proof

    def promote(self):
        require(self.phase == "refreshed", "final fenced catch-up required")
        self.supervisor.verify_stopped(self.layout.binding())
        self.supervisor.verify_fence(self.boundary)
        proof = verify_tree(self.layout, self.rows, self.sqlite_paths,
                            recorded_link_exceptions=capture_link_exceptions(self.boundary))
        proof.update(self.restore_atimes(self.boundary))
        receipt = self.supervisor.acceptance(self.layout.binding(), self.source, self.scope, "activation")
        self.accepted(receipt, proof, "activation", self.boundary["capture_id"])
        # Recheck the volatile fence immediately before giving ownership to the adapter.
        self.supervisor.verify_fence(self.boundary)
        self.phase = "activating"
        self.checkpoint("activation-intent", {**proof, "capture_id": self.boundary["capture_id"],
                        "acceptance": receipt})
        self.supervisor.verify_stopped(self.layout.binding())
        self.supervisor.verify_fence(self.boundary)
        self.owner_receipt = self.supervisor.activate_candidate(proof, receipt)
        require(self.owner_receipt["root_binding"] == proof["root_binding"], "activated different roots")
        self.checkpoint("activated", {**proof, "owner": self.owner_receipt})
        self.phase = "active"
        return self.owner_receipt

    def fallback(self, latest_capture):
        require(self.phase == "active", "fallback requires a tracked candidate owner")
        self.supervisor.verify_stopped(self.layout.binding())
        latest = self.authenticated(latest_capture, frozen=True)
        require(latest["origin_root_binding"] == self.layout.binding(), "fallback capture is stale incumbent state")
        require(latest_capture != self.boundary["capture_id"], "fresh post-write fallback capture required")
        # Backup snapshots may normalize/checkpoint SQLite differently from the
        # stopped live files. Reconcile against that latest authenticated capture,
        # retaining old mains/WALs/test files rather than falling back to old data.
        proof = self._refresh(latest)
        receipt = self.supervisor.acceptance(self.layout.binding(), self.source, self.scope, "latest-data-fallback")
        self.accepted(receipt, proof, "latest-data-fallback", latest_capture)
        self.supervisor.verify_fence(latest)
        self.phase = "falling-back"
        self.checkpoint("fallback-intent", {**proof, "capture_id": latest_capture, "acceptance": receipt})
        self.supervisor.verify_stopped(self.layout.binding())
        self.supervisor.verify_fence(latest)
        owner = self.supervisor.activate_compatible_fallback(proof, receipt)
        require(owner["root_binding"] == proof["root_binding"], "fallback redirected to stale roots")
        self.checkpoint("latest-data-fallback", {**proof, "capture_id": latest_capture, "owner": owner})
        self.phase = "fallback"
        return owner

    def cleanup(self):
        raise Blocked("Cleanup remains unavailable; human QA and separate scoped implementation are required")
