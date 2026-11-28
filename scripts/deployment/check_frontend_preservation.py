"""Reject frontend candidates that omit live source changes outside a reviewed scope."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check(live_artifact, live_source, candidate_source, changed_paths):
    rows = json.loads(Path(live_artifact).read_text())['source_files']
    allowed = set(changed_paths)
    known = set()
    unexpected = []
    changed = []
    for row in rows:
        relative = Path(row['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Source manifest contains an unsafe relative path')
        name = str(relative)
        known.add(name)
        previous = Path(live_source) / relative
        candidate = Path(candidate_source) / relative
        if previous.is_symlink() or digest(previous) != row['sha256']:
            raise ValueError('Live source differs from its pinned artifact: ' + name)
        differs = (candidate.is_symlink() or not candidate.is_file()
                   or digest(candidate) != row['sha256'])
        if differs:
            changed.append(name)
            if name not in allowed:
                unexpected.append(name)
    if allowed - known:
        raise ValueError('Changed-path scope must name pinned live inputs')
    return dict(passed=not unexpected, compared=len(rows),
                reviewed_changed_paths=sorted(allowed),
                changed_paths=sorted(changed),
                unexpected_changed_paths=sorted(unexpected))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-artifact', type=Path, required=True)
    parser.add_argument('--live-source', type=Path, required=True)
    parser.add_argument('--candidate-source', type=Path, required=True)
    parser.add_argument('--changed-path', action='append', default=[])
    args = parser.parse_args()
    result = check(args.live_artifact, args.live_source,
                   args.candidate_source, args.changed_path)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
