/** Ask the extension to copy text to the OS clipboard (fallback path). */
export function parentClipboardWrite(text: string) {
  try {
    window.parent.postMessage(
      { type: 'vscode-iframe-clipboard-copy', text },
      '*'
    );
  } catch (_err) {
    void 0;
  }
}

function documentClipboardWrite(text: string): boolean {
  try {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.top = '0';
    textarea.style.left = '0';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const copied = document.execCommand('copy');
    textarea.remove();
    return copied;
  } catch {
    return false;
  }
}

/** Copy helper that prefers navigator.clipboard and falls back to the bridge. */
export async function writeClipboardViaBridge(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    if (documentClipboardWrite(text)) {
      return true;
    }
    parentClipboardWrite(text);
    return false;
  }
}
