import { type PolicyHeading } from './renderPolicyMarkdown';

interface PolicyTocProps {
  headings: PolicyHeading[];
  /** Visual variant. "block" sits in document flow; "sidebar" stays narrow + sticky. */
  variant: 'block' | 'sidebar';
}

/**
 * Table of contents for a rendered policy. Renders h2 headings as
 * anchor-jump links keyed to the slug IDs emitted by renderPolicyMarkdown.
 *
 * Two variants, both driven by the same data:
 *
 *   - "block"   — bordered box, full-width, sits above the article. Always
 *                 visible on every screen size. The simpler choice.
 *   - "sidebar" — narrow column on the right (only on lg+ screens), sticky
 *                 so it stays in view while the user reads. The component
 *                 itself does NOT do the layout — the caller wraps it in a
 *                 sticky container; this component only renders the list.
 *                 On smaller screens the caller should hide the sidebar
 *                 variant and render a "block" instance above the article
 *                 instead, so mobile readers still get a ToC.
 */
export function PolicyToc({ headings, variant }: PolicyTocProps) {
  if (headings.length === 0) return null;

  if (variant === 'sidebar') {
    return (
      <nav aria-label="Table of contents" className="text-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
          On this page
        </p>
        <ol className="space-y-1 border-l border-gray-200 pl-3">
          {headings.map((h) => (
            <li key={h.slug}>
              <a
                href={`#${h.slug}`}
                className="block text-gray-600 hover:text-emerald-700 hover:underline leading-snug"
              >
                {h.text}
              </a>
            </li>
          ))}
        </ol>
      </nav>
    );
  }

  return (
    <nav
      aria-label="Table of contents"
      className="border border-gray-200 rounded-md bg-gray-50 p-4 my-6"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">
        On this page
      </p>
      <ol className="grid sm:grid-cols-2 gap-x-6 gap-y-1 text-sm list-decimal pl-5">
        {headings.map((h) => (
          <li key={h.slug} className="pl-1">
            <a
              href={`#${h.slug}`}
              className="text-emerald-700 hover:text-emerald-800 hover:underline"
            >
              {h.text.replace(/^\d+\.\s*/, '')}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
