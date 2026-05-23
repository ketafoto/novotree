import { Fragment, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

/**
 * Minimal markdown renderer for the privacy policy (and any future static
 * legal page). Supports headings (#…###), paragraphs, **bold**, *italic*,
 * `inline code`, [links](href), bullet lists, horizontal rules, and pipe
 * tables. The markdown source lives in-repo at docs/legal/privacy.md and is
 * fully under our control, so the renderer can stay narrow — we don't want
 * a third-party markdown dep on a public-facing route.
 *
 * Internal links (paths starting with "/") render as react-router <Link>;
 * everything else renders as a plain anchor.
 */

interface ParsedRow {
  cells: string[];
}

function parseTableRow(line: string): ParsedRow | null {
  if (!line.includes('|')) return null;
  const trimmed = line.trim().replace(/^\||\|$/g, '');
  const cells = trimmed.split('|').map((c) => c.trim());
  return { cells };
}

function isTableSeparator(line: string): boolean {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}

const INLINE_LINK = /\[([^\]]+)\]\(([^)]+)\)/;
const INLINE_BOLD = /\*\*([^*]+)\*\*/;
const INLINE_ITALIC = /(?<!\*)\*([^*]+)\*(?!\*)/;
const INLINE_CODE = /`([^`]+)`/;
const ITALIC_UNDERSCORE = /_([^_]+)_/;

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let remaining = text;
  let idx = 0;

  while (remaining.length > 0) {
    const matches = [
      { kind: 'link', m: INLINE_LINK.exec(remaining) },
      { kind: 'bold', m: INLINE_BOLD.exec(remaining) },
      { kind: 'code', m: INLINE_CODE.exec(remaining) },
      { kind: 'italic', m: INLINE_ITALIC.exec(remaining) },
      { kind: 'italicU', m: ITALIC_UNDERSCORE.exec(remaining) },
    ].filter((x): x is { kind: string; m: RegExpExecArray } => x.m !== null);

    if (matches.length === 0) {
      nodes.push(remaining);
      break;
    }

    matches.sort((a, b) => a.m.index - b.m.index);
    const next = matches[0];
    const before = remaining.slice(0, next.m.index);
    if (before) nodes.push(before);

    const key = `${keyPrefix}-${idx++}`;
    if (next.kind === 'link') {
      const [, label, href] = next.m;
      if (href.startsWith('/')) {
        nodes.push(
          <Link key={key} to={href} className="text-emerald-700 underline hover:text-emerald-800">
            {label}
          </Link>
        );
      } else {
        nodes.push(
          <a
            key={key}
            href={href}
            className="text-emerald-700 underline hover:text-emerald-800"
            rel="noopener noreferrer"
          >
            {label}
          </a>
        );
      }
    } else if (next.kind === 'bold') {
      nodes.push(<strong key={key}>{next.m[1]}</strong>);
    } else if (next.kind === 'code') {
      nodes.push(
        <code key={key} className="bg-gray-100 text-gray-800 px-1 rounded text-sm">
          {next.m[1]}
        </code>
      );
    } else {
      nodes.push(<em key={key}>{next.m[1]}</em>);
    }

    remaining = remaining.slice(next.m.index + next.m[0].length);
  }

  return nodes;
}

export function renderPolicyMarkdown(source: string): ReactNode {
  const lines = source.replace(/\r\n/g, '\n').split('\n');
  const blocks: ReactNode[] = [];
  let i = 0;
  let blockKey = 0;

  const next = () => `b-${blockKey++}`;

  while (i < lines.length) {
    const line = lines[i];

    // Blank line
    if (line.trim() === '') {
      i += 1;
      continue;
    }

    // Horizontal rule
    if (/^\s*---+\s*$/.test(line)) {
      blocks.push(<hr key={next()} className="my-6 border-gray-200" />);
      i += 1;
      continue;
    }

    // Heading
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const key = next();
      const content = renderInline(heading[2], `h${level}-${blockKey}`);
      if (level === 1) {
        blocks.push(
          <h1 key={key} className="text-3xl font-semibold mt-4 mb-3">
            {content}
          </h1>
        );
      } else if (level === 2) {
        blocks.push(
          <h2 key={key} className="text-xl font-semibold mt-6 mb-2">
            {content}
          </h2>
        );
      } else {
        blocks.push(
          <h3 key={key} className="text-lg font-semibold mt-5 mb-2">
            {content}
          </h3>
        );
      }
      i += 1;
      continue;
    }

    // Table
    if (line.includes('|') && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      const headerRow = parseTableRow(line);
      if (headerRow) {
        i += 2;
        const rows: ParsedRow[] = [];
        while (i < lines.length && lines[i].includes('|') && lines[i].trim() !== '') {
          const row = parseTableRow(lines[i]);
          if (row) rows.push(row);
          i += 1;
        }
        const key = next();
        blocks.push(
          <div key={key} className="overflow-x-auto my-4">
            <table className="min-w-full border border-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {headerRow.cells.map((cell, idx) => (
                    <th
                      key={idx}
                      className="border border-gray-200 px-3 py-2 text-left font-semibold"
                    >
                      {renderInline(cell, `${key}-th-${idx}`)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, rIdx) => (
                  <tr key={rIdx}>
                    {row.cells.map((cell, cIdx) => (
                      <td key={cIdx} className="border border-gray-200 px-3 py-2 align-top">
                        {renderInline(cell, `${key}-${rIdx}-${cIdx}`)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        continue;
      }
    }

    // Bullet list
    if (/^\s*[-*]\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        const content = lines[i].replace(/^\s*[-*]\s+/, '');
        items.push(
          <li key={i} className="mb-1">
            {renderInline(content, `li-${i}`)}
          </li>
        );
        i += 1;
      }
      blocks.push(
        <ul key={next()} className="list-disc pl-6 my-3 space-y-1">
          {items}
        </ul>
      );
      continue;
    }

    // Paragraph — accumulate consecutive non-blank lines
    const paragraphLines: string[] = [line];
    i += 1;
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !/^(#{1,6})\s+/.test(lines[i]) &&
      !/^\s*---+\s*$/.test(lines[i]) &&
      !/^\s*[-*]\s+/.test(lines[i]) &&
      !(lines[i].includes('|') && i + 1 < lines.length && isTableSeparator(lines[i + 1]))
    ) {
      paragraphLines.push(lines[i]);
      i += 1;
    }
    const text = paragraphLines.join(' ');
    blocks.push(
      <p key={next()} className="my-3">
        {renderInline(text, `p-${blockKey}`)}
      </p>
    );
  }

  return <Fragment>{blocks}</Fragment>;
}
