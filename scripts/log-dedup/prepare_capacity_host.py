"""Create an inert corrected host helper; never edit or launch an old package."""
import argparse
import hashlib
import json
import os
from pathlib import Path

BASE_SHA256 = '6496ebb5bdba7870b0db0c279e06a6651f1d3bbc0cc4c99860ada399d8242a2b'


def patched_source(raw):
    if hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise ValueError('Qualified original host source required')
    text = raw.decode()
    start = text.index("  self.record('releasing_authenticated_capacity'")
    end = text.index('  for name in [PROXY,READER,MAIN]:', start)
    text = text[:start] + (
        "  release_guard=load(self.config['capacity_release_source'],'qualified_capacity_release')\n"
        "  released=release_guard.release(self,status)\n"
    ) + text[end:]
    start = text.index("  if self.data['released']is None:", text.index(' def recover_boundary('))
    text = text[:start] + (
        "  if self.data['released']is None and self.data.get('capacity_release_intent')is not None:\n"
        "   release_guard=load(self.config['capacity_release_source'],'qualified_capacity_reconcile')\n"
        "   release_guard.reconcile(self)\n"
    ) + text[start:]
    compile(text, 'host_boundary.py', 'exec')
    return text.encode()


def prepare(source, output):
    host = patched_source(Path(source).read_bytes())
    helper = Path(__file__).with_name('capacity_release.py').read_bytes()
    output = Path(output)
    output.mkdir(mode=0o700)
    refs = {}
    for name, raw in [('host_boundary.py', host), ('capacity_release.py', helper)]:
        path = output / name
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o400)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        refs[name] = dict(path=str(path.resolve()), bytes=len(raw),
                          sha256=hashlib.sha256(raw).hexdigest())
    result = dict(state='inert_not_armed', source_sha256=BASE_SHA256,
                  host_source=refs['host_boundary.py'],
                  capacity_release_source=refs['capacity_release.py'])
    with (output / 'PREPARED.private.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output), indent=2))
