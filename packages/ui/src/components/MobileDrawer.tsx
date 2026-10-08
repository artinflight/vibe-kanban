import { useRef, type ReactNode } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { XIcon } from '@phosphor-icons/react';

interface MobileDrawerProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  title?: string;
}

/** Modal sheet: Radix owns focus trapping, Escape and background inertness.
 * Restore the opener explicitly because triggers live outside Dialog.Root. */
export function MobileDrawer({
  open,
  onClose,
  children,
  title = 'Projects',
}: MobileDrawerProps) {
  const opener = useRef<HTMLElement | null>(null);
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(value) => {
        if (!value) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-[100]" />
        <Dialog.Content
          aria-describedby={undefined}
          onOpenAutoFocus={() => {
            opener.current =
              document.activeElement instanceof HTMLElement
                ? document.activeElement
                : null;
          }}
          onCloseAutoFocus={(event) => {
            if (opener.current?.isConnected) {
              event.preventDefault();
              opener.current.focus({ preventScroll: true });
            }
          }}
          className="mobile-sheet fixed inset-x-0 bottom-0 bg-primary z-[101] flex flex-col rounded-t-2xl border border-border shadow-lg"
        >
          <div className="flex items-center justify-between px-4 py-2 border-b shrink-0">
            <Dialog.Title className="text-lg font-medium text-high">
              {title}
            </Dialog.Title>
            <Dialog.Close
              className="flex items-center justify-center text-normal"
              aria-label="Close sheet"
            >
              <XIcon className="size-icon-lg" />
            </Dialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
