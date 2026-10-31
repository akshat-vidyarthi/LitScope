import React, { useState, useEffect } from 'react';
import {
  Project,
  ResearchGap,
  GapAnalysisSummary,
  api,
  CuratedPaper,
} from '../api/client';
import {
  Plus,
  RefreshCw,
  Search,
  BookOpen,
  ChevronDown,
  ChevronUp,
  FileText,
  Trash2,
  X,
  Download,
  HelpCircle,
} from 'lucide-react';
import { toast } from './Toast';
import { ConfirmModal } from './ConfirmModal';

interface ResearchGapsViewProps {
  project: Project;
  canEdit: boolean;
  onOpenPaperReader: (paperId: number, pageNumber?: number) => void;
}

export const ResearchGapsView: React.FC<ResearchGapsViewProps> = ({
  project,
  canEdit,
  onOpenPaperReader,
}) => {
  const [summary, setSummary] = useState<GapAnalysisSummary | null>(null);
  const [projectPapers, setProjectPapers] = useState<CuratedPaper[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [activeTypeFilter, setActiveTypeFilter] = useState<string>('all');
  const [activeStatusFilter, setActiveStatusFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedGapIds, setExpandedGapIds] = useState<Set<number>>(new Set());

  // Custom gap modal state (Title, Category, Paper ONLY - Image 1)
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [customTitle, setCustomTitle] = useState<string>('');
  const [customType, setCustomType] = useState<string>('methodological');
  const [customPaperId, setCustomPaperId] = useState<number | null>(null);
  const [submittingCustom, setSubmittingCustom] = useState<boolean>(false);

  // Delete modal state
  const [gapToDelete, setGapToDelete] = useState<ResearchGap | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const [gapsData, curated] = await Promise.all([
        api.getProjectGaps(project.id),
        api.getCuratedPapers(project.id),
      ]);
      setSummary(gapsData);
      setProjectPapers(curated);
      if (curated && curated.length > 0) {
        setCustomPaperId(curated[0].paper_id);
      }
      // Supporting evidence is hidden by default
    } catch (err: any) {
      toast.error(err.message || 'Failed to load research gaps');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [project.id]);

  const handleGenerate = async () => {
    if (!canEdit) return;
    try {
      setGenerating(true);
      const data = await api.generateProjectGaps(project.id, true);
      setSummary(data);
      toast.success(`Discovered ${data.total_gaps} candidate research gaps paper-wise!`);
    } catch (err: any) {
      toast.error(err.message || 'Failed to analyze research gaps');
    } finally {
      setGenerating(false);
    }
  };

  const handleUpdateStatus = async (gap: ResearchGap, newStatus: string) => {
    if (!canEdit) return;
    try {
      const updated = await api.updateProjectGap(project.id, gap.id, {
        review_status: newStatus,
      });
      setSummary((prev) => {
        if (!prev) return prev;
        const updatedGaps = prev.gaps.map((g) => (g.id === gap.id ? updated : g));
        return {
          ...prev,
          gaps: updatedGaps,
          validated_count: updatedGaps.filter((g) => ['validated', 'refined'].includes(g.review_status)).length,
          pending_count: updatedGaps.filter((g) => g.review_status === 'pending').length,
          dismissed_count: updatedGaps.filter((g) => g.review_status === 'dismissed').length,
        };
      });
    } catch (err: any) {
      toast.error(err.message || 'Failed to update gap status');
    }
  };

  const handleCreateCustom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customTitle.trim()) {
      toast.error('Gap title is required.');
      return;
    }
    if (!customPaperId) {
      toast.error('Please select which paper has this gap.');
      return;
    }
    try {
      setSubmittingCustom(true);
      const newGap = await api.createCustomGap(project.id, {
        paper_id: customPaperId,
        gap_title: customTitle.trim(),
        gap_type: customType,
      });
      setSummary((prev) => {
        if (!prev) return prev;
        const updatedGaps = [newGap, ...prev.gaps];
        return {
          ...prev,
          gaps: updatedGaps,
          total_gaps: updatedGaps.length,
          validated_count: prev.validated_count + 1,
        };
      });
      setShowAddModal(false);
      setCustomTitle('');
      toast.success('Custom research gap recorded successfully!');
    } catch (err: any) {
      toast.error(err.message || 'Failed to add custom gap');
    } finally {
      setSubmittingCustom(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!gapToDelete) return;
    try {
      await api.deleteProjectGap(project.id, gapToDelete.id);
      setSummary((prev) => {
        if (!prev) return prev;
        const updatedGaps = prev.gaps.filter((g) => g.id !== gapToDelete.id);
        return {
          ...prev,
          gaps: updatedGaps,
          total_gaps: updatedGaps.length,
        };
      });
      toast.success(`Removed gap: "${gapToDelete.gap_title}"`);
    } catch (err: any) {
      toast.error(err.message || 'Failed to delete gap');
    } finally {
      setGapToDelete(null);
    }
  };

  const toggleExpand = (gapId: number) => {
    setExpandedGapIds((prev) => {
      const next = new Set(prev);
      if (next.has(gapId)) next.delete(gapId);
      else next.add(gapId);
      return next;
    });
  };

  const handleExport = async (format: 'csv' | 'markdown') => {
    try {
      await api.exportGaps(project.id, format);
      toast.success(`Exported research gaps as ${format.toUpperCase()}`);
    } catch (err: any) {
      toast.error(err.message || 'Export failed');
    }
  };

  // Filtered gaps list
  const filteredGaps = (summary?.gaps || []).filter((g) => {
    if (activeTypeFilter !== 'all' && g.gap_type !== activeTypeFilter) return false;
    if (activeStatusFilter !== 'all') {
      if (activeStatusFilter === 'validated' && !['validated', 'refined'].includes(g.review_status)) return false;
      if (activeStatusFilter === 'pending' && g.review_status !== 'pending') return false;
      if (activeStatusFilter === 'dismissed' && g.review_status !== 'dismissed') return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTitle = g.gap_title.toLowerCase().includes(q);
      const matchDesc = g.description.toLowerCase().includes(q);
      const matchPaper = (g.paper_title || '').toLowerCase().includes(q);
      if (!matchTitle && !matchDesc && !matchPaper) return false;
    }
    return true;
  });

  const getTypeBadge = (type: string) => {
    switch (type) {
      case 'methodological':
        return { label: 'Methodological Gap', bg: 'bg-indigo-50 text-indigo-700 border-indigo-200' };
      case 'dataset_context':
        return { label: 'Dataset & Context', bg: 'bg-indigo-50 text-indigo-700 border-indigo-200' };
      case 'contradiction':
        return { label: 'Contradictions', bg: 'bg-indigo-50 text-indigo-700 border-indigo-200' };
      case 'author_stated_limitation':
        return { label: 'Author Limitations', bg: 'bg-indigo-50 text-indigo-700 border-indigo-200' };
      default:
        return { label: type, bg: 'bg-indigo-50 text-indigo-700 border-indigo-200' };
    }
  };

  return (
    <div className="space-y-4">
      {/* Clean Standard Header (Point 3 - Removed unnecessary gradient & dark color) */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-slate-200">
        <div>
          <h3 className="text-base font-bold text-slate-900">Research Gaps</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Candidate research gaps identified paper-wise across your study collection.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          {canEdit && (
            <button
              onClick={handleGenerate}
              disabled={generating || (summary?.papers_count || 0) === 0}
              className="inline-flex items-center px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white rounded-lg text-xs font-semibold shadow-xs transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${generating ? 'animate-spin' : ''}`} />
              {generating ? 'Analyzing Gaps...' : 'Re-analyze Gaps'}
            </button>
          )}

          {canEdit && (
            <button
              onClick={() => setShowAddModal(true)}
              className="inline-flex items-center px-3 py-1.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-medium shadow-xs transition"
            >
              <Plus className="w-3.5 h-3.5 mr-1 text-slate-500" />
              Add Custom Gap
            </button>
          )}

          <div className="flex items-center bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden">
            <button
              onClick={() => handleExport('csv')}
              className="px-2.5 py-1.5 text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition flex items-center border-r border-slate-200"
              title="Export as CSV"
            >
              <Download className="w-3 h-3 mr-1 text-slate-400" />
              CSV
            </button>
            <button
              onClick={() => handleExport('markdown')}
              className="px-2.5 py-1.5 text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition flex items-center"
              title="Export as Markdown"
            >
              <FileText className="w-3 h-3 mr-1 text-slate-400" />
              Markdown
            </button>
          </div>
        </div>
      </div>

      {/* Single-Line Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Category Filter Chips */}
        <div className="flex items-center space-x-1.5 flex-wrap gap-y-1">
          {[
            { id: 'all', label: 'All Types' },
            { id: 'methodological', label: 'Methodological' },
            { id: 'dataset_context', label: 'Dataset & Context' },
            { id: 'contradiction', label: 'Contradictions' },
            { id: 'author_stated_limitation', label: 'Author Limitations' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTypeFilter(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition ${
                activeTypeFilter === tab.id
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Right side: All Statuses Dropdown & Search Bar */}
        <div className="flex items-center space-x-2 flex-shrink-0">
          <select
            value={activeStatusFilter}
            onChange={(e) => setActiveStatusFilter(e.target.value)}
            className="text-xs bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-xs cursor-pointer"
          >
            <option value="all">All Statuses</option>
            <option value="validated">Validated</option>
            <option value="pending">Pending</option>
            <option value="dismissed">Dismissed</option>
          </select>

          <div className="relative w-48 sm:w-60">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search gaps or notes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-xs"
            />
          </div>
        </div>
      </div>

      {/* Gaps List */}
      {loading ? (
        <div className="text-center py-16 bg-white rounded-xl border border-slate-200 shadow-xs">
          <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin mx-auto mb-2" />
          <p className="text-xs text-slate-500">Loading research gaps...</p>
        </div>
      ) : filteredGaps.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-slate-200 shadow-xs p-8">
          <HelpCircle className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-800">
            {summary?.total_gaps === 0 ? 'No Research Gaps Identified Yet' : 'No Gaps Match Your Filter'}
          </h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto mt-1 mb-5 leading-relaxed">
            {summary?.total_gaps === 0
              ? 'Click "Re-analyze Gaps" above to discover candidate research gaps across your collection.'
              : 'Try clearing your search query or switching to another category.'}
          </p>
          {canEdit && summary?.total_gaps === 0 && (
            <button
              onClick={handleGenerate}
              disabled={generating || (summary?.papers_count || 0) === 0}
              className="inline-flex items-center px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold transition"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Analyze Research Gaps Now
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredGaps.map((gap) => {
            const isExpanded = expandedGapIds.has(gap.id);
            const typeInfo = getTypeBadge(gap.gap_type);
            const isValidated = ['validated', 'refined'].includes(gap.review_status);
            const isDismissed = gap.review_status === 'dismissed';
            const paperName = gap.paper_title || gap.supporting_evidence[0]?.paper_title || 'Paper';
            const instanceCount = gap.supporting_evidence.length;
            const instanceLabel = `${paperName} (${instanceCount} ${instanceCount === 1 ? 'instance' : 'instances'})`;

            return (
              <div
                key={gap.id}
                className={`bg-white rounded-xl border transition-all duration-200 overflow-hidden shadow-xs ${
                  isValidated
                    ? 'border-emerald-400 ring-1 ring-emerald-200'
                    : isDismissed
                    ? 'border-rose-400 ring-1 ring-rose-200'
                    : 'border-amber-400 ring-1 ring-amber-200'
                }`}
              >
                {/* Card Header */}
                <div className="p-4 sm:p-5">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    {/* ONLY keep type of gap label and validated/pending/dismissed label */}
                    <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                      <span className={`px-2.5 py-0.5 rounded-md text-[11px] font-semibold border ${typeInfo.bg}`}>
                        {typeInfo.label}
                      </span>
                      {isValidated && (
                        <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                          Validated
                        </span>
                      )}
                      {gap.review_status === 'pending' && (
                        <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-amber-100 text-amber-800 border border-amber-200">
                          Pending
                        </span>
                      )}
                      {isDismissed && (
                        <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-rose-100 text-rose-800 border border-rose-200">
                          Dismissed
                        </span>
                      )}
                    </div>

                    {/* Top Right Controls: 3-Point Slider + Delete Icon + Expand Chevron */}
                    <div className="flex items-center space-x-2 flex-shrink-0">
                      {canEdit && (
                        <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200 text-xs select-none shadow-xs">
                          <button
                            type="button"
                            onClick={() => handleUpdateStatus(gap, 'validated')}
                            className={`px-2.5 py-0.5 rounded-md font-semibold text-[10px] sm:text-[11px] transition ${
                              isValidated
                                ? 'bg-emerald-600 text-white shadow-xs'
                                : 'text-slate-600 hover:text-emerald-700 hover:bg-slate-200/60'
                            }`}
                            title="Validate gap"
                          >
                            Validate
                          </button>
                          <button
                            type="button"
                            onClick={() => handleUpdateStatus(gap, 'pending')}
                            className={`px-2.5 py-0.5 rounded-md font-semibold text-[10px] sm:text-[11px] transition ${
                              gap.review_status === 'pending'
                                ? 'bg-amber-500 text-white shadow-xs'
                                : 'text-slate-600 hover:text-amber-700 hover:bg-slate-200/60'
                            }`}
                            title="Mark Pending"
                          >
                            Pending
                          </button>
                          <button
                            type="button"
                            onClick={() => handleUpdateStatus(gap, 'dismissed')}
                            className={`px-2.5 py-0.5 rounded-md font-semibold text-[10px] sm:text-[11px] transition ${
                              isDismissed
                                ? 'bg-rose-600 text-white shadow-xs'
                                : 'text-slate-600 hover:text-rose-700 hover:bg-slate-200/60'
                            }`}
                            title="Dismiss gap"
                          >
                            Dismiss
                          </button>
                        </div>
                      )}

                      {canEdit && (
                        <button
                          onClick={() => setGapToDelete(gap)}
                          title="Delete Gap"
                          className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}

                      <button
                        onClick={() => toggleExpand(gap.id)}
                        className="p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition"
                        title={isExpanded ? 'Collapse evidence' : 'Expand evidence'}
                      >
                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  {/* Title & Description */}
                  <h4 className="text-sm font-bold text-slate-900 leading-snug mb-1">
                    {gap.gap_title}
                  </h4>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    {gap.description}
                  </p>

                  {/* Bottom Link with Paper Name & Instances */}
                  <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between">
                    <button
                      onClick={() => toggleExpand(gap.id)}
                      className="text-[11px] text-indigo-600 hover:text-indigo-800 font-semibold flex items-center transition truncate max-w-full"
                    >
                      <span className="truncate">
                        {instanceLabel}
                      </span>
                      {isExpanded ? (
                        <ChevronUp className="w-3.5 h-3.5 ml-1 flex-shrink-0" />
                      ) : (
                        <ChevronDown className="w-3.5 h-3.5 ml-1 flex-shrink-0" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Evidence Drawer (Collapsible) */}
                {isExpanded && (
                  <div className="border-t border-slate-100 bg-slate-50/70 p-4 space-y-2">
                    <h5 className="text-[10px] font-bold text-slate-600 uppercase tracking-wider flex items-center">
                      <BookOpen className="w-3 h-3 mr-1 text-indigo-600" />
                      Supporting Evidence ({gap.supporting_evidence.length})
                    </h5>
                    {gap.supporting_evidence.length === 0 ? (
                      <p className="text-xs text-slate-400 italic">No direct quoted passages attached.</p>
                    ) : (
                      <div className="space-y-1.5">
                        {gap.supporting_evidence.map((s, idx) => (
                          <div
                            key={idx}
                            className="bg-white rounded-lg p-2.5 border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-start justify-between gap-2"
                          >
                            <div className="space-y-0.5">
                              <p className="text-xs text-slate-700 italic">
                                "{s.quote}"
                              </p>
                              {s.section && (
                                <span className="text-[10px] text-slate-400 uppercase font-medium">
                                  Section: {s.section}
                                </span>
                              )}
                            </div>

                            <button
                              onClick={() => onOpenPaperReader(s.paper_id, s.page_number)}
                              className="inline-flex items-center self-start px-2 py-0.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded text-[10px] font-semibold border border-indigo-200 flex-shrink-0 transition"
                              title="Open paper directly at this cited page"
                            >
                              <FileText className="w-3 h-3 mr-1" />
                              {s.page_number ? `Page ${s.page_number}` : 'Open Reader'}
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Add Custom Gap Modal (Point 2 - Image 1: Title, Category, Paper ONLY) */}
      {showAddModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <h3 className="text-base font-bold text-slate-900 flex items-center">
                <Plus className="w-4 h-4 mr-2 text-indigo-600" />
                Record Custom Research Gap
              </h3>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateCustom} className="space-y-4">
              {/* Gap Title */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Gap Title *
                </label>
                <input
                  type="text"
                  required
                  value={customTitle}
                  onChange={(e) => setCustomTitle(e.target.value)}
                  placeholder="e.g. Absence of Multi-Spectral Infrared Validation"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              {/* Gap Category (Point 4: Temporal removed) */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Gap Category
                </label>
                <select
                  value={customType}
                  onChange={(e) => setCustomType(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none bg-white"
                >
                  <option value="methodological">Methodological (Missing algorithms/models)</option>
                  <option value="dataset_context">Dataset & Context (Missing environments/samples)</option>
                  <option value="contradiction">Contradictions (Conflicting findings)</option>
                  <option value="author_stated_limitation">Author Limitations (Stated in conclusion)</option>
                </select>
              </div>

              {/* Paper Selector (Point 2: which paper has this gap) */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Paper (Which paper has this gap) *
                </label>
                <select
                  required
                  value={customPaperId || ''}
                  onChange={(e) => setCustomPaperId(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none bg-white"
                >
                  {projectPapers.map((cp) => (
                    <option key={cp.paper_id} value={cp.paper_id}>
                      {cp.title} ({cp.year || 'N/A'})
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex justify-end space-x-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-xs text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingCustom}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold transition"
                >
                  {submittingCustom ? 'Saving...' : 'Add Gap'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirm Delete Gap Modal */}
      <ConfirmModal
        isOpen={!!gapToDelete}
        title="Delete Candidate Research Gap"
        message={`Are you sure you want to delete "${gapToDelete?.gap_title || ''}"?\n\nThis will remove the gap from this project study.`}
        confirmText="Delete Gap"
        danger={true}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setGapToDelete(null)}
      />
    </div>
  );
};
