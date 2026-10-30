import React from 'react';
import { BookOpen, FolderGit2, Database, LogOut, LogIn } from 'lucide-react';
import { User } from '../api/client';

interface NavbarProps {
  activeTab: 'projects' | 'library';
  setActiveTab: (tab: 'projects' | 'library') => void;
  dbStatus: 'connected' | 'disconnected' | 'checking';
  currentUser: User | null;
  onOpenAuth: () => void;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  dbStatus,
  currentUser,
  onOpenAuth,
  onLogout,
}) => {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
      <div className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          {/* Logo and Brand */}
          <div className="flex items-center space-x-3">
            <div className="bg-indigo-600 text-white p-2 rounded-lg shadow-sm">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <span className="font-bold text-lg text-slate-900 tracking-tight">LitScope</span>
              <span className="ml-2 text-xs font-semibold text-indigo-700 bg-indigo-50 px-2.5 py-0.5 rounded-full border border-indigo-200">
                Phase 4 Conventional RAG
              </span>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex space-x-1">
            <button
              onClick={() => setActiveTab('projects')}
              className={`flex items-center px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'projects'
                  ? 'bg-slate-100 text-slate-900 font-semibold'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <FolderGit2 className="w-4 h-4 mr-2" />
              Projects
            </button>
            <button
              onClick={() => setActiveTab('library')}
              className={`flex items-center px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'library'
                  ? 'bg-slate-100 text-slate-900 font-semibold'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <Database className="w-4 h-4 mr-2" />
              Master Library
            </button>
          </nav>

          {/* Right Section: DB Health + User Profile */}
          <div className="flex items-center space-x-4">
            {/* Database Health Badge */}
            <div className="flex items-center space-x-1.5 hidden md:flex">
              <div
                className={`w-2 h-2 rounded-full ${
                  dbStatus === 'connected'
                    ? 'bg-emerald-500'
                    : dbStatus === 'checking'
                    ? 'bg-amber-400'
                    : 'bg-rose-500'
                }`}
              />
              <span className="text-xs text-slate-400 font-medium">
                {dbStatus === 'connected' ? 'PostgreSQL' : 'Offline'}
              </span>
            </div>

            {/* User Account / Auth Actions */}
            {currentUser ? (
              <div className="flex items-center space-x-3 pl-2 border-l border-slate-200">
                <div className="flex items-center space-x-2">
                  <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold text-xs">
                    {currentUser.full_name
                      ? currentUser.full_name[0].toUpperCase()
                      : currentUser.email[0].toUpperCase()}
                  </div>
                  <div className="hidden sm:block text-left">
                    <p className="text-xs font-semibold text-slate-800 leading-tight">
                      {currentUser.full_name || currentUser.email.split('@')[0]}
                    </p>
                    <span className="text-[10px] uppercase font-bold text-indigo-600 bg-indigo-50 px-1.5 py-0.2 rounded border border-indigo-100">
                      {currentUser.role}
                    </span>
                  </div>
                </div>

                <button
                  onClick={onLogout}
                  title="Sign Out"
                  className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <button
                onClick={onOpenAuth}
                className="inline-flex items-center px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm transition"
              >
                <LogIn className="w-3.5 h-3.5 mr-1.5" />
                Sign In
              </button>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
