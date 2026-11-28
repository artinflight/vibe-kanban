export const PASTEL_PROJECT_COLORS = [
  '6 78% 84%',
  '28 92% 82%',
  '45 95% 78%',
  '84 64% 80%',
  '145 55% 78%',
  '174 58% 78%',
  '202 82% 82%',
  '232 72% 84%',
  '262 70% 86%',
  '302 62% 85%',
  '334 78% 84%',
  '358 74% 84%',
] as const;

export function getProjectInitials(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return '??';

  const words = trimmed.split(/[\s_-]+/).filter(Boolean);
  if (words.length >= 2) {
    return (
      words[0].charAt(0) + words[words.length - 1].charAt(0)
    ).toUpperCase();
  }
  return trimmed.slice(0, 2).toUpperCase();
}

export function getProjectAbbreviation(project: {
  name: string;
  abbreviation?: string;
}): string {
  const abbreviation = project.abbreviation?.trim();
  if (abbreviation) return abbreviation.slice(0, 3).toUpperCase();
  return getProjectInitials(project.name);
}

export function getProjectButtonStyle(
  project: { color: string },
  isActive: boolean
) {
  return {
    backgroundColor: `hsl(${project.color} / ${isActive ? 1 : 0.72})`,
    color: 'hsl(222 35% 18%)',
    boxShadow: isActive ? `0 0 0 2px hsl(${project.color} / 0.35)` : undefined,
  };
}

export function getLocalProjectColor(projectId: string): string {
  let hash = 0;
  for (const char of projectId) {
    hash = (hash * 31 + char.charCodeAt(0)) % PASTEL_PROJECT_COLORS.length;
  }
  return PASTEL_PROJECT_COLORS[hash];
}
