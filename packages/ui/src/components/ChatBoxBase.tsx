import { useId, useState, type ReactNode } from 'react';
import {
  ImageIcon,
  PaperclipIcon,
  SlidersHorizontalIcon,
} from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { cn } from '../lib/cn';
import { Toolbar } from './Toolbar';
import { usePhoneLayout } from '../lib/usePhoneLayout';

export enum VisualVariant {
  NORMAL = 'NORMAL',
  FEEDBACK = 'FEEDBACK',
  EDIT = 'EDIT',
  PLAN = 'PLAN',
}

export interface DropzoneProps {
  getRootProps: () => Record<string, unknown>;
  getInputProps: () => Record<string, unknown>;
  isDragActive: boolean;
}

interface ChatBoxBaseProps {
  // Editor node (provided by frontend)
  editor: ReactNode;

  // Error display
  error?: string | null;

  // Header content (right side - session/executor dropdown)
  headerRight?: ReactNode;

  // Header content (left side - stats)
  headerLeft?: ReactNode;

  // Footer left content (additional toolbar items like attach button)
  footerLeft?: ReactNode;

  // Footer right content (action buttons)
  footerRight: ReactNode;

  // Model selector node (rendered with footer controls)
  modelSelector?: ReactNode;

  // Banner content (queued message indicator, feedback mode indicator)
  banner?: ReactNode;

  // visualVariant
  visualVariant: VisualVariant;

  // Whether the workspace is running (shows animated border)
  isRunning?: boolean;

  // Dropzone props for drag-and-drop image uploads
  dropzone?: DropzoneProps;
  isAttachmentDisabled?: boolean;
}

/**
 * Base chat box layout component.
 * Provides shared structure for CreateChatBox and SessionChatBox.
 */
export function ChatBoxBase({
  editor,
  error,
  headerRight,
  headerLeft,
  footerLeft,
  footerRight,
  modelSelector,
  banner,
  visualVariant,
  isRunning,
  dropzone,
  isAttachmentDisabled = false,
}: ChatBoxBaseProps) {
  const { t } = useTranslation(['common', 'tasks']);
  const phone = usePhoneLayout();
  const [optionsOpen, setOptionsOpen] = useState(false);
  const optionsId = useId();

  const isDragActive = dropzone?.isDragActive ?? false;

  return (
    <div
      {...(dropzone?.getRootProps() ?? {})}
      className={cn(
        'mobile-composer relative flex w-chat max-w-full flex-col rounded-sm border border-border bg-secondary',
        (visualVariant === VisualVariant.FEEDBACK ||
          visualVariant === VisualVariant.EDIT ||
          visualVariant === VisualVariant.PLAN) &&
          'border-brand bg-brand/10',
        isRunning && 'chat-box-running'
      )}
    >
      {dropzone && <input {...dropzone.getInputProps()} />}

      {isDragActive && (
        <div className="absolute inset-0 z-50 flex items-center justify-center rounded-sm border-2 border-dashed border-brand bg-primary/80 backdrop-blur-sm pointer-events-none animate-in fade-in-0 duration-150">
          <div className="text-center">
            <div className="mx-auto mb-2 w-10 h-10 rounded-full bg-brand/10 flex items-center justify-center">
              <ImageIcon className="h-5 w-5 text-brand" />
            </div>
            <p className="text-sm font-medium text-high">
              {t('tasks:dropzone.dropImagesHere')}
            </p>
            <p className="text-xs text-low mt-0.5">
              {t('tasks:dropzone.supportedFormats')}
            </p>
          </div>
        </div>
      )}
      {/* Error alert */}
      {error && (
        <div className="bg-error/10 border-b px-double py-base">
          <p className="text-error text-sm">{error}</p>
        </div>
      )}

      {/* Banner content (queued indicator, feedback mode, etc.) */}
      {banner}

      {/* Header - Stats and selector */}
      {!phone && visualVariant === VisualVariant.NORMAL && (
        <div className="mobile-composer-header flex items-center gap-base border-b px-base py-base">
          <div className="flex flex-1 items-center gap-base text-sm min-w-0 overflow-hidden">
            {headerLeft}
          </div>
          <Toolbar className="gap-[9px]">{headerRight}</Toolbar>
        </div>
      )}

      {/* Editor area */}
      <div className="flex flex-col gap-plusfifty px-base py-base rounded-md">
        {editor}

        {/* Footer - Controls */}
        {phone ? (
          <>
            <div className="phone-prompt-actions">
              <button
                type="button"
                aria-expanded={optionsOpen}
                aria-controls={optionsId}
                onClick={() => setOptionsOpen(!optionsOpen)}
              >
                <SlidersHorizontalIcon size={20} /> Options
              </button>
              <button
                type="button"
                aria-label="Attach file"
                disabled={isAttachmentDisabled}
                onClick={(event) =>
                  event.currentTarget
                    .closest('.mobile-composer')
                    ?.querySelector<HTMLInputElement>(
                      '.phone-prompt-tools input[type="file"]'
                    )
                    ?.click()
                }
              >
                <PaperclipIcon size={20} />
              </button>
              <div
                className="phone-prompt-send"
                onMouseDownCapture={(event) => {
                  // Touch generates a compatibility mousedown before click.
                  // Keep the keyboard open: blur restores bottom navigation
                  // and moves these buttons before mouseup can activate them.
                  const focused = document.activeElement;
                  if (
                    event.button === 0 &&
                    event.target instanceof Element &&
                    event.target.closest('button:not(:disabled)') &&
                    focused instanceof HTMLElement &&
                    focused.isContentEditable &&
                    event.currentTarget
                      .closest('.mobile-composer')
                      ?.contains(focused)
                  ) {
                    event.preventDefault();
                  }
                }}
              >
                {footerRight}
              </div>
            </div>
            <section
              id={optionsId}
              hidden={!optionsOpen}
              className="phone-prompt-options"
              aria-label="Prompt options"
            >
              <div className="phone-option-label">Model & permissions</div>
              <Toolbar className="mobile-model-selector flex-wrap">
                {modelSelector}
              </Toolbar>
              {visualVariant === VisualVariant.NORMAL && (
                <>
                  <div className="phone-option-label">Session</div>
                  <Toolbar className="flex-wrap">{headerRight}</Toolbar>
                  <div className="phone-prompt-context">{headerLeft}</div>
                </>
              )}
              <Toolbar className="phone-prompt-tools flex-wrap">
                {footerLeft}
              </Toolbar>
            </section>
          </>
        ) : (
          <div className="mobile-composer-controls flex items-end justify-between gap-base">
            <Toolbar className="flex-1 min-w-0 flex-wrap !gap-half">
              <div className="mobile-model-selector contents">
                {modelSelector}
              </div>
              <div className="mobile-composer-actions contents">
                {footerLeft}
              </div>
            </Toolbar>
            <div className="flex shrink-0 gap-base">{footerRight}</div>
          </div>
        )}
      </div>
    </div>
  );
}
