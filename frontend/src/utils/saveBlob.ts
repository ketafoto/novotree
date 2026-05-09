import apiClient from '../api/client';
import { isLocalApp } from '../config/appMode';
import toast from 'react-hot-toast';

interface SaveAsResponse {
  saved: boolean;
  path: string | null;
}

/**
 * Save a Blob to disk under `suggestedFilename`.
 *
 * In the **local desktop app**, pywebview/WebView2 don't reliably surface
 * a SaveAs dialog for `<a download>` clicks (the file silently lands in a
 * default Downloads folder, or nowhere visible to the user). We POST the
 * blob to `/api/local/save-as` instead, which opens a native SaveAs dialog
 * via pywebview and writes the bytes to the user's chosen path.
 *
 * In the **web/VM build** there's nothing weird — fall back to the classic
 * Object-URL + `<a download>` click that browsers handle natively.
 */
export async function saveBlob(blob: Blob, suggestedFilename: string): Promise<void> {
  if (isLocalApp) {
    try {
      const res = await apiClient.post<SaveAsResponse>(
        '/local/save-as',
        blob,
        {
          params: { suggested_filename: suggestedFilename },
          headers: { 'Content-Type': 'application/octet-stream' },
          // Don't let axios stringify a Blob — send raw bytes.
          transformRequest: [(data) => data],
        },
      );
      if (res.data.saved && res.data.path) {
        toast.success(`Saved to ${res.data.path}`);
      }
      // If the user cancelled the dialog, res.data.saved is false — stay silent.
    } catch (err) {
      toast.error('Save failed');
      throw err;
    }
    return;
  }

  // Web build: standard browser-driven download.
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement('a');
    a.href = url;
    a.download = suggestedFilename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  } finally {
    URL.revokeObjectURL(url);
  }
}

/**
 * Same as `saveBlob` but takes a data-URL (e.g. what `html-to-image.toPng()`
 * returns). Decodes it into a Blob first and delegates.
 */
export async function saveDataUrl(dataUrl: string, suggestedFilename: string): Promise<void> {
  const resp = await fetch(dataUrl);
  const blob = await resp.blob();
  await saveBlob(blob, suggestedFilename);
}
