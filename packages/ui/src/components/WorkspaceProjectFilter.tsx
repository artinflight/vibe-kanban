import { FolderIcon, CaretDownIcon } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { cn } from '../lib/cn';
import type { MultiSelectDropdownOption } from './MultiSelectDropdown';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuSeparator,
} from './Dropdown';

interface WorkspaceProjectFilterProps {
  options: MultiSelectDropdownOption<string>[];
  projectIds: string[];
  onChange: (projectIds: string[]) => void;
}

/** Direct project selection for the phone workspace list. */
export function WorkspaceProjectFilter({
  options,
  projectIds,
  onChange,
}: WorkspaceProjectFilterProps) {
  const { t } = useTranslation('common');
  const allProjects = t('kanban.workspaceSidebar.allProjects');
  const selection =
    projectIds.length === 0
      ? allProjects
      : projectIds.length === 1
        ? (options.find((option) => option.value === projectIds[0])?.label ??
          t('kanban.workspaceSidebar.projectsSelected', { count: 1 }))
        : t('kanban.workspaceSidebar.projectsSelected', {
            count: projectIds.length,
          });

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={cn(
            'phone-project-filter',
            projectIds.length > 0 && 'phone-project-filter-active'
          )}
          aria-label={`${t('kanban.workspaceSidebar.projectFilterLabel')}: ${selection}`}
          title={selection}
        >
          <FolderIcon size={20} className="shrink-0" aria-hidden="true" />
          <span className="truncate">{selection}</span>
          <CaretDownIcon size={16} className="shrink-0" aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        className="phone-project-filter-menu w-[min(22rem,calc(100vw-2rem))]"
        aria-label={t('kanban.workspaceSidebar.projectFilterLabel')}
      >
        <DropdownMenuCheckboxItem
          checked={projectIds.length === 0}
          onSelect={(event) => event.preventDefault()}
          onCheckedChange={() => onChange([])}
        >
          {allProjects}
        </DropdownMenuCheckboxItem>
        <DropdownMenuSeparator />
        {options.map((option) => (
          <DropdownMenuCheckboxItem
            key={option.value}
            checked={projectIds.includes(option.value)}
            onSelect={(event) => event.preventDefault()}
            onCheckedChange={() =>
              onChange(
                projectIds.includes(option.value)
                  ? projectIds.filter((id) => id !== option.value)
                  : [...projectIds, option.value]
              )
            }
          >
            {option.renderOption?.() ?? option.label}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
