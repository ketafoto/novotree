import { useEffect, useState, type ReactNode } from 'react';
import { Folder, FileText, FileCog, ExternalLink, FolderInput, Loader2, FolderOpen } from 'lucide-react';
import toast from 'react-hot-toast';
import { Card } from '../../components/common/Card';
import { Modal } from '../../components/common/Modal';
import { Button } from '../../components/common/Button';
import { localApi, type LocalAppInfo } from '../../api/local';
import { apiErrorMessage } from '../../utils/apiError';

/**
 * Read-only display of the on-disk paths the desktop launcher chose at
 * startup (data folder, config file, log file), plus a "Change…" button
 * for the data folder that opens a native picker, moves the data, and
 * restarts the app.
 *
 * Local-app only — gated by `isLocalApp` at the call site (SettingsPage.tsx).
 * Tree-shaken out of the web bundle because the backend route returns 404
 * there anyway.
 */
export function LocalAppInfoCard() {
  const [info, setInfo] = useState<LocalAppInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  // "Change data folder" flow state
  const [picking, setPicking] = useState(false);
  const [pendingPath, setPendingPath] = useState<string | null>(null);
  const [moving, setMoving] = useState(false);

  useEffect(() => {
    localApi
      .info()
      .then(setInfo)
      .catch((err) => setError(apiErrorMessage(err, 'Failed to load locations')));
  }, []);

  const handlePickDataDir = async () => {
    setPicking(true);
    try {
      const { path } = await localApi.pickDataDir();
      if (!path) return; // user cancelled
      if (info && path === info.data_dir) {
        toast('That is already the current data folder.');
        return;
      }
      setPendingPath(path);
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Folder picker failed'));
    } finally {
      setPicking(false);
    }
  };

  const handleConfirmMove = async () => {
    if (!pendingPath) return;
    setMoving(true);
    try {
      const res = await localApi.changeDataDir(pendingPath);
      toast.success(
        `Moved ${res.items_moved} item${res.items_moved === 1 ? '' : 's'} to the new folder.`,
      );
      // Backend rebound DATASETS_DIR in-process — no restart. Reload the SPA
      // so React Query drops every cached fetch from the OLD location.
      window.location.reload();
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to move data folder'));
      setMoving(false);
      setPendingPath(null);
    }
  };

  if (error) {
    return (
      <Card title="Locations">
        <p className="text-sm text-red-600">{error}</p>
      </Card>
    );
  }
  if (!info) {
    return (
      <Card title="Locations">
        <p className="text-sm text-gray-400">Loading…</p>
      </Card>
    );
  }

  return (
    <>
      <Card title="Locations">
        <p className="text-sm text-gray-600 mb-4">
          Where NovoTree stores its files on this machine.
        </p>
        <div className="space-y-3">
          <PathRow
            icon={<Folder className="w-4 h-4" />}
            label="Data folder"
            hint="Your tree's SQLite databases and media files"
            value={info.data_dir}
            hideOpenWithDefault
            extraAction={
              <button
                type="button"
                onClick={handlePickDataDir}
                disabled={picking}
                title="Pick a different folder and move the data there"
                className="flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-gray-300 text-gray-700 hover:bg-gray-50 rounded-md transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {picking
                  ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  : <FolderInput className="w-3.5 h-3.5" />}
                <span>Change…</span>
              </button>
            }
          />
          <PathRow
            icon={<FileCog className="w-4 h-4" />}
            label="Config file"
            hint="Remembers your data-folder choice"
            value={info.config_file}
          />
          <PathRow
            icon={<FileText className="w-4 h-4" />}
            label="Log file"
            hint="Rotating launcher log (≤ ~6 MB on disk)"
            value={info.log_file}
          />
        </div>
      </Card>

      <Modal
        open={pendingPath !== null}
        onClose={() => !moving && setPendingPath(null)}
        title="Move data folder?"
      >
        <div className="space-y-4">
          <p className="text-gray-700">
            NovoTree will:
          </p>
          <ol className="list-decimal list-inside space-y-1 text-sm text-gray-600 ml-2">
            <li>Move every file from the current data folder into the new one</li>
            <li>Update <code className="text-xs bg-gray-100 px-1 rounded">config.json</code> to remember the new location</li>
            <li>Reload the page so it reads from the new folder</li>
          </ol>
          <div className="space-y-2 pt-2">
            <PathBlock label="From" value={info.data_dir} />
            <PathBlock label="To" value={pendingPath ?? ''} />
          </div>
          <p className="text-xs text-gray-500">
            The new folder must be empty. If anything goes wrong during the
            move, the page will not reload — your data stays where it is and
            you can sort it out by hand.
          </p>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="secondary"
              onClick={() => setPendingPath(null)}
              disabled={moving}
            >
              Cancel
            </Button>
            <Button onClick={handleConfirmMove} isLoading={moving}>
              {moving ? 'Moving…' : 'Move data folder'}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}

interface PathRowProps {
  icon: ReactNode;
  label: string;
  hint: string;
  value: string;
  extraAction?: ReactNode;
  /** Hide the "Open with default program" button. Set true for directories
   *  where it would just duplicate the File Explorer button — File Explorer
   *  IS the default program for folders, so the second button is noise. */
  hideOpenWithDefault?: boolean;
}

function PathRow({ icon, label, hint, value, extraAction, hideOpenWithDefault }: PathRowProps) {
  const handleOpenInExplorer = async () => {
    if (!value) return;
    try {
      await localApi.openInExplorer(value);
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to open Explorer'));
    }
  };

  const handleOpenWithDefault = async () => {
    if (!value) return;
    try {
      await localApi.openWithDefault(value);
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to open'));
    }
  };

  return (
    <div className="flex items-start gap-3">
      <div className="flex-shrink-0 mt-1 text-gray-400">{icon}</div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-700">{label}</p>
        <p className="text-xs text-gray-400">{hint}</p>
        <p className="mt-0.5 text-xs font-mono text-gray-600 break-all select-text" title={value}>
          {value || <span className="italic text-gray-400">(unset)</span>}
        </p>
      </div>
      {value && (
        <>
          <button
            type="button"
            onClick={handleOpenInExplorer}
            title="Open in File Explorer"
            className="flex-shrink-0 p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
          >
            <FolderOpen className="w-4 h-4" />
          </button>
          {!hideOpenWithDefault && (
            <button
              type="button"
              onClick={handleOpenWithDefault}
              title="Open with default program"
              className="flex-shrink-0 p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
            </button>
          )}
        </>
      )}
      {extraAction}
    </div>
  );
}

function PathBlock({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
      <p className="text-sm font-mono text-gray-700 break-all">{value}</p>
    </div>
  );
}
