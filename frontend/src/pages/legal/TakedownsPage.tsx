import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Shield, AlertTriangle, CheckCircle2, Trash2 } from 'lucide-react';
import toast from 'react-hot-toast';

import { Button } from '../../components/common/Button';
import { takedownApi, type TakedownRow, type TakedownStatus } from '../../api/takedown';
import { usePrivacyConfig } from '../../hooks/usePrivacyConfig';
import { TestTakedownTimestampPanel } from './TestTakedownTimestampPanel';

const STATUS_LABEL: Record<TakedownStatus, string> = {
  open: 'Open',
  acknowledged: 'Acknowledged',
  resolved: 'Resolved',
  escalated: 'Escalated',
};

const STATUS_BADGE: Record<TakedownStatus, string> = {
  open: 'bg-amber-100 text-amber-800',
  acknowledged: 'bg-blue-100 text-blue-800',
  resolved: 'bg-emerald-100 text-emerald-800',
  escalated: 'bg-red-100 text-red-800',
};

function StatusBadge({ status }: { status: TakedownStatus }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_BADGE[status]}`}>
      {STATUS_LABEL[status]}
    </span>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function TakedownCard({
  row,
  onResolve,
  onDelete,
  resolving,
  deleting,
  test_allowOverride,
  test_onOverridden,
}: {
  row: TakedownRow;
  onResolve: (id: number) => void;
  onDelete: (id: number) => void;
  resolving: boolean;
  deleting: boolean;
  test_allowOverride: boolean;
  test_onOverridden: (updated: TakedownRow) => void;
}) {
  const isTerminal = row.status === 'resolved' || row.status === 'escalated';
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-500">#{row.id}</span>
            <StatusBadge status={row.status} />
            {row.status === 'escalated' && (
              <AlertTriangle className="w-4 h-4 text-red-600" aria-label="SLA exceeded" />
            )}
          </div>
          <p className="text-base font-medium text-gray-900 mt-1">
            {row.requester_name}
          </p>
          <p className="text-sm text-gray-600">
            <a className="hover:underline" href={`mailto:${row.requester_email}`}>
              {row.requester_email}
            </a>
            {row.requester_phone && <span className="ml-2 text-gray-400">• {row.requester_phone}</span>}
          </p>
        </div>
        <div className="text-right text-xs text-gray-500 shrink-0">
          <div>Submitted {formatDate(row.created_at)}</div>
          {row.escalated_at && (
            <div className="text-red-700">Escalated {formatDate(row.escalated_at)}</div>
          )}
          {row.resolved_at && row.status === 'resolved' && (
            <div className="text-emerald-700">Resolved {formatDate(row.resolved_at)}</div>
          )}
        </div>
      </div>

      {row.individual_id && (
        <div className="text-sm">
          <span className="text-gray-500">Individual ID hint: </span>
          <code className="px-1.5 py-0.5 bg-gray-100 rounded text-gray-700">{row.individual_id}</code>
        </div>
      )}

      <div className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 rounded p-3">
        {row.message}
      </div>

      <div className="flex items-center justify-end gap-2 pt-1">
        {row.status !== 'resolved' && (
          <Button
            size="sm"
            variant="secondary"
            onClick={() => onResolve(row.id)}
            isLoading={resolving}
          >
            <CheckCircle2 className="w-4 h-4 mr-1" />
            Mark resolved
          </Button>
        )}
        {isTerminal && (
          <Button
            size="sm"
            variant="danger"
            onClick={() => onDelete(row.id)}
            isLoading={deleting}
          >
            <Trash2 className="w-4 h-4 mr-1" />
            Delete
          </Button>
        )}
      </div>

      {test_allowOverride && (
        <TestTakedownTimestampPanel row={row} onUpdated={test_onOverridden} />
      )}
    </div>
  );
}

export function TakedownsPage() {
  const queryClient = useQueryClient();
  const { config } = usePrivacyConfig();
  const [includeResolved, setIncludeResolved] = useState(false);
  const [pendingId, setPendingId] = useState<number | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ['takedowns', includeResolved],
    queryFn: () => takedownApi.list(includeResolved),
  });

  const resolveMutation = useMutation({
    mutationFn: takedownApi.resolve,
    onMutate: (id) => setPendingId(id),
    onSettled: () => setPendingId(null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['takedowns'] });
      toast.success('Marked resolved');
    },
    onError: () => toast.error('Could not update — please retry'),
  });

  const deleteMutation = useMutation({
    mutationFn: takedownApi.remove,
    onMutate: (id) => setPendingId(id),
    onSettled: () => setPendingId(null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['takedowns'] });
      toast.success('Request deleted');
    },
    onError: () => toast.error('Could not delete — please retry'),
  });

  const handleDelete = (id: number) => {
    if (!window.confirm(
      'Delete this takedown record? It will no longer be visible. ' +
      'The system would auto-delete it after the retention window anyway — ' +
      'use this only if you need it gone now.',
    )) return;
    deleteMutation.mutate(id);
  };

  const slaDays = config?.takedown_sla_days ?? 30;
  const retentionMonths = config?.takedown_request_retention_months ?? 12;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <header className="flex items-center gap-3">
        <Shield className="w-7 h-7 text-emerald-600" />
        <div>
          <h1 className="text-2xl font-semibold">Privacy — takedown requests</h1>
          <p className="text-sm text-gray-600">
            "Remove me from a tree" requests submitted by data subjects.
            Respond within {slaDays} days or the system auto-escalates.
          </p>
        </div>
      </header>

      <div className="bg-amber-50 border border-amber-200 rounded p-4 text-sm text-amber-900">
        After acting on a request (removing or anonymising the individual),
        click <strong>Mark resolved</strong> so the system stops the SLA timer.
        Resolved and escalated rows are auto-deleted after {retentionMonths} months.
      </div>

      <div className="flex items-center justify-end">
        <label className="text-sm text-gray-600 flex items-center gap-2">
          <input
            type="checkbox"
            checked={includeResolved}
            onChange={(e) => setIncludeResolved(e.target.checked)}
          />
          Show resolved
        </label>
      </div>

      {isLoading && <p className="text-gray-500">Loading…</p>}
      {error && <p className="text-red-600">Could not load takedown requests.</p>}

      {data && data.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          No takedown requests {includeResolved ? 'on record' : 'awaiting action'}.
        </div>
      )}

      {data && data.length > 0 && (
        <div className="space-y-3">
          {data.map((row) => (
            <TakedownCard
              key={row.id}
              row={row}
              onResolve={(id) => resolveMutation.mutate(id)}
              onDelete={handleDelete}
              resolving={pendingId === row.id && resolveMutation.isPending}
              deleting={pendingId === row.id && deleteMutation.isPending}
              test_allowOverride={config?.test_allow_timestamp_override ?? false}
              test_onOverridden={() =>
                queryClient.invalidateQueries({ queryKey: ['takedowns'] })
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
