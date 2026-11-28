import { CheckIcon, FolderIcon } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { cn } from '../lib/cn';
import type { MultiSelectDropdownOption } from './MultiSelectDropdown';
import { getProjectButtonStyle } from '../lib/projectAppearance';

export interface WorkspaceProjectFilterChipOption
  extends MultiSelectDropdownOption<string> {
  abbreviation?: string;
  color?: string;
}

interface WorkspaceProjectFilterChipsProps {
  options: WorkspaceProjectFilterChipOption[];
  projectIds: string[];
  onChange: (projectIds: string[]) => void;
}

/** Inline project toggles for desktop workspace lists and sidebars. */
export function WorkspaceProjectFilterChips({
  options,
  projectIds,
  onChange,
}: WorkspaceProjectFilterChipsProps) {
  const { t } = useTranslation('common');
  const allProjects = t('kanban.workspaceSidebar.allProjects');

  const chip = (
    label: string,
    selected: boolean,
    onClick: () => void,
    option?: WorkspaceProjectFilterChipOption
  ) => (
    <button
      type="button"
      aria-pressed={selected}
      aria-label={label}
      title={label}
      onClick={onClick}
      style={
        option?.color
          ? getProjectButtonStyle({ color: option.color }, selected)
          : undefined
      }
      className={cn(
        'workspace-project-filter-chip flex h-7 min-w-9 shrink-0 max-w-24 items-center justify-center gap-1 rounded-full border px-2 text-[11px] font-medium leading-none transition-colors',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand',
        selected
          ? 'border-brand bg-brand/10 text-brand'
          : 'border-border bg-panel text-normal hover:bg-secondary'
      )}
    >
      {selected && (
        <CheckIcon
          aria-hidden="true"
          className="size-icon-2xs shrink-0"
          weight="bold"
        />
      )}
      <span className="truncate">
        {option
          ? (option.abbreviation ?? (
              <FolderIcon aria-hidden="true" className="size-icon-xs" />
            ))
          : t('kanban.workspaceSidebar.assignmentAll')}
      </span>
    </button>
  );

  return (
    <div
      role="group"
      aria-label={t('kanban.workspaceSidebar.projectFilterLabel')}
      className="workspace-project-filter-chips flex min-w-0 gap-half overflow-x-auto overscroll-x-contain py-half"
    >
      {chip(allProjects, projectIds.length === 0, () => onChange([]))}
      {options.map((option) => (
        <div key={option.value} className="shrink-0">
          {chip(
            option.label,
            projectIds.includes(option.value),
            () =>
              onChange(
                projectIds.includes(option.value)
                  ? projectIds.filter((id) => id !== option.value)
                  : [...projectIds, option.value]
              ),
            option
          )}
        </div>
      ))}
    </div>
  );
}
