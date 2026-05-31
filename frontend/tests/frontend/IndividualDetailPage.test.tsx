/**
 * Tests for IndividualDetailPage — modal layering behaviour.
 *
 * These tests verify that only one dialog is visible at a time when the user
 * triggers the photo-upload flow from the Photos section modal.  The bug was
 * that ModalPhotosSection (z-50) and PhotoUploadDialog (z-50) were both
 * mounted simultaneously after file selection, with the Photos modal on top
 * because it appeared later in the DOM, making the upload dialog unreachable.
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { IndividualDetailPage } from '../../src/pages/individuals/IndividualDetailPage';

// ── API mocks ────────────────────────────────────────────────────────────────

vi.mock('../../src/api/individuals', () => ({
  individualsApi: {
    get: vi.fn().mockResolvedValue({
      id: 1,
      gedcom_id: 'I1',
      sex_code: 'M',
      names: [{ id: 1, given_name: 'Test', family_name: 'Person' }],
      birth_date: null,
      birth_date_approx: null,
      birth_place: null,
      death_date: null,
      death_date_approx: null,
      death_place: null,
      notes: null,
      created_by: 'owner1',
    }),
    delete: vi.fn(),
  },
}));

vi.mock('../../src/api/families', () => ({
  familiesApi: { list: vi.fn().mockResolvedValue([]) },
}));

vi.mock('../../src/api/events', () => ({
  eventsApi: { list: vi.fn().mockResolvedValue([]) },
}));

vi.mock('../../src/api/types', () => ({
  typesApi: {
    getEventTypes: vi.fn().mockResolvedValue([]),
    getSexTypes: vi.fn().mockResolvedValue([]),
    getMediaTypes: vi.fn().mockResolvedValue([]),
    getFamilyRoles: vi.fn().mockResolvedValue([]),
    getFamilyTypes: vi.fn().mockResolvedValue([]),
    getNameTypes: vi.fn().mockResolvedValue([]),
    getDateApproxTypes: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock('../../src/api/media', () => ({
  mediaApi: {
    list: vi.fn().mockResolvedValue([]),
    getFileUrl: vi.fn().mockReturnValue('mock://photo'),
    delete: vi.fn(),
    setDefault: vi.fn(),
    uploadPhoto: vi.fn(),
    recropPhoto: vi.fn(),
    update: vi.fn(),
  },
}));

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

// IndividualDetailPage calls useAuth() for `isOwner`. This test renders the
// page without an AuthProvider, so mock the hook directly — the photo-dialog
// layering under test does not depend on the real auth flow. Owner = full
// edit affordances (the Media card's double-click → upload path).
vi.mock('../../src/contexts/AuthContext', () => ({
  useAuth: () => ({ isOwner: true }),
}));

// ── Helpers ──────────────────────────────────────────────────────────────────

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/individuals/1']}>
        <Routes>
          <Route path="/individuals/:id" element={<IndividualDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-photo');
  vi.spyOn(URL, 'revokeObjectURL').mockReturnValue(undefined);
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe('IndividualDetailPage – photo dialog layering', () => {
  it('closes the Photos section modal when a file is selected for upload', async () => {
    renderPage();

    // Wait for the page to finish loading (individual name appears in h1).
    // Use findByRole with level:1 because the name also appears in the Names card.
    await screen.findByRole('heading', { name: 'Test Person', level: 1 });

    // Double-click the Media card to open ModalPhotosSection.
    // Card renders role="button" on its root div when onDoubleClick is set.
    // We find the Media card by locating its h3 heading and walking up to
    // the nearest role="button" ancestor.
    const photosHeading = screen.getByRole('heading', { name: 'Media' });
    const photosCard = photosHeading.closest('[role="button"]')!;
    await userEvent.dblClick(photosCard);

    // ModalPhotosSection is now open: the "Add Photo" button inside it is visible.
    expect(screen.getByRole('button', { name: /add photo/i })).toBeInTheDocument();
    // PhotoUploadDialog is NOT yet open: no "OK" button exists.
    expect(screen.queryByRole('button', { name: /^ok$/i })).not.toBeInTheDocument();

    // Simulate a file being chosen from the OS file picker.
    // userEvent.upload sets input.files and fires the change event.
    // At this point showPhotoDialog=false, so the only file input in the DOM
    // is the page-level hidden one (addPhotoInputRef).
    const fileInput = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const fakePhoto = new File(['(fake jpeg bytes)'], 'photo.jpg', { type: 'image/jpeg' });
    await userEvent.upload(fileInput, fakePhoto);

    // After the fix: setSectionModal(null) is called before setShowPhotoDialog(true),
    // so ModalPhotosSection unmounts and PhotoUploadDialog mounts.
    // "Add Photo" button from the Photos modal must be gone.
    expect(screen.queryByRole('button', { name: /add photo/i })).not.toBeInTheDocument();
    // "OK" button from PhotoUploadDialog footer must be present.
    expect(screen.getByRole('button', { name: /^ok$/i })).toBeInTheDocument();
  });
});
