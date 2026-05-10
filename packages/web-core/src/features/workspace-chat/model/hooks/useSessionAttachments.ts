import { useCallback, useState } from 'react';
import { attachmentsApi } from '@/shared/lib/api';
import type { LocalAttachmentMetadata } from '@vibe/ui/components/WorkspaceContext';
import {
  buildWorkspaceAttachmentMarkdown,
  formatAttachmentSize,
  MAX_ATTACHMENT_UPLOAD_BYTES,
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
  const [isUploading, setIsUploading] = useState(false);

  const uploadFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return;

      if (!workspaceId) {
        setUploadError('Select a workspace before attaching files.');
        return;
      }

      if (!sessionId) {
        setUploadError(
          'Attachments in a new session need a backend update. Start or select a session first, then attach the file.'
        );
        return;
      }

      const uploadResults: AttachmentResponse[] = [];
      const uploadFailures: string[] = [];

      setUploadError(null);
      setIsUploading(true);
      for (const file of files) {
        if (file.size > MAX_ATTACHMENT_UPLOAD_BYTES) {
          uploadFailures.push(
            `${file.name}: file is ${formatAttachmentSize(
              file.size
            )}; max upload size is ${formatAttachmentSize(
              MAX_ATTACHMENT_UPLOAD_BYTES
            )}`
          );
          continue;
        }

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
            error instanceof Error ? error.message : 'Unknown error';
          uploadFailures.push(`${file.name}: ${message}`);
        }
      }
      setIsUploading(false);

      if (uploadResults.length > 0) {
        setUploadedAttachments((prev) => [...prev, ...uploadResults]);
        const allMarkdown = uploadResults
          .map(buildWorkspaceAttachmentMarkdown)
          .join('\n\n');
        onInsertMarkdown(allMarkdown);
      }

      if (uploadFailures.length > 0) {
        setUploadError(`Failed to upload ${uploadFailures.join('; ')}`);
      }
    },
    [workspaceId, sessionId, onInsertMarkdown]
  );

  const clearUploadedAttachments = useCallback(() => {
    setUploadedAttachments([]);
    setUploadError(null);
  }, []);

  const clearUploadError = useCallback(() => {
    setUploadError(null);
  }, []);

  const localAttachments: LocalAttachmentMetadata[] = uploadedAttachments.map(
    toLocalAttachmentMetadata
  );

  return {
    uploadFiles,
    localAttachments,
    clearUploadedAttachments,
    uploadError,
    clearUploadError,
    isUploading,
  };
}
