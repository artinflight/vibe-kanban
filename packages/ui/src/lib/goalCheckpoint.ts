export interface GoalCheckpoint {
  requirements: Record<string, string>;
  completed: Record<string, string>;
  disposition: "continue" | "needs_input" | "complete";
  reason: string;
  recovery_plan?: string;
}

function isStringMap(value: unknown): value is Record<string, string> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    Object.values(value).every((item) => typeof item === "string")
  );
}

// Render trailing checkpoints, including legacy completion reports, leaving examples and
// malformed messages available as ordinary Markdown. Never mutate saved logs.
export function splitGoalCheckpoint(content: string): {
  content: string;
  checkpoint?: GoalCheckpoint;
} {
  const end = "</vk_goal_checkpoint>";
  const start = "<vk_goal_checkpoint>";
  const trimmed = content.trimEnd();
  if (!trimmed.endsWith(end)) return { content };
  const index = trimmed.lastIndexOf(start);
  if (index < 0) return { content };
  const prefix = trimmed.slice(0, index);
  // The protocol is a standalone block, not inline prose or a code example.
  if (prefix.slice(prefix.lastIndexOf("\n") + 1).trim()) return { content };
  let fence: { char: string; length: number } | undefined;
  for (const line of prefix.split("\n")) {
    const match = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(line);
    if (!match) continue;
    if (!fence) fence = { char: match[1][0], length: match[1].length };
    else if (
      match[1][0] === fence.char &&
      match[1].length >= fence.length &&
      !match[2].trim()
    )
      fence = undefined;
  }
  if (fence) return { content };
  const json = trimmed.slice(index + start.length, -end.length);
  if (new TextEncoder().encode(json).length > 450_000) return { content };
  try {
    const value = JSON.parse(json);
    if (
      !value ||
      !isStringMap(value.requirements) ||
      !isStringMap(value.completed) ||
      !["continue", "needs_input", "complete"].includes(value.disposition) ||
      typeof value.reason !== "string" ||
      (value.recovery_plan !== undefined &&
        typeof value.recovery_plan !== "string")
    )
      return { content };
    return { content: prefix.trimEnd(), checkpoint: value };
  } catch {
    return { content };
  }
}
