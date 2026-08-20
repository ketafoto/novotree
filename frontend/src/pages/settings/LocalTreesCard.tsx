import { useCallback, useEffect, useState } from 'react';
import { Check, Plus, Trash2, TreeDeciduous } from 'lucide-react';
import toast from 'react-hot-toast';
import { Card } from '../../components/common/Card';
import { Modal } from '../../components/common/Modal';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { localApi, type TreeInfo } from '../../api/local';
import { apiErrorMessage } from '../../utils/apiError';

/**
 * Tree switcher for the desktop app: lists every tree in the current data
 * folder and lets the user open a different one or start a new one.
 *
 * Distinct from LocalAppInfoCard's "Change…" button, which moves the whole
 * data folder somewhere else. This card changes WHICH tree inside that folder
 * is open and moves nothing.
 *
 * Local-app only - gated by `isLocalApp` at the call site (SettingsPage.tsx).
 */
export function LocalTreesCard() {
  const [trees, setTrees] = useState<TreeInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [pendingSwitch, setPendingSwitch] = useState<string | null>(null);
  const [switching, setSwitching] = useState(false);

  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [createOpen, setCreateOpen] = useState(false);

  const [pendingDelete, setPendingDelete] = useState<TreeInfo | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState('');
  const [deleting, setDeleting] = useState(false);

  const refresh = useCallback(
    () =>
      localApi
        .listTrees()
        .then((res) => setTrees(res.trees))
        .catch((err) => setError(apiErrorMessage(err, 'Failed to load trees'))),
    [],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  /* Both actions end the same way: the backend has rebound the process to a
     different tree, so every cached row in React Query now belongs to the
     wrong one. A full reload is the cheapest correct way to drop them.
  */
  const handleSwitch = async () => {
    if (!pendingSwitch) return;
    setSwitching(true);
    try {
      await localApi.switchTree(pendingSwitch);
      window.location.reload();
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to switch tree'));
      setSwitching(false);
      setPendingSwitch(null);
    }
  };

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) return;
    setCreating(true);
    try {
      await localApi.createTree(name);
      window.location.reload();
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to create tree'));
      setCreating(false);
    }
  };

  /* Unlike switching, deleting cannot touch the open tree, so the page does
     not need to reload - refetching the list is enough.
  */
  const handleDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      const res = await localApi.deleteTree(pendingDelete.owner_id);
      const links = res.purged['auth_share_tokens'] ?? 0;
      toast.success(
        links > 0
          ? `Deleted "${res.deleted}" and ${links} share link${links === 1 ? '' : 's'}.`
          : `Deleted "${res.deleted}".`,
      );
      await refresh();
      setPendingDelete(null);
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to delete tree'));
    } finally {
      setDeleting(false);
    }
  };

  if (error) {
    return (
      <Card title="Trees">
        <p className="text-sm text-red-600">{error}</p>
      </Card>
    );
  }
  if (!trees) {
    return (
      <Card title="Trees">
        <p className="text-sm text-gray-400">Loading…</p>
      </Card>
    );
  }

  return (
    <>
      <Card
        title="Trees"
        actions={
          <Button variant="secondary" size="sm" onClick={() => { setNewName(''); setCreateOpen(true); }}>
            <Plus className="w-4 h-4 mr-1.5" />
            New tree…
          </Button>
        }
      >
        <p className="text-sm text-gray-600 mb-4">
          Every tree stored in your data folder. Only one is open at a time.
        </p>
        <ul className="divide-y divide-gray-100 border border-gray-200 rounded-md">
          {trees.map((tree) => (
            <li key={tree.owner_id} className="flex items-center gap-3 px-4 py-3">
              <TreeDeciduous
                className={`w-4 h-4 flex-shrink-0 ${tree.is_active ? 'text-green-600' : 'text-gray-300'}`}
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">
                  {tree.owner_id}
                  {tree.is_active && (
                    <span className="ml-2 inline-flex items-center gap-1 text-xs font-normal text-green-700">
                      <Check className="w-3 h-3" />
                      open
                    </span>
                  )}
                </p>
                <p className="text-xs text-gray-400">{describeTree(tree)}</p>
              </div>
              {!tree.is_active && (
                <>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setPendingSwitch(tree.owner_id)}
                  >
                    Open
                  </Button>
                  <button
                    type="button"
                    onClick={() => { setDeleteConfirm(''); setPendingDelete(tree); }}
                    title={`Delete "${tree.owner_id}" permanently`}
                    className="flex-shrink-0 p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      </Card>

      <Modal
        open={pendingSwitch !== null}
        onClose={() => !switching && setPendingSwitch(null)}
        title="Open a different tree?"
      >
        <div className="space-y-4">
          <p className="text-gray-700">
            NovoTree will close <strong>{trees.find((t) => t.is_active)?.owner_id}</strong> and
            open <strong>{pendingSwitch}</strong>.
          </p>
          <p className="text-sm text-gray-500">
            Nothing is moved or deleted — both trees stay in your data folder, and you can
            switch back at any time. The page reloads so it reads from the new tree.
          </p>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setPendingSwitch(null)} disabled={switching}>
              Cancel
            </Button>
            <Button onClick={handleSwitch} isLoading={switching}>
              {switching ? 'Opening…' : 'Open tree'}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={createOpen}
        onClose={() => !creating && setCreateOpen(false)}
        title="New tree"
      >
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            Creates an empty tree in your data folder and opens it. Your current tree is
            left untouched.
          </p>
          <Input
            label="Tree name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="e.g. Mother's side"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter' && newName.trim() && !creating) handleCreate();
            }}
          />
          <p className="text-xs text-gray-500">
            Letters, digits, spaces, hyphens and underscores. The name becomes a folder
            inside your data folder, so it also has to be a valid folder name.
          </p>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setCreateOpen(false)} disabled={creating}>
              Cancel
            </Button>
            <Button onClick={handleCreate} isLoading={creating} disabled={!newName.trim()}>
              {creating ? 'Creating…' : 'Create and open'}
            </Button>
          </div>
        </div>
      </Modal>
      <Modal
        open={pendingDelete !== null}
        onClose={() => !deleting && setPendingDelete(null)}
        title="Delete this tree?"
      >
        <div className="space-y-4">
          <p className="text-gray-700">
            This permanently deletes <strong>{pendingDelete?.owner_id}</strong> and
            everything in it — every person, photo and note.
          </p>
          {(pendingDelete?.share_links ?? 0) > 0 && (
            <p className="text-sm text-gray-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
              It also removes <strong>{pendingDelete?.share_links}</strong> share{' '}
              {pendingDelete?.share_links === 1 ? 'link' : 'links'} pointing at this tree.
              Anyone holding {pendingDelete?.share_links === 1 ? 'it' : 'one'} will no longer
              be able to open it.
            </p>
          )}
          <p className="text-sm text-red-600">
            It is not moved to the Recycle Bin and cannot be undone. If you might want
            this tree back, close this dialog and copy its folder somewhere safe first.
          </p>
          <Input
            label={`Type the tree name to confirm`}
            value={deleteConfirm}
            onChange={(e) => setDeleteConfirm(e.target.value)}
            placeholder={pendingDelete?.owner_id ?? ''}
            autoFocus
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setPendingDelete(null)} disabled={deleting}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={handleDelete}
              isLoading={deleting}
              disabled={deleteConfirm !== pendingDelete?.owner_id}
            >
              {deleting ? 'Deleting…' : 'Delete permanently'}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}

function describeTree({ individuals, size_bytes, modified_at }: TreeInfo): string {
  const parts: string[] = [
    individuals === null
      ? 'not readable'
      : `${individuals} ${individuals === 1 ? 'person' : 'people'}`,
    formatBytes(size_bytes),
  ];
  if (modified_at) {
    parts.push(`last changed ${new Date(modified_at).toLocaleDateString()}`);
  }
  return parts.join(' · ');
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB'];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
}
