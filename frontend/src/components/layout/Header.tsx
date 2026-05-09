import { useState } from 'react';
import { Link } from 'react-router-dom';
import { LogOut, User, TreeDeciduous, Heart } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { isLocalApp } from '../../config/appMode';
import { DonateModal } from '../common/DonateButton';
import { AboutDialog } from '../common/AboutDialog';

export function Header() {
  const { editor, logout } = useAuth();
  // Lift the Donate modal's state here so the About dialog can also open it
  // (matches novoface's "Donate ♥" button INSIDE the About modal).
  const [donateOpen, setDonateOpen] = useState(false);

  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between">
        {/* Logo and Title */}
        <Link to="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
          <div className="w-10 h-10 bg-emerald-600 rounded-lg flex items-center justify-center">
            <TreeDeciduous className="w-6 h-6 text-white" />
          </div>
          <span className="text-xl font-semibold text-gray-900">Genealogy DB</span>
        </Link>

        {/* Right-side actions */}
        <div className="flex items-center gap-3">
          {/* Local-only: Donate ♥ + About ⓘ.  About can open Donate. */}
          {isLocalApp && (
            <>
              <button
                type="button"
                onClick={() => setDonateOpen(true)}
                title="Support NovoTree development"
                className="flex items-center gap-2 px-3 py-1.5 border border-pink-300 text-pink-600 hover:border-pink-500 hover:text-pink-700 hover:bg-pink-50 rounded-lg transition-colors text-sm font-medium"
              >
                <Heart className="w-4 h-4" fill="currentColor" />
                <span>Donate</span>
              </button>
              <AboutDialog onOpenDonate={() => setDonateOpen(true)} />
              <DonateModal open={donateOpen} onClose={() => setDonateOpen(false)} />
            </>
          )}

          {/* Editor identity + logout: hidden in local mode — there's only
              one synthetic "local" user with no real session, so showing
              the name is noise and clicking Logout dumps the user onto a
              non-existent /login route. */}
          {!isLocalApp && editor && (
            <>
              <div className="flex items-center gap-2 text-gray-600">
                <User className="w-5 h-5" />
                <span className="font-medium">{editor.display_name || editor.editor_id}</span>
              </div>
              <button
                onClick={logout}
                className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <LogOut className="w-5 h-5" />
                <span>Logout</span>
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

