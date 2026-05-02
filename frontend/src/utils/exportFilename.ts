/**
 * Build download filenames for exported artifacts.
 *
 * Mirrors backend/api/export.py::_build_export_filename so client-side
 * exports (tree image) and server-side exports (GEDCOM) share one format:
 *   novotree-<owner>-<kind>-<YYYYMMDD>-<HHMMSS>.<ext>
 */

const EXPORT_FILENAME_PREFIX = 'novotree';

function exportTimestamp(d: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return (
    `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}` +
    `-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
  );
}

export function buildExportFilename(
  ownerId: string,
  kind: string,
  ext: string,
  options: { withTimestamp?: boolean } = {},
): string {
  const { withTimestamp = true } = options;
  const base = `${EXPORT_FILENAME_PREFIX}-${ownerId}-${kind}`;
  return withTimestamp ? `${base}-${exportTimestamp()}.${ext}` : `${base}.${ext}`;
}
