import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { ProjectsView } from './components/ProjectsView';
import { LibraryView } from './components/LibraryView';
import { api } from './api/client';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'projects' | 'library'>('projects');
  const [dbStatus, setDbStatus] = useState<'connected' | 'disconnected' | 'checking'>('checking');

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

  useEffect(() => {
    checkDb();
    const interval = setInterval(checkDb, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} dbStatus={dbStatus} />
      <main className="flex-1">
        {activeTab === 'projects' ? <ProjectsView /> : <LibraryView />}
      </main>
    </div>
  );
};

export default App;
