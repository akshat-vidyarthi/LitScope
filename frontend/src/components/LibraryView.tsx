import React, { useState, useEffect } from 'react';
import { Search, Plus, BookOpen, BookmarkCheck, Calendar, User } from 'lucide-react';
import { api, Paper, Project } from '../api/client';

export const LibraryView: React.FC = () => {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [curatingPaper, setCuratingPaper] = useState<Paper | null>(null);

  // New Paper Form
  const [paperForm, setPaperForm] = useState({
    title: '',
    doi: '',
    authors: '',
    year: new Date().getFullYear(),
    venue: '',
    abstract: '',
  });

  // Curation Modal Form
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [curationStatus, setCurationStatus] = useState('included');
  const [curationNotes, setCurationNotes] = useState('');

  const loadData = async () => {
    try {
      setLoading(true);
      const [papersData, projectsData] = await Promise.all([
        api.getPapers(searchTerm || undefined),
        api.getProjects(),
      ]);
      setPapers(papersData);
      setProjects(projectsData);
      if (projectsData.length > 0 && !selectedProjectId) {
        setSelectedProjectId(projectsData[0].id);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const delayDebounce = setTimeout(() => {
      loadData();
    }, 250);
    return () => clearTimeout(delayDebounce);
  }, [searchTerm]);

  const handleAddPaper = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!paperForm.title.trim()) return;
    try {
      const created = await api.createPaper({
        ...paperForm,
        year: paperForm.year ? Number(paperForm.year) : undefined,
      });
      setPapers([created, ...papers]);
      setShowAddModal(false);
      setPaperForm({
        title: '',
        doi: '',
        authors: '',
        year: new Date().getFullYear(),
        venue: '',
        abstract: '',
      });
    } catch (err: any) {
      alert(err.message || 'Failed to add paper');
    }
  };

  const handleCurateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!curatingPaper || !selectedProjectId) return;
    try {
      await api.curatePaper(
        selectedProjectId,
        curatingPaper.id,
        curationStatus,
        curationNotes
      );
      alert(
        `Curated "${curatingPaper.title}" into ${
          projects.find((p) => p.id === selectedProjectId)?.name
        } as '${curationStatus}'!`
      );
      setCuratingPaper(null);
      setCurationNotes('');
    } catch (err) {
      alert('Failed to curate paper');
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Top Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Master Research Library</h1>
          <p className="text-sm text-slate-500 mt-1">
            Canonical, deduplicated repository of all research papers across projects.
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="inline-flex items-center px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg shadow-sm transition"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Paper to Library
        </button>
      </div>

      {/* Search Bar */}
      <div className="relative mb-6">
        <Search className="w-5 h-5 text-slate-400 absolute left-3.5 top-3" />
        <input
          type="text"
          placeholder="Search master library by title, abstract keyword, or author..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-11 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm shadow-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
        />
      </div>

      {/* Papers Grid */}
      {loading ? (
        <div className="text-center py-12 text-slate-400">Loading library...</div>
      ) : papers.length === 0 ? (
        <div className="text-center py-16 bg-white border border-slate-200 rounded-xl p-8 shadow-sm">
          <BookOpen className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-800">No papers found</h3>
          <p className="text-sm text-slate-500 mt-1 mb-4">
            Add a canonical paper record manually or through search discovery.
          </p>
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700"
          >
            Add First Paper
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {papers.map((paper) => (
            <div
              key={paper.id}
              className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:border-slate-300 transition"
            >
              <div className="flex justify-between items-start">
                <div className="space-y-1 max-w-4xl">
                  <h3 className="text-base font-bold text-slate-900 leading-snug">
                    {paper.title}
                  </h3>
                  <div className="flex items-center space-x-4 text-xs text-slate-500 pt-1">
                    {paper.authors && (
                      <span className="flex items-center">
                        <User className="w-3.5 h-3.5 mr-1 text-slate-400" />
                        {paper.authors}
                      </span>
                    )}
                    {paper.year && (
                      <span className="flex items-center">
                        <Calendar className="w-3.5 h-3.5 mr-1 text-slate-400" />
                        {paper.year}
                      </span>
                    )}
                    {paper.venue && (
                      <span className="font-medium text-slate-700 italic">
                        {paper.venue}
                      </span>
                    )}
                    {paper.doi && (
                      <span className="font-mono bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                        DOI: {paper.doi}
                      </span>
                    )}
                  </div>
                  {paper.abstract && (
                    <p className="text-xs text-slate-600 mt-3 line-clamp-3 leading-relaxed">
                      {paper.abstract}
                    </p>
                  )}
                </div>

                {/* Curate Action Button */}
                <button
                  onClick={() => setCuratingPaper(paper)}
                  className="inline-flex items-center px-3 py-1.5 border border-slate-300 hover:border-indigo-600 hover:text-indigo-600 rounded-lg text-xs font-semibold text-slate-700 transition"
                >
                  <BookmarkCheck className="w-4 h-4 mr-1.5 text-indigo-500" />
                  Curate into Project
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Paper Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-xl w-full p-6 space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Add Canonical Paper</h3>
            <form onSubmit={handleAddPaper} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Paper Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Deep Residual Learning for Image Recognition"
                  value={paperForm.title}
                  onChange={(e) => setPaperForm({ ...paperForm, title: e.target.value })}
                  className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase">
                    DOI (Unique Identifier)
                  </label>
                  <input
                    type="text"
                    placeholder="10.1109/CVPR.2016.90"
                    value={paperForm.doi}
                    onChange={(e) => setPaperForm({ ...paperForm, doi: e.target.value })}
                    className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase">
                    Year
                  </label>
                  <input
                    type="number"
                    value={paperForm.year}
                    onChange={(e) =>
                      setPaperForm({ ...paperForm, year: Number(e.target.value) })
                    }
                    className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase">
                    Authors
                  </label>
                  <input
                    type="text"
                    placeholder="He, K., Zhang, X., Ren, S., & Sun, J."
                    value={paperForm.authors}
                    onChange={(e) => setPaperForm({ ...paperForm, authors: e.target.value })}
                    className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase">
                    Venue / Journal
                  </label>
                  <input
                    type="text"
                    placeholder="IEEE CVPR"
                    value={paperForm.venue}
                    onChange={(e) => setPaperForm({ ...paperForm, venue: e.target.value })}
                    className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Abstract
                </label>
                <textarea
                  rows={3}
                  placeholder="Paste abstract here..."
                  value={paperForm.abstract}
                  onChange={(e) => setPaperForm({ ...paperForm, abstract: e.target.value })}
                  className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700"
                >
                  Save to Library
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Curate into Project Modal */}
      {curatingPaper && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Curate Paper into Project</h3>
            <p className="text-xs text-slate-500 font-medium line-clamp-1">
              Paper: {curatingPaper.title}
            </p>

            <form onSubmit={handleCurateSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Select Project *
                </label>
                <select
                  required
                  value={selectedProjectId || ''}
                  onChange={(e) => setSelectedProjectId(Number(e.target.value))}
                  className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none bg-white"
                >
                  {projects.map((proj) => (
                    <option key={proj.id} value={proj.id}>
                      {proj.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Inclusion Status
                </label>
                <select
                  value={curationStatus}
                  onChange={(e) => setCurationStatus(e.target.value)}
                  className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none bg-white"
                >
                  <option value="included">Included (Core evidence study)</option>
                  <option value="candidate">Candidate (Under preliminary review)</option>
                  <option value="excluded">Excluded (Screened out of scope)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Project Notes
                </label>
                <textarea
                  rows={2}
                  placeholder="e.g. Focus on Section 4 methodology for RQ1."
                  value={curationNotes}
                  onChange={(e) => setCurationNotes(e.target.value)}
                  className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setCuratingPaper(null)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700"
                >
                  Save Curation Link
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
