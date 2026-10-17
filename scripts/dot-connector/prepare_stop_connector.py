"""Prepare an additive exact-stop overlay against a pinned adapter; never install."""
import argparse
import hashlib
from pathlib import Path
import shutil


def patched(source):
    if "import stop_control" in source:
        raise ValueError("Stop already integrated; reconcile its owner baseline")
    if '"connector_queued_for_capacity"' not in source or "sidechat_connector.TOOLS" not in source:
        raise ValueError("Required capacity and sidechat integrations are missing")
    replacements = [
        ("import sidechat_connector\n", "import sidechat_connector\nimport stop_control\n"),
        (" + sidechat_connector.TOOLS", " + stop_control.TOOLS + sidechat_connector.TOOLS"),
        ('            if name in sidechat_connector.NAMES:',
         '            if name in stop_control.HANDLERS:\n'
         '                return {"jsonrpc":"2.0","id":msg["id"],"result":stop_control.HANDLERS[name](sys.modules[__name__],args)}\n'
         '            if name in sidechat_connector.NAMES:'),
        ("no deletion/stopping/admin tools.",
         "No deletion/admin tools. Exact stop_agent_execution requires explicit owner authorization or CU-verified budget exhaustion; never use workspace Stop or shell as a fallback."),
    ]
    for before, after in replacements:
        if source.count(before) != 1:
            raise ValueError("Adapter changed; reconcile exact stop integration anchors")
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
        parser.error("Adapter baseline changed; coordinate before overwriting anything")
    candidate = patched(source.decode())
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "adapter.py").write_text(candidate)
    shutil.copyfile(Path(__file__).with_name("stop_control.py"), args.output / "stop_control.py")
    print("Prepared stop overlay only; no service, live source or private state changed.")


if __name__ == "__main__":
    main()
