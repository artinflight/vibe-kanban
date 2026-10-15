"""Prepare a reviewable connector candidate; never install/restart live services."""
import argparse
import hashlib
from pathlib import Path
import shutil


def patched(source):
    # The live ca3fe817 capacity correction must remain byte-for-byte intact.
    if '"connector_queued_for_capacity"' not in source or '"execution_capacity"' not in source:
        raise ValueError("Required ca3fe817 queued-capacity correction is missing")
    if "import steering" in source:
        raise ValueError("Steering already integrated; reconcile the candidate manually")
    anchors = [
        ("import approval_notifications\n", "import approval_notifications\nimport steering\n"),
        (" + approval_notifications.TOOLS}}", " + approval_notifications.TOOLS + steering.TOOLS}}"),
        ('            if name == "run_session_prompt":',
         '            if name in steering.HANDLERS:\n'
         '                return {"jsonrpc":"2.0","id":msg["id"],"result":steering.HANDLERS[name](sys.modules[__name__],args)}\n'
         '            if name == "run_session_prompt":'),
    ]
    for before, after in anchors:
        if source.count(before) != 1:
            raise ValueError("Connector changed; review integration anchors before preparation")
        source = source.replace(before, after)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.adapter.read_bytes()
    if hashlib.sha256(source).hexdigest() != args.expected_sha256:
        parser.error("Adapter baseline changed; reread and coordinate with its owner")
    candidate = patched(source.decode())
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "adapter.py").write_text(candidate)
    shutil.copyfile(Path(__file__).with_name("steering.py"), args.output / "steering.py")
    print("Prepared candidate only; production files and services are unchanged.")


if __name__ == "__main__":
    main()
