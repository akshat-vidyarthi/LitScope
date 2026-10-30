import React, { useState, useEffect } from 'react';
import { Paper, api } from '../api/client';
import {
  X,
  FileText,
  Loader2,
  AlertTriangle,
} from 'lucide-react';

interface PaperReaderModalProps {
  paper: Paper;
  onClose: () => void;
  onPaperUpdated?: () => void;
}

export const PaperReaderModal: React.FC<PaperReaderModalProps> = ({
  paper,
  onClose,
}) => {
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let activeUrl: string | null = null;

    const loadPdfStream = async () => {
      setLoading(true);
      setError(null);
      try {
        const blob = await api.downloadPaperPdfBlob(paper.id);
        const url = window.URL.createObjectURL(blob);
        activeUrl = url;
        setPdfBlobUrl(url);
      } catch (err: any) {
        setError(err.message || 'Failed to load PDF preview in window');
      } finally {
        setLoading(false);
      }
    };

    loadPdfStream();

    return () => {
      if (activeUrl) {
        window.URL.revokeObjectURL(activeUrl);
      }
    };
  }, [paper.id]);

  const version = paper.latest_version;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-2 sm:p-4 overflow-hidden">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-6xl h-[94vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Top Header Bar */}
        <div className="flex items-center justify-between px-6 py-3.5 border-b border-slate-800 bg-slate-900">
          <div className="flex-1 min-w-0 pr-4">
            <div className="flex items-center space-x-3 mb-1">
              <span className="inline-flex items-center text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                <FileText className="w-3 h-3 mr-1" />
                PDF Document Viewer
              </span>

              {version?.page_count ? (
                <span className="text-xs font-medium text-slate-400">
                  {version.page_count} Pages
                </span>
              ) : null}
            </div>

            <h2 className="text-base font-bold text-slate-100 truncate" title={paper.title}>
              {paper.title}
            </h2>
            <p className="text-xs text-slate-400 truncate">
              {paper.authors ? `${paper.authors}` : ''}
              {paper.authors && paper.year ? ' • ' : ''}
              {paper.year ? `${paper.year}` : ''}
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded-lg transition"
              title="Close Viewer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Main PDF Viewer Frame */}
        <div className="flex-1 bg-slate-950 relative overflow-hidden">
          {loading && (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
              <p className="text-sm font-medium">Opening PDF in viewer...</p>
            </div>
          )}

          {error && !loading && (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 space-y-3 p-6 text-center">
              <AlertTriangle className="w-10 h-10 text-rose-400" />
              <p className="text-sm text-rose-300 font-semibold">{error}</p>
              <p className="text-xs text-slate-500 max-w-sm">
                Unable to display the PDF directly in window. The file may be missing or inaccessible.
              </p>
              <button
                onClick={onClose}
                className="px-4 py-2 text-xs bg-slate-800 text-slate-200 rounded-lg hover:bg-slate-700"
              >
                Close
              </button>
            </div>
          )}

          {!loading && !error && pdfBlobUrl && (
            <iframe
              src={`${pdfBlobUrl}#toolbar=1&navpanes=1`}
              title={paper.title}
              className="w-full h-full border-0 bg-slate-950"
            />
          )}
        </div>
      </div>
    </div>
  );
};
