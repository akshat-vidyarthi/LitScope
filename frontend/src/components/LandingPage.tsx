import React, { useState } from 'react';
import { BookOpen, Shield, CheckCircle2, Lock, Mail, User as UserIcon, ArrowRight, Layers, FileText } from 'lucide-react';
import { api, User } from '../api/client';

interface LandingPageProps {
  onLoginSuccess: (user: User) => void;
  dbStatus: 'connected' | 'disconnected' | 'checking';
}

export const LandingPage: React.FC<LandingPageProps> = ({ onLoginSuccess, dbStatus }) => {
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);
    setLoading(true);

    try {
      if (authMode === 'register') {
        // 1. Register Account
        await api.register(email, password, fullName || undefined);
        // 2. Redirect to Log In mode with pre-filled email and success message
        setAuthMode('login');
        setPassword('');
        setSuccessMessage('Account created successfully! Please sign in with your credentials.');
      } else {
        // 3. Log In and redirect to actual workspace
        const loginData = await api.login(email, password);
        onLoginSuccess(loginData.user);
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between">
      {/* Top Header */}
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-indigo-600 text-white p-2 rounded-lg shadow-sm">
              <BookOpen className="w-5 h-5" />
            </div>
            <span className="font-bold text-lg text-slate-900 tracking-tight">LitScope</span>
          </div>

          <div className="flex items-center space-x-2">
            <div
              className={`w-2 h-2 rounded-full ${
                dbStatus === 'connected' ? 'bg-emerald-500' : 'bg-rose-500'
              }`}
            />
            <span className="text-xs text-slate-400 font-medium">
              {dbStatus === 'connected' ? 'PostgreSQL Active' : 'Offline'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Hero & Auth Card Section */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 flex-1 flex flex-col lg:flex-row items-center justify-center gap-12">
        {/* Left: Product Value Proposition */}
        <div className="lg:w-1/2 space-y-6 text-left">
          <div className="inline-flex items-center space-x-2 bg-indigo-50 border border-indigo-100 px-3 py-1 rounded-full">
            <Shield className="w-3.5 h-3.5 text-indigo-600" />
            <span className="text-xs font-semibold text-indigo-700">Private Research Intelligence Platform</span>
          </div>

          <h1 className="text-4xl sm:text-5xl font-extrabold text-slate-900 tracking-tight leading-tight">
            Discover, curate, and synthesize research over time.
          </h1>

          <p className="text-base text-slate-600 leading-relaxed max-w-xl">
            More than an ephemeral chat over a folder of PDFs. LitScope combines a persistent
            canonical library with project-specific research collections, verifiable citations,
            and evidence matrices.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4">
            <div className="flex items-start space-x-3 bg-white p-3.5 rounded-xl border border-slate-200 shadow-sm">
              <Layers className="w-5 h-5 text-indigo-600 mt-0.5 shrink-0" />
              <div>
                <h4 className="text-xs font-bold text-slate-900">Canonical Master Library</h4>
                <p className="text-[11px] text-slate-500 mt-0.5">Deduplicated papers stored once, shared across multiple projects.</p>
              </div>
            </div>

            <div className="flex items-start space-x-3 bg-white p-3.5 rounded-xl border border-slate-200 shadow-sm">
              <FileText className="w-5 h-5 text-indigo-600 mt-0.5 shrink-0" />
              <div>
                <h4 className="text-xs font-bold text-slate-900">Project Separability</h4>
                <p className="text-[11px] text-slate-500 mt-0.5">Custom research questions, scope criteria, and isolated notes.</p>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Authentication Card */}
        <div className="lg:w-5/12 w-full max-w-md">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl p-8 space-y-6">
            {/* Tab switch between Sign In and Register */}
            <div className="flex border-b border-slate-200">
              <button
                type="button"
                onClick={() => {
                  setAuthMode('login');
                  setError(null);
                  setSuccessMessage(null);
                }}
                className={`flex-1 pb-3 text-sm font-semibold border-b-2 transition ${
                  authMode === 'login'
                    ? 'border-indigo-600 text-indigo-600'
                    : 'border-transparent text-slate-400 hover:text-slate-700'
                }`}
              >
                Sign In
              </button>
              <button
                type="button"
                onClick={() => {
                  setAuthMode('register');
                  setError(null);
                  setSuccessMessage(null);
                }}
                className={`flex-1 pb-3 text-sm font-semibold border-b-2 transition ${
                  authMode === 'register'
                    ? 'border-indigo-600 text-indigo-600'
                    : 'border-transparent text-slate-400 hover:text-slate-700'
                }`}
              >
                Sign Up
              </button>
            </div>

            {/* Success Message Banner (Shown after registration redirect) */}
            {successMessage && (
              <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs p-3.5 rounded-xl flex items-start space-x-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <span>{successMessage}</span>
              </div>
            )}

            {/* Error Banner */}
            {error && (
              <div className="bg-rose-50 border border-rose-200 text-rose-700 text-xs p-3.5 rounded-xl">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {authMode === 'register' && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                    Full Name
                  </label>
                  <div className="relative mt-1">
                    <UserIcon className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                    <input
                      type="text"
                      placeholder="Dr. Alex Rivera"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      className="w-full pl-9 pr-3 py-2.5 border border-slate-300 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                    />
                  </div>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                  Email Address
                </label>
                <div className="relative mt-1">
                  <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  <input
                    type="email"
                    required
                    placeholder="researcher@university.edu"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full pl-9 pr-3 py-2.5 border border-slate-300 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                  Password
                </label>
                <div className="relative mt-1">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  <input
                    type="password"
                    required
                    minLength={6}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full pl-9 pr-3 py-2.5 border border-slate-300 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-semibold shadow-md transition disabled:opacity-50 flex items-center justify-center space-x-2"
              >
                <span>{loading ? 'Processing...' : authMode === 'register' ? 'Create Account' : 'Sign In'}</span>
                {!loading && <ArrowRight className="w-4 h-4" />}
              </button>
            </form>

            <div className="text-center pt-2">
              <span className="text-xs text-slate-400">
                {authMode === 'login' ? "Don't have an account? " : 'Already have an account? '}
              </span>
              <button
                type="button"
                onClick={() => {
                  setAuthMode(authMode === 'login' ? 'register' : 'login');
                  setError(null);
                  setSuccessMessage(null);
                }}
                className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 underline ml-1"
              >
                {authMode === 'login' ? 'Sign Up' : 'Sign In'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-4 text-center text-xs text-slate-400">
        LitScope — Conventional RAG Research Intelligence Platform
      </footer>
    </div>
  );
};
