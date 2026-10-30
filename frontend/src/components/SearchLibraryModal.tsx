import React, { useState, useEffect } from 'react';
import { Search, X, Plus, Check, Loader2, BookOpen, User as UserIcon, Calendar, FileText } from 'lucide-react';
import { api, Paper, Project, CuratedPaper } from '../api/client';

interface SearchLibraryModalProps {
  project: Project;
  curatedPapers: CuratedPaper[];
  onClose: () => void;
  onPaperAdded: () => void;
}

export const SearchLibraryModal: React.FC<SearchLibraryModalProps> = ({
  project,
  curatedPapers,
  onClose,
  onPaperAdded,
}) => {
  const [libraryPapers, setLibraryPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [addingId, setAddingId] = useState<number | null>(null);
  const [addedIds, setAddedIds] = useState<Set<number>>(new Set());

  // Initialize addedIds from existing curated papers
  useEffect(() => {
    const existing = new Set<number>(curatedPapers.map((cp) => cp.paper_id));
    setAddedIds(existing);
  }, [curatedPapers]);

  // Load master library papers
  useEffect(() => {
    const fetchPapers = async () => {
      setLoading(true);
      try {
        const papers = await api.getPapers();
        setLibraryPapers(papers);
      } catch (err) {
        console.error('Failed to load library papers:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchPapers();
  }, []);

  const handleAddPaper = async (paperId: number) => {
    setAddingId(paperId);
    try {
      await api.curatePaper(project.id, paperId, 'included', '');
      setAddedIds((prev) => new Set([...prev, paperId]));
      onPaperAdded();
    } catch (err: any) {
      alert(err.message || 'Failed to add paper to project');
    } finally {
      setAddingId(null);
    }
  };

  const filteredPapers = libraryPapers.filter((p) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    const titleMatch = p.title.toLowerCase().includes(term);
    const authorMatch = p.authors?.toLowerCase().includes(term) ?? false;
    return titleMatch || authorMatch;
  });

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full p-6 flex flex-col max-h-[88vh] space-y-4">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-lg font-bold text-slate-900">Search Master Library</h3>
            <p className="text-xs text-slate-500">
              Browse and add papers from your library to <span className="font-semibold text-slate-700">{project.name}</span>
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search Input */}
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search by title or author name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs sm:text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none focus:bg-white transition"
          />
        </div>

        {/* Papers List */}
        <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 text-slate-400 space-y-2">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
              <p className="text-xs font-medium">Loading library papers...</p>
            </div>
          ) : filteredPapers.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-xs">
              <BookOpen className="w-8 h-8 text-slate-300 mx-auto mb-2" />
              <p className="font-semibold text-slate-600">No papers found</p>
              <p className="text-slate-400 mt-0.5">
                {searchTerm ? 'Try a different search query.' : 'Upload PDFs to your master library first.'}
              </p>
            </div>
          ) : (
            filteredPapers.map((paper) => {
              const isAdded = addedIds.has(paper.id);
              const isAddingThis = addingId === paper.id;
              const pageCount = paper.latest_version?.page_count;

              return (
                <div
                  key={paper.id}
                  className="flex items-center justify-between p-3.5 rounded-xl border border-slate-200 hover:border-slate-300 hover:bg-slate-50/50 transition gap-3"
                >
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-semibold text-slate-900 leading-snug truncate" title={paper.title}>
                      {paper.title}
                    </h4>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500 mt-1">
                      {paper.authors && (
                        <span className="flex items-center truncate max-w-xs">
                          <UserIcon className="w-3 h-3 mr-1 text-slate-400 flex-shrink-0" />
                          <span className="truncate">{paper.authors}</span>
                        </span>
                      )}
                      {paper.year && (
                        <span className="flex items-center flex-shrink-0">
                          <Calendar className="w-3 h-3 mr-1 text-slate-400" />
                          {paper.year}
                        </span>
                      )}
                      {pageCount && (
                        <span className="flex items-center flex-shrink-0 text-slate-400 font-mono">
                          <FileText className="w-3 h-3 mr-1" />
                          {pageCount}p
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex-shrink-0">
                    {isAdded ? (
                      <span className="inline-flex items-center px-2.5 py-1 text-xs font-semibold rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200">
                        <Check className="w-3.5 h-3.5 mr-1 text-emerald-600" />
                        Added
                      </span>
                    ) : (
                      <button
                        onClick={() => handleAddPaper(paper.id)}
                        disabled={isAddingThis}
                        className="inline-flex items-center px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition disabled:opacity-50"
                      >
                        {isAddingThis ? (
                          <>
                            <Loader2 className="w-3 h-3 mr-1.5 animate-spin" />
                            Adding...
                          </>
                        ) : (
                          <>
                            <Plus className="w-3.5 h-3.5 mr-1" />
                            Add to Project
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end pt-3 border-t border-slate-100">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
