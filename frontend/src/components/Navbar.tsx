import React from 'react';
import { BookOpen, FolderGit2, Database } from 'lucide-react';

interface NavbarProps {
  activeTab: 'projects' | 'library';
  setActiveTab: (tab: 'projects' | 'library') => void;
  dbStatus: 'connected' | 'disconnected' | 'checking';
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab, dbStatus }) => {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          {/* Logo and Brand */}
          <div className="flex items-center space-x-3">
            <div className="bg-indigo-600 text-white p-2 rounded-lg shadow-sm">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <span className="font-bold text-lg text-slate-900 tracking-tight">LitScope</span>
              <span className="ml-2 text-xs font-medium text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-100">
                Phase 1 Baseline
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

          {/* Database Health Badge */}
          <div className="flex items-center space-x-2">
            <div
              className={`w-2.5 h-2.5 rounded-full ${
                dbStatus === 'connected'
                  ? 'bg-emerald-500 ring-4 ring-emerald-100 animate-pulse'
                  : dbStatus === 'checking'
                  ? 'bg-amber-400'
                  : 'bg-rose-500 ring-4 ring-rose-100'
              }`}
            />
            <span className="text-xs text-slate-500 font-medium">
              {dbStatus === 'connected'
                ? 'PostgreSQL Connected'
                : dbStatus === 'checking'
                ? 'Connecting...'
                : 'Database Offline'}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};
