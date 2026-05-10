import { useCallback, useEffect, useRef, useState } from 'react';
import { attachmentsApi } from '@/shared/lib/api';
import type { LocalAttachmentMetadata } from '@vibe/ui/components/WorkspaceContext';
import {
  buildWorkspaceAttachmentMarkdown,
  formatAttachmentSize,
  MAX_ATTACHMENT_UPLOAD_BYTES,
  toLocalAttachmentMetadata,
} from '@/shared/lib/workspaceAttachments';
import type { DraftWorkspaceAttachment } from 'shared/types';

/**
 * Hook for handling attachments during workspace creation.
 * Uploads attachments and tracks their IDs for association with the workspace.
 * Also tracks uploaded attachments for immediate preview in the editor.
 * Supports restoring previously uploaded attachments from a persisted draft.
 */
export function useCreateAttachments(
  onInsertMarkdown: (markdown: string) => void,
  initialAttachments?: DraftWorkspaceAttachment[],
  onAttachmentsChange?: (attachments: DraftWorkspaceAttachment[]) => void
) {
  const [attachments, setAttachments] = useState<DraftWorkspaceAttachment[]>(
    initialAttachments ?? []
  );
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const hasInitialized = useRef(false);

  useEffect(() => {
    if (hasInitialized.current) return;
    if (initialAttachments && initialAttachments.length > 0) {
      hasInitialized.current = true;
      setAttachments(initialAttachments);
    }
  }, [initialAttachments]);

  useEffect(() => {
    onAttachmentsChange?.(attachments);
  }, [attachments, onAttachmentsChange]);

  const uploadFiles = useCallback(
    async (selectedFiles: File[]) => {
      if (selectedFiles.length === 0) return;

      const uploadResults: DraftWorkspaceAttachment[] = [];
      const uploadFailures: string[] = [];

      setUploadError(null);
      setIsUploading(true);
      for (const attachment of selectedFiles) {
        if (attachment.size > MAX_ATTACHMENT_UPLOAD_BYTES) {
          uploadFailures.push(
            `${attachment.name}: file is ${formatAttachmentSize(
              attachment.size
            )}; max upload size is ${formatAttachmentSize(
              MAX_ATTACHMENT_UPLOAD_BYTES
            )}`
          );
          continue;
        }

        try {
          const response = await attachmentsApi.upload(attachment);
          uploadResults.push({
            id: response.id,
            file_path: response.file_path,
            original_name: response.original_name,
            mime_type: response.mime_type,
            size_bytes: Number(response.size_bytes) as unknown as bigint,
          });
        } catch (error) {
          console.error('Failed to upload attachment:', error);
          const message =
            error instanceof Error ? error.message : 'Unknown error';
          uploadFailures.push(`${attachment.name}: ${message}`);
        }
      }
      setIsUploading(false);

      if (uploadResults.length > 0) {
        setAttachments((prev) => [...prev, ...uploadResults]);
        const allMarkdown = uploadResults
          .map(buildWorkspaceAttachmentMarkdown)
          .join('\n\n');
        onInsertMarkdown(allMarkdown);
      }

      if (uploadFailures.length > 0) {
        setUploadError(`Failed to upload ${uploadFailures.join('; ')}`);
      }
    },
    [onInsertMarkdown]
  );

  const getAttachmentIds = useCallback(() => {
    const ids = attachments.map((attachment) => attachment.id);
    return ids.length > 0 ? ids : null;
  }, [attachments]);

  const clearAttachments = useCallback(() => {
    setAttachments([]);
    setUploadError(null);
  }, []);

  const clearUploadError = useCallback(() => {
    setUploadError(null);
  }, []);

  const localAttachments: LocalAttachmentMetadata[] = attachments.map(
    (attachment) =>
      toLocalAttachmentMetadata({
        ...attachment,
        hash: '',
        created_at: '',
        updated_at: '',
      })
  );

  return {
    uploadFiles,
    getAttachmentIds,
    clearAttachments,
    localAttachments,
    uploadError,
    clearUploadError,
    isUploading,
  };
}
