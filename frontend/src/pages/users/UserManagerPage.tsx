import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Share2,
  Copy,
  Trash2,
  Plus,
  Users,
  UserCheck,
  UserX,
  RefreshCw,
  CheckCircle,
  XCircle,
  Link as LinkIcon,
  Mail,
} from 'lucide-react';
import { usersApi } from '../../api/auth';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { Spinner } from '../../components/common/Spinner';
import toast from 'react-hot-toast';

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
  const [showCreate, setShowCreate] = useState(false);

  const activeTokens = tokens.filter((t) => t.is_active);

  const create = async () => {
    setIsCreating(true);
    try {
      await usersApi.createShareToken({ label: label.trim() || undefined, expires_after_days: 90 });
      qc.invalidateQueries({ queryKey: ['share-tokens'] });
      toast.success('Share link created');
      setLabel('');
      setShowCreate(false);
    } catch {
      toast.error('Failed to create share link');
    } finally {
      setIsCreating(false);
    }
  };

  const copy = (token: string) => {
    const url = `${window.location.origin}/tree?share=${token}`;
    navigator.clipboard.writeText(url).then(() => toast.success('Link copied!'));
  };

  const revoke = async (id: number) => {
    try {
      await usersApi.revokeShareToken(id);
      qc.invalidateQueries({ queryKey: ['share-tokens'] });
      toast.success('Link revoked');
    } catch {
      toast.error('Failed to revoke');
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
              onKeyDown={(e) => { if (e.key === 'Enter') void create(); }}
            />
          </div>
          <Button size="sm" onClick={create} disabled={isCreating} isLoading={isCreating}>
            Create
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setShowCreate(false)}>
            Cancel
          </Button>
        </div>
      )}

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
                <p className="text-sm font-medium text-gray-800">{t.label || 'Unnamed link'}</p>
                <p className="text-xs text-gray-400 font-mono truncate">
                  {window.location.origin}/tree?share={t.token}
                </p>
                {t.created_at && (
                  <p className="text-xs text-gray-400">
                    Created {new Date(t.created_at).toLocaleDateString()}
                    {t.last_used_at && ` · Last used ${new Date(t.last_used_at).toLocaleDateString()}`}
                  </p>
                )}
              </div>
              <button
                onClick={() => copy(t.token)}
                className="p-1.5 hover:bg-gray-100 rounded"
                title="Copy link"
              >
                <Copy className="w-4 h-4 text-gray-500" />
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
// Contributors tab
// ──────────────────────────────────────────────────────────────
function ContributorsTab() {
  const qc = useQueryClient();
  const { data: contributors = [], isLoading } = useQuery({
    queryKey: ['contributors'],
    queryFn: usersApi.listContributors,
  });

  const [resetLinks, setResetLinks] = useState<Record<string, string>>({});

  const toggleActive = async (editor_id: string, is_active: boolean) => {
    try {
      await usersApi.setContributorActive(editor_id, !is_active);
      qc.invalidateQueries({ queryKey: ['contributors'] });
    } catch {
      toast.error('Failed to update status');
    }
  };

  const resetPassword = async (editor_id: string) => {
    try {
      const res = await usersApi.resetContributorPassword(editor_id);
      if (res.emailed) {
        toast.success('Password reset email sent');
      } else {
        setResetLinks((prev) => ({ ...prev, [editor_id]: res.link }));
        toast.success('Reset link generated');
      }
    } catch {
      toast.error('Failed to reset password');
    }
  };

  if (isLoading) return <div className="py-8 flex justify-center"><Spinner /></div>;

  if (contributors.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        <Users className="w-10 h-10 mx-auto mb-2" />
        <p className="text-sm">No contributors yet.</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-gray-100">
      {contributors.map((c) => (
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
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => void toggleActive(c.editor_id, c.is_active)}
                className={`p-1.5 rounded ${c.is_active ? 'hover:bg-red-50' : 'hover:bg-emerald-50'}`}
                title={c.is_active ? 'Deactivate' : 'Activate'}
              >
                {c.is_active
                  ? <UserX className="w-4 h-4 text-red-400" />
                  : <UserCheck className="w-4 h-4 text-emerald-500" />
                }
              </button>
              <button
                onClick={() => void resetPassword(c.editor_id)}
                className="p-1.5 hover:bg-gray-100 rounded"
                title="Reset password"
              >
                <RefreshCw className="w-4 h-4 text-gray-500" />
              </button>
            </div>
          </div>
          {resetLinks[c.editor_id] && (
            <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              <LinkIcon className="w-4 h-4 text-amber-600 flex-shrink-0" />
              <span className="text-xs font-mono text-amber-700 truncate flex-1">
                {resetLinks[c.editor_id]}
              </span>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(resetLinks[c.editor_id]).then(() =>
                    toast.success('Link copied!')
                  );
                }}
                className="text-xs text-amber-700 hover:underline flex-shrink-0"
              >
                Copy
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// Requests tab (pending invitations)
// ──────────────────────────────────────────────────────────────
function RequestsTab() {
  const qc = useQueryClient();
  const { data: invitations = [], isLoading } = useQuery({
    queryKey: ['invitations'],
    queryFn: usersApi.listInvitations,
  });

  const [approveLinks, setApproveLinks] = useState<Record<number, string>>({});

  const approve = async (id: number) => {
    try {
      const res = await usersApi.approveInvitation(id);
      qc.invalidateQueries({ queryKey: ['invitations'] });
      qc.invalidateQueries({ queryKey: ['contributors'] });
      if (res.emailed) {
        toast.success('Approved — set-password email sent');
      } else if (res.needs_set_password) {
        setApproveLinks((prev) => ({ ...prev, [id]: res.link }));
        toast.success('Approved — share the link below');
      } else {
        toast.success('Approved');
      }
    } catch {
      toast.error('Failed to approve');
    }
  };

  const reject = async (id: number) => {
    try {
      await usersApi.rejectInvitation(id);
      qc.invalidateQueries({ queryKey: ['invitations'] });
      toast.success('Request rejected');
    } catch {
      toast.error('Failed to reject');
    }
  };

  if (isLoading) return <div className="py-8 flex justify-center"><Spinner /></div>;

  const pending = invitations.filter((inv) => inv.status === 'pending');
  const processed = invitations.filter((inv) => inv.status !== 'pending');

  return (
    <div className="space-y-6">
      {pending.length === 0 && (
        <div className="text-center py-8 text-gray-400">
          <Mail className="w-10 h-10 mx-auto mb-2" />
          <p className="text-sm">No pending requests.</p>
        </div>
      )}

      {pending.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Pending ({pending.length})
          </h3>
          <div className="divide-y divide-gray-100">
            {pending.map((inv) => (
              <div key={inv.id} className="py-4 space-y-2">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800">{inv.display_name}</p>
                    {inv.email && <p className="text-xs text-gray-500">{inv.email}</p>}
                    {inv.message && (
                      <p className="text-xs text-gray-600 italic mt-1 bg-gray-50 rounded px-2 py-1">
                        "{inv.message}"
                      </p>
                    )}
                    <p className="text-xs text-gray-400 mt-1">
                      Requested {new Date(inv.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => void approve(inv.id)}
                      className="p-1.5 hover:bg-emerald-50 rounded"
                      title="Approve"
                    >
                      <CheckCircle className="w-5 h-5 text-emerald-500" />
                    </button>
                    <button
                      onClick={() => void reject(inv.id)}
                      className="p-1.5 hover:bg-red-50 rounded"
                      title="Reject"
                    >
                      <XCircle className="w-5 h-5 text-red-400" />
                    </button>
                  </div>
                </div>
                {approveLinks[inv.id] && (
                  <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                    <LinkIcon className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                    <span className="text-xs font-mono text-emerald-700 truncate flex-1">
                      {approveLinks[inv.id]}
                    </span>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(approveLinks[inv.id]).then(() =>
                          toast.success('Link copied!')
                        );
                      }}
                      className="text-xs text-emerald-700 hover:underline flex-shrink-0"
                    >
                      Copy
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {processed.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Processed
          </h3>
          <div className="divide-y divide-gray-100">
            {processed.map((inv) => (
              <div key={inv.id} className="py-3 flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-700">{inv.display_name}</p>
                  {inv.email && <p className="text-xs text-gray-400">{inv.email}</p>}
                </div>
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                    inv.status === 'approved'
                      ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-red-100 text-red-600'
                  }`}
                >
                  {inv.status}
                </span>
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
type Tab = 'share' | 'contributors' | 'requests';

export function UserManagerPage() {
  const [tab, setTab] = useState<Tab>('share');

  const tabs: { id: Tab; label: string }[] = [
    { id: 'share', label: 'Share Links' },
    { id: 'contributors', label: 'Contributors' },
    { id: 'requests', label: 'Requests' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">User Manager</h1>
        <p className="text-gray-600 mt-1">Manage share links, contributors, and access requests</p>
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
        {tab === 'requests' && <RequestsTab />}
      </Card>
    </div>
  );
}
