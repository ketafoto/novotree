/**
 * TEST-ONLY component — shifts created_at / resolved_at on a takedown row so
 * the SLA reminder / escalation / retention sweep paths can be exercised on
 * a test VM without waiting 30 days.
 *
 * Gated by `PrivacyConfig.test_allow_timestamp_override`. The backend rejects
 * the underlying endpoint when the flag is off, so the parent component is
 * responsible for not rendering this panel in production. All symbols in
 * this file are `test_`-prefixed so they grep cleanly during review.
 *
 * Must remain off in production. See backend
 * PrivacySettings.test_allow_timestamp_override.
 */
import { useState } from 'react';
import { Beaker } from 'lucide-react';
import toast from 'react-hot-toast';

import { Button } from '../../components/common/Button';
import { takedownApi, type TakedownRow } from '../../api/takedown';

interface TestTakedownTimestampPanelProps {
  row: TakedownRow;
  onUpdated: (updated: TakedownRow) => void;
}

// Presets keyed to the sweeper thresholds:
//   - reminder fires at day 14, so -15d puts an open row past the threshold
//   - escalation fires at day takedown_sla_days (default 30), so -31d trips it
//   - retention deletion fires at takedown_request_retention_months (default 12),
//     so -13mo on a resolved/escalated row makes it eligible for cleanup
const test_PRESETS: ReadonlyArray<{ label: string; days: number; hint: string }> = [
  { label: '-15 days', days: -15, hint: 'past reminder threshold' },
  { label: '-31 days', days: -31, hint: 'past escalation threshold' },
  { label: '-13 months', days: -395, hint: 'past retention threshold (resolved/escalated only)' },
];

function test_isoNDaysFromNow(days: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString();
}

function test_toLocalInputValue(iso: string): string {
  // <input type="datetime-local"> wants "YYYY-MM-DDTHH:mm" in local time.
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

function test_fromLocalInputValue(localValue: string): string {
  // Reverse of the above — `new Date(local)` interprets the value in the
  // browser's local TZ, then toISOString gives us UTC.
  return new Date(localValue).toISOString();
}

export function TestTakedownTimestampPanel({ row, onUpdated }: TestTakedownTimestampPanelProps) {
  const [open, setOpen] = useState(false);
  const [createdAt, setCreatedAt] = useState(test_toLocalInputValue(row.created_at));
  const [resolvedAt, setResolvedAt] = useState(
    row.resolved_at ? test_toLocalInputValue(row.resolved_at) : '',
  );
  const [submitting, setSubmitting] = useState(false);

  const test_applyPreset = (days: number) => {
    setCreatedAt(test_toLocalInputValue(test_isoNDaysFromNow(days)));
  };

  const test_applyResolvedPreset = (days: number) => {
    setResolvedAt(test_toLocalInputValue(test_isoNDaysFromNow(days)));
  };

  const test_submit = async () => {
    setSubmitting(true);
    try {
      const payload: { test_created_at?: string; test_resolved_at?: string } = {};
      if (createdAt) payload.test_created_at = test_fromLocalInputValue(createdAt);
      if (resolvedAt) payload.test_resolved_at = test_fromLocalInputValue(resolvedAt);
      const updated = await takedownApi.test_overrideTimestamps(row.id, payload);
      onUpdated(updated);
      toast.success('Timestamps overridden (TEST)');
    } catch {
      toast.error('Override failed — check that PRIVACY_ALLOW_TIMESTAMP_OVERRIDE is set');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="border-2 border-dashed border-fuchsia-300 bg-fuchsia-50 rounded p-3 text-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-fuchsia-900 font-medium"
      >
        <Beaker className="w-4 h-4" />
        Testing tools — {open ? 'hide' : 'show'}
        <span className="text-xs text-fuchsia-700 font-normal">
          (PRIVACY_ALLOW_TIMESTAMP_OVERRIDE is on)
        </span>
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          <p className="text-xs text-fuchsia-900">
            Shift this row's timestamps to test the sweeper. The in-process scheduler runs hourly;
            on the test VM you can force a sweep with{' '}
            <code className="bg-fuchsia-100 px-1 rounded">sudo systemctl restart novotree</code>{' '}
            or{' '}
            <code className="bg-fuchsia-100 px-1 rounded">
              sudo systemctl start novotree-backend-monitor.service
            </code>
            .
          </p>

          <div className="space-y-2">
            <label className="block text-xs font-medium text-fuchsia-900">
              created_at
            </label>
            <div className="flex flex-wrap gap-2 items-center">
              <input
                type="datetime-local"
                value={createdAt}
                onChange={(e) => setCreatedAt(e.target.value)}
                className="px-2 py-1 border border-fuchsia-300 rounded text-sm bg-white"
              />
              {test_PRESETS.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  onClick={() => test_applyPreset(p.days)}
                  title={p.hint}
                  className="px-2 py-1 text-xs bg-white border border-fuchsia-300 rounded hover:bg-fuchsia-100"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <label className="block text-xs font-medium text-fuchsia-900">
              resolved_at{' '}
              <span className="font-normal text-fuchsia-700">
                (only meaningful when status is resolved or escalated)
              </span>
            </label>
            <div className="flex flex-wrap gap-2 items-center">
              <input
                type="datetime-local"
                value={resolvedAt}
                onChange={(e) => setResolvedAt(e.target.value)}
                className="px-2 py-1 border border-fuchsia-300 rounded text-sm bg-white"
              />
              {test_PRESETS.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  onClick={() => test_applyResolvedPreset(p.days)}
                  title={p.hint}
                  className="px-2 py-1 text-xs bg-white border border-fuchsia-300 rounded hover:bg-fuchsia-100"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex justify-end">
            <Button size="sm" onClick={test_submit} isLoading={submitting}>
              Apply override
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
