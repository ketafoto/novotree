import apiClient from '../api/client';
import { isLocalApp } from '../config/appMode';
import toast from 'react-hot-toast';

interface SaveAsResponse {
  saved: boolean;
  path: string | null;
}

export interface SaveBlobResult {
  saved: boolean;
  // Absolute filesystem path of the saved file. Only set in the local-app
  // build (where pywebview returns it); always null in the web build, where
  // browsers don't reveal the download path for security reasons.
  path: string | null;
}

export interface SaveBlobOptions {
  // When true, suppress the built-in "Saved to ..." success toast so the
  // caller can render its own (e.g. a richer toast with Open / Show-in-folder
  // actions). The "Save failed" error toast is always shown.
  silent?: boolean;
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
export async function saveBlob(
  blob: Blob,
  suggestedFilename: string,
  options: SaveBlobOptions = {},
): Promise<SaveBlobResult> {
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
      if (!options.silent && res.data.saved && res.data.path) {
        toast.success(`Saved to ${res.data.path}`);
      }
      // If the user cancelled the dialog, res.data.saved is false — stay silent.
      return { saved: res.data.saved, path: res.data.path };
    } catch (err) {
      toast.error('Save failed');
      throw err;
    }
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
  return { saved: true, path: null };
}

/**
 * Same as `saveBlob` but takes a data-URL (e.g. what `html-to-image.toPng()`
 * returns). Decodes it into a Blob first and delegates.
 */
export async function saveDataUrl(
  dataUrl: string,
  suggestedFilename: string,
  options: SaveBlobOptions = {},
): Promise<SaveBlobResult> {
  const resp = await fetch(dataUrl);
  const blob = await resp.blob();
  return saveBlob(blob, suggestedFilename, options);
}
