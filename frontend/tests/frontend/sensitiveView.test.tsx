/**
 * Unit tests for the session-scoped "show sensitive" state (PRIVACY_DESIGN.md 3.7).
 *
 * Regression context: the toggle lived in three separate `useState(false)` calls,
 * one in each surface that shows sensitive data (both tree views and the
 * individual detail page). Those pages are lazily mounted and unmount on
 * navigation, so the toggle silently reset every time the Owner moved between
 * them, and the three surfaces never agreed with each other. 3.7 specifies
 * *per-session*, so the old behaviour was stricter than the design - revealing
 * sensitive data became a chore repeated on every visit.
 *
 * These tests pin the two properties that fix depends on: the value survives
 * unmount/remount, and every consumer sees the same value. They also pin the
 * boundary that must NOT move - a fresh session still starts hidden, and the
 * choice never reaches localStorage.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, act, cleanup } from '@testing-library/react';
import {
  SensitiveViewProvider,
  useSensitiveView,
} from '../../src/contexts/SensitiveViewContext';

const STORAGE_KEY = 'novotree.showSensitive';

/** Renders the current value and lets a test flip it, standing in for the toggle. */
function Consumer({ label = 'a' }: { label?: string }) {
  const { showSensitive, setShowSensitive } = useSensitiveView();
  return (
    <button data-testid={label} onClick={() => setShowSensitive(!showSensitive)}>
      {showSensitive ? 'shown' : 'hidden'}
    </button>
  );
}

function renderWithProvider(ui: React.ReactNode) {
  return render(<SensitiveViewProvider>{ui}</SensitiveViewProvider>);
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});

afterEach(cleanup);

describe('SensitiveViewProvider', () => {
  it('starts hidden in a fresh session', () => {
    renderWithProvider(<Consumer />);
    expect(screen.getByTestId('a')).toHaveTextContent('hidden');
  });

  it('reveals on toggle', () => {
    renderWithProvider(<Consumer />);
    act(() => screen.getByTestId('a').click());
    expect(screen.getByTestId('a')).toHaveTextContent('shown');
  });

  it('survives unmount and remount', () => {
    // The actual bug: navigating away from a tree view unmounted the page and
    // reset its useState, so the Owner had to re-reveal on every visit.
    const first = renderWithProvider(<Consumer />);
    act(() => screen.getByTestId('a').click());
    expect(screen.getByTestId('a')).toHaveTextContent('shown');

    first.unmount();
    renderWithProvider(<Consumer />);

    expect(screen.getByTestId('a')).toHaveTextContent('shown');
  });

  it('is shared by every surface at once', () => {
    // Previously each page held its own copy, so the tree and the detail page
    // could disagree about whether sensitive data was revealed.
    renderWithProvider(
      <>
        <Consumer label="tree" />
        <Consumer label="detail" />
      </>,
    );

    act(() => screen.getByTestId('tree').click());

    expect(screen.getByTestId('tree')).toHaveTextContent('shown');
    expect(screen.getByTestId('detail')).toHaveTextContent('shown');
  });

  it('hides again on toggle off, and forgets the choice', () => {
    renderWithProvider(<Consumer />);
    act(() => screen.getByTestId('a').click());
    act(() => screen.getByTestId('a').click());

    expect(screen.getByTestId('a')).toHaveTextContent('hidden');
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('picks up a value already in sessionStorage', () => {
    // Covers a reload: the local app reloads itself after switching tree or
    // data folder, which remounts the whole provider.
    sessionStorage.setItem(STORAGE_KEY, '1');
    renderWithProvider(<Consumer />);
    expect(screen.getByTestId('a')).toHaveTextContent('shown');
  });

  it('never writes to localStorage', () => {
    // 3.7 promises the choice is not persisted; sessionStorage keeps it scoped
    // to one session, localStorage would outlive it.
    renderWithProvider(<Consumer />);
    act(() => screen.getByTestId('a').click());
    expect(localStorage.length).toBe(0);
  });

  it('falls back to hidden when storage throws', () => {
    // Private-browsing modes and disabled storage make sessionStorage throw.
    // Hidden is both the documented default and the safe answer.
    const getItem = vi
      .spyOn(Storage.prototype, 'getItem')
      .mockImplementation(() => {
        throw new Error('storage disabled');
      });
    const setItem = vi
      .spyOn(Storage.prototype, 'setItem')
      .mockImplementation(() => {
        throw new Error('storage disabled');
      });

    try {
      renderWithProvider(<Consumer />);
      expect(screen.getByTestId('a')).toHaveTextContent('hidden');
      // The toggle must still work for this mount even though nothing persists.
      act(() => screen.getByTestId('a').click());
      expect(screen.getByTestId('a')).toHaveTextContent('shown');
    } finally {
      getItem.mockRestore();
      setItem.mockRestore();
    }
  });

  it('throws when used outside the provider', () => {
    const onError = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      expect(() => render(<Consumer />)).toThrow(/SensitiveViewProvider/);
    } finally {
      onError.mockRestore();
    }
  });
});
