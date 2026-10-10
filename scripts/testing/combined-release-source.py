"""Fence the candidate to the deployed source plus reviewed capture, consent, mobile and assignment fixes."""
import hashlib
import json
from pathlib import Path
import subprocess

BASE = "5ce84ee21be814b1519cfb2715b50f3432c3e8ba"
BACKEND = "c3c48e6324f778ccd03a5761c2314b440e9ceac3"
REVIEWED = {
    "capture": "6e27580a4f38975f40326ba773e7f82a27384be6",
    "consent": "b5e49f393a419a03631cf71ddca74d52e08b9cdc",
}

JOINT_BASE = 'cdad6e956fd23f2a0810ff19e57d3eeab0b43a66'
CAPTURE_BASE = 'aa11dd6a5707bba400db2f893eebc857633be437'
ASSIGNMENT_PATCH_SHA256 = '2bf68d675423ee8803c994d54ab231e27d0af9ef5d6fdcfabbc2ed38a20252af'
MOBILE_FILES = ('packages/ui/src/components/ChatBoxBase.tsx', 'packages/ui/src/components/KanbanCardContent.tsx', 'packages/ui/src/components/SessionChatBox.tsx', 'packages/web-core/src/app/styles/new/index.css', 'packages/web-core/src/features/kanban/ui/KanbanContainer.tsx', 'packages/web-core/src/features/workspace-chat/model/hooks/usePromptSubmission.ts', 'packages/web-core/src/features/workspace-chat/ui/SessionChatBoxContainer.tsx', 'packages/web-core/src/shared/hooks/useMobileViewport.ts', 'scripts/testing/mobile-send-browser.mjs', 'scripts/testing/mobile-ux-browser.mjs', 'scripts/testing/prompt-submission-browser.tsx', 'scripts/testing/run-prompt-submission-browser.mjs')
ASSIGNMENT_FILES = {
    "crates/db/migrations/20261009000000_local_issue_assignments.sql": "308e0a6702e621943b2b9c1e7bb5e00712065e5c2c18bbcef4e5b942dcd946ec",
    "crates/db/src/models/local_issue_assignee.rs": "14dd636f2a00d67d8ed4e2e9fe72132cc146a2c67d14555ed05ac9f9ebde36de",
    "crates/db/src/models/mod.rs": "ffb212a7dd9b8d89837727dc890814d9311ce67744ddd4b7d472e08909400bfc",
    "crates/server/src/routes/local_assignments.rs": "3c131b569ec855417c6aa34a79e9057af10126a330cb4f404c0f00ea4ed1e3a1",
    "crates/server/src/routes/local_compat.rs": "5a51dbe3d494d188610de7a3bc24abe2e3288a79b62f094abbb01190a26be498",
    "crates/server/src/routes/mod.rs": "916a365864d55782ff60a1f71c4edc070c11cd771a60ce27e7730c28c3b17fef",
    "packages/ui/src/components/KanbanIssuePanel.tsx": "0b45ae395c1b34889c338427ee3a8a375e123fbcc4eda8d79308c880f005e895",
    "packages/ui/src/components/WorkspacesSidebar.tsx": "ea0d509a47f1fb8c0c28a2a48aa2debe342b3158ec04ec93445959b6e6635328",
    "packages/web-core/src/features/kanban/ui/KanbanContainer.tsx": "9664d9fe53ac03d3e8d6a4ad3ac569653119bc2190451ac33c2d90182f9f5527",
    "packages/web-core/src/i18n/locales/en/common.json": "394adafd8a7431fe9670fe00b500e315932edc072552746dd19f289d0882f67f",
    "packages/web-core/src/i18n/locales/es/common.json": "6c6c43977a85a116df0ee1aec4c2027f8aa192af54236882c0efd084e386cde7",
    "packages/web-core/src/i18n/locales/fr/common.json": "5c033e723c4ba28700ada4e72843f4b0a937e1deff486d054e764f4154f09869",
    "packages/web-core/src/i18n/locales/ja/common.json": "91e7a0cb378721d1b5f1b0ec0bd929afb9c75678d7a1e8007c8beef324b9ac8d",
    "packages/web-core/src/i18n/locales/ko/common.json": "8a02778cb572f37e2c3848aa64b1da77dd4d21e0dd2864071624719ac2a9fba0",
    "packages/web-core/src/i18n/locales/zh-Hans/common.json": "c79d2f52b4bd7b70b80573dd84c004f43c311ae42c234cc43c0f3125e5e8897d",
    "packages/web-core/src/i18n/locales/zh-Hant/common.json": "6ff57218a502cbd2c28eb49216aab078c1c2bc77f76ad28b77292a8ab1a9d0b6",
    "packages/web-core/src/pages/kanban/KanbanIssuePanelContainer.tsx": "f3d27a2c02e392de584a718d1fd99d2e02d6da7bfc0a5c22d8d66ad2a3919bd8",
    "packages/web-core/src/pages/kanban/LocalProjectKanban.tsx": "0fd5d136d1c8bc10e01767645f0862624827d63d16039a3023c82b91294fd786",
    "packages/web-core/src/pages/kanban/ProjectKanban.tsx": "e1b5b503f1ffe860c4c5bf60999e805ffddce5e8eee9e336fc95b309c379f340",
    "packages/web-core/src/pages/kanban/ProjectRightSidebarContainer.tsx": "78b7c22e71fdbdc04b44d80233dcd30cff54ffd1d8fa3a5f718faf4df11552a9",
    "packages/web-core/src/pages/workspaces/WorkspacesSidebarContainer.tsx": "ba541e46834442e7affce2b5ebc93dedb58857ea193abccf06b8b3559e6f641d",
    "packages/web-core/src/pages/workspaces/workspaceAssignmentFilter.test.ts": "b9c9c50667a0b542513f8ff338b2501be3c13cfade5009addbdcffd9aa534995",
    "packages/web-core/src/pages/workspaces/workspaceAssignmentFilter.ts": "26671c49e428e89f39f6d80b54a8bf27130f3939353df969b113046191ec9196",
    "packages/web-core/src/shared/dialogs/kanban/AssigneeSelectionDialog.tsx": "e1be439783a5fad8fb6264ec0a86115fa581690725348e86c775a6be606f5f5e",
    "packages/web-core/src/shared/hooks/useExpectedIssueOpen.ts": "d8a2eefad9b532afc4bd0d5b8d677c6ea3f8c1a79e89ea47399b94b2726cb111",
    "packages/web-core/src/shared/hooks/useKanbanIssueComposerScratch.ts": "01506aad9561af8dfd4e4942cb941af55052eea69eaa63f4407fadea9c8a3bf7",
    "packages/web-core/src/shared/hooks/useLocalParticipants.ts": "170a6af4de34f83a986e5f97f0282aecfc77664c60d383765ba089fb8e1be68c",
    "packages/web-core/src/shared/hooks/useProjectWorkspaceCreateDraft.ts": "22d38ed875d9e743885f526592030348833a289ddced25de3de8ec385ec4ba39",
    "packages/web-core/src/shared/lib/issueCreation.test.ts": "1c7068ab4ca54fdd6125dbde18900d28f5ac8cfd07a321a169e4e4911753a16a",
    "packages/web-core/src/shared/lib/issueCreation.ts": "181f95e7d3fa9d09725b6468c8412bb5ff22b24c7e67f82e6388cd0f9d39923b",
    "packages/web-core/src/shared/providers/remote/OrgProvider.tsx": "32e4220d145467c67795f8f51a22e2f897b7d09051077704fe92c84c147b6ac5",
    "packages/web-core/src/shared/stores/useKanbanIssueComposerStore.ts": "1ec8d68f7702ff447db0a9895b18dcb01355347c64b9c13525a8a4a3060083e3",
    "scripts/testing/kanban-issue-panel.fixture.tsx": "789b29989fc07ad596123d29f0f1fdba92443191d0cbd69554a9d86c7928b496",
    "scripts/testing/kanban-issue-panel.test.tsx": "1cb10f2e559488719b4f05a10b8228d9e5cdcf708c0b133f84116d1445d430be",
    "scripts/testing/run-kanban-issue-panel-tests.mjs": "617483d9940ddf304e5a9d6691770f42a2037ced493d08ca9af3280e46033500"
}
PREPARATION_FILES = {".github/workflows/test.yml", "scripts/testing/combined-release-source.py", "scripts/build-combined-capture-consent.py"}


