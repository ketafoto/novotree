import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Shield, AlertTriangle, CheckCircle2, Trash2, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';

import { Button } from '../../components/common/Button';
import {
  privacyRequestsApi,
  type PrivacyRequestRow,
  type PrivacyRequestStatus,
  type PrivacyRequestType,
} from '../../api/privacy_requests';
import { individualsApi } from '../../api/individuals';
import { usePrivacyConfig } from '../../hooks/usePrivacyConfig';
import { formatIndividualName, getLatestName } from '../../utils/nameUtils';
import { TestPrivacyRequestTimestampPanel } from './TestPrivacyRequestTimestampPanel';

const STATUS_LABEL: Record<PrivacyRequestStatus, string> = {
  open: 'Open',
  acknowledged: 'Acknowledged',
  resolved: 'Resolved',
  escalated: 'Escalated',
};

const STATUS_BADGE: Record<PrivacyRequestStatus, string> = {
  open: 'bg-amber-100 text-amber-800',
  acknowledged: 'bg-blue-100 text-blue-800',
  resolved: 'bg-emerald-100 text-emerald-800',
  escalated: 'bg-red-100 text-red-800',
};

const REQUEST_TYPE_LABEL: Record<PrivacyRequestType, string> = {
  removal: 'Removal',
  access: 'Access',
  correction: 'Correction',
};

const REQUEST_TYPE_BADGE: Record<PrivacyRequestType, string> = {
  removal: 'bg-rose-100 text-rose-800',
  access: 'bg-indigo-100 text-indigo-800',
  correction: 'bg-cyan-100 text-cyan-800',
};

// Filter value shown in the queue header. 'all' is the default — Owners
// usually want the full queue, and per-kind filtering is a triage convenience.
type RequestTypeFilter = 'all' | PrivacyRequestType;

// Best-effort link from a request to the named Individuals. The requester's
// message is free-form so this is a heuristic -- match every GEDCOM-shaped ID
// (`I` followed by digits). A removal request from the tree selection CTA
// (PRIVACY_DESIGN.md 3.9) packs several; an access request may name one. If
// nothing matches, no block is rendered; the spec is explicit that we do not
// build a search UI for this.
const INDIVIDUAL_ID_RE = /\bI\d+\b/g;

function extractIndividualIds(message: string): string[] {
  const matches = message.match(INDIVIDUAL_ID_RE);
  // Dedup while preserving first-seen order (the same person may be named twice).
  return matches ? [...new Set(matches)] : [];
}

// One referenced person, resolved against the Owner's individuals list. When
// `individual` is found we can show the real name and link to the numeric
// detail route; otherwise we fall back to the raw GEDCOM id with no link (the
// id may be a typo, or the person may already have been deleted).
interface ReferencedPerson {
  gedcomId: string;
  numericId?: number;
  name?: string;
}

function resolveReferencedPeople(
  message: string,
  byGedcomId: Map<string, { id: number; name: string }>,
): ReferencedPerson[] {
  return extractIndividualIds(message).map((gedcomId) => {
    const hit = byGedcomId.get(gedcomId);
    return { gedcomId, numericId: hit?.id, name: hit?.name };
  });
}

function StatusBadge({ status }: { status: PrivacyRequestStatus }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_BADGE[status]}`}>
      {STATUS_LABEL[status]}
    </span>
  );
}

function RequestTypeBadge({ type }: { type: PrivacyRequestType }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${REQUEST_TYPE_BADGE[type]}`}>
      {REQUEST_TYPE_LABEL[type]}
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

function PrivacyRequestCard({
  row,
  individualsByGedcomId,
  onResolve,
  onDelete,
  resolving,
  deleting,
  test_allowOverride,
  test_onOverridden,
}: {
  row: PrivacyRequestRow;
  individualsByGedcomId: Map<string, { id: number; name: string }>;
  onResolve: (id: number) => void;
  onDelete: (id: number) => void;
  resolving: boolean;
  deleting: boolean;
  test_allowOverride: boolean;
  test_onOverridden: (updated: PrivacyRequestRow) => void;
}) {
  const isTerminal = row.status === 'resolved' || row.status === 'escalated';
  // People named by id in the message -- removal, access, or correction alike
  // (see comment on INDIVIDUAL_ID_RE).
  const referencedPeople = resolveReferencedPeople(row.message, individualsByGedcomId);

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-gray-500">#{row.id}</span>
            <RequestTypeBadge type={row.request_type} />
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

      {referencedPeople.length > 0 && (
        <div className="text-sm space-y-1">
          <span className="text-gray-500">Referenced people:</span>
          <ul className="space-y-1">
            {referencedPeople.map((person) => (
              <li key={person.gedcomId} className="flex items-center gap-2">
                {person.numericId !== undefined ? (
                  <Link
                    to={`/individuals/${person.numericId}`}
                    className="inline-flex items-center gap-1 text-indigo-700 hover:text-indigo-800 hover:underline"
                  >
                    {person.name}
                    <code className="bg-indigo-50 px-1 rounded text-xs">{person.gedcomId}</code>
                    <ExternalLink className="w-3 h-3" />
                  </Link>
                ) : (
                  // Unresolved -- id may be a typo or the person is already gone.
                  <span className="inline-flex items-center gap-1 text-gray-500">
                    <code className="bg-gray-100 px-1 rounded text-xs">{person.gedcomId}</code>
                    <span className="text-xs">(not found on this tree)</span>
                  </span>
                )}
              </li>
            ))}
          </ul>
          {row.request_type === 'access' && (
            <p className="text-xs text-gray-500">
              Use the "Export data" button on each Individual page (§2.6) to fulfil this access
              request, then mark resolved.
            </p>
          )}
        </div>
      )}

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
        <TestPrivacyRequestTimestampPanel row={row} onUpdated={test_onOverridden} />
      )}
    </div>
  );
}

