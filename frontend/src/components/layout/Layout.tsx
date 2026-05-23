import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

export function Layout() {
  // No min-h-screen here. App.tsx wraps Layout in a `flex-1` column above the
  // global PrivacyFooter — the standard sticky-footer pattern (footer at the
  // end of the document, visible when content fits, pushed below content
  // when it doesn't, browser scrollbar makes "more below" discoverable).
  // If Layout asserts its own 100vh on top of that, the document is always
  // a hair taller than the viewport and the footer sits just below the fold
  // with no scrollbar to hint at it.
  return (
    <div className="flex flex-col h-full bg-gray-50">
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

