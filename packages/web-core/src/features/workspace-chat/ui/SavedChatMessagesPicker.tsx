import {
  ChatCircleTextIcon,
  GearSixIcon,
  PlusCircleIcon,
} from '@phosphor-icons/react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@vibe/ui/components/Dropdown';
import { ToolbarIconButton } from '@vibe/ui/components/Toolbar';
import { SettingsDialog } from '@/shared/dialogs/settings/SettingsDialog';
import { useSavedChatMessages } from '@/shared/stores/useUiPreferencesStore';

type SavedChatMessagesPickerProps = {
  disabled?: boolean;
  onSelect: (content: string) => void;
};

export function SavedChatMessagesPicker({
  disabled,
  onSelect,
}: SavedChatMessagesPickerProps) {
  const [savedMessages] = useSavedChatMessages();
  const completeMessages = savedMessages.filter(
    (message) => message.title.trim() && message.content.trim()
  );
  const hasMessages = completeMessages.length > 0;

  const handleOpenSettings = () => {
    SettingsDialog.show({ initialSection: 'general' });
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <ToolbarIconButton
          icon={ChatCircleTextIcon}
          aria-label="Saved messages"
          title="Insert saved message"
          disabled={disabled}
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-80">
        <DropdownMenuLabel>Saved messages</DropdownMenuLabel>
        {hasMessages ? (
          completeMessages.map((message) => (
            <DropdownMenuItem
              key={message.id}
              icon={ChatCircleTextIcon}
              onSelect={() => onSelect(message.content)}
            >
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-sm">{message.title}</span>
                <span className="truncate text-xs text-low">
                  {message.content}
                </span>
              </span>
            </DropdownMenuItem>
          ))
        ) : (
          <DropdownMenuItem disabled icon={PlusCircleIcon}>
            Create saved messages in Settings
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem icon={GearSixIcon} onSelect={handleOpenSettings}>
          Manage saved messages
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
