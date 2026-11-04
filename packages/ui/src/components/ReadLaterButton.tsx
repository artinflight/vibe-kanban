import { BookmarkSimpleIcon } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';

export function ReadLaterButton({
  later = false,
  onToggle,
}: {
  later?: boolean;
  onToggle: () => void;
}) {
  const { t } = useTranslation('common');
  const label = later
    ? t('workspaces.returnToAttention')
    : t('workspaces.readLater');
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      aria-pressed={later}
      onPointerDown={(event) => event.stopPropagation()}
      onKeyDown={(event) => event.stopPropagation()}
      onClick={(event) => {
        event.stopPropagation();
        onToggle();
      }}
      className="inline-flex min-h-11 md:min-h-0 shrink-0 items-center gap-half rounded-sm px-base py-half text-sm text-low hover:bg-tertiary hover:text-normal focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand"
    >
      <BookmarkSimpleIcon
        className="size-icon-sm"
        weight={later ? 'fill' : 'regular'}
      />
      {label}
    </button>
  );
}
