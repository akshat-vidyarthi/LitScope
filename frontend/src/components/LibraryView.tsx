import React, { useState, useEffect } from 'react';
import {
  Search,
  BookOpen,
  Calendar,
  User as UserIcon,
  Shield,
  Upload,
  FileText,
  Pencil,
  FolderPlus,
} from 'lucide-react';
import { api, Paper, Project, User } from '../api/client';
import { UploadPdfModal } from './UploadPdfModal';
import { PaperReaderModal } from './PaperReaderModal';

interface LibraryViewProps {
  currentUser: User | null;
  onOpenAuth: () => void;
}

export const LibraryView: React.FC<LibraryViewProps> = ({ currentUser, onOpenAuth }) => {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [curatingPaper, setCuratingPaper] = useState<Paper | null>(null);
  const [readingPaper, setReadingPaper] = useState<Paper | null>(null);
  const [editingPaper, setEditingPaper] = useState<Paper | null>(null);
  const [editForm, setEditForm] = useState({ title: '', authors: '', year: '' });

  // Add to Project Modal Form
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [curationStatus, setCurationStatus] = useState('included');
  const [curationNotes, setCurationNotes] = useState('');

  const loadData = async () => {
    if (!currentUser) {
      setPapers([]);
      setProjects([]);
      setLoading(false);
      return;
    }
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
    if (!currentUser) {
      setLoading(false);
      return;
    }
    const delayDebounce = setTimeout(() => {
      loadData();
    }, 250);
    return () => clearTimeout(delayDebounce);
  }, [searchTerm, currentUser]);

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
      const projName = projects.find((p) => p.id === selectedProjectId)?.name || 'project';
      alert(`Added "${curatingPaper.title}" to ${projName}!`);
      setCuratingPaper(null);
      setCurationNotes('');
    } catch (err: any) {
      alert(err.message || 'Failed to add paper to project');
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingPaper) return;
    try {
      await api.updatePaper(editingPaper.id, {
        title: editForm.title.trim() || undefined,
        authors: editForm.authors.trim() || undefined,
        year: editForm.year ? Number(editForm.year) : undefined,
      });
      setEditingPaper(null);
      loadData();
    } catch (err: any) {
      alert(err.message || 'Failed to update paper');
    }
  };

  if (!currentUser) {
    return (
      <div className="max-w-md mx-auto my-20 p-8 bg-white border border-slate-200 rounded-2xl shadow-sm text-center space-y-4">
        <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-full flex items-center justify-center mx-auto">
          <Shield className="w-6 h-6" />
        </div>
        <h2 className="text-xl font-bold text-slate-900">Private Master Library</h2>
        <p className="text-sm text-slate-500">
          The master research library is private-by-default. Sign in to view and upload papers.
        </p>
        <button
          onClick={onOpenAuth}
          className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold shadow-sm transition"
        >
          Sign In / Create Account
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Master Research Library</h1>
          <p className="text-sm text-slate-500 mt-1">
            Canonical, deduplicated repository of academic papers and ingested full text.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowUploadModal(true)}
            className="inline-flex items-center px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg shadow-sm transition"
          >
            <Upload className="w-4 h-4 mr-2" />
            Upload PDF
          </button>
          <button
            disabled
            className="inline-flex items-center px-3.5 py-2 bg-slate-100 text-slate-400 text-sm font-medium rounded-lg border border-slate-200 cursor-not-allowed transition"
            title="Search Online will be available in future phase"
          >
            <Search className="w-4 h-4 mr-1.5" />
            Search Online
          </button>
        </div>
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
            Upload an academic PDF to add your first paper.
          </p>
          <div className="flex justify-center space-x-3">
            <button
              onClick={() => setShowUploadModal(true)}
              className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 shadow-sm transition"
            >
              <Upload className="w-4 h-4 mr-2" />
              Upload Research PDF
            </button>
            <button
              disabled
              className="inline-flex items-center px-4 py-2 bg-slate-100 border border-slate-200 text-slate-400 rounded-lg text-sm font-medium cursor-not-allowed"
            >
              <Search className="w-4 h-4 mr-1.5" />
              Search Online
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {papers.map((paper) => {
            const version = paper.latest_version;
            return (
              <div
                key={paper.id}
                className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:border-slate-300 transition"
              >
                <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                  <div className="space-y-1.5 flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      {version ? (
                        <span className="inline-flex items-center text-xs font-medium px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                          <FileText className="w-3 h-3 mr-1 text-slate-500" />
                          {version.page_count} Pages
                        </span>
                      ) : (
                        <span className="inline-flex items-center text-xs font-medium px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-500">
                          Metadata Only
                        </span>
                      )}
                    </div>

                    <h3 className="text-base font-bold text-slate-900 leading-snug">
                      {paper.title}
                    </h3>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 pt-0.5">
                      {paper.authors && (
                        <span className="flex items-center">
                          <UserIcon className="w-3.5 h-3.5 mr-1 text-slate-400" />
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
                      <p className="text-xs text-slate-600 mt-2 line-clamp-3 leading-relaxed">
                        {paper.abstract}
                      </p>
                    )}
                  </div>

                  {/* Actions Column */}
                  <div className="flex lg:flex-col sm:flex-row items-center lg:items-end gap-2 flex-shrink-0 pt-2 lg:pt-0">
                    {version ? (
                      <button
                        onClick={() => setReadingPaper(paper)}
                        className="inline-flex items-center px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg text-xs font-semibold transition"
                      >
                        <BookOpen className="w-4 h-4 mr-1.5 text-indigo-600" />
                        Read Document
                      </button>
                    ) : (
                      <button
                        onClick={() => setShowUploadModal(true)}
                        className="inline-flex items-center px-3 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-300 rounded-lg text-xs font-semibold transition"
                      >
                        <Upload className="w-4 h-4 mr-1.5 text-slate-500" />
                        Attach PDF
                      </button>
                    )}

                    <div className="flex items-center space-x-1.5">
                      <button
                        onClick={() => {
                          setEditingPaper(paper);
                          setEditForm({
                            title: paper.title || '',
                            authors: paper.authors || '',
                            year: paper.year ? paper.year.toString() : '',
                          });
                        }}
                        className="p-1.5 border border-slate-300 hover:border-slate-400 hover:bg-slate-50 rounded-lg text-slate-600 hover:text-slate-900 transition"
                        title="Edit paper metadata"
                        aria-label="Edit paper metadata"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>

                      <button
                        onClick={() => setCuratingPaper(paper)}
                        className="p-1.5 border border-slate-300 hover:border-indigo-600 hover:bg-indigo-50 rounded-lg text-indigo-600 hover:text-indigo-700 transition"
                        title="Add to Project"
                        aria-label="Add to Project"
                      >
                        <FolderPlus className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Upload PDF Modal */}
      {showUploadModal && (
        <UploadPdfModal
          projects={projects}
          onClose={() => setShowUploadModal(false)}
          onSuccess={() => {
            loadData();
          }}
        />
      )}

      {/* Document Reader Modal */}
      {readingPaper && (
        <PaperReaderModal
          paper={readingPaper}
          onClose={() => setReadingPaper(null)}
          onPaperUpdated={loadData}
        />
      )}

      {/* Add Paper to Project Modal */}
      {curatingPaper && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Add Paper to Project</h3>
            <p className="text-xs text-slate-500 font-medium line-clamp-1">
              Paper: {curatingPaper.title}
            </p>

            <form onSubmit={handleCurateSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Select Project
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
                  Add to Project
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* Edit Paper Details Modal */}
      {editingPaper && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Edit Paper Details</h3>
            <form onSubmit={handleEditSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Paper Title
                </label>
                <input
                  type="text"
                  required
                  value={editForm.title}
                  onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                  className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Authors
                </label>
                <input
                  type="text"
                  value={editForm.authors}
                  onChange={(e) => setEditForm({ ...editForm, authors: e.target.value })}
                  placeholder="e.g. Akshat Vidyarthi, Ayush Trivedi"
                  className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Publication Year
                </label>
                <input
                  type="number"
                  value={editForm.year}
                  onChange={(e) => setEditForm({ ...editForm, year: e.target.value })}
                  placeholder="e.g. 2024"
                  className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setEditingPaper(null)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
