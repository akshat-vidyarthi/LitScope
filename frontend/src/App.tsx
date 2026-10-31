import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { ProjectsView } from './components/ProjectsView';
import { LibraryView } from './components/LibraryView';
import { DiscoveryView } from './components/DiscoveryView';
import { LandingPage } from './components/LandingPage';
import { ToastContainer } from './components/Toast';
import { api, User } from './api/client';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'projects' | 'library' | 'discovery'>('projects');
  const [dbStatus, setDbStatus] = useState<'connected' | 'disconnected' | 'checking'>('checking');
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);

  const checkDb = async () => {
    try {
      const res = await api.checkHealth();
      if (res.database === 'connected') {
        setDbStatus('connected');
      } else {
        setDbStatus('disconnected');
      }
    } catch (err) {
      setDbStatus('disconnected');
    }
  };

  const loadUser = async () => {
    try {
      const user = await api.getCurrentUser();
      setCurrentUser(user);
    } catch (err) {
      setCurrentUser(null);
    } finally {
      setInitialLoading(false);
    }
  };

  useEffect(() => {
    checkDb();
    loadUser();
    const interval = setInterval(checkDb, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = () => {
    api.logout();
    setCurrentUser(null);
    setActiveTab('projects');
  };

  if (initialLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-400 text-sm">
        Loading LitScope...
      </div>
    );
  }

  // 1. Unauthenticated: Render Landing Page with Register -> Login flow
  if (!currentUser) {
    return (
      <LandingPage
        dbStatus={dbStatus}
        onLoginSuccess={(user) => setCurrentUser(user)}
      />
    );
  }

  // 2. Authenticated: Render Actual Research Workspace (Projects & Master Library)
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <ToastContainer />
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        dbStatus={dbStatus}
        currentUser={currentUser}
        onOpenAuth={() => {}}
        onLogout={handleLogout}
      />

      <main className="flex-1">
        {activeTab === 'projects' ? (
          <ProjectsView
            currentUser={currentUser}
            onOpenAuth={() => {}}
          />
        ) : activeTab === 'library' ? (
          <LibraryView
            currentUser={currentUser}
            onOpenAuth={() => {}}
          />
        ) : (
          <DiscoveryView />
        )}
      </main>
    </div>
  );
};

export default App;
