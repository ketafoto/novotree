import { useEffect, useState } from 'react';
import { UserRound } from 'lucide-react';
import toast from 'react-hot-toast';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { localApi, type LocalAppInfo } from '../../api/local';
import { apiErrorMessage } from '../../utils/apiError';

/**
 * Who is recorded as adding records, shown separately from which tree is open
 * because the two are genuinely different things: a tree is a dataset, an
 * editor is a person. They used to be the same value, which made one person
 * appear as a different author in every tree.
 *
 * Local-app only - gated by `isLocalApp` at the call site (SettingsPage.tsx).
 */
export function LocalIdentityCard() {
  const [info, setInfo] = useState<LocalAppInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [editorId, setEditorId] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    localApi
      .info()
      .then((res) => {
        setInfo(res);
        setEditorId(res.editor_id);
        setDisplayName(res.display_name);
      })
      .catch((err) => setError(apiErrorMessage(err, 'Failed to load identity')));
  }, []);

  const dirty =
    info !== null && (editorId !== info.editor_id || displayName !== info.display_name);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await localApi.setIdentity(editorId.trim(), displayName.trim());
      setInfo(res);
      setEditorId(res.editor_id);
      setDisplayName(res.display_name);
      toast.success('Saved. Records you add from now on use this name.');
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to save identity'));
    } finally {
      setSaving(false);
    }
  };

  if (error) {
    return (
      <Card title="You">
        <p className="text-sm text-red-600">{error}</p>
      </Card>
    );
  }
  if (!info) {
    return (
      <Card title="You">
        <p className="text-sm text-gray-400">Loading…</p>
      </Card>
    );
  }

  return (
    <Card title="You">
      <div className="flex items-start gap-3 mb-5">
        <UserRound className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-400" />
        <p className="text-sm text-gray-600">
          Every person, photo and event you add is recorded as{' '}
          <strong className="text-gray-800">added by {displayName || editorId}</strong>. This
          is separate from which tree is open, so you stay the same author in all of your
          trees.
        </p>
      </div>

      <div className="space-y-4 max-w-md">
        <Input
          label="Your name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder={editorId}
          helperText="Shown next to records you add. Change it freely — it is only a label."
        />
        <Input
          label="Editor ID"
          value={editorId}
          onChange={(e) => setEditorId(e.target.value)}
          helperText="Letters, digits, hyphens and underscores. Max 32 characters."
        />
      </div>

      <div className="mt-4 rounded-md bg-gray-50 border border-gray-200 px-4 py-3">
        <p className="text-xs text-gray-600 leading-relaxed">
          <strong className="text-gray-700">Where this ID comes from.</strong> On the online
          version at novospace.cz, your editor ID is created for you from your registration
          email — the part before the <code className="bg-white px-1 rounded">@</code>, with
          anything other than letters, digits, hyphens and underscores replaced (so{' '}
          <code className="bg-white px-1 rounded">anna.smith@gmail.com</code> becomes{' '}
          <code className="bg-white px-1 rounded">anna_smith</code>). The desktop app carries
          the same ID so records you add offline and online show one author. If you don't use
          the online version, this is just a name you pick.
        </p>
      </div>

      {dirty && (
        <div className="mt-4 flex items-center gap-3">
          <Button onClick={handleSave} isLoading={saving} disabled={!editorId.trim()}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
          <button
            type="button"
            onClick={() => {
              setEditorId(info.editor_id);
              setDisplayName(info.display_name);
            }}
            disabled={saving}
            className="text-sm text-gray-500 hover:text-gray-700 disabled:opacity-60"
          >
            Reset
          </button>
          <p className="text-xs text-gray-400">
            Applies to new records — existing ones keep the name they were added under.
          </p>
        </div>
      )}
    </Card>
  );
}
