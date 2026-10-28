import React, { useState, useRef, useEffect } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  Shield,
  MessageSquare,
  FileSearch,
  Scale,
  GitCompare,
  FolderOpen,
  LayoutDashboard,
  ClipboardCheck,
  LogOut,
  User as UserIcon,
  Menu,
  X,
  ChevronDown,
  Sparkles,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  const handleLogout = async () => {
    setProfileMenuOpen(false);
    await logout();
    navigate('/login');
  };

  // Close menus on route change
  useEffect(() => {
    setMobileMenuOpen(false);
    setProfileMenuOpen(false);
  }, [location.pathname]);

  // Click outside listener for profile menu
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setProfileMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const navItems = [
    { name: 'Dashboard', to: '/dashboard', icon: LayoutDashboard },
    { name: 'Ask Policy', to: '/ask', icon: MessageSquare },
    { name: 'Claim Rehearsal', to: '/claim-rehearsal', icon: ClipboardCheck, badge: 'New' },
    { name: 'Scenario Analyzer', to: '/scenarios', icon: Scale },
    { name: 'Compare', to: '/compare', icon: GitCompare },
    { name: 'Explorer', to: '/explorer', icon: FileSearch },
    { name: 'Library', to: '/library', icon: FolderOpen },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-200/80 bg-white/95 backdrop-blur-md transition-all">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand / Logo */}
        <div className="flex items-center gap-6">
          <NavLink
            to="/dashboard"
            className="flex items-center gap-2.5 transition-opacity hover:opacity-90 focus:outline-hidden"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-600 to-teal-700 text-white shadow-xs shadow-emerald-700/20">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-slate-900">
                Cover<span className="text-emerald-600">Scope</span>
              </span>
              <span className="hidden text-[9px] font-semibold uppercase tracking-wider text-slate-400 sm:block -mt-1">
                Insurance Intelligence
              </span>
            </div>
          </NavLink>
        </div>

        {/* Desktop Navigation Tabs */}
        <nav className="hidden lg:flex items-center space-x-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/dashboard'}
                className={({ isActive }) =>
                  `relative flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium whitespace-nowrap transition-all ${
                    isActive
                      ? 'bg-emerald-50 text-emerald-700 font-semibold shadow-xs'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`
                }
              >
                <Icon className="h-3.5 w-3.5 shrink-0" />
                <span>{item.name}</span>
                {item.badge && (
                  <span className="rounded-full bg-emerald-100 px-1.5 py-0.2 text-[9px] font-bold uppercase tracking-wider text-emerald-800">
                    {item.badge}
                  </span>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* User profile dropdown & Mobile Toggle */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* User profile menu */}
          <div className="relative" ref={profileRef}>
            <button
              onClick={() => setProfileMenuOpen((prev) => !prev)}
              className="flex items-center gap-2 rounded-lg border border-slate-200/80 bg-slate-50/50 p-1.5 sm:px-2.5 sm:py-1.5 transition hover:bg-slate-100 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20"
              title="Account Menu"
            >
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-emerald-600 to-teal-700 text-white text-xs font-semibold">
                {user?.display_name ? user.display_name.charAt(0).toUpperCase() : <UserIcon className="h-3.5 w-3.5" />}
              </div>
              <div className="hidden text-left sm:block">
                <p className="text-xs font-semibold text-slate-800 leading-tight truncate max-w-[110px]">
                  {user?.display_name || 'Policyholder'}
                </p>
                <p className="text-[10px] text-slate-400 capitalize -mt-0.5">
                  {user?.role || 'User'}
                </p>
              </div>
              <ChevronDown className="hidden h-3 w-3 text-slate-400 sm:block" />
            </button>

            {/* Profile Dropdown Popover */}
            {profileMenuOpen && (
              <div className="absolute right-0 mt-2 w-56 rounded-xl border border-slate-200 bg-white p-2 shadow-lg shadow-slate-900/5 z-50 animate-in fade-in-50 duration-150">
                <div className="border-b border-slate-100 px-3 py-2 text-left">
                  <p className="text-xs font-bold text-slate-900">{user?.display_name || 'Policyholder'}</p>
                  <p className="text-[11px] text-slate-500 truncate">{user?.email}</p>
                  <div className="mt-1 flex items-center gap-1.5">
                    <span className="inline-flex items-center rounded-full bg-emerald-50 px-1.5 py-0.5 text-[9px] font-semibold text-emerald-700 capitalize">
                      {user?.role || 'Policyholder'}
                    </span>
                    <span className="text-[10px] text-slate-400">• Active Session</span>
                  </div>
                </div>

                <div className="py-1">
                  <NavLink
                    to="/library"
                    onClick={() => setProfileMenuOpen(false)}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 transition"
                  >
                    <FolderOpen className="h-3.5 w-3.5 text-slate-400" />
                    <span>My Policy Documents</span>
                  </NavLink>
                  <NavLink
                    to="/claim-rehearsal"
                    onClick={() => setProfileMenuOpen(false)}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 transition"
                  >
                    <ClipboardCheck className="h-3.5 w-3.5 text-emerald-600" />
                    <span>Run Claim Rehearsal</span>
                  </NavLink>
                </div>

                <div className="border-t border-slate-100 pt-1">
                  <button
                    onClick={handleLogout}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium text-rose-600 hover:bg-rose-50 transition"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    <span>Sign Out</span>
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Mobile hamburger menu button */}
          <button
            onClick={() => setMobileMenuOpen((prev) => !prev)}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600 lg:hidden hover:bg-slate-100 focus:outline-hidden"
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="border-t border-slate-200/80 bg-white px-4 py-3 shadow-md lg:hidden space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/dashboard'}
                className={({ isActive }) =>
                  `flex items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition ${
                    isActive
                      ? 'bg-emerald-50 text-emerald-700 font-semibold'
                      : 'text-slate-700 hover:bg-slate-100'
                  }`
                }
              >
                <div className="flex items-center gap-2.5">
                  <Icon className="h-4 w-4" />
                  <span>{item.name}</span>
                </div>
                {item.badge && (
                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                    {item.badge}
                  </span>
                )}
              </NavLink>
            );
          })}
        </div>
      )}
    </header>
  );
};
