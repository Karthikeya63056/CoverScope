import React, { useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  Upload,
  FileText,
  Trash2,
  Lock,
  ExternalLink,
  MessageSquare,
  AlertCircle,
  CheckCircle2,
  Clock,
  Layers,
  Search,
  ClipboardCheck,
  Download,
} from 'lucide-react';
import { api } from '../lib/api-client';
import type { PolicySummary } from '../lib/types';

export const DocumentLibraryPage: React.FC = () => {
  const [policies, setPolicies] = useState<PolicySummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchPolicies = async () => {
    try {
      setIsLoading(true);
      const res = await api.listPolicies();
      setPolicies(res.policies || []);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to fetch policy documents.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchPolicies();
  }, []);

  const handleFileUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setErrorMsg('Only PDF documents are supported (.pdf).');
      return;
    }

    if (file.size > 20_000_000) {
      setErrorMsg('File exceeds the 20 MB limit. Please upload a smaller document.');
      return;
    }

    setIsUploading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const summary = await api.uploadPolicy(file);
      setSuccessMsg(`Successfully uploaded and processed "${summary.filename}" (${summary.page_count} pages).`);
      await fetchPolicies();
    } catch (err: any) {
      setErrorMsg(err.message || 'Document processing failed.');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDeletePolicy = async (id: string, name: string) => {
    if (
      !window.confirm(
        `Permanently delete policy "${name}" from your MongoDB database and GridFS storage?\n\nThis will permanently purge the raw document, indexed chunks, and analysis history. This action cannot be undone.`
      )
    ) {
      return;
    }
    try {
      await api.deletePolicy(id);
      setSuccessMsg(`Policy "${name}" permanently deleted from database and storage.`);
      setPolicies(policies.filter((p) => (p.policy_id || p.id) !== id && p.id !== id));
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to delete policy.');
    }
  };

  const handleDownloadPolicy = async (id: string, name: string) => {
    try {
      const blob = await api.downloadPolicy(id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = name.endsWith('.pdf') ? name : `${name}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to download policy PDF.');
    }
  };

  const filtered = (policies || []).filter((p) => {
    const name = (p.filename || p.document_name || '').toLowerCase();
    const id = (p.policy_id || p.id || '').toLowerCase();
    const query = (searchTerm || '').toLowerCase();
    return name.includes(query) || id.includes(query);
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Document Library</h1>
        <p className="text-sm text-slate-500 mt-1">
          Upload and manage your health insurance policy schedules, master terms, and endorsement riders.
        </p>
      </div>

      {/* Notifications */}
      {errorMsg && (
        <div className="flex items-start gap-2.5 rounded-lg border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      {successMsg && (
        <div className="flex items-start gap-2.5 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-xs text-emerald-800">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 mt-0.5" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Upload Dropzone */}
      <div
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (e.dataTransfer.files?.[0]) {
            handleFileUpload(e.dataTransfer.files[0]);
          }
        }}
        className={`group relative flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 text-center transition ${
          isUploading
            ? 'border-emerald-400 bg-emerald-50/50 pointer-events-none'
            : 'border-slate-300 bg-white hover:border-emerald-500 hover:bg-slate-50/50'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.[0]) {
              handleFileUpload(e.target.files[0]);
            }
          }}
        />

        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-50 text-emerald-600 group-hover:scale-110 transition">
          {isUploading ? (
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-emerald-600 border-t-transparent" />
          ) : (
            <Upload className="h-6 w-6" />
          )}
        </div>

        <p className="mt-3 text-sm font-semibold text-slate-800">
          {isUploading ? 'Extracting text and indexing chunks...' : 'Click to upload or drag & drop PDF'}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          Supports official Health Insurance Policy Schedules (PDF, max 20MB)
        </p>
      </div>

      {/* Policy Search & Table */}
      <div className="rounded-xl border border-slate-200/80 bg-white shadow-xs">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 border-b border-slate-100 p-4">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-900">All Policy Documents</span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 font-medium">
              {policies.length}
            </span>
          </div>

          <div className="relative w-full sm:w-64">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search policies..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 py-1.5 pl-8 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-emerald-500 focus:bg-white focus:outline-none"
            />
          </div>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-xs text-slate-500">
            <div className="mx-auto h-5 w-5 animate-spin rounded-full border-2 border-emerald-600 border-t-transparent mb-2" />
            Loading policies from MongoDB Atlas...
          </div>
        ) : filtered.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50/80 text-slate-600 border-b border-slate-100">
                <tr>
                  <th className="py-3 px-4 font-semibold">Document</th>
                  <th className="py-3 px-4 font-semibold">Pages</th>
                  <th className="py-3 px-4 font-semibold">Indexed Chunks</th>
                  <th className="py-3 px-4 font-semibold">Characters</th>
                  <th className="py-3 px-4 font-semibold">Status</th>
                  <th className="py-3 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filtered.map((p) => {
                  const name = p.filename || p.document_name || 'Policy Document';
                  const id = p.policy_id || p.id || '';
                  const pages = p.page_count ?? 1;
                  const chunks = p.total_chunks ?? p.metadata?.chunk_count ?? 0;
                  const chars = p.total_characters ?? p.metadata?.char_count ?? 0;
                  const status = p.status || p.processing_status || 'processed';
                  const isBundled = (status === 'bundled' || p.status === 'bundled');
                  return (
                    <tr key={id || name} className="hover:bg-slate-50/50">
                      <td className="py-3.5 px-4 font-medium text-slate-900">
                        <div className="flex items-center gap-2.5">
                          <div className={`rounded-md p-1.5 ${isBundled ? 'bg-blue-50 text-blue-600' : 'bg-emerald-50 text-emerald-600'}`}>
                            <FileText className="h-4 w-4" />
                          </div>
                          <div>
                            <p className="truncate max-w-xs font-semibold">{name}</p>
                            <p className="text-[10px] text-slate-400 font-mono truncate max-w-xs">
                              ID: {id ? id.slice(0, 16) + '...' : 'Loaded'}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="py-3.5 px-4">{pages} pages</td>
                      <td className="py-3.5 px-4">{chunks} chunks</td>
                      <td className="py-3.5 px-4">{chars.toLocaleString()}</td>
                      <td className="py-3.5 px-4">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium capitalize ${
                          isBundled ? 'bg-blue-50 text-blue-700' : 'bg-emerald-50 text-emerald-700'
                        }`}>
                          {isBundled ? 'Demo Policy' : status}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleDownloadPolicy(id, name)}
                            title="Download original PDF document"
                            className="rounded p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition"
                          >
                            <Download className="h-3.5 w-3.5 text-slate-600" />
                          </button>
                          <Link
                            to={`/claim-rehearsal?policy=${id}`}
                            title="Rehearse a claim against this policy"
                            className="rounded p-1 text-slate-500 hover:bg-emerald-50 hover:text-emerald-700"
                          >
                            <ClipboardCheck className="h-3.5 w-3.5 text-emerald-600" />
                          </Link>
                          <Link
                            to={`/ask?policy=${id}`}
                            title="Ask questions about this policy"
                            className="rounded p-1 text-slate-500 hover:bg-emerald-50 hover:text-emerald-700"
                          >
                            <MessageSquare className="h-3.5 w-3.5" />
                          </Link>
                          <Link
                            to={`/explorer?policy=${id}`}
                            title="Explore policy pages and extracted facts"
                            className="rounded p-1 text-slate-500 hover:bg-blue-50 hover:text-blue-700"
                          >
                            <Layers className="h-3.5 w-3.5" />
                          </Link>
                          {isBundled ? (
                            <span
                              title="Bundled demonstration policy is read-only"
                              className="inline-flex items-center rounded p-1 text-slate-300 cursor-not-allowed"
                            >
                              <Lock className="h-3.5 w-3.5" />
                            </span>
                          ) : (
                            <button
                              onClick={() => handleDeletePolicy(id, name)}
                              title="Permanently delete from database and storage"
                              className="rounded p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600 transition"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center text-xs text-slate-500">
            No policies found matching your search.
          </div>
        )}
      </div>
    </div>
  );
};
