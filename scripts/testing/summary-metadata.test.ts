import assert from "node:assert/strict";
import { test } from "node:test";
import {
  createEditor,
  $getRoot,
  $createParagraphNode,
  $createTextNode,
} from "lexical";
import { findSummaryMetadataChildren } from "../../packages/web-core/src/shared/lib/summaryMetadata";

const original = [
  "PR",
  "Docs",
  "Churn",
  "Human Needed",
  "Commit/Push",
  "Preview URL",
  "Branch",
  "Worktree",
];
const updated = [...original.slice(0, 4), "Completion", ...original.slice(4)];
for (const labels of [
  original,
  [...original, "Version"],
  updated,
  [...updated, "Version"],
  ["Completion"],
]) {
  for (const separate of [false, true]) {
    test(`compact metadata: ${labels.join(", ")} (${separate ? "paragraphs" : "one paragraph"})`, () => {
      const editor = createEditor({
        onError: (error) => {
          throw error;
        },
      });
      editor.update(
        () => {
          const root = $getRoot();
          root.append(
            $createParagraphNode().append(
              $createTextNode("Validation narrative stays normal."),
            ),
          );
          const lines = labels.map((label) => `${label}:: Example`);
          for (const text of separate ? lines : [lines.join("\n")]) {
            root.append($createParagraphNode().append($createTextNode(text)));
          }
          const matched = findSummaryMetadataChildren(root.getChildren());
          assert.equal(matched.length, separate ? labels.length : 1);
          assert.ok(
            matched.every(
              (node) => !node.getTextContent().includes("Validation narrative"),
            ),
          );
        },
        { discrete: true },
      );
    });
  }
}
test("ordinary completion prose is not summary metadata", () => {
  const editor = createEditor({
    onError: (error) => {
      throw error;
    },
  });
  editor.update(
    () => {
      $getRoot().append(
        $createParagraphNode().append(
          $createTextNode("Completion was verified."),
        ),
      );
      assert.deepEqual(
        findSummaryMetadataChildren($getRoot().getChildren()),
        [],
      );
    },
    { discrete: true },
  );
});
