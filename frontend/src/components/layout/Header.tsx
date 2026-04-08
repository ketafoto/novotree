import { Link } from 'react-router-dom';
import { LogOut, User, TreeDeciduous } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

export function Header() {
  const { editor, logout } = useAuth();

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

        {/* User Menu */}
        {editor && (
          <div className="flex items-center gap-4">
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
          </div>
        )}
      </div>
    </header>
  );
}