def git(*args):
    return subprocess.check_output(["git", *args])


def blob(ref, path):
    return git("show", f"{ref}:{path}")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_capture_assignment_base():
    approved = {}
    for ref in REVIEWED.values():
        names = git("diff", "--name-only", BACKEND, ref).decode().splitlines()
        for name in names:
            if name.startswith(("crates/", "packages/", "scripts/testing/")):
                assert name not in approved, f"Overlapping reviewed changes: {name}"
                approved[name] = ref
    assert len(approved) == 21
    extra = {
        ".github/workflows/test.yml", "HANDOFF.md", "STREAM.md",
        "handoffs/e3e1-combined-capture-consent.md",
        "VK_COMBINED_CAPTURE_CONSENT_20261010.md",
        "scripts/testing/combined-release-source.py",
        "scripts/build-combined-capture-consent.py",
        "crates/server/tests/fixtures/c3_strict_log_reader.rs",
    }
    changed = set(git("diff", "--name-only", BASE, "HEAD").decode().splitlines())
    changed.update(git("diff", "--name-only", "HEAD").decode().splitlines())
    assert changed <= set(approved) | extra | set(MOBILE_FILES) | set(ASSIGNMENT_FILES), f"Unapproved changes: {changed - set(approved) - extra - set(MOBILE_FILES) - set(ASSIGNMENT_FILES)}"
    for name, ref in approved.items():
        actual, expected = Path(name).read_bytes(), blob(JOINT_BASE if name in MOBILE_FILES else ref, name)
        if name == "crates/server/tests/report_review_integration.rs":
            assert actual.startswith(expected.rstrip()), "Existing writer acceptance was changed"
        else:
            assert actual == expected, f"Reviewed implementation changed: {name}"
    overlay = git("diff", "--name-only", BACKEND, BASE).decode().splitlines()
    live_code = [name for name in overlay if name.startswith(("packages/", "scripts/"))]
    for name in live_code:
        if name in ASSIGNMENT_FILES:
            assert digest(Path(name).read_bytes()) == ASSIGNMENT_FILES[name], name
        else:
            assert Path(name).read_bytes() == blob(JOINT_BASE if name in MOBILE_FILES else BASE, name), f"Live-only source changed: {name}"
    # Reconcile the previous capture-only fence; never broadly allow a branch.
    assert set(git("diff", "--name-only", CAPTURE_BASE, JOINT_BASE).decode().splitlines()) == set(MOBILE_FILES)
    joint_changes = set(git("diff", "--name-only", JOINT_BASE, "HEAD").decode().splitlines())
    joint_changes.update(git("diff", "--name-only", "HEAD").decode().splitlines())
    assert joint_changes <= set(ASSIGNMENT_FILES) | PREPARATION_FILES, joint_changes
    for name, expected_sha in ASSIGNMENT_FILES.items():
        assert digest(Path(name).read_bytes()) == expected_sha, f"Assignment bytes changed: {name}"
    for name in MOBILE_FILES:
        if name not in ASSIGNMENT_FILES:
            assert Path(name).read_bytes() == blob(JOINT_BASE, name), f"Mobile bytes changed: {name}"
    # Keep the actual old reader function as a compiled, exact rollback fixture.
    reader = blob(BACKEND, "crates/utils/src/execution_logs.rs")
    reader = reader[reader.index(b"pub async fn read_execution_log_strict("):]
    assert Path("crates/server/tests/fixtures/c3_strict_log_reader.rs").read_bytes().endswith(reader)
    # No schema, permissions, routing, connector or dependency lock changes.
    for name in ("Cargo.toml", "Cargo.lock", "pnpm-lock.yaml", "shared/types.ts"):
        assert Path(name).read_bytes() == blob(BASE, name), name
    return {
        "sourceCommit": git("rev-parse", "HEAD").decode().strip(),
        "sourceTree": git("rev-parse", "HEAD^{tree}").decode().strip(),
        "base": BASE, "incumbentBackend": BACKEND, "reviewed": REVIEWED,
        "approvedFiles": sorted(approved),
        "jointBase": JOINT_BASE, "captureBase": CAPTURE_BASE,
        "assignmentPatchSha256": ASSIGNMENT_PATCH_SHA256,
        "assignmentFiles": ASSIGNMENT_FILES, "mobileFiles": sorted(MOBILE_FILES),
        "migrationSha256": ASSIGNMENT_FILES["crates/db/migrations/20261009000000_local_issue_assignments.sql"],
        "preservedLiveFiles": {name: digest(blob(BASE, name)) for name in live_code},
        "incumbentStrictReaderFunctionSha256": digest(reader),
    }


