import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { shareUrl } from '../../utils/shareUrl';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Share2,
  Copy,
  Check,
  Trash2,
  Plus,
  Users,
  UserCheck,
  RefreshCw,
  Link as LinkIcon,
  ShieldOff,
  ShieldCheck,
  Clock,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { usersApi } from '../../api/auth';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { Spinner } from '../../components/common/Spinner';
import { ShareSensitiveBadge } from '../../components/common/ShareSensitiveBadge';
import { ShareConsentModal } from '../../components/ShareConsentModal';
import toast from 'react-hot-toast';
import { apiErrorMessage } from '../../utils/apiError';

function copyToClipboard(text: string) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(() => toast.success('Link copied!'));
  } else {
    // navigator.clipboard is unavailable on plain HTTP (non-localhost) — use legacy fallback
    const el = document.createElement('textarea');
    el.value = text;
    el.style.position = 'fixed';
    el.style.opacity = '0';
    document.body.appendChild(el);
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);
    toast.success('Link copied!');
  }
}

// ──────────────────────────────────────────────────────────────
// Share Tokens tab
// ──────────────────────────────────────────────────────────────
function ShareTokensTab() {
  const qc = useQueryClient();
  const { data: tokens = [], isLoading } = useQuery({
    queryKey: ['share-tokens'],
    queryFn: usersApi.listShareTokens,
  });

  const [isCreating, setIsCreating] = useState(false);
  const [label, setLabel] = useState('');
  const [expiryDays, setExpiryDays] = useState(90);
  const [showCreate, setShowCreate] = useState(false);
  const [showConsent, setShowConsent] = useState(false);
  const [copiedTokenId, setCopiedTokenId] = useState<number | null>(null);

  const activeTokens = tokens.filter((t) => t.is_active);

  const create = async (exposeSensitive: boolean) => {
    setIsCreating(true);
    try {
      await usersApi.createShareToken({
        label: label.trim() || undefined,
        expires_after_days: expiryDays,
        expose_sensitive: exposeSensitive,
        acknowledgement: true,
      });
      qc.invalidateQueries({ queryKey: ['share-tokens'] });
      toast.success('Share link created');
      setLabel('');
      setShowCreate(false);
      setShowConsent(false);
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to create share link'));
    } finally {
      setIsCreating(false);
    }
  };

  const copy = (t: { id: number; token: string }) => {
    copyToClipboard(shareUrl(t.token));
    setCopiedTokenId(t.id);
    setTimeout(() => setCopiedTokenId(null), 2000);
  };

  const revoke = async (id: number) => {
    try {
      await usersApi.revokeShareToken(id);
      qc.invalidateQueries({ queryKey: ['share-tokens'] });
      toast.success('Link revoked');
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to revoke'));
    }
  };

  if (isLoading) return <div className="py-8 flex justify-center"><Spinner /></div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          Share links give read-only tree access to anyone with the URL.
        </p>
        <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
          <Plus className="w-4 h-4 mr-1" />
          New link
        </Button>
      </div>

      {showCreate && (
        <div className="flex gap-2 items-end border border-gray-200 rounded-lg p-4 bg-gray-50">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">Label (optional)</label>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. Family reunion 2026"
              className="block w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              onKeyDown={(e) => { if (e.key === 'Enter') setShowConsent(true); }}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Expires in</label>
            <select
              value={expiryDays}
              onChange={(e) => setExpiryDays(Number(e.target.value))}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value={30}>1 month</option>
              <option value={90}>3 months</option>
              <option value={180}>6 months</option>
              <option value={365}>1 year</option>
              <option value={3650}>10 years</option>
            </select>
          </div>
          <Button size="sm" onClick={() => setShowConsent(true)} disabled={isCreating}>
            Create
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setShowCreate(false)}>
            Cancel
          </Button>
        </div>
      )}

      <ShareConsentModal
        open={showConsent}
        onCancel={() => setShowConsent(false)}
        onConfirm={create}
        isSubmitting={isCreating}
      />

      {activeTokens.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <Share2 className="w-10 h-10 mx-auto mb-2" />
          <p className="text-sm">No active share links.</p>
        </div>
      ) : (
        <div className="divide-y divide-gray-100">
          {activeTokens.map((t) => (
            <div key={t.id} className="flex items-center gap-3 py-3">
              <Share2 className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{t.label || 'Unnamed link'}</p>
                <p className="text-xs text-gray-400 font-mono truncate">
                  {shareUrl(t.token)}
                </p>
                {t.created_at && (
                  <>
                    <p className="text-xs text-gray-400">
                      Created {new Date(t.created_at).toLocaleDateString()}
                      {t.last_used_at && ` · Last used ${new Date(t.last_used_at).toLocaleDateString()}`}
                      {' · '}
                      <span className="text-emerald-600">
                        Expires {new Date(new Date(t.created_at).getTime() + t.expires_after_days * 86400000).toLocaleDateString()}
                      </span>
                    </p>
                    <p className="text-xs text-gray-400" title="Your confirmation that you had the right to share this tree was recorded when the link was created.">
                      <Check className="inline w-3 h-3 text-emerald-500 mr-0.5" aria-hidden /> Acknowledged on {new Date(t.created_at).toLocaleDateString()}
                    </p>
                  </>
                )}
                <div className="mt-1">
                  <ShareSensitiveBadge exposeSensitive={t.expose_sensitive} />
                </div>
              </div>
              <button
                onClick={() => copy(t)}
                className="p-1.5 hover:bg-gray-100 rounded"
                title="Copy link"
              >
                {copiedTokenId === t.id
                  ? <Check className="w-4 h-4 text-emerald-500" />
                  : <Copy className="w-4 h-4 text-gray-500" />}
              </button>
              <button
                onClick={() => void revoke(t.id)}
                className="p-1.5 hover:bg-red-50 rounded"
                title="Revoke"
              >
                <Trash2 className="w-4 h-4 text-red-400" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// Contributions panel (lazy-loaded per contributor)
// ──────────────────────────────────────────────────────────────
type ContributionKind = 'individual' | 'family' | 'event' | 'media';

function ContributionsPanel({ editor_id }: { editor_id: string }) {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({
    queryKey: ['contributor-contributions', editor_id],
    queryFn: () => usersApi.getContributorContributions(editor_id),
  });

  if (isLoading) return <div className="py-2 pl-2"><Spinner size="sm" /></div>;
  if (!data) return null;

  const sections: { label: string; kind: ContributionKind; items: typeof data.individuals }[] = [
    { label: 'Individuals', kind: 'individual', items: data.individuals },
    { label: 'Families', kind: 'family', items: data.families },
    { label: 'Events', kind: 'event', items: data.events },
    { label: 'Media', kind: 'media', items: data.media },
  ];
  const visibleSections = sections.filter((s) => s.items.length > 0);

  if (visibleSections.length === 0) return <p className="text-xs text-gray-400 py-1 pl-2">No contributions found.</p>;

  const targetFor = (kind: ContributionKind, item: typeof data.individuals[number]): string | null => {
    if (kind === 'individual') return `/individuals/${item.id}`;
    if (kind === 'family') return `/families/${item.id}`;
    if (item.individual_id) return `/individuals/${item.individual_id}`;
    if (item.family_id) return `/families/${item.family_id}`;
    return null;
  };

  return (
    <div className="mt-2 pl-2 border-l-2 border-gray-100 space-y-1.5">
      <p className="text-xs text-gray-400 italic">Double-click an item to open it for editing.</p>
      {visibleSections.map(({ label, kind, items }) => (
        <div key={label}>
          <p className="text-xs font-semibold text-gray-500">{label} ({items.length})</p>
          <ul className="mt-0.5 space-y-0.5">
            {items.slice(0, 10).map((item) => {
              const target = targetFor(kind, item);
              return (
                <li
                  key={item.id}
                  onDoubleClick={() => target && navigate(target)}
                  title={target ? 'Double-click to open' : undefined}
                  className={`text-xs text-gray-600 truncate select-none ${target ? 'cursor-pointer hover:bg-gray-50 hover:text-gray-900 rounded px-1' : 'px-1'}`}
                >
                  · {item.label}
                </li>
              );
            })}
            {items.length > 10 && (
              <li className="text-xs text-gray-400 px-1">… and {items.length - 10} more</li>
            )}
          </ul>
        </div>
      ))}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// Contributors tab
// ──────────────────────────────────────────────────────────────
function ContributorsTab() {
  const qc = useQueryClient();
  const { data: contributors = [], isLoading } = useQuery({
    queryKey: ['contributors'],
    queryFn: usersApi.listContributors,
    staleTime: 0,
  });

  const [resetLinks, setResetLinks] = useState<Record<string, string>>({});
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [expandedContributions, setExpandedContributions] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null); // "<editor_id>:<action>"

  const isBusy = (editor_id: string, action: string) => busy === `${editor_id}:${action}`;
  const anyBusy = (editor_id: string) => busy?.startsWith(`${editor_id}:`) ?? false;

  const withBusy = async (editor_id: string, action: string, fn: () => Promise<void>) => {
    const key = `${editor_id}:${action}`;
    if (busy) return;
    setBusy(key);
    try { await fn(); } finally { setBusy(null); }
  };

  const approve = (editor_id: string) => withBusy(editor_id, 'approve', async () => {
    try {
      await usersApi.activateContributor(editor_id);
      qc.invalidateQueries({ queryKey: ['contributors'] });
      toast.success('Contributor approved — they can now log in');
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to approve'));
    }
  });

  const freeze = (editor_id: string) => withBusy(editor_id, 'freeze', async () => {
    try {
      await usersApi.setContributorActive(editor_id, false);
      qc.invalidateQueries({ queryKey: ['contributors'] });
      toast.success('Account frozen — login and edits disabled');
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to freeze account'));
    }
  });

  const unfreeze = (editor_id: string) => withBusy(editor_id, 'unfreeze', async () => {
    try {
      await usersApi.setContributorActive(editor_id, true);
      qc.invalidateQueries({ queryKey: ['contributors'] });
      toast.success('Account unfrozen');
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to unfreeze account'));
    }
  });

  const resetPassword = (editor_id: string) => withBusy(editor_id, 'reset', async () => {
    try {
      const res = await usersApi.resetContributorPassword(editor_id);
      if (res.emailed) {
        toast.success('Password reset email sent');
      } else {
        setResetLinks((prev) => ({ ...prev, [editor_id]: res.link }));
        toast.success('Reset link generated');
      }
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to reset password'));
    }
  });

  const deleteContributor = (editor_id: string) => withBusy(editor_id, 'delete', async () => {
    try {
      await usersApi.deleteContributor(editor_id);
      qc.invalidateQueries({ queryKey: ['contributors'] });
      setConfirmDelete(null);
      toast.success('Contributor account deleted');
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? 'Failed to delete';
      toast.error(msg);
      setConfirmDelete(null);
    }
  });

  const deleteContributorWithData = (editor_id: string) => withBusy(editor_id, 'delete', async () => {
    try {
      await usersApi.deleteContributorWithData(editor_id);
      qc.invalidateQueries({ queryKey: ['contributors'] });
      setConfirmDelete(null);
      toast.success('Contributor and all their contributions deleted');
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? 'Failed to delete';
      toast.error(msg);
      setConfirmDelete(null);
    }
  });

  if (isLoading) return <div className="py-8 flex justify-center"><Spinner /></div>;

  // pending approval: inactive and never logged in (signed up, email verified, awaiting owner)
  // frozen: inactive but has logged in before (owner froze them)
  const pendingApproval = contributors.filter((c) => !c.is_active && !c.last_login_at);
  const frozen = contributors.filter((c) => !c.is_active && !!c.last_login_at);
  const active = contributors.filter((c) => c.is_active);

  if (contributors.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        <Users className="w-10 h-10 mx-auto mb-2" />
        <p className="text-sm">No contributors yet.</p>
      </div>
    );
  }

  const renderDeleteButton = (editor_id: string, hasContributions: boolean) => {
    if (confirmDelete === editor_id) {
      return (
        <span className="flex items-center gap-1">
          <button
            onClick={() => void (hasContributions ? deleteContributorWithData(editor_id) : deleteContributor(editor_id))}
            disabled={anyBusy(editor_id)}
            className="flex items-center gap-1 px-2 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isBusy(editor_id, 'delete') ? <Spinner size="sm" /> : null}
            {hasContributions ? 'Delete everything' : 'Confirm delete'}
          </button>
          <button
            onClick={() => setConfirmDelete(null)}
            disabled={anyBusy(editor_id)}
            className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
        </span>
      );
    }
    return (
      <button
        onClick={() => setConfirmDelete(editor_id)}
        disabled={anyBusy(editor_id)}
        className="p-1.5 hover:bg-red-50 rounded disabled:opacity-50 disabled:cursor-not-allowed"
        title={hasContributions ? 'Delete contributor and all their contributions' : 'Delete account'}
      >
        <Trash2 className="w-4 h-4 text-red-400" />
      </button>
    );
  };

  const renderContributionsToggle = (editor_id: string) => {
    const expanded = expandedContributions === editor_id;
    return (
      <button
        onClick={() => setExpandedContributions(expanded ? null : editor_id)}
        className="flex items-center gap-0.5 text-xs text-blue-500 hover:text-blue-700 mt-0.5"
      >
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        {expanded ? 'Hide contributions' : 'View contributions'}
      </button>
    );
  };

  return (
    <div className="space-y-6">
      {/* Pending approval */}
      {pendingApproval.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" />
            Awaiting approval ({pendingApproval.length})
          </h3>
          <div className="divide-y divide-gray-100">
            {pendingApproval.map((c) => (
              <div key={c.editor_id} className="py-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-800">{c.display_name}</p>
                    <p className="text-xs text-gray-500">
                      @{c.editor_id}
                      {c.email && <> · {c.email}</>}
                    </p>
                    {c.created_at && (
                      <p className="text-xs text-gray-400">
                        Signed up {new Date(c.created_at).toLocaleDateString()}
                      </p>
                    )}
                    {c.has_contributions && renderContributionsToggle(c.editor_id)}
                    {c.message && (
                      <div className="mt-1 bg-gray-50 rounded px-2 py-1">
                        <p className="text-xs text-gray-400 mb-0.5">Signup note from {c.display_name}:</p>
                        <p className="text-xs text-gray-600 italic">"{c.message}"</p>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => void approve(c.editor_id)}
                      disabled={anyBusy(c.editor_id)}
                      className="flex items-center gap-1 px-2.5 py-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 text-xs font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      title="Approve — enable login for this contributor"
                    >
                      {isBusy(c.editor_id, 'approve') ? <Spinner size="sm" /> : <UserCheck className="w-4 h-4" />}
                      Approve
                    </button>
                    {renderDeleteButton(c.editor_id, c.has_contributions)}
                  </div>
                </div>
                {confirmDelete === c.editor_id && c.has_contributions && (
                  <p className="text-xs text-red-500">This will permanently delete the contributor account and all their contributions to the tree.</p>
                )}
                {expandedContributions === c.editor_id && <ContributionsPanel editor_id={c.editor_id} />}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Frozen accounts */}
      {frozen.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
            <ShieldOff className="w-3.5 h-3.5" />
            Frozen ({frozen.length})
          </h3>
          <div className="divide-y divide-gray-100">
            {frozen.map((c) => (
              <div key={c.editor_id} className="py-4 space-y-1">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-500">{c.display_name}</p>
                    <p className="text-xs text-gray-400">
                      @{c.editor_id}
                      {c.email && <> · {c.email}</>}
                    </p>
                    {c.has_contributions && renderContributionsToggle(c.editor_id)}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => void unfreeze(c.editor_id)}
                      disabled={anyBusy(c.editor_id)}
                      className="flex items-center gap-1 px-2.5 py-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 text-xs font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      title="Unfreeze — re-enable login"
                    >
                      {isBusy(c.editor_id, 'unfreeze') ? <Spinner size="sm" /> : <ShieldCheck className="w-3.5 h-3.5" />}
                      Unfreeze
                    </button>
                    {renderDeleteButton(c.editor_id, c.has_contributions)}
                  </div>
                </div>
                {confirmDelete === c.editor_id && c.has_contributions && (
                  <p className="text-xs text-red-500">This will permanently delete the contributor account and all their contributions to the tree.</p>
                )}
                {expandedContributions === c.editor_id && <ContributionsPanel editor_id={c.editor_id} />}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Active contributors */}
      {active.length > 0 && (
        <div>
          {(pendingApproval.length > 0 || frozen.length > 0) && (
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
              Active ({active.length})
            </h3>
          )}
          <div className="divide-y divide-gray-100">
            {active.map((c) => (
              <div key={c.editor_id} className="py-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-800">{c.display_name}</p>
                    <p className="text-xs text-gray-500">
                      @{c.editor_id}
                      {c.email && <> · {c.email}</>}
                    </p>
                    {c.last_login_at && (
                      <p className="text-xs text-gray-400">
                        Last login {new Date(c.last_login_at).toLocaleDateString()}
                      </p>
                    )}
                    {c.has_contributions && renderContributionsToggle(c.editor_id)}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => void freeze(c.editor_id)}
                      disabled={anyBusy(c.editor_id)}
                      className="flex items-center gap-1 px-2.5 py-1.5 hover:bg-amber-50 text-amber-600 text-xs font-medium rounded-lg transition-colors border border-transparent hover:border-amber-200 disabled:opacity-50 disabled:cursor-not-allowed"
                      title="Freeze — disable login and edits immediately"
                    >
                      {isBusy(c.editor_id, 'freeze') ? <Spinner size="sm" /> : <ShieldOff className="w-3.5 h-3.5" />}
                      Freeze
                    </button>
                    <button
                      onClick={() => void resetPassword(c.editor_id)}
                      disabled={anyBusy(c.editor_id)}
                      className="p-1.5 hover:bg-gray-100 rounded disabled:opacity-50 disabled:cursor-not-allowed"
                      title="Reset password"
                    >
                      {isBusy(c.editor_id, 'reset') ? <Spinner size="sm" /> : <RefreshCw className="w-4 h-4 text-gray-500" />}
                    </button>
                    {renderDeleteButton(c.editor_id, c.has_contributions)}
                  </div>
                </div>
                {confirmDelete === c.editor_id && c.has_contributions && (
                  <p className="text-xs text-red-500">This will permanently delete the contributor account and all their contributions to the tree.</p>
                )}
                {resetLinks[c.editor_id] && (
                  <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                    <LinkIcon className="w-4 h-4 text-amber-600 flex-shrink-0" />
                    <span className="text-xs font-mono text-amber-700 truncate flex-1">
                      {resetLinks[c.editor_id]}
                    </span>
                    <button
                      onClick={() => copyToClipboard(resetLinks[c.editor_id])}
                      className="text-xs text-amber-700 hover:underline flex-shrink-0"
                    >
                      Copy
                    </button>
                  </div>
                )}
                {expandedContributions === c.editor_id && <ContributionsPanel editor_id={c.editor_id} />}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// Page root
// ──────────────────────────────────────────────────────────────
type Tab = 'share' | 'contributors';

export function UserManagerPage() {
  const [tab, setTab] = useState<Tab>('share');

  const tabs: { id: Tab; label: string }[] = [
    { id: 'share', label: 'Share Links' },
    { id: 'contributors', label: 'Contributors' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">User Manager</h1>
        <p className="text-gray-600 mt-1">Manage share links and contributors</p>
      </div>

      <Card>
        {/* Tabs */}
        <div className="border-b border-gray-200 -mx-6 -mt-6 px-6 mb-6">
          <nav className="flex gap-6">
            {tabs.map(({ id, label }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={`py-3 text-sm font-medium border-b-2 transition-colors ${
                  tab === id
                    ? 'border-emerald-500 text-emerald-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>

        {tab === 'share' && <ShareTokensTab />}
        {tab === 'contributors' && <ContributorsTab />}
      </Card>
    </div>
  );
}