export function PrivacyRequestsPage() {
  const queryClient = useQueryClient();
  const { config } = usePrivacyConfig();
  const [includeResolved, setIncludeResolved] = useState(false);
  const [typeFilter, setTypeFilter] = useState<RequestTypeFilter>('all');
  const [pendingId, setPendingId] = useState<number | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ['privacy-requests', includeResolved],
    queryFn: () => privacyRequestsApi.list(includeResolved),
  });

  // Resolve the GEDCOM ids packed into request messages to real people so each
  // card can show a name + a working link to the numeric detail route (the raw
  // I-id is not a valid /individuals/{id} param). Owner-only page, so the full
  // list is already authorized; fetched once and shared across all cards.
  const { data: individuals } = useQuery({
    queryKey: ['individuals', 'privacy-request-refs'],
    queryFn: () => individualsApi.list({ limit: 100000 }),
  });

  const individualsByGedcomId = useMemo(() => {
    const map = new Map<string, { id: number; name: string }>();
    for (const ind of individuals ?? []) {
      if (ind.gedcom_id) {
        map.set(ind.gedcom_id, {
          id: ind.id,
          name: formatIndividualName(getLatestName(ind.names)),
        });
      }
    }
    return map;
  }, [individuals]);

  const filtered = useMemo(() => {
    if (!data) return data;
    return typeFilter === 'all' ? data : data.filter((r) => r.request_type === typeFilter);
  }, [data, typeFilter]);

  const resolveMutation = useMutation({
    mutationFn: privacyRequestsApi.resolve,
    onMutate: (id) => setPendingId(id),
    onSettled: () => setPendingId(null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['privacy-requests'] });
      toast.success('Marked resolved');
    },
    onError: () => toast.error('Could not update — please retry'),
  });

  const deleteMutation = useMutation({
    mutationFn: privacyRequestsApi.remove,
    onMutate: (id) => setPendingId(id),
    onSettled: () => setPendingId(null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['privacy-requests'] });
      toast.success('Request deleted');
    },
    onError: () => toast.error('Could not delete — please retry'),
  });

  const handleDelete = (id: number) => {
    if (!window.confirm(
      'Delete this privacy-request record? It will no longer be visible. ' +
      'The system would auto-delete it after the retention window anyway — ' +
      'use this only if you need it gone now.',
    )) return;
    deleteMutation.mutate(id);
  };

  const slaDays = config?.privacy_request_sla_days ?? 30;
  const retentionMonths = config?.privacy_request_retention_months ?? 12;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <header className="flex items-center gap-3">
        <Shield className="w-7 h-7 text-emerald-600" />
        <div>
          <h1 className="text-2xl font-semibold">Privacy requests</h1>
          <p className="text-sm text-gray-600">
            Removal, access, and correction requests submitted by data subjects.
            Respond within {slaDays} days or the system auto-escalates.
          </p>
        </div>
      </header>

      <div className="bg-amber-50 border border-amber-200 rounded p-4 text-sm text-amber-900">
        After acting on a request (removing, exporting, or correcting the records),
        click <strong>Mark resolved</strong> so the system stops the SLA timer.
        Resolved and escalated rows are auto-deleted after {retentionMonths} months.
      </div>

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-gray-600">Filter:</span>
          {(['all', 'removal', 'access', 'correction'] as const).map((kind) => (
            <button
              key={kind}
              type="button"
              onClick={() => setTypeFilter(kind)}
              className={`px-2.5 py-1 rounded text-xs font-medium border ${
                typeFilter === kind
                  ? 'bg-emerald-50 border-emerald-300 text-emerald-800'
                  : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
              }`}
            >
              {kind === 'all' ? 'All' : REQUEST_TYPE_LABEL[kind]}
            </button>
          ))}
        </div>
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
      {error && <p className="text-red-600">Could not load privacy requests.</p>}

      {filtered && filtered.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          No privacy requests {includeResolved ? 'on record' : 'awaiting action'}
          {typeFilter !== 'all' && ` (${REQUEST_TYPE_LABEL[typeFilter]} filter active)`}.
        </div>
      )}

      {filtered && filtered.length > 0 && (
        <div className="space-y-3">
          {filtered.map((row) => (
            <PrivacyRequestCard
              key={row.id}
              row={row}
              individualsByGedcomId={individualsByGedcomId}
              onResolve={(id) => resolveMutation.mutate(id)}
              onDelete={handleDelete}
              resolving={pendingId === row.id && resolveMutation.isPending}
              deleting={pendingId === row.id && deleteMutation.isPending}
              test_allowOverride={config?.test_allow_timestamp_override ?? false}
              test_onOverridden={() =>
                queryClient.invalidateQueries({ queryKey: ['privacy-requests'] })
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
