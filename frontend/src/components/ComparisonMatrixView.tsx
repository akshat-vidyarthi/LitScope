import React, { useState, useEffect } from 'react';
import {
  Table,
  Sparkles,
  Download,
  Edit2,
  Check,
  X,
  FileText,
  Loader2,
  Search,
  RefreshCw,
  AlertCircle,
  BookOpen,
} from 'lucide-react';
import {
  api,
  Project,
  MatrixEvidenceRow,
} from '../api/client';
import { toast } from './Toast';

interface ComparisonMatrixViewProps {
  project: Project;
  onOpenPaperReader: (paperId: number, pageNumber?: number) => void;
  canEdit: boolean;
}

type MatrixColumnKey = 'objective' | 'methodology' | 'datasets' | 'findings' | 'limitations';

export const ComparisonMatrixView: React.FC<ComparisonMatrixViewProps> = ({
  project,
  onOpenPaperReader,
  canEdit,
}) => {
  const [rows, setRows] = useState<MatrixEvidenceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Inline editing state
  const [editingCell, setEditingCell] = useState<{ paperId: number; column: MatrixColumnKey } | null>(null);
  const [editValue, setEditValue] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);

  const loadMatrix = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getProjectMatrix(project.id);
      setRows(data.rows);
    } catch (err: any) {
      setError(err.message || 'Failed to load comparison matrix');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMatrix();
  }, [project.id]);

  const handleExtract = async (force: boolean = false) => {
    setExtracting(true);
    setError(null);
    try {
      const data = await api.extractMatrixEvidence(project.id, undefined, force);
      setRows(data.rows);
    } catch (err: any) {
      setError(err.message || 'Evidence extraction failed');
    } finally {
      setExtracting(false);
    }
  };

  const handleExtractSingle = async (paperId: number) => {
    setExtracting(true);
    setError(null);
    try {
      const data = await api.extractMatrixEvidence(project.id, [paperId], true);
      setRows(data.rows);
    } catch (err: any) {
      setError(err.message || 'Single paper extraction failed');
    } finally {
      setExtracting(false);
    }
  };

  const handleExportCsv = async () => {
    setExporting(true);
    try {
      await api.exportMatrixCsv(project.id);
    } catch (err: any) {
      toast.error(err.message || 'Failed to export CSV');
    } finally {
      setExporting(false);
    }
  };

  const startEditCell = (paperId: number, column: MatrixColumnKey, currentValue?: string) => {
    if (!canEdit) return;
    setEditingCell({ paperId, column });
    setEditValue(currentValue || '');
  };

  const saveEditCell = async () => {
    if (!editingCell) return;
    setSavingEdit(true);
    try {
      const updatedRow = await api.updateMatrixCell(project.id, editingCell.paperId, {
        [editingCell.column]: editValue,
      });
      setRows((prev) =>
        prev.map((r) => (r.paper_id === editingCell.paperId ? updatedRow : r))
      );
      toast.success('Matrix evidence updated');
      setEditingCell(null);
    } catch (err: any) {
      toast.error(err.message || 'Failed to update cell');
    } finally {
      setSavingEdit(false);
    }
  };

  const filteredRows = rows.filter((r) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      r.title.toLowerCase().includes(term) ||
      (r.authors && r.authors.toLowerCase().includes(term)) ||
      (r.methodology && r.methodology.toLowerCase().includes(term)) ||
      (r.datasets && r.datasets.toLowerCase().includes(term)) ||
      (r.findings && r.findings.toLowerCase().includes(term))
    );
  });

  const extractedCount = rows.filter((r) => r.status === 'completed').length;

  if (loading) {
    return (
      <div className="p-12 text-center text-slate-500 text-sm flex flex-col items-center justify-center space-y-3">
        <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
        <p>Loading study comparison matrix...</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top Toolbar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center space-x-2">
            <h3 className="font-bold text-slate-900 text-base flex items-center">
              <Table className="w-4 h-4 mr-2 text-indigo-600" />
              Cross-Paper Comparison Matrix
            </h3>
            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
              {extractedCount} / {rows.length} Extracted
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Structured comparative synthesis across methodology, datasets, results & analysis, and conclusions.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Search within matrix */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Filter matrix..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-8 pr-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-indigo-500 w-44"
            />
          </div>

          {/* Export CSV Button */}
          <button
            onClick={handleExportCsv}
            disabled={exporting || rows.length === 0}
            className="inline-flex items-center px-3 py-1.5 bg-slate-100 hover:bg-slate-200 disabled:opacity-50 text-slate-700 text-xs font-semibold rounded-lg border border-slate-200 transition cursor-pointer"
            title="Export comparative matrix as CSV spreadsheet"
          >
            {exporting ? (
              <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
            ) : (
              <Download className="w-3.5 h-3.5 mr-1.5 text-slate-500" />
            )}
            Export CSV
          </button>

          {/* Extract Matrix Button */}
          {canEdit && (
            <button
              onClick={() => handleExtract(false)}
              disabled={extracting || rows.length === 0}
              className="inline-flex items-center px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white text-xs font-semibold rounded-lg shadow-xs transition cursor-pointer"
            >
              {extracting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  Extracting Evidence...
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                  Extract Matrix
                </>
              )}
            </button>
          )}

          {canEdit && extractedCount > 0 && (
            <button
              onClick={() => handleExtract(true)}
              disabled={extracting}
              className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition"
              title="Re-extract all papers"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs flex items-center">
          <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Empty States */}
      {rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-xs">
          <BookOpen className="w-10 h-10 text-slate-300 mx-auto mb-2" />
          <h4 className="font-semibold text-slate-800 text-sm">No curated papers in this study</h4>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
            Add papers from the Master Library or Discover Literature tab to populate your comparison matrix.
          </p>
        </div>
      ) : filteredRows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-500 text-xs">
          No papers match your filter "{searchTerm}".
        </div>
      ) : (
        /* Matrix Grid Table Container */
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="overflow-x-auto max-h-[calc(100vh-310px)] overflow-y-auto">
            <table className="min-w-[1200px] w-full text-left text-xs border-collapse">
              <thead className="bg-slate-100/90 sticky top-0 z-10 border-b border-slate-200 text-slate-700 font-bold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="p-3.5 w-64 min-w-[240px] border-r border-slate-200">Paper & Metadata</th>
                  <th className="p-3.5 w-72 min-w-[260px] border-r border-slate-200">Research Objective</th>
                  <th className="p-3.5 w-72 min-w-[260px] border-r border-slate-200">Methodology & Architecture</th>
                  <th className="p-3.5 w-64 min-w-[220px] border-r border-slate-200">Datasets & Benchmarks</th>
                  <th className="p-3.5 w-72 min-w-[260px] border-r border-slate-200">Result & Analysis</th>
                  <th className="p-3.5 w-64 min-w-[220px]">Conclusion</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {filteredRows.map((row) => {
                  const isPending = row.status !== 'completed';

                  return (
                    <tr key={row.paper_id} className="hover:bg-slate-50/60 transition group">
                      {/* Column 1: Paper & Metadata */}
                      <td className="p-3.5 align-top border-r border-slate-200 bg-slate-50/30">
                        <div className="space-y-1.5">
                          <h4 className="font-bold text-slate-900 leading-snug line-clamp-2" title={row.title}>
                            {row.title}
                          </h4>
                          <p className="text-[11px] text-slate-500 line-clamp-1">
                            {row.authors || 'Unknown'} {row.year ? `(${row.year})` : ''}
                          </p>
                          {row.venue && (
                            <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-200 text-slate-700 max-w-[200px] truncate">
                              {row.venue}
                            </span>
                          )}

                          <div className="pt-1 flex items-center space-x-2">
                            {row.has_pdf && (
                              <button
                                type="button"
                                onClick={() => onOpenPaperReader(row.paper_id, 1)}
                                className="inline-flex items-center text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 transition cursor-pointer"
                              >
                                <FileText className="w-3.5 h-3.5 mr-1" />
                                Read PDF
                              </button>
                            )}

                            {isPending && canEdit && (
                              <button
                                type="button"
                                onClick={() => handleExtractSingle(row.paper_id)}
                                disabled={extracting}
                                className="inline-flex items-center text-[10px] px-2 py-0.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded border border-indigo-200 font-medium transition cursor-pointer"
                              >
                                <Sparkles className="w-3 h-3 mr-1" />
                                Extract
                              </button>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Render Matrix Dimension Cells */}
                      {(['objective', 'methodology', 'datasets', 'findings', 'limitations'] as MatrixColumnKey[]).map((col, idx) => {
                        const cellText = row[col];
                        const prov = row.provenance?.[col];
                        const isEditingThis = editingCell?.paperId === row.paper_id && editingCell?.column === col;

                        return (
                          <td
                            key={col}
                            className={`p-3.5 align-top leading-relaxed text-slate-700 relative ${
                              idx < 4 ? 'border-r border-slate-200' : ''
                            }`}
                          >
                            {isEditingThis ? (
                              <div className="space-y-2">
                                <textarea
                                  value={editValue}
                                  onChange={(e) => setEditValue(e.target.value)}
                                  rows={4}
                                  className="w-full p-2 text-xs bg-white border border-indigo-400 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
                                />
                                <div className="flex items-center space-x-1.5 justify-end">
                                  <button
                                    onClick={() => setEditingCell(null)}
                                    disabled={savingEdit}
                                    className="p-1 text-slate-400 hover:text-slate-600 rounded"
                                  >
                                    <X className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    onClick={saveEditCell}
                                    disabled={savingEdit}
                                    className="px-2 py-0.5 bg-indigo-600 text-white rounded text-[11px] font-semibold flex items-center"
                                  >
                                    {savingEdit ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Check className="w-3 h-3 mr-1" />}
                                    Save
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <div className="space-y-1.5">
                                {isPending ? (
                                  <span className="text-slate-400 italic text-[11px]">
                                    Not extracted yet
                                  </span>
                                ) : (
                                  <>
                                    <p className="whitespace-pre-wrap">{cellText || 'Not specified'}</p>
                                    <div className="flex flex-wrap items-center gap-1.5 pt-1">
                                      {/* Clickable Citation Pill */}
                                      {prov?.page && (
                                        <button
                                          type="button"
                                          onClick={() => onOpenPaperReader(row.paper_id, prov.page)}
                                          className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition cursor-pointer"
                                          title={`Jump directly to Page ${prov.page} in PDF reader`}
                                        >
                                          p. {prov.page}
                                        </button>
                                      )}

                                      {/* Manual Edit Indicator */}
                                      {row.is_custom_edited && (
                                        <span className="text-[10px] px-1 py-0.2 rounded bg-amber-50 text-amber-700 border border-amber-200">
                                          Edited
                                        </span>
                                      )}

                                      {/* Hover Edit Pencil */}
                                      {canEdit && (
                                        <button
                                          onClick={() => startEditCell(row.paper_id, col, cellText)}
                                          className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-indigo-600 transition ml-auto"
                                          title="Edit cell"
                                        >
                                          <Edit2 className="w-3 h-3" />
                                        </button>
                                      )}
                                    </div>
                                  </>
                                )}
                              </div>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
