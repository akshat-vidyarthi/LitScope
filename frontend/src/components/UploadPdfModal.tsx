import React, { useState, useRef } from 'react';
import { api, Project, PaperUploadResponse } from '../api/client';
import {
  X,
  Upload,
  FileText,
  CheckCircle,
  AlertCircle,
  Loader2,
  Copy,
} from 'lucide-react';

interface UploadPdfModalProps {
  onClose: () => void;
  onSuccess: (result: PaperUploadResponse) => void;
  projects?: Project[];
  defaultProjectId?: number;
}

export const UploadPdfModal: React.FC<UploadPdfModalProps> = ({
  onClose,
  onSuccess,
  projects = [],
  defaultProjectId,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [title, setTitle] = useState<string>('');
  const [authors, setAuthors] = useState<string>('');
  const [year, setYear] = useState<string>('');
  const [projectId, setProjectId] = useState<number | undefined>(defaultProjectId);
  const [uploading, setUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<PaperUploadResponse | null>(null);
  const [errorResult, setErrorResult] = useState<{ title: string; message: string } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF documents are supported (.pdf).');
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setError('File size exceeds the 50 MB limit.');
      return;
    }
    setError(null);
    setSelectedFile(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setError('Please select a PDF file to upload.');
      return;
    }

    setUploading(true);
    setError(null);
    setErrorResult(null);

    const formData = new FormData();
    formData.append('file', selectedFile);
    if (title.trim()) formData.append('title', title.trim());
    if (authors.trim()) formData.append('authors', authors.trim());
    if (year.trim()) formData.append('year', year.trim());
    if (projectId) formData.append('project_id', projectId.toString());

    try {
      const result = await api.uploadPdf(formData);
      setUploadResult(result);
      onSuccess(result);
    } catch (err: any) {
      const msg = err.message || 'Failed to upload PDF';
      const isScanned = msg.toLowerCase().includes('scanned') || msg.toLowerCase().includes('image') || msg.toLowerCase().includes('selectable');
      setErrorResult({
        title: isScanned ? 'Unsupported Document Type' : 'Upload Error',
        message: msg,
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/90">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-indigo-500/10 text-indigo-400 rounded-lg border border-indigo-500/20">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100">Upload Research PDF</h2>
              <p className="text-xs text-slate-400">Add academic paper to your research library</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded-lg transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {errorResult ? (
          /* Error Pop-up View (Scanned PDF or format error) */
          <div className="p-6 space-y-4">
            <div className="p-4 rounded-xl border flex items-start space-x-3 bg-rose-500/10 border-rose-500/20 text-rose-300">
              <AlertCircle className="w-5 h-5 mt-0.5 flex-shrink-0 text-rose-400" />
              <div className="text-xs space-y-1">
                <p className="font-semibold text-sm text-rose-200">
                  {errorResult.title}
                </p>
                <p className="leading-relaxed">
                  {errorResult.message}
                </p>
              </div>
            </div>

            <div className="flex justify-end space-x-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setErrorResult(null);
                  setSelectedFile(null);
                }}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition"
              >
                Try Another PDF
              </button>
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition"
              >
                Close
              </button>
            </div>
          </div>
        ) : uploadResult ? (
          /* Result View */
          <div className="p-6 space-y-4">
            <div
              className={`p-4 rounded-xl border flex items-start space-x-3 ${
                uploadResult.is_duplicate
                  ? 'bg-amber-500/10 border-amber-500/20 text-amber-300'
                  : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
              }`}
            >
              {uploadResult.is_duplicate ? (
                <Copy className="w-5 h-5 mt-0.5 flex-shrink-0 text-amber-400" />
              ) : (
                <CheckCircle className="w-5 h-5 mt-0.5 flex-shrink-0 text-emerald-400" />
              )}
              <div className="text-xs space-y-1">
                <p className="font-semibold text-sm">
                  {uploadResult.is_duplicate ? (projectId ? 'Paper Added to Project' : 'Already in Library') : 'Extraction Successful'}
                </p>
                <p>
                  {uploadResult.is_duplicate
                    ? (uploadResult.message || (projectId ? 'This paper was already in your Master Library and has now been added to your project.' : 'This paper is already in your library.'))
                    : `Extraction successful • ${uploadResult.pages_extracted} pages extracted.`}
                </p>
              </div>
            </div>

            <div className="flex justify-end space-x-3 pt-2">
              <button
                onClick={onClose}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition"
              >
                {projectId ? 'Close & View Project' : 'Close & View Library'}
              </button>
            </div>
          </div>
        ) : (
          /* Form View */
          <form onSubmit={handleSubmit} className="p-6 space-y-5">
            {error && (
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center">
                <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0 text-rose-400" />
                <span>{error}</span>
              </div>
            )}

            {/* Drag and Drop Zone */}
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition ${
                isDragging
                  ? 'border-indigo-500 bg-indigo-500/10'
                  : selectedFile
                  ? 'border-emerald-500/40 bg-emerald-500/5'
                  : 'border-slate-700 hover:border-slate-600 bg-slate-950/50'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                onChange={handleFileChange}
                className="hidden"
              />

              {selectedFile ? (
                <div className="flex items-center justify-center space-x-3 text-slate-200">
                  <FileText className="w-8 h-8 text-emerald-400" />
                  <div className="text-left">
                    <p className="text-sm font-semibold truncate max-w-xs">{selectedFile.name}</p>
                    <p className="text-xs text-slate-400">
                      {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                    </p>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <Upload className="w-8 h-8 mx-auto text-slate-500" />
                  <p className="text-sm text-slate-300">
                    <span className="font-semibold text-indigo-400">Click to browse</span> or drag and drop PDF here
                  </p>
                  <p className="text-xs text-slate-500">PDF papers up to 50 MB</p>
                </div>
              )}
            </div>

            {/* Metadata Fields */}
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Paper Title
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Auto-extracted from PDF if left blank"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Authors
                  </label>
                  <input
                    type="text"
                    value={authors}
                    onChange={(e) => setAuthors(e.target.value)}
                    placeholder="Auto-extracted if left blank"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Year
                  </label>
                  <input
                    type="number"
                    value={year}
                    onChange={(e) => setYear(e.target.value)}
                    placeholder="Auto-extracted if left blank"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </div>
              </div>

              {/* Destination Dropdown */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Add to
                </label>
                <select
                  value={projectId || ''}
                  onChange={(e) => setProjectId(e.target.value ? Number(e.target.value) : undefined)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="">Master Library</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-800">
              <button
                type="button"
                onClick={onClose}
                disabled={uploading}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={uploading || !selectedFile}
                className="inline-flex items-center px-5 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-50 transition"
              >
                {uploading ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload className="w-3.5 h-3.5 mr-1.5" />
                    Upload
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
