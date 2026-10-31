import React, { useState, useEffect } from 'react';
import {
  Send,
  Loader2,
  BookOpen,
  FileText,
  AlertCircle,
  Sparkles,
  ChevronDown,
  ChevronRight,
  MessageSquare,
  Clock,
  Copy,
  Check,
  Trash2,
  Download,
} from 'lucide-react';
import { api, Project, ProjectQuery, RetrievedChunk, CuratedPaper } from '../api/client';
import { toast } from './Toast';
import { ConfirmModal } from './ConfirmModal';

interface ProjectQAWorkspaceProps {
  project: Project;
  onOpenPaperReader: (paperId: number, pageNumber?: number) => void;
}

export const ProjectQAWorkspace: React.FC<ProjectQAWorkspaceProps> = ({
  project,
  onOpenPaperReader,
}) => {
  const [queries, setQueries] = useState<ProjectQuery[]>([]);
  const [projectPapers, setProjectPapers] = useState<CuratedPaper[]>([]);
  const [selectedPaperId, setSelectedPaperId] = useState<number | 'all'>('all');
  const [loadingHistory, setLoadingHistory] = useState<boolean>(true);
  const [question, setQuestion] = useState<string>('');
  const [retrievalDepth, setRetrievalDepth] = useState<number>(5);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedQueryIds, setExpandedQueryIds] = useState<number[]>([]);
  const [copiedQueryId, setCopiedQueryId] = useState<number | null>(null);
  const [queryToDelete, setQueryToDelete] = useState<number | null>(null);

  const loadHistory = async () => {
    try {
      setLoadingHistory(true);
      const [queriesData, papersData] = await Promise.all([
        api.getProjectQueries(project.id),
        api.getCuratedPapers(project.id),
      ]);
      setQueries(queriesData);
      setProjectPapers(papersData || []);
      // By default keep queries minimized in lazy column format, or expand the latest
      if (queriesData.length > 0) {
        setExpandedQueryIds([queriesData[0].id]);
      } else {
        setExpandedQueryIds([]);
      }
    } catch (err) {
      console.error('Failed to load query history:', err);
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, [project.id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || submitting) return;

    setSubmitting(true);
    setError(null);
    try {
      const paperIdParam = selectedPaperId === 'all' ? undefined : selectedPaperId;
      const result = await api.askProjectQuestion(project.id, q, retrievalDepth, paperIdParam);
      setQueries([result, ...queries]);
      // Auto-expand the newly generated answer
      setExpandedQueryIds((prev) => [result.id, ...prev.filter((id) => id !== result.id)]);
      setQuestion('');
    } catch (err: any) {
      setError(err.message || 'Failed to synthesize answer');
    } finally {
      setSubmitting(false);
    }
  };

  const toggleExpandQuery = (id: number) => {
    setExpandedQueryIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleExpandAll = () => {
    setExpandedQueryIds(queries.map((q) => q.id));
  };

  const handleCollapseAll = () => {
    setExpandedQueryIds([]);
  };

  const handleCitationClick = (citationText: string, chunks: RetrievedChunk[]) => {
    // Extract page number if present (e.g., "p. 3" or "p. 12")
    const pageMatch = citationText.match(/p\.\s*(\d+)/i);
    const pageNumber = pageMatch ? parseInt(pageMatch[1], 10) : undefined;

    // Match citation to paper in retrieved chunks
    const matched = chunks.find((c) => {
      if (c.citation === citationText) return true;
      if (citationText.toLowerCase().includes(c.paper_title.slice(0, 15).toLowerCase())) return true;
      if (pageNumber && c.page_number === pageNumber) return true;
      return false;
    });

    if (matched) {
      onOpenPaperReader(matched.paper_id, pageNumber || matched.page_number);
    } else if (chunks.length > 0) {
      onOpenPaperReader(chunks[0].paper_id, pageNumber || chunks[0].page_number);
    }
  };

  const handleCopyAnswer = async (e: React.MouseEvent, id: number, text: string) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
      setCopiedQueryId(id);
      setTimeout(() => setCopiedQueryId(null), 2000);
    } catch (err) {
      console.error('Failed to copy to clipboard', err);
    }
  };

  const handleDeleteQuery = (e: React.MouseEvent, queryId: number) => {
    e.stopPropagation();
    setQueryToDelete(queryId);
  };

  const handleConfirmDeleteQuery = async () => {
    if (!queryToDelete) return;
    try {
      await api.deleteProjectQuery(project.id, queryToDelete);
      setQueries((prev) => prev.filter((q) => q.id !== queryToDelete));
      setExpandedQueryIds((prev) => prev.filter((id) => id !== queryToDelete));
      toast.success('Query deleted from history');
    } catch (err: any) {
      toast.error(err.message || 'Failed to delete query');
    } finally {
      setQueryToDelete(null);
    }
  };

  const handleExportMarkdown = (e: React.MouseEvent, q: ProjectQuery) => {
    e.stopPropagation();
    const content = `# Research Question: ${q.question}\n\n**Date:** ${new Date(q.created_at).toLocaleString()}\n**Project:** ${project.name} (#${project.id})\n\n---\n\n## Grounded Synthesis\n\n${q.answer}\n\n---\n\n## Citations\n\n${q.citations.map((c) => `- ${c}`).join('\n')}\n`;

    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `litscope_synthesis_${q.id}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Inline Markdown & Interactive Citation Tokenizer
  const renderInlineText = (text: string, chunks: RetrievedChunk[]) => {
    // 1. Split on citation patterns: [Paper Title..., p. X]
    const citationParts = text.split(/(\[[^\]]+,\s*p\.\s*\d+[^\]]*\])/g);

    return citationParts.map((part, i) => {
      // If this part is a citation tag, render as an interactive pill button
      if (part.startsWith('[') && part.includes('p.') && part.endsWith(']')) {
        return (
          <button
            key={i}
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              handleCitationClick(part, chunks);
            }}
            className="inline-flex items-center gap-1 px-1.5 py-0.5 mx-0.5 font-medium text-xs text-indigo-700 bg-indigo-50 hover:bg-indigo-100 hover:text-indigo-900 border border-indigo-200/90 rounded-md transition shadow-xs cursor-pointer align-baseline"
            title="Click to jump directly to cited page in PDF"
          >
            <BookOpen className="w-3 h-3 text-indigo-600 inline flex-shrink-0" />
            <span>{part}</span>
          </button>
        );
      }

      // 2. Parse bold tags: **text**
      const boldParts = part.split(/(\*\*[^*]+\*\*)/g);
      return (
        <React.Fragment key={i}>
          {boldParts.map((bPart, j) => {
            if (bPart.startsWith('**') && bPart.endsWith('**') && bPart.length >= 4) {
              return (
                <strong key={j} className="font-semibold text-slate-900">
                  {bPart.slice(2, -2)}
                </strong>
              );
            }
            return bPart;
          })}
        </React.Fragment>
      );
    });
  };

  // Full Academic Markdown Document Parser
  const renderAcademicAnswer = (rawAnswer: string, chunks: RetrievedChunk[]) => {
    const lines = rawAnswer.split('\n');
    const elements: React.ReactNode[] = [];
    let currentList: React.ReactNode[] = [];

    const flushList = () => {
      if (currentList.length > 0) {
        elements.push(
          <ul key={`ul-${elements.length}`} className="my-2 space-y-1.5 pl-4 list-disc marker:text-indigo-500">
            {currentList}
          </ul>
        );
        currentList = [];
      }
    };

    lines.forEach((line, idx) => {
      const trimmed = line.trim();

      // Heading 3: ### Heading
      if (trimmed.startsWith('### ')) {
        flushList();
        elements.push(
          <h4
            key={idx}
            className="text-sm font-bold text-slate-900 mt-4 mb-2 pb-1 border-b border-slate-100 flex items-center"
          >
            {renderInlineText(trimmed.replace(/^###\s+/, ''), chunks)}
          </h4>
        );
        return;
      }

      // Heading 2: ## Heading
      if (trimmed.startsWith('## ')) {
        flushList();
        elements.push(
          <h3
            key={idx}
            className="text-base font-bold text-slate-900 mt-5 mb-2.5 pb-1 border-b border-slate-200 flex items-center"
          >
            {renderInlineText(trimmed.replace(/^##\s+/, ''), chunks)}
          </h3>
        );
        return;
      }

      // Bullet List Item: * Item or - Item
      if (trimmed.startsWith('* ') || trimmed.startsWith('- ')) {
        const itemText = trimmed.replace(/^[*|-]\s+/, '');
        currentList.push(
          <li key={idx} className="text-xs sm:text-sm text-slate-800 leading-relaxed">
            {renderInlineText(itemText, chunks)}
          </li>
        );
        return;
      }

      // Callout or Note
      if (trimmed.startsWith('*(Note:') || trimmed.startsWith('> ')) {
        flushList();
        elements.push(
          <div
            key={idx}
            className="my-3 p-3 bg-slate-50 border-l-4 border-indigo-400 text-xs text-slate-600 rounded-r-lg italic"
          >
            {renderInlineText(trimmed, chunks)}
          </div>
        );
        return;
      }

      // Standard Paragraph
      if (trimmed.length > 0) {
        flushList();
        elements.push(
          <p key={idx} className="text-xs sm:text-sm text-slate-800 leading-relaxed my-2">
            {renderInlineText(trimmed, chunks)}
          </p>
        );
      }
    });

    flushList();
    return elements;
  };

  return (
    <div className="space-y-3.5">
      {/* Compact Question Input Form */}
      <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 shadow-xs space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-1.5 text-indigo-700">
            <Sparkles className="w-3.5 h-3.5" />
            <h3 className="text-xs font-bold uppercase tracking-wider">
              Ask Project Research Assistant
            </h3>
          </div>
          <span className="text-[10px] font-semibold text-slate-500 bg-white border border-slate-200 px-2 py-0.5 rounded-full shadow-xs">
            Grounded RAG
          </span>
        </div>

        <form onSubmit={handleSubmit} className="space-y-2.5">
          <div className="relative">
            <textarea
              rows={2}
              required
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask an academic question grounded in this project's papers (e.g. 'What datasets, models, and empirical findings are reported?')..."
              className="w-full px-3.5 py-2 bg-white border border-slate-200 rounded-xl text-xs sm:text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none resize-none shadow-xs placeholder:text-slate-400"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            {/* Quick Suggestion Chips */}
            <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500">
              <span className="font-semibold text-slate-600 mr-0.5">Suggestions:</span>
              {project.research_question && (
                <button
                  type="button"
                  onClick={() => setQuestion(project.research_question || '')}
                  className="px-2 py-0.5 bg-white border border-slate-200 rounded-md hover:bg-slate-100 hover:text-slate-800 transition truncate max-w-[150px] shadow-xs"
                  title={project.research_question}
                >
                  Project Question
                </button>
              )}
              <button
                type="button"
                onClick={() => setQuestion('What empirical findings, metrics, and limitations are reported?')}
                className="px-2 py-0.5 bg-white border border-slate-200 rounded-md hover:bg-slate-100 hover:text-slate-800 transition shadow-xs"
              >
                Findings & Metrics
              </button>
              <button
                type="button"
                onClick={() => setQuestion('What datasets and machine learning algorithms were evaluated?')}
                className="px-2 py-0.5 bg-white border border-slate-200 rounded-md hover:bg-slate-100 hover:text-slate-800 transition shadow-xs"
              >
                Datasets & Models
              </button>
            </div>

            {/* Paper Selection, Depth & Submit */}
            <div className="flex items-center space-x-2 flex-wrap gap-y-1.5">
              {/* Scope Dropdown: Specific paper or all papers */}
              <div className="flex items-center space-x-1.5 bg-white border border-slate-200 rounded-md px-2 py-1 text-xs shadow-xs">
                <FileText className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                <select
                  value={selectedPaperId}
                  onChange={(e) => setSelectedPaperId(e.target.value === 'all' ? 'all' : Number(e.target.value))}
                  className="bg-transparent text-[11px] text-slate-700 font-medium focus:outline-none cursor-pointer max-w-[140px] sm:max-w-[200px] truncate"
                  title={
                    selectedPaperId === 'all'
                      ? 'Synthesizing from all curated papers in this project'
                      : `Restricted to: ${projectPapers.find((p) => p.paper_id === selectedPaperId)?.title || ''}`
                  }
                >
                  <option value="all">
                    All Papers {projectPapers.length > 0 ? `(${projectPapers.length})` : ''}
                  </option>
                  {projectPapers.map((paper) => (
                    <option key={paper.paper_id} value={paper.paper_id}>
                      {paper.title} {paper.year ? `(${paper.year})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              {/* Retrieval Depth */}
              <div className="flex items-center space-x-1 bg-white border border-slate-200 rounded-md p-0.5 text-xs shadow-xs">
                <span className="text-[10px] font-semibold text-slate-500 px-1">Depth:</span>
                {[3, 5, 8].map((depth) => (
                  <button
                    key={depth}
                    type="button"
                    onClick={() => setRetrievalDepth(depth)}
                    className={`px-1.5 py-0.5 rounded text-[10px] font-semibold transition ${
                      retrievalDepth === depth
                        ? 'bg-indigo-600 text-white shadow-xs'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {depth}
                  </button>
                ))}
              </div>

              <button
                type="submit"
                disabled={submitting || !question.trim()}
                className="inline-flex items-center px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs transition disabled:opacity-50 cursor-pointer"
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                    Synthesizing...
                  </>
                ) : (
                  <>
                    <Send className="w-3.5 h-3.5 mr-1.5" />
                    Ask Assistant
                  </>
                )}
              </button>
            </div>
          </div>
        </form>

        {error && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 flex items-center">
            <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0 text-rose-500" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Prominent Loading Card while generating answer (Point 1) */}
      {submitting && (
        <div className="bg-white border-2 border-indigo-200 rounded-xl p-6 shadow-sm space-y-4 animate-pulse">
          <div className="flex items-center space-x-3.5">
            <div className="w-9 h-9 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600 shadow-xs">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-slate-900">Synthesizing Grounded Answer...</h4>
              <p className="text-xs text-slate-500">
                Retrieving project literature and generating citation-backed findings
              </p>
            </div>
          </div>
          <div className="space-y-2 pt-2">
            <div className="h-3.5 bg-slate-100 rounded w-3/4"></div>
            <div className="h-3.5 bg-slate-100 rounded w-full"></div>
            <div className="h-3.5 bg-slate-100 rounded w-5/6"></div>
          </div>
        </div>
      )}

      {/* Lazy Column Feed of Research Questions (Points 2 & 3) */}
      <div className="space-y-3">
        {/* Feed Header with Expand/Collapse Controls */}
        <div className="flex justify-between items-center px-1">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Research Inquiries ({queries.length})
          </h4>

          {queries.length > 0 && (
            <div className="flex items-center space-x-2 text-xs">
              <button
                type="button"
                onClick={handleExpandAll}
                className="text-xs font-medium text-slate-500 hover:text-indigo-600 transition"
              >
                Expand All
              </button>
              <span className="text-slate-300">•</span>
              <button
                type="button"
                onClick={handleCollapseAll}
                className="text-xs font-medium text-slate-500 hover:text-indigo-600 transition"
              >
                Minimize All
              </button>
            </div>
          )}
        </div>

        {loadingHistory ? (
          <div className="text-center py-12 text-slate-400 space-y-2">
            <Loader2 className="w-6 h-6 animate-spin mx-auto text-indigo-500" />
            <p className="text-xs">Loading research Q&A history...</p>
          </div>
        ) : queries.length === 0 ? (
          <div className="border border-dashed border-slate-200 rounded-xl p-10 text-center text-slate-400 text-sm space-y-2 bg-white">
            <MessageSquare className="w-10 h-10 text-slate-300 mx-auto" />
            <p className="font-semibold text-slate-700">No questions asked yet in this project.</p>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              Type an inquiry above or select a suggestion chip to retrieve evidence and synthesize grounded answers with page citations.
            </p>
          </div>
        ) : (
          /* Lazy Column Container */
          <div className="max-h-[calc(100vh-320px)] overflow-y-auto space-y-3 pr-1">
            {queries.map((q) => {
              const isExpanded = expandedQueryIds.includes(q.id);

              return (
                <div
                  key={q.id}
                  className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs hover:border-slate-300 transition"
                >
                  {/* Minimized Header: Question Only (Point 3) */}
                  <div
                    onClick={() => toggleExpandQuery(q.id)}
                    className="p-4 bg-slate-50/70 hover:bg-slate-100/70 flex justify-between items-center gap-3 cursor-pointer transition select-none"
                  >
                    <div className="flex items-center space-x-3 flex-1 min-w-0">
                      <div className="text-slate-400 hover:text-slate-600 p-0.5 flex-shrink-0">
                        {isExpanded ? (
                          <ChevronDown className="w-4 h-4 text-indigo-600" />
                        ) : (
                          <ChevronRight className="w-4 h-4" />
                        )}
                      </div>
                      <div className="min-w-0 flex-1 flex items-center space-x-2">
                        <h4 className="text-sm font-semibold text-slate-900 truncate" title={q.question}>
                          {q.question}
                        </h4>
                        {(() => {
                          const distinctPapers = Array.from(new Set(q.retrieved_chunks.map((c) => c.paper_title)));
                          if (distinctPapers.length === 1) {
                            return (
                              <span
                                className="text-[10px] font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200 px-1.5 py-0.5 rounded-md truncate max-w-[140px] sm:max-w-[200px] flex-shrink-0"
                                title={`Answer grounded in: ${distinctPapers[0]}`}
                              >
                                {distinctPapers[0]}
                              </span>
                            );
                          }
                          return null;
                        })()}
                      </div>
                    </div>

                    {/* Right Meta and Actions */}
                    <div className="flex items-center space-x-2 text-slate-400 text-xs flex-shrink-0">
                      <div className="hidden sm:flex items-center space-x-1 text-[11px] text-slate-400 mr-1">
                        <Clock className="w-3.5 h-3.5" />
                        <span>{new Date(q.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </div>

                      {/* Copy Answer Button */}
                      <button
                        type="button"
                        onClick={(e) => handleCopyAnswer(e, q.id, q.answer)}
                        className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-200/80 rounded-md transition"
                        title="Copy Answer Markdown to Clipboard"
                      >
                        {copiedQueryId === q.id ? (
                          <Check className="w-3.5 h-3.5 text-emerald-600" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>

                      {/* Export Markdown Button */}
                      <button
                        type="button"
                        onClick={(e) => handleExportMarkdown(e, q)}
                        className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-200/80 rounded-md transition"
                        title="Download as Markdown note"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </button>

                      {/* Delete Query Button */}
                      <button
                        type="button"
                        onClick={(e) => handleDeleteQuery(e, q.id)}
                        className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition"
                        title="Delete from project history"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Expanded Body: Synthesized Answer & Citations (Points 2 & 3) */}
                  {isExpanded && (
                    <div className="p-5 border-t border-slate-100 bg-white space-y-4">
                      {/* Rich Formatted Answer */}
                      <div className="prose prose-sm max-w-none">
                        {renderAcademicAnswer(q.answer, q.retrieved_chunks)}
                      </div>

                      {/* Citations Row */}
                      {q.citations && q.citations.length > 0 && (
                        <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center gap-1.5">
                          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center mr-1">
                            <FileText className="w-3 h-3 mr-1 text-slate-400" />
                            Cited Sources:
                          </span>
                          {q.citations.map((cite, idx) => (
                            <button
                              key={idx}
                              onClick={() => handleCitationClick(cite, q.retrieved_chunks)}
                              className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 transition cursor-pointer"
                              title="Click to jump directly to cited page in PDF"
                            >
                              <BookOpen className="w-3 h-3 mr-1 text-indigo-500" />
                              {cite}
                            </button>
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
      </div>

      <ConfirmModal
        isOpen={queryToDelete !== null}
        title="Delete Question from History"
        message="Are you sure you want to delete this question and its grounded synthesis answer from project history?"
        confirmText="Delete"
        danger={true}
        onConfirm={handleConfirmDeleteQuery}
        onCancel={() => setQueryToDelete(null)}
      />
    </div>
  );
};
