import { CheckIcon } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { cn } from '../lib/cn';
import type { MultiSelectDropdownOption } from './MultiSelectDropdown';

interface WorkspaceProjectFilterChipsProps {
  options: MultiSelectDropdownOption<string>[];
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

  const chip = (label: string, selected: boolean, onClick: () => void) => (
    <button
      type="button"
      aria-pressed={selected}
      title={label}
      onClick={onClick}
      className={cn(
        'workspace-project-filter-chip flex shrink-0 max-w-[16rem] items-center gap-half rounded-full border px-base py-half text-base transition-colors',
        'focus:outline-none focus-visible:ring-1 focus-visible:ring-brand',
        selected
          ? 'border-brand bg-brand/10 text-brand'
          : 'border-border bg-panel text-normal hover:bg-secondary'
      )}
    >
      <CheckIcon
        aria-hidden="true"
        className={cn('size-icon-xs shrink-0', !selected && 'invisible')}
        weight="bold"
      />
      <span className="truncate">{label}</span>
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
          {chip(option.label, projectIds.includes(option.value), () =>
            onChange(
              projectIds.includes(option.value)
                ? projectIds.filter((id) => id !== option.value)
                : [...projectIds, option.value]
            )
          )}
        </div>
      ))}
    </div>
  );
}
