import React, { useState, useEffect } from 'react';
import {
  Project,
  LiteratureReview,
  ReviewReference,
  api,
} from '../api/client';
import {
  Sparkles,
  RefreshCw,
  Copy,
  Check,
  Download,
  BookOpen,
  FileText,
  Clock,
  Layers,
} from 'lucide-react';
import { toast } from './Toast';

interface LiteratureReviewViewProps {
  project: Project;
  canEdit: boolean;
  onOpenPaperReader: (paperId: number, pageNumber?: number) => void;
}

export const LiteratureReviewView: React.FC<LiteratureReviewViewProps> = ({
  project,
  canEdit,
  onOpenPaperReader,
}) => {
  const [currentReview, setCurrentReview] = useState<LiteratureReview | null>(null);
  const [history, setHistory] = useState<LiteratureReview[]>([]);
  const [papersCount, setPapersCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);

  // Word count selector: 200, 350, 500, or 'custom'
  const [selectedWordPreset, setSelectedWordPreset] = useState<number | 'custom'>(350);
  const [customWordCount, setCustomWordCount] = useState<number>(600);
  const [copied, setCopied] = useState<boolean>(false);

  const loadData = async () => {
    try {
      setLoading(true);
      const data = await api.getProjectReviews(project.id);
      setCurrentReview(data.current_review);
      setHistory(data.history);
      setPapersCount(data.papers_count);
    } catch (err: any) {
      toast.error(err.message || 'Failed to load literature review');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [project.id]);

  const activeTargetWordCount = selectedWordPreset === 'custom' ? customWordCount : selectedWordPreset;

  const handleGenerate = async () => {
    if (!canEdit) return;
    if (activeTargetWordCount < 100 || activeTargetWordCount > 2500) {
      toast.error('Please enter a target word count between 100 and 2500 words.');
      return;
    }

    try {
      setGenerating(true);
      const newReview = await api.generateProjectReview(project.id, activeTargetWordCount);
      setCurrentReview(newReview);
      setHistory((prev) => [newReview, ...prev]);
      toast.success(`Generated continuous literature review (${newReview.actual_word_count} words)!`);
    } catch (err: any) {
      toast.error(err.message || 'Failed to generate literature review');
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = async () => {
    if (!currentReview) return;
    try {
      await navigator.clipboard.writeText(currentReview.review_text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast.success('Literature review copied to clipboard');
    } catch (err) {
      toast.error('Failed to copy to clipboard');
    }
  };

  const handleExport = async (format: 'markdown' | 'bibtex') => {
    if (!currentReview) return;
    try {
      await api.exportProjectReview(project.id, format, currentReview.id);
      toast.success(`Exported literature review as ${format.toUpperCase()}`);
    } catch (err: any) {
      toast.error(err.message || 'Export failed');
    }
  };

  const handleSelectHistoryVersion = (reviewId: number) => {
    const selected = history.find((h) => h.id === reviewId);
    if (selected) {
      setCurrentReview(selected);
    }
  };

  // Render text with interactive citation badges [X]
  const renderInteractiveText = (text: string, references: ReviewReference[]) => {
    const refMap = new Map<number, ReviewReference>();
    references.forEach((r) => refMap.set(r.ref_index, r));

    // Split text by bracketed references like [1], [2], [14]
    const parts = text.split(/(\[\d+\])/g);

    return parts.map((part, idx) => {
      const match = part.match(/^\[(\d+)\]$/);
      if (match) {
        const refIndex = parseInt(match[1], 10);
        const ref = refMap.get(refIndex);

        if (ref) {
          return (
            <button
              key={idx}
              type="button"
              onClick={() => onOpenPaperReader(ref.paper_id)}
              className="inline-flex items-center gap-0.5 px-1.5 py-0.2 mx-0.5 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 hover:text-indigo-900 border border-indigo-200 rounded transition shadow-2xs cursor-pointer align-baseline"
              title={`[${refIndex}] ${ref.title} (${ref.year || 'N/A'})\nClick to open in reader`}
            >
              <span>{part}</span>
            </button>
          );
        }
      }
      return <span key={idx}>{part}</span>;
    });
  };

  return (
    <div className="space-y-4">
      {/* Clean Standard Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-slate-200">
        <div>
          <h3 className="text-base font-bold text-slate-900">Literature Review</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Continuous academic synthesis connecting all papers included in this study.
          </p>
        </div>

        {/* Word Count Selector & Actions */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Preset Buttons */}
          <div className="flex items-center space-x-1 bg-white border border-slate-200 rounded-lg p-0.5 shadow-xs text-xs">
            {[200, 350, 500].map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => setSelectedWordPreset(preset)}
                className={`px-2.5 py-1 rounded-md text-xs font-semibold transition ${
                  selectedWordPreset === preset
                    ? 'bg-indigo-600 text-white shadow-xs'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`}
              >
                {preset}w
              </button>
            ))}
            <button
              type="button"
              onClick={() => setSelectedWordPreset('custom')}
              className={`px-2.5 py-1 rounded-md text-xs font-semibold transition ${
                selectedWordPreset === 'custom'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              Custom
            </button>
          </div>

          {/* Custom Word Input */}
          {selectedWordPreset === 'custom' && (
            <div className="flex items-center space-x-1 bg-white border border-slate-200 rounded-lg px-2 py-0.5 shadow-xs">
              <input
                type="number"
                min={100}
                max={2500}
                step={50}
                value={customWordCount}
                onChange={(e) => setCustomWordCount(Math.max(100, parseInt(e.target.value, 10) || 100))}
                className="w-16 text-xs text-slate-800 font-semibold focus:outline-none"
              />
              <span className="text-[11px] text-slate-400 font-medium">words</span>
            </div>
          )}

          {/* Generate Button */}
          {canEdit && (
            <button
              onClick={handleGenerate}
              disabled={generating || papersCount === 0}
              className="inline-flex items-center px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white rounded-lg text-xs font-semibold shadow-xs transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${generating ? 'animate-spin' : ''}`} />
              {generating ? 'Synthesizing Review...' : currentReview ? 'Re-generate' : 'Generate Review'}
            </button>
          )}

          {/* Export Actions (when review exists) */}
          {currentReview && (
            <div className="flex items-center space-x-1.5">
              <button
                onClick={handleCopy}
                className="inline-flex items-center px-2.5 py-1.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-medium shadow-xs transition"
                title="Copy text to clipboard"
              >
                {copied ? <Check className="w-3.5 h-3.5 mr-1 text-emerald-600" /> : <Copy className="w-3.5 h-3.5 mr-1 text-slate-500" />}
                {copied ? 'Copied' : 'Copy'}
              </button>

              <div className="flex items-center bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden">
                <button
                  onClick={() => handleExport('markdown')}
                  className="px-2.5 py-1.5 text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition flex items-center border-r border-slate-200"
                  title="Export as Markdown (.md)"
                >
                  <Download className="w-3 h-3 mr-1 text-slate-400" />
                  MD
                </button>
                <button
                  onClick={() => handleExport('bibtex')}
                  className="px-2.5 py-1.5 text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition flex items-center"
                  title="Export Bibliography as BibTeX (.bib)"
                >
                  <BookOpen className="w-3 h-3 mr-1 text-slate-400" />
                  BibTeX
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="text-center py-16 bg-white rounded-xl border border-slate-200 shadow-xs">
          <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin mx-auto mb-2" />
          <p className="text-xs text-slate-500">Loading literature review...</p>
        </div>
      ) : !currentReview ? (
        <div className="text-center py-16 bg-white rounded-xl border border-slate-200 shadow-xs p-8">
          <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-800">No Literature Review Generated Yet</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto mt-1 mb-5 leading-relaxed">
            {papersCount === 0
              ? 'Add and curate papers into your project collection first, then generate a continuous academic literature review.'
              : `Select your desired target word count (${activeTargetWordCount}w) and click "Generate Review" to synthesize all ${papersCount} included papers into one flowing narrative.`}
          </p>
          {canEdit && papersCount > 0 && (
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="inline-flex items-center px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold transition"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              Generate Literature Review ({activeTargetWordCount}w)
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {/* Meta Bar */}
          <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs">
            <div className="flex items-center space-x-3 text-slate-600 flex-wrap gap-y-1">
              <span className="font-semibold text-slate-900">
                {currentReview.actual_word_count} words
              </span>
              <span className="text-slate-300">•</span>
              <span>Target: {currentReview.target_word_count}w</span>
              <span className="text-slate-300">•</span>
              <span className="inline-flex items-center text-indigo-700 font-medium">
                <Layers className="w-3.5 h-3.5 mr-1 text-indigo-500" />
                {currentReview.paper_references.length} Papers Connected
              </span>
              <span className="text-slate-300">•</span>
              <span className="inline-flex items-center text-slate-500 text-[11px]">
                <Clock className="w-3 h-3 mr-1 text-slate-400" />
                {new Date(currentReview.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
              </span>
            </div>

            {/* Version Switcher if multiple drafts exist */}
            {history.length > 1 && (
              <div className="flex items-center space-x-1.5">
                <span className="text-[11px] text-slate-500 font-medium">Draft:</span>
                <select
                  value={currentReview.id}
                  onChange={(e) => handleSelectHistoryVersion(Number(e.target.value))}
                  className="bg-white border border-slate-200 rounded-md px-2 py-0.5 text-xs text-slate-700 font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500 shadow-2xs cursor-pointer"
                >
                  {history.map((h, i) => (
                    <option key={h.id} value={h.id}>
                      Draft {history.length - i} ({h.actual_word_count}w - {new Date(h.created_at).toLocaleDateString()})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Continuous Academic Review Narrative Card */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6 sm:p-8 space-y-4">
            <div className="prose prose-slate max-w-none text-xs sm:text-sm text-slate-800 leading-relaxed font-serif space-y-4">
              {currentReview.review_text.split('\n\n').map((paragraph, idx) => {
                const trimmed = paragraph.trim();
                if (!trimmed) return null;
                return (
                  <p key={idx} className="text-justify leading-relaxed">
                    {renderInteractiveText(trimmed, currentReview.paper_references)}
                  </p>
                );
              })}
            </div>

            {/* Separator */}
            <div className="pt-6 border-t border-slate-100 space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center">
                <BookOpen className="w-3.5 h-3.5 mr-1.5 text-indigo-600" />
                References ({currentReview.paper_references.length})
              </h4>

              <div className="space-y-2">
                {currentReview.paper_references.map((ref) => (
                  <div
                    key={ref.ref_index}
                    className="flex flex-col sm:flex-row sm:items-start justify-between gap-2 p-2.5 bg-slate-50/70 hover:bg-slate-50 rounded-lg border border-slate-100 text-xs transition"
                  >
                    <div className="flex items-start space-x-2">
                      <span className="font-bold text-indigo-700 flex-shrink-0">
                        [{ref.ref_index}]
                      </span>
                      <div className="space-y-0.5">
                        <p className="text-slate-800 font-medium">
                          {ref.authors || 'Anonymous'}.{' '}
                          <span className="italic">"{ref.title}"</span>{' '}
                          ({ref.year || 'n.d.'}).
                        </p>
                        {ref.doi && (
                          <p className="text-[11px] text-slate-400 font-mono">
                            DOI: https://doi.org/{ref.doi}
                          </p>
                        )}
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => onOpenPaperReader(ref.paper_id)}
                      className="inline-flex items-center self-start px-2 py-0.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded text-[10px] font-semibold border border-indigo-200 flex-shrink-0 transition"
                      title="Open paper in reader"
                    >
                      <FileText className="w-3 h-3 mr-1" />
                      Open Paper
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