# The recovery owner tested this exact application tree on the accepted joint base.
# Packaging may change only this fence and the scoped hosted validation workflow.
RECOVERY_TESTED = "ae263d4730bf8cca33050bde85b1c3de305acec0"
RECOVERY_DELIVERED = "3a166309a09cf425c4d12a8cfcc9dfa7d9b9c368"
ACCEPTED_JOINT = "604285afbe9a8889aeff2c6a681bd3df998d3770"
PACKAGING_ONLY = {"scripts/testing/combined-release-source.py", ".github/workflows/test.yml"}


def verify():
    assert git("rev-parse", RECOVERY_TESTED + "^{tree}").decode().strip() == "c829e38881fb552dcf21770e60b84a57fcdaa86b"
    subprocess.run(["git", "merge-base", "--is-ancestor", ACCEPTED_JOINT, RECOVERY_DELIVERED], check=True)
    assert not git("diff", "--name-only", RECOVERY_TESTED, RECOVERY_DELIVERED, "--", "crates", "packages", "shared", "Cargo.toml", "Cargo.lock", "pnpm-lock.yaml").strip()
    changed = set(git("diff", "--name-only", RECOVERY_DELIVERED, "HEAD").decode().splitlines())
    changed.update(git("diff", "--name-only", "HEAD").decode().splitlines())
    assert changed <= PACKAGING_ONLY, f"Unreviewed source changes: {changed - PACKAGING_ONLY}"
    for path, expected in ASSIGNMENT_FILES.items():
        assert digest(Path(path).read_bytes()) == expected, path
    for path in MOBILE_FILES:
        if path not in ASSIGNMENT_FILES:
            assert Path(path).read_bytes() == blob(JOINT_BASE, path), path
    for path in ("Cargo.toml", "Cargo.lock", "pnpm-lock.yaml", "shared/types.ts"):
        assert Path(path).read_bytes() == blob(ACCEPTED_JOINT, path), path
    assert not git("diff", "--name-only", ACCEPTED_JOINT, RECOVERY_DELIVERED, "--", "crates/db").strip()
    recovery_files = [p for p in git("diff", "--name-only", ACCEPTED_JOINT, RECOVERY_TESTED).decode().splitlines() if p.startswith(("crates/", "packages/", "scripts/testing/"))]
    return {"sourceCommit": git("rev-parse", "HEAD").decode().strip(),
            "sourceTree": git("rev-parse", "HEAD^{tree}").decode().strip(),
            "acceptedJoint": ACCEPTED_JOINT, "recoveryTested": RECOVERY_TESTED,
            "recoveryDelivered": RECOVERY_DELIVERED,
            "assignmentFiles": ASSIGNMENT_FILES, "mobileFiles": sorted(MOBILE_FILES),
            "recoveryFiles": {p: digest(Path(p).read_bytes()) for p in recovery_files},
            "migrationSha256": ASSIGNMENT_FILES["crates/db/migrations/20261009000000_local_issue_assignments.sql"],
            "queueRepairIncluded": False, "gitEnforcementActivated": False,
            "unreadAutoClearEnabled": False, "nightlyScheduleEnabled": False,
            "preservedModule": "inventory-history-be3478171-20261009", "routingMode": "Recommend-only"}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
