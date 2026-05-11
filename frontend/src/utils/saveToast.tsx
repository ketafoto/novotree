import toast from 'react-hot-toast';
import { CheckCircle, ExternalLink, FolderOpen, X } from 'lucide-react';
import apiClient from '../api/client';
import { isLocalApp } from '../config/appMode';
import { apiErrorMessage } from './apiError';
import type { SaveBlobResult } from './saveBlob';

const OPEN_FILE_ENDPOINT = '/local/open-with-default';
const SHOW_IN_FOLDER_ENDPOINT = '/local/open-in-explorer';

async function openSavedFile(path: string): Promise<void> {
  try {
    await apiClient.post(OPEN_FILE_ENDPOINT, { path });
  } catch (err) {
    toast.error(apiErrorMessage(err, 'Failed to open file'));
  }
}

async function showSavedInFolder(path: string): Promise<void> {
  try {
    await apiClient.post(SHOW_IN_FOLDER_ENDPOINT, { path });
  } catch (err) {
    toast.error(apiErrorMessage(err, 'Failed to open folder'));
  }
}

/**
 * Show a post-save toast. In the local app it's a clickable card with
 * "Open" and "Show in folder" action buttons (Chrome-download-bar style);
 * in the web build it falls back to a plain success toast.
 *
 * Stays silent when the user cancelled the save dialog (`saved` is false).
 */
export function showSaveToast(result: SaveBlobResult): void {
  if (!result.saved) return;

  if (isLocalApp && result.path) {
    const path = result.path;
    toast.custom((t) => (
      <div
        className={`max-w-md w-full bg-white shadow-lg rounded-lg pointer-events-auto border border-gray-200 overflow-hidden transition-opacity ${
          t.visible ? 'opacity-100' : 'opacity-0'
        }`}
      >
        <div className="p-3">
          <div className="flex items-start gap-2">
            <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900">Saved</p>
              <p className="text-xs text-gray-500 font-mono truncate" title={path}>
                {path}
              </p>
            </div>
            <button
              onClick={() => toast.dismiss(t.id)}
              className="p-1 hover:bg-gray-100 rounded"
              aria-label="Dismiss"
            >
              <X className="w-4 h-4 text-gray-400" />
            </button>
          </div>
          <div className="mt-2 flex gap-2 pl-7">
            <button
              onClick={() => {
                openSavedFile(path);
                toast.dismiss(t.id);
              }}
              className="inline-flex items-center text-xs font-medium text-emerald-700 hover:text-emerald-800 hover:underline"
            >
              <ExternalLink className="w-3.5 h-3.5 mr-1" />
              Open
            </button>
            <button
              onClick={() => {
                showSavedInFolder(path);
                toast.dismiss(t.id);
              }}
              className="inline-flex items-center text-xs font-medium text-emerald-700 hover:text-emerald-800 hover:underline"
            >
              <FolderOpen className="w-3.5 h-3.5 mr-1" />
              Show in folder
            </button>
          </div>
        </div>
      </div>
    ), { duration: 8000 });
    return;
  }

  // Web build: no path available, plain success toast.
  toast.success('Saved');
}
