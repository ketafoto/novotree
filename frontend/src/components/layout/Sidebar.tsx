import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  User,
  Heart,
  GitBranch,
  Download,
  Upload,
  ArrowLeftRight,
  Settings,
  Shield,
  ChevronDown,
  Users,
  LogOut,
} from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { isLocalApp } from '../../config/appMode';

interface NavItemProps {
  to: string;
  icon: React.ReactNode;
  label: string;
  end?: boolean;
}

function NavItem({ to, icon, label, end }: NavItemProps) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
          isActive
            ? 'bg-emerald-50 text-emerald-700 font-medium'
            : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
        }`
      }
    >
      {icon}
      <span>{label}</span>
    </NavLink>
  );
}

interface NavGroupProps {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}

function NavGroup({ icon, label, children }: NavGroupProps) {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <div>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full px-4 py-3 text-gray-600 hover:bg-gray-100 hover:text-gray-900 rounded-lg transition-colors"
      >
        <div className="flex items-center gap-3">
          {icon}
          <span>{label}</span>
        </div>
        <ChevronDown
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>
      {isOpen && <div className="ml-4 mt-1 space-y-1">{children}</div>}
    </div>
  );
}

export function Sidebar() {
  const { editor, isOwner, logout } = useAuth();

  return (
    <aside className="w-64 bg-white border-r border-gray-200 flex flex-col p-4">
      <nav className="space-y-1 flex-1">
        <NavItem
          to="/"
          icon={<LayoutDashboard className="w-5 h-5" />}
          label="Dashboard"
          end
        />

        <div className="pt-2">
          <NavItem
            to="/individuals"
            icon={<User className="w-5 h-5" />}
            label="Individuals"
          />
        </div>

        <NavItem
          to="/families"
          icon={<Heart className="w-5 h-5" />}
          label="Families"
        />

        <NavItem
          to="/tree"
          icon={<GitBranch className="w-5 h-5" />}
          label="Tree"
        />

        <div className="border-t border-gray-200 my-4" />

        <NavGroup icon={<ArrowLeftRight className="w-5 h-5" />} label="Data Exchange">
          <NavItem
            to="/export"
            icon={<Download className="w-5 h-5" />}
            label="Export"
          />
          {isOwner && (
            <NavItem
              to="/import"
              icon={<Upload className="w-5 h-5" />}
              label="Import"
            />
          )}
        </NavGroup>

        {/* User Manager: hidden in local mode — the local app is single-user
            with no contributors / share tokens / signups to manage. */}
        {isOwner && !isLocalApp && (
          <NavItem
            to="/users"
            icon={<Users className="w-5 h-5" />}
            label="User Manager"
          />
        )}

        {/* Privacy: Owner-only triage queue for privacy requests
            (removal, access, correction). Hidden in local mode — local app
            has no public surface to file privacy requests against. */}
        {isOwner && !isLocalApp && (
          <NavItem
            to="/legal/privacy-requests"
            icon={<Shield className="w-5 h-5" />}
            label="Privacy requests"
          />
        )}

        <NavItem
          to="/settings"
          icon={<Settings className="w-5 h-5" />}
          label="Settings"
        />
      </nav>

      {/* User info + sign out at bottom — hidden in local mode for the same
          reason as in Header.tsx: the synthetic "local" editor isn't a real
          session, the name is noise, and Sign out lands on a non-existent
          /login route ("Not Found" black screen). */}
      {!isLocalApp && editor && (
        <div className="border-t border-gray-200 pt-4 mt-4">
          <div className="px-4 mb-2">
            <p className="text-sm font-medium text-gray-800 truncate">{editor.display_name}</p>
            <p className="text-xs text-gray-400 capitalize">{editor.role}</p>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-3 w-full px-4 py-2 text-gray-500 hover:bg-gray-100 rounded-lg transition-colors text-sm"
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </button>
        </div>
      )}
    </aside>
  );
}
