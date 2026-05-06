import { useCallback, useState } from 'react';
import { attachmentsApi } from '@/shared/lib/api';
import type { LocalAttachmentMetadata } from '@vibe/ui/components/WorkspaceContext';
import {
  buildWorkspaceAttachmentMarkdown,
  toLocalAttachmentMetadata,
} from '@/shared/lib/workspaceAttachments';
import type { AttachmentResponse } from 'shared/types';

/**
 * Hook for handling attachments in session follow-up messages.
 * Uploads attachments to the workspace and calls back with markdown to insert.
 * Also tracks uploaded attachments for immediate preview in the editor.
 */
export function useSessionAttachments(
  workspaceId: string | undefined,
  sessionId: string | undefined,
  onInsertMarkdown: (markdown: string) => void
) {
  const [uploadedAttachments, setUploadedAttachments] = useState<
    AttachmentResponse[]
  >([]);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const uploadFiles = useCallback(
    async (files: File[]) => {
      setUploadError(null);

      if (!workspaceId || !sessionId) {
        setUploadError(
          'Attachments can only be added after a chat session exists.'
        );
        return;
      }

      const uploadResults: AttachmentResponse[] = [];
      const failures: string[] = [];

      for (const file of files) {
        try {
          const response = await attachmentsApi.uploadForAttempt(
            workspaceId,
            sessionId,
            file
          );
          uploadResults.push(response);
        } catch (error) {
          console.error('Failed to upload attachment:', error);
          const message =
            error instanceof Error ? error.message : 'Unknown upload error';
          failures.push(`${file.name}: ${message}`);
        }
      }

      if (uploadResults.length > 0) {
        setUploadedAttachments((prev) => [...prev, ...uploadResults]);
        const allMarkdown = uploadResults
          .map(buildWorkspaceAttachmentMarkdown)
          .join('\n\n');
        onInsertMarkdown(allMarkdown);
      }

      if (failures.length > 0) {
        setUploadError(`Failed to upload ${failures.join('; ')}`);
      }
    },
    [workspaceId, sessionId, onInsertMarkdown]
  );

  const clearUploadedAttachments = useCallback(() => {
    setUploadedAttachments([]);
  }, []);

  const clearUploadError = useCallback(() => setUploadError(null), []);

  const localAttachments: LocalAttachmentMetadata[] = uploadedAttachments.map(
    toLocalAttachmentMetadata
  );

  return {
    uploadFiles,
    localAttachments,
    clearUploadedAttachments,
    uploadError,
    clearUploadError,
  };
}
