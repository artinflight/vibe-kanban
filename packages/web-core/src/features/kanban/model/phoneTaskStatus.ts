// An untouched project shows every status. Keep an explicit valid selection.
export function resolvePhoneTaskStatus(
  statuses: { id: string }[],
  selected: string | null | undefined
): string | null {
  return selected && statuses.some((status) => status.id === selected)
    ? selected
    : null;
}
