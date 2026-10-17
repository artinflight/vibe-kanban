#!/usr/bin/env python3
"""Tiny measured reuse workflow; no compiler, provider calls or production writes."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from vk_prepare import Preparation
from vk_prep_common import storage


COMMAND = r'''
import hashlib,json,os,sys
from pathlib import Path
step=sys.argv[1];root=Path(os.environ['USAGE_OUTPUT'])
source=Path('fixture.json').read_bytes();value=json.loads(source)
assert value['schema']==1 and value['history']=='preserve complete sessions'
assert value['validation']=='unchanged' and value['model']=='unchanged'
bound={'source_sha256':hashlib.sha256(source).hexdigest(),'value':value['value']}
if step=='validate':(root/'validated.json').write_text(json.dumps(bound,sort_keys=True))
elif step=='build':
 assert json.loads((root/'validated.json').read_text())==bound
 (root/'artifact.json').write_text(json.dumps(bound,sort_keys=True))
else:assert json.loads((root/'artifact.json').read_text())==bound
with Path(os.environ['USAGE_EVENTS']).open('a') as log:log.write(step+'\n')
'''


def benchmark(root, repository=None):
    root = storage(root)
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="usage-fixture-", dir=root) as temporary:
        fixture = Path(temporary)
        source = fixture / "source"
        source.mkdir()
        subprocess.run(["git", "init", "-q", str(source)], check=True)
        for key, value in (("user.name", "Usage fixture"), ("user.email", "fixture@example.invalid")):
            subprocess.run(["git", "-C", str(source), "config", key, value], check=True)
        outputs = fixture / "outputs"
        outputs.mkdir()
        events = fixture / "events"
        steps = [
            {"id": "validate", "command": [sys.executable, "-c", COMMAND, "validate"],
             "outputs": [str(outputs / "validated.json")], "cacheable": True},
            {"id": "build", "command": [sys.executable, "-c", COMMAND, "build"],
             "outputs": [str(outputs / "artifact.json")], "depends_on": ["validate"], "cacheable": True},
            {"id": "fresh", "command": [sys.executable, "-c", COMMAND, "fresh"],
             "depends_on": ["build"], "volatile": True, "cacheable": False},
        ]
        plan = {"environment": {"USAGE_OUTPUT": str(outputs), "USAGE_EVENTS": str(events)}, "steps": steps}
        modes = {}
        for mode in ("always_rerun", "fingerprinted_reuse"):
            selected = copy.deepcopy(plan)
            if mode == "always_rerun":
                for step in selected["steps"]:
                    step["cacheable"] = False
            events.write_text("")
            requests = []
            for phase, value in (("cold", "first"), ("identical_repeat", "first"), ("changed_input", "changed")):
                data = {"schema": 1, "value": value, "history": "preserve complete sessions",
                        "validation": "unchanged", "model": "unchanged"}
                (source / "fixture.json").write_text(json.dumps(data, sort_keys=True))
                subprocess.run(["git", "-C", str(source), "add", "."], check=True)
                subprocess.run(["git", "-C", str(source), "commit", "--allow-empty", "-qm", "fixture"], check=True)
                before = len(events.read_text().splitlines())
                result = Preparation(source, fixture / mode, selected).run()
                requests.append({"phase": phase, "passed": result["passed"],
                                 "launches": len(events.read_text().splitlines()) - before,
                                 "reused": [name for name, row in result["steps"].items() if row["reused"]],
                                 "artifact_sha256": hashlib.sha256((outputs / "artifact.json").read_bytes()).hexdigest()})
            calls = events.read_text().splitlines()
            modes[mode] = {"requests": requests, "step_launches": len(calls), "fresh_checks": calls.count("fresh")}
        for before, after in zip(modes["always_rerun"]["requests"], modes["fingerprinted_reuse"]["requests"]):
            if not before["passed"] or not after["passed"] or before["artifact_sha256"] != after["artifact_sha256"]:
                raise ValueError("Workflow acceptance changed")
        report = {"schema": 1, "fixture_only": True, "models_changed": False,
                  "provider_calls": {"before": 0, "after": 0}, "native_model_savings_proved": False,
                  "same_command_sha256": hashlib.sha256(COMMAND.encode()).hexdigest(), "modes": modes}
        if repository:
            repository = Path(repository)
            manifest = json.loads((repository / "CONTINUITY_ARCHIVE.json").read_text())
            before = sum(row["bytes"] for row in manifest["archives"])
            after = sum((repository / row["original"]).stat().st_size for row in manifest["archives"])
            report["pickup"] = {"before_bytes": before, "after_bytes": after, "fewer_bytes": before - after,
                                "reduction_percent": 100 * (before - after) / before,
                                "historical_bytes_preserved": before,
                                "relevant_topic_reads_additional": True, "billed_token_savings": None}
            common = ["VK_RESTART_QUEUE_WAKEUP.md", "scripts/deployment/vk_prepare.py",
                      "scripts/deployment/vk_prep_common.py", "scripts/deployment/test_vk_preparation.py"]
            common_bytes = sum(len((repository / name).read_bytes()) for name in common)
            report["representative_input"] = {
                "common_reads": {name: hashlib.sha256((repository / name).read_bytes()).hexdigest() for name in common},
                "common_bytes": common_bytes, "before_bytes": before + common_bytes,
                "after_bytes": after + common_bytes, "fewer_bytes": before - after,
                "measurement": "UTF-8 file bytes for the same recipe; not provider tokens"}
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--repository", type=Path)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.root, args.repository), indent=2))


if __name__ == "__main__":
    main()
