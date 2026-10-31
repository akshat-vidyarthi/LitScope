import React, { useState, useEffect } from 'react';
import {
  Search,
  Compass,
  ExternalLink,
  FileText,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Globe,
  Calendar,
  Plus,
} from 'lucide-react';
import {
  api,
  DiscoveredPaper,
  Project,
  DiscoveryImportResponse,
} from '../api/client';
import { toast } from './Toast';

export const DiscoveryView: React.FC = () => {
  const [query, setQuery] = useState('');
  const [fromYear, setFromYear] = useState('');
  const [toYear, setToYear] = useState('');
  const [limit, setLimit] = useState(10);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [results, setResults] = useState<DiscoveredPaper[]>([]);
  const [searchedQuery, setSearchedQuery] = useState<string | null>(null);

  // Projects list for one-click add to project
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectMap, setSelectedProjectMap] = useState<Record<string, number>>({});

  // Importing state tracking per paper id
  const [importingId, setImportingId] = useState<string | null>(null);
  const [importStatusMap, setImportStatusMap] = useState<Record<string, DiscoveryImportResponse>>({});
  const [expandedAbstracts, setExpandedAbstracts] = useState<Record<string, boolean>>({});

  // Load user projects once on mount
  useEffect(() => {
    api.getProjects().then(setProjects).catch(() => {});
  }, []);

  const handleSearch = async (searchQ?: string) => {
    const q = (searchQ !== undefined ? searchQ : query).trim();
    if (!q) return;

    setIsSearching(true);
    setSearchError(null);
    setSearchedQuery(q);

    const fYear = fromYear ? parseInt(fromYear, 10) : undefined;
    const tYear = toYear ? parseInt(toYear, 10) : undefined;

    try {
      const data = await api.searchDiscovery(q, fYear, tYear, limit);
      setResults(data.results);
    } catch (err: any) {
      setSearchError(err.message || 'Failed to search scholarly repositories');
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleImport = async (paper: DiscoveredPaper) => {
    setImportingId(paper.id);
    const targetProjectId = selectedProjectMap[paper.id];

    try {
      const res = await api.importDiscoveredPaper({
        title: paper.title,
        authors: paper.authors,
        year: paper.year,
        venue: paper.venue,
        doi: paper.doi,
        abstract: paper.abstract,
        source_url: paper.landing_page_url,
        pdf_url: paper.pdf_url,
        project_id: targetProjectId,
      });

      setImportStatusMap((prev) => ({ ...prev, [paper.id]: res }));
      // Mark as in_library
      setResults((prev) =>
        prev.map((p) => (p.id === paper.id ? { ...p, in_library: true } : p))
      );
      toast.success(`Imported "${paper.title}" to library!`);
    } catch (err: any) {
      toast.error(err.message || 'Import failed');
    } finally {
      setImportingId(null);
    }
  };

  const toggleAbstract = (id: string) => {
    setExpandedAbstracts((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header Banner */}
      <div className="mb-8">
        <div className="flex items-center space-x-3 mb-2">
          <div className="bg-indigo-600 text-white p-2 rounded-lg shadow-sm">
            <Compass className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Scholarly Literature Discovery
            </h1>
            <p className="text-sm text-slate-500">
              Search scholarly research papers with guaranteed open-access full-text PDFs ready for reading and vector indexing.
            </p>
          </div>
        </div>
      </div>

      {/* Search Bar & Options */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-8">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSearch();
          }}
          className="space-y-4"
        >
          <div className="flex flex-col md:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-5 h-5 absolute left-3.5 top-3.5 text-slate-400" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by keywords, title, author, or DOI (e.g. 10.1038/s41586-020-2649-2)..."
                className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white text-sm"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {/* Year Range Filter */}
              <div className="flex items-center bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-slate-700">
                <Calendar className="w-4 h-4 text-slate-400 mr-2 flex-shrink-0" />
                <span className="text-xs text-slate-500 mr-1.5 font-medium">Year:</span>
                <input
                  type="number"
                  placeholder="From"
                  value={fromYear}
                  onChange={(e) => setFromYear(e.target.value)}
                  className="w-16 bg-white border border-slate-200 rounded px-1.5 py-1 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 text-center"
                  min={1950}
                  max={2030}
                />
                <span className="text-slate-400 text-xs mx-1">–</span>
                <input
                  type="number"
                  placeholder="To"
                  value={toYear}
                  onChange={(e) => setToYear(e.target.value)}
                  className="w-16 bg-white border border-slate-200 rounded px-1.5 py-1 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 text-center"
                  min={1950}
                  max={2030}
                />
              </div>

              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="px-3 py-3 bg-slate-50 border border-slate-300 rounded-lg text-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value={10}>10 results</option>
                <option value={20}>20 results</option>
                <option value={25}>25 results</option>
              </select>

              <button
                type="submit"
                disabled={isSearching || !query.trim()}
                className="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white rounded-lg font-medium text-sm transition-colors flex items-center justify-center min-w-[110px] shadow-sm cursor-pointer"
              >
                {isSearching ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Searching...
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4 mr-2" />
                    Search
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Quick Search Chips */}
          <div className="flex flex-wrap items-center gap-2 pt-1 text-xs text-slate-500">
            <span className="font-medium flex items-center">
              <Sparkles className="w-3.5 h-3.5 mr-1 text-indigo-500" /> Suggested topics:
            </span>
            {[
              'Attention Is All You Need',
              'Deep Residual Learning',
              'CRISPR Cas9 Gene Editing',
              'Retrieval Augmented Generation',
              'Fake Currency Detection',
            ].map((topic) => (
              <button
                key={topic}
                type="button"
                onClick={() => {
                  setQuery(topic);
                  handleSearch(topic);
                }}
                className="px-2.5 py-1 bg-slate-100 hover:bg-indigo-50 hover:text-indigo-600 rounded-md text-slate-600 transition-colors"
              >
                {topic}
              </button>
            ))}
          </div>
        </form>
      </div>

      {/* Error Banner */}
      {searchError && (
        <div className="p-4 mb-6 bg-red-50 border border-red-200 rounded-xl flex items-center text-red-700 text-sm">
          <AlertCircle className="w-5 h-5 mr-3 flex-shrink-0" />
          <span>{searchError}</span>
        </div>
      )}

      {/* Results List */}
      {searchedQuery && !isSearching && results.length === 0 && !searchError && (
        <div className="text-center py-16 bg-white rounded-xl border border-slate-200 shadow-sm p-8">
          <Globe className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-800">No open-access PDF papers found</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto mt-1">
            Try adjusting your search terms, broadening the publication year range, or searching by a specific DOI.
          </p>
        </div>
      )}

      {results.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-700">
              Found {results.length} papers with full-text PDFs for "{searchedQuery}"
            </h2>
            <span className="text-xs text-slate-500">
              Showing open-access research papers
            </span>
          </div>

          <div className="space-y-4">
            {results.map((paper) => {
              const isImporting = importingId === paper.id;
              const importInfo = importStatusMap[paper.id];
              const isExpanded = !!expandedAbstracts[paper.id];

              return (
                <div
                  key={paper.id}
                  className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 hover:border-slate-300 transition-all"
                >
                  <div className="flex flex-col lg:flex-row justify-between items-start gap-4">
                    <div className="flex-1 min-w-0">
                      {/* Source & Badges */}
                      <div className="flex flex-wrap items-center gap-2 mb-2">
                        {paper.year && (
                          <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">
                            {paper.year}
                          </span>
                        )}

                        {paper.venue && (
                          <span className="px-2 py-0.5 rounded text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-100 max-w-[280px] truncate">
                            {paper.venue}
                          </span>
                        )}

                        <span className="flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <FileText className="w-3 h-3 mr-1" /> PDF Available
                        </span>

                        {paper.citation_count > 0 && (
                          <span className="px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">
                            {paper.citation_count.toLocaleString()} citations
                          </span>
                        )}

                        {paper.in_library && (
                          <span className="flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                            <CheckCircle2 className="w-3 h-3 mr-1" /> Added
                          </span>
                        )}
                      </div>

                      {/* Title */}
                      <h3 className="text-lg font-bold text-slate-900 mb-1 leading-snug">
                        {paper.landing_page_url ? (
                          <a
                            href={paper.landing_page_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-indigo-600 transition-colors inline-flex items-baseline"
                          >
                            <span>{paper.title}</span>
                            <ExternalLink className="w-3.5 h-3.5 ml-1.5 opacity-60 flex-shrink-0" />
                          </a>
                        ) : (
                          paper.title
                        )}
                      </h3>

                      {/* Authors */}
                      {paper.authors && paper.authors.length > 0 && (
                        <p className="text-xs text-slate-600 mb-3">
                          {paper.authors.slice(0, 8).join(', ')}
                          {paper.authors.length > 8 && ` +${paper.authors.length - 8} more`}
                        </p>
                      )}

                      {/* DOI */}
                      {paper.doi && (
                        <p className="text-xs text-slate-400 font-mono mb-3">
                          DOI: {paper.doi}
                        </p>
                      )}

                      {/* Abstract snippet with expand/collapse */}
                      {paper.abstract && (
                        <div className="mt-2 text-xs text-slate-600 leading-relaxed bg-slate-50 p-3 rounded-lg border border-slate-150">
                          <p>
                            {isExpanded
                              ? paper.abstract
                              : paper.abstract.length > 280
                              ? `${paper.abstract.slice(0, 280)}...`
                              : paper.abstract}
                          </p>
                          {paper.abstract.length > 280 && (
                            <button
                              type="button"
                              onClick={() => toggleAbstract(paper.id)}
                              className="mt-1 text-indigo-600 hover:text-indigo-700 font-medium inline-flex items-center text-xs"
                            >
                              {isExpanded ? (
                                <>
                                  Show less <ChevronUp className="w-3 h-3 ml-0.5" />
                                </>
                              ) : (
                                <>
                                  Read full abstract <ChevronDown className="w-3 h-3 ml-0.5" />
                                </>
                              )}
                            </button>
                          )}
                        </div>
                      )}

                      {/* Post-Import Feedback Banner */}
                      {importInfo && (
                        <div className="mt-3 p-2.5 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-xs flex items-center">
                          <CheckCircle2 className="w-4 h-4 mr-2 text-emerald-600 flex-shrink-0" />
                          <span>{importInfo.message}</span>
                        </div>
                      )}
                    </div>

                    {/* Actions Column */}
                    <div className="flex flex-col sm:flex-row lg:flex-col gap-2 w-full lg:w-56 flex-shrink-0 pt-2 lg:pt-0 border-t lg:border-t-0 border-slate-100">
                      {/* Destination Selector (Master Library or Project Name) */}
                      {!paper.in_library && (
                        <div>
                          <label className="block text-[11px] font-semibold text-slate-500 mb-1">
                            Destination:
                          </label>
                          <select
                            value={selectedProjectMap[paper.id] || ''}
                            onChange={(e) => {
                              const val = e.target.value ? Number(e.target.value) : undefined;
                              setSelectedProjectMap((prev) => {
                                const copy = { ...prev };
                                if (val) copy[paper.id] = val;
                                else delete copy[paper.id];
                                return copy;
                              });
                            }}
                            className="w-full text-xs px-2.5 py-1.5 bg-slate-50 border border-slate-300 rounded-md text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                          >
                            <option value="">Master Library</option>
                            {projects.map((p) => (
                              <option key={p.id} value={p.id}>
                                {p.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}

                      {/* Add Button */}
                      <button
                        onClick={() => handleImport(paper)}
                        disabled={isImporting || paper.in_library}
                        className={`w-full px-4 py-2.5 rounded-lg text-xs font-semibold flex items-center justify-center transition-colors shadow-sm ${
                          paper.in_library
                            ? 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed'
                            : 'bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer'
                        }`}
                      >
                        {isImporting ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                            Adding...
                          </>
                        ) : paper.in_library ? (
                          <>
                            <CheckCircle2 className="w-3.5 h-3.5 mr-1.5 text-blue-500" />
                            Added
                          </>
                        ) : (
                          <>
                            <Plus className="w-3.5 h-3.5 mr-1.5" />
                            Add
                          </>
                        )}
                      </button>

                      {paper.pdf_url && (
                        <a
                          href={paper.pdf_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="w-full px-3 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 rounded-lg text-xs font-medium text-center inline-flex items-center justify-center transition-colors"
                        >
                          <ExternalLink className="w-3 h-3 mr-1" />
                          View PDF Source
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
