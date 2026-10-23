#!/usr/bin/env python3
"""Render a review candidate outside .github. Never install or activate it."""
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
READY = "(github.event_name != 'pull_request' || github.event.pull_request.draft == false)"
EVENTS = """  pull_request:
    branches: [staging, main]
    types: [opened, reopened, synchronize, ready_for_review, converted_to_draft, edited]
"""


def render(source, spec):
    # Keep original commands, manual inputs, push/release behavior and actions.
    source = re.sub(r"^  pull_request:\n(?:^    .*\n|^\n)*", EVENTS,
                    source, count=1, flags=re.M)
    prefix, jobs = source.split("\njobs:\n", 1)
    prefix = re.sub(r"^permissions:\n(?:^  .*\n)+", "", prefix, flags=re.M)
    prefix += "\npermissions:\n  contents: read\n  pull-requests: read\n"
    # Retain cancellation of superseded PRs; never cancel protected-branch work.
    if "\nconcurrency:" not in prefix:
        prefix += "\nconcurrency:\n  group: ${{ github.workflow }}-${{ github.ref }}\n  cancel-in-progress: ${{ github.event_name == 'pull_request' }}\n"
    blocks = re.split(r"(?=^  [a-z][a-z0-9-]*:\n)", jobs, flags=re.M)
    output = []
    for block in blocks:
        if not block.strip():
            continue
        job = block.split(":", 1)[0].strip()
        if job not in spec["required_jobs"]:
            output.append(block)  # Existing operator-only artifact build.
            continue
        match = re.search(r"^    if: (.*)\n((?:^      .*\n)*)", block, re.M)
        if match:
            old = match[1]
            if old == ">-":
                old = " ".join(line.strip() for line in match[2].splitlines())
            block = block[:match.start()] + f"    if: {READY} && ({old})\n" + block[match.end():]
        else:
            block = block.replace(f"  {job}:\n", f"  {job}:\n    if: {READY}\n", 1)
        if job == "changes":
            # Final validation exercises every existing suite, including remote
            # and desktop; path filters must not turn missing tests green.
            block = re.sub(r"(      [\w-]+: )\$\{\{ (steps.filter.outputs.*?) \}\}",
                           r"\1${{ github.event_name == 'pull_request' && 'true' || \2 }}", block)
        if job == "branch-policy":
            block = block.replace(
                '        run: node scripts/check-branch-policy.mjs "${{ github.base_ref }}" "${{ github.head_ref }}"',
                '        env:\n          VK_CI_BASE_BRANCH: ${{ github.base_ref }}\n          VK_CI_HEAD_BRANCH: ${{ github.head_ref }}\n'
                '        run: node scripts/check-branch-policy.mjs "$VK_CI_BASE_BRANCH" "$VK_CI_HEAD_BRANCH"',
            )
        if job == "backend-remote-checks":
            block = block.replace("Skip backend remote checks without deploy key", "Require private dependency access")
            block = block.replace('run: echo "::notice::VK_PRIVATE_DEPLOY_KEY is not configured; skipping backend remote checks that require private dependencies."',
                                  'run: echo "::error::Private dependency access is required for real remote checks."; exit 1')
        if job == "ops-governance":
            block = block.rstrip() + """

      - name: Test checkpoint CI policy
        run: |
          python3 -m pip install --disable-pip-version-check --no-cache-dir 'PyYAML==6.0.1'
          python3 -B -m unittest discover -s scripts/ci/checkpoint_policy -p 'test_*.py' -v

"""
        # Artifact exporters must name the tested merge tree, rather than an
        # untested head-only tree. Branch-freshness intentionally checks HEAD.
        block = block.replace("${{ github.event.pull_request.head.sha || github.sha }}", "${{ github.sha }}")
        output.append(block)
    expected = json.dumps(spec["required_jobs"], separators=(",", ":"))
    # A dispatch/push must never create a skipped/successful required PR context
    # on the same source SHA. GitHub accepts skipped required checks as green.
    output.append(f"""
  checkpoint-result:
    name: ${{{{ github.event_name == 'pull_request' && '{spec['context']}' || 'Non-PR / {spec['context']}' }}}}
    if: always()
    needs: {expected}
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    permissions:
      contents: read
      pull-requests: read
    steps:
      - uses: actions/checkout@v6
        with:
          persist-credentials: false
      - name: Require real tests on the current source and base
        if: github.event_name == 'pull_request'
        env:
          GH_TOKEN: ${{{{ github.token }}}}
          VK_CI_REQUIRED_JOBS: '{expected}'
          VK_CI_RESULTS: ${{{{ toJSON(needs) }}}}
        run: python3 -B scripts/ci/checkpoint_policy/verify_result.py
""")
    return prefix + "\njobs:\n" + "".join(output)


def candidate(name, spec):
    baseline = (HERE / "baseline" / name).read_bytes()
    if hashlib.sha256(baseline).hexdigest() != spec["source_sha256"]:
        raise ValueError(f"{name}: reviewed baseline changed")
    generated = render(baseline.decode(), spec)
    active = (ROOT / ".github/workflows" / name).read_bytes()
    if active not in (baseline, generated.encode()):
        raise ValueError(f"{name} changed: re-review the current base before regenerating")
    return generated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve()
    # No live/workspace workflow writes, including through a symlink.
    if target == ROOT or ROOT in target.parents and target.parts[len(ROOT.parts)] == ".github":
        parser.error("render outside .github; installation needs separate owner authorization")
    policy = json.loads((HERE / "policy.json").read_text())
    candidates = {}
    for name, spec in policy["workflows"].items():
        try:
            candidates[name] = candidate(name, spec)
        except ValueError as error:
            parser.error(str(error))
    target.mkdir(parents=True, exist_ok=True)
    for name, source in candidates.items():
        path = target / name
        if path.is_symlink():
            parser.error("refusing symlink output")
        path.write_text(source)
    print(json.dumps({"state": "prepared_only", "workflows": sorted(candidates)}))


if __name__ == "__main__":
    main()
