import React, { useState, useEffect, useRef, useTransition } from 'react';
import {
  FileUp,
  Languages,
  Loader2,
  AlertCircle,
  FileText,
  CheckCircle2,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import { PdfViewerBox } from './components/PdfViewerBox.tsx';
import {
  EnginePicker,
  OllamaStatusNotice,
  RemoteEngineNotice,
} from './components/EnginePicker.tsx';
import { TranslationWarningBanner } from './components/TranslationWarningBanner.tsx';
import {
  createTranslationJob,
  cancelTranslationJob,
  fetchEngines,
  fetchJobStatus,
  fetchJobResultBlob,
  checkHealth,
  POLL_INTERVAL_MS,
  type EnginesResponse,
  type JobProgress,
  type JobStatusResponse,
} from './services/api.ts';

// How often to re-ask Ollama while it is not ready, so starting it or
// finishing `ollama pull` shows up without a click.
const ENGINE_RECHECK_MS = 10000;

const TARGET_LANGUAGES = [
  { code: 'vi', name: 'Tiếng Việt (vi)' },
  { code: 'en', name: 'English (en)' },
  { code: 'fr', name: 'Français (fr)' },
  { code: 'de', name: 'Deutsch (de)' },
  { code: 'es', name: 'Español (es)' },
  { code: 'it', name: 'Italiano (it)' },
  { code: 'pt', name: 'Português (pt)' },
  { code: 'nl', name: 'Nederlands (nl)' },
  { code: 'pl', name: 'Polski (pl)' },
  { code: 'tr', name: 'Türkçe (tr)' },
  { code: 'id', name: 'Bahasa Indonesia (id)' },
  { code: 'ms', name: 'Bahasa Melayu (ms)' },
  { code: 'af', name: 'Afrikaans (af)' },
  { code: 'ca', name: 'Català (ca)' },
  { code: 'cs', name: 'Čeština (cs)' },
  { code: 'cy', name: 'Cymraeg (cy)' },
  { code: 'da', name: 'Dansk (da)' },
  { code: 'et', name: 'Eesti (et)' },
  { code: 'eu', name: 'Euskara (eu)' },
  { code: 'fi', name: 'Suomi (fi)' },
  { code: 'ga', name: 'Gaeilge (ga)' },
  { code: 'gl', name: 'Galego (gl)' },
  { code: 'hr', name: 'Hrvatski (hr)' },
  { code: 'hu', name: 'Magyar (hu)' },
  { code: 'is', name: 'Íslenska (is)' },
  { code: 'lt', name: 'Lietuvių (lt)' },
  { code: 'lv', name: 'Latviešu (lv)' },
  { code: 'mt', name: 'Malti (mt)' },
  { code: 'no', name: 'Norsk (no)' },
  { code: 'ro', name: 'Română (ro)' },
  { code: 'sk', name: 'Slovenčina (sk)' },
  { code: 'sl', name: 'Slovenščina (sl)' },
  { code: 'sq', name: 'Shqip (sq)' },
  { code: 'sv', name: 'Svenska (sv)' },
  { code: 'sw', name: 'Kiswahili (sw)' },
  { code: 'tl', name: 'Tagalog (tl)' },
];

// Mirrors pdf2zh.translator.SUPPORTED_DOMAINS (see docs/implementation-plan-2026-09-10.md
// Phase C v2). An empty value means "no domain selected" - the backend
// treats that the same as omitting the field.
const DOMAINS = [
  { code: '', name: 'Không chọn' },
  { code: 'natural_sciences', name: 'Khoa học tự nhiên (Vật lý/Toán/Hóa)' },
  { code: 'technology', name: 'Kỹ thuật/Công nghệ (CNTT/AI/Kỹ thuật)' },
  { code: 'medicine', name: 'Y khoa/Sinh học' },
];

export const App: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [targetLanguage, setTargetLanguage] = useState<string>('vi');
  const [domain, setDomain] = useState<string>('');
  const [backendReady, setBackendReady] = useState<boolean>(false);
  const [isTranslating, setIsTranslating] = useState<boolean>(false);
  const [progress, setProgress] = useState<JobProgress>({ done: 0, total: 0 });
  const [errorText, setErrorText] = useState<string | null>(null);
  const [resultBlob, setResultBlob] = useState<Blob | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [engine, setEngine] = useState<string>('ollama');
  const [ollamaModel, setOllamaModel] = useState<string>('translategemma:12b');
  const [engineInfo, setEngineInfo] = useState<EnginesResponse | null>(null);
  const [checkingEngines, setCheckingEngines] = useState<boolean>(false);
  const [finishedJob, setFinishedJob] = useState<JobStatusResponse | null>(null);
  const [isCancelling, setIsCancelling] = useState<boolean>(false);
  const [noticeText, setNoticeText] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingTimerRef = useRef<number | null>(null);
  const jobIdRef = useRef<string | null>(null);
  const modelChosenRef = useRef<boolean>(false);

  const refreshEngines = async (model: string = ollamaModel) => {
    setCheckingEngines(true);
    try {
      const info = await fetchEngines(model);
      setEngineInfo(info);
      // Until the user picks one, prefer a model that is already downloaded:
      // a weak machine that only pulled the 4B should not be told to pull 12B.
      const installed = info.ollama.installed_models;
      if (!modelChosenRef.current && installed.length > 0 && !installed.includes(model)) {
        setOllamaModel(installed[0]);
      }
    } catch {
      setEngineInfo(null);
    } finally {
      setCheckingEngines(false);
    }
  };

  useEffect(() => {
    if (!backendReady) return;
    refreshEngines(ollamaModel);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendReady, ollamaModel]);

  const ollamaReady = engineInfo?.ollama.ready ?? false;

  useEffect(() => {
    if (!backendReady || engine !== 'ollama' || ollamaReady || isTranslating) return;
    const timer = window.setInterval(() => refreshEngines(ollamaModel), ENGINE_RECHECK_MS);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendReady, engine, ollamaReady, ollamaModel, isTranslating]);

  // Poll backend health until ready
  useEffect(() => {
    let active = true;
    const pollHealth = async () => {
      try {
        const res = await checkHealth();
        if (res.status === 'ready' && active) {
          setBackendReady(true);
          return;
        }
      } catch {
        if (active) setBackendReady(false);
      }
      if (active) {
        setTimeout(pollHealth, 1500);
      }
    };
    pollHealth();
    return () => {
      active = false;
    };
  }, []);

  // Cleanup polling timer on unmount
  useEffect(() => {
    return () => {
      if (pollingTimerRef.current) {
        window.clearTimeout(pollingTimerRef.current);
      }
    };
  }, []);

  const handleFileChange = (file: File | null) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
      setErrorText('Chỉ hỗ trợ tệp tin định dạng PDF.');
      return;
    }
    setErrorText(null);
    setNoticeText(null);
    setFinishedJob(null);
    setSelectedFile(file);
    setResultBlob(null);
    setProgress({ done: 0, total: 0 });
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const startTranslation = async () => {
    if (!selectedFile || isTranslating) return;

    setErrorText(null);
    setNoticeText(null);
    setFinishedJob(null);
    setResultBlob(null);
    setIsTranslating(true);
    setIsCancelling(false);
    setProgress({ done: 0, total: 0 });

    try {
      const { job_id } = await createTranslationJob(
        selectedFile,
        targetLanguage,
        domain,
        engine,
        ollamaModel,
      );
      jobIdRef.current = job_id;

      const poll = async () => {
        try {
          const statusRes = await fetchJobStatus(job_id);
          setProgress(statusRes.progress);

          if (statusRes.status === 'complete' || statusRes.status === 'complete_with_warnings') {
            const blob = await fetchJobResultBlob(job_id);
            setResultBlob(blob);
            setFinishedJob(statusRes);
            setIsTranslating(false);
            jobIdRef.current = null;
          } else if (statusRes.status === 'error') {
            setErrorText(statusRes.error || 'Dịch tài liệu thất bại.');
            setIsTranslating(false);
            jobIdRef.current = null;
          } else if (statusRes.status === 'cancelled') {
            setNoticeText('Đã hủy tác vụ dịch. Không có tệp kết quả nào được tạo.');
            setIsTranslating(false);
            setIsCancelling(false);
            jobIdRef.current = null;
          } else {
            pollingTimerRef.current = window.setTimeout(poll, POLL_INTERVAL_MS);
          }
        } catch (err: any) {
          const msg = err.response?.data?.detail || err.message || 'Lỗi khi kiểm tra tiến độ dịch.';
          setErrorText(msg);
          setIsTranslating(false);
        }
      };

      pollingTimerRef.current = window.setTimeout(poll, POLL_INTERVAL_MS);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Không thể bắt đầu tác vụ dịch.';
      setErrorText(msg);
      setIsTranslating(false);
    }
  };

  const cancelTranslation = async () => {
    const jobId = jobIdRef.current;
    if (!jobId || isCancelling) return;
    setIsCancelling(true);
    try {
      await cancelTranslationJob(jobId);
    } catch (err: any) {
      setErrorText(err.response?.data?.detail || err.message || 'Không thể hủy tác vụ.');
      setIsCancelling(false);
    }
  };

  const engineBlocked =
    engineInfo !== null &&
    ((engine === 'ollama' && !ollamaReady) ||
      (engine === 'azure' && !engineInfo.azure.configured));

  const handleDownload = () => {
    if (!resultBlob || !selectedFile) return;
    const stem = selectedFile.name.replace(/\.[^/.]+$/, '');
    const filename = `${stem}-${targetLanguage}.pdf`;
    const url = URL.createObjectURL(resultBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const progressPercent =
    progress.total > 0 ? Math.min(100, Math.round((progress.done / progress.total) * 100)) : 0;

  return (
    <div className="flex flex-col h-screen bg-gray-50 text-gray-900">
      {/* Top Navigation Bar */}
      <header className="bg-[#14452F] text-white px-5 py-3 shadow-md flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-white/10 p-1.5 rounded-lg">
            <Languages size={22} className="text-white" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight leading-tight">PDF Translate</h1>
            <p className="text-xs text-emerald-100/70">Bảo toàn bố cục, bảng biểu & công thức</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs bg-black/20 px-2.5 py-1 rounded-full">
            <span
              className={`w-2 h-2 rounded-full ${
                backendReady ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            <span className="text-emerald-50">
              {backendReady ? 'Backend sẵn sàng' : 'Đang kết nối backend...'}
            </span>
          </div>
          <img src="/icon.png" alt="PDF Translate" className="w-8 h-8 rounded-md object-cover" />
        </div>
      </header>

      {/* Action & Configuration Panel */}
      <div className="bg-white border-b border-gray-200 px-5 py-3 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* File Picker */}
          <div className="flex items-center gap-3">
            <input
              type="file"
              ref={fileInputRef}
              accept=".pdf,application/pdf"
              className="hidden"
              onChange={(e) => handleFileChange(e.target.files?.[0] || null)}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isTranslating}
              className="flex items-center gap-2 bg-gray-100 hover:bg-gray-200 text-gray-800 text-sm font-medium px-3.5 py-2 rounded-md border border-gray-300 transition-colors disabled:opacity-50"
            >
              <FileUp size={16} />
              <span>{selectedFile ? 'Chọn file khác' : 'Chọn file PDF'}</span>
            </button>

            {selectedFile ? (
              <div className="flex items-center gap-2 text-sm text-gray-700 bg-gray-50 border border-gray-200 px-3 py-1.5 rounded-md">
                <FileText size={16} className="text-[#14452F]" />
                <span className="font-medium truncate max-w-xs">{selectedFile.name}</span>
                <span className="text-xs text-gray-400">
                  ({(selectedFile.size / 1024).toFixed(1)} KB)
                </span>
              </div>
            ) : (
              <span className="text-xs text-gray-400">Chưa chọn tệp tin (Kéo thả hoặc bấm nút)</span>
            )}
          </div>

          {/* Language Selection & Translate Button */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <label htmlFor="target-lang" className="text-xs font-semibold text-gray-600">
                Ngôn ngữ đích:
              </label>
              <select
                id="target-lang"
                value={targetLanguage}
                onChange={(e) => setTargetLanguage(e.target.value)}
                disabled={isTranslating}
                className="text-sm bg-white border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-[#14452F] disabled:opacity-50 font-medium"
              >
                {TARGET_LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <label htmlFor="domain" className="text-xs font-semibold text-gray-600">
                Lĩnh vực:
              </label>
              <select
                id="domain"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                disabled={isTranslating}
                title="Ép đúng thuật ngữ chuyên ngành thay vì để engine tự dịch (tùy chọn)"
                className="text-sm bg-white border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-[#14452F] disabled:opacity-50 font-medium"
              >
                {DOMAINS.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.name}
                  </option>
                ))}
              </select>
            </div>

            <EnginePicker
              engine={engine}
              model={ollamaModel}
              info={engineInfo}
              checking={checkingEngines}
              disabled={isTranslating}
              onEngineChange={setEngine}
              onModelChange={(model) => {
                modelChosenRef.current = true;
                setOllamaModel(model);
              }}
              onRefresh={() => refreshEngines(ollamaModel)}
            />

            <button
              onClick={startTranslation}
              disabled={!selectedFile || isTranslating || !backendReady || engineBlocked}
              title={engineBlocked ? 'Bộ dịch chưa sẵn sàng – xem hướng dẫn bên dưới' : undefined}
              className="flex items-center gap-2 bg-[#14452F] hover:bg-[#0f3624] text-white text-sm font-medium px-6 py-2 rounded-md shadow transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              {isTranslating ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  <span>Đang dịch...</span>
                </>
              ) : (
                <>
                  <RefreshCw size={15} />
                  <span>Dịch ngay</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Translation Progress Bar */}
        {isTranslating && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <div className="flex items-center justify-between text-xs text-gray-600 mb-1 font-medium">
              <span className="flex items-center gap-1.5 text-[#14452F]">
                <Loader2 size={13} className="animate-spin" />
                Đang xử lý dịch tài liệu...
              </span>
              <span>
                {progress.total > 0
                  ? `Đã dịch ${progress.done} / ${progress.total} trang (${progressPercent}%)`
                  : 'Đang chuẩn bị mô hình...'}
              </span>
              <button
                onClick={cancelTranslation}
                disabled={isCancelling}
                title="Dừng sau trang đang dịch; không tạo tệp kết quả"
                className="flex items-center gap-1 text-red-700 hover:bg-red-50 border border-red-200 rounded px-2 py-0.5 disabled:opacity-50"
              >
                <XCircle size={13} />
                {isCancelling ? 'Đang hủy...' : 'Hủy'}
              </button>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
              <div
                className="bg-[#14452F] h-2 rounded-full transition-all duration-300 ease-out"
                style={{
                  width: progress.total > 0 ? `${progressPercent}%` : '20%',
                }}
              />
            </div>
          </div>
        )}

        {engine === 'ollama' && !isTranslating && <OllamaStatusNotice info={engineInfo} />}
        {!isTranslating && <RemoteEngineNotice engine={engine} info={engineInfo} />}

        {finishedJob && <TranslationWarningBanner result={finishedJob} />}

        {noticeText && (
          <div className="mt-3 p-3 bg-gray-50 border border-gray-200 rounded-md text-xs text-gray-700">
            {noticeText}
          </div>
        )}

        {/* Error Notice */}
        {errorText && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-md flex items-start gap-2.5 text-red-700 text-xs">
            <AlertCircle size={16} className="shrink-0 mt-0.5 text-red-600" />
            <div className="flex-1 font-medium leading-relaxed">{errorText}</div>
          </div>
        )}
      </div>

      {/* Main Workspace (Dual PDF Viewers or Drag & Drop Area) */}
      <main className="flex-1 p-4 overflow-hidden">
        {selectedFile ? (
          <div className="grid grid-cols-2 gap-4 h-full">
            {/* Left Viewer: Original Document */}
            <div className="h-full overflow-hidden">
              <PdfViewerBox title="Tài liệu gốc (Original)" file={selectedFile} />
            </div>

            {/* Right Viewer: Translated Document */}
            <div className="h-full overflow-hidden">
              <PdfViewerBox
                title={`Tài liệu đã dịch (${targetLanguage.toUpperCase()})`}
                file={resultBlob}
                onDownload={resultBlob ? handleDownload : undefined}
                downloadFilename={selectedFile ? `${selectedFile.name.replace(/\.[^/.]+$/, '')}-${targetLanguage}.pdf` : undefined}
              />
            </div>
          </div>
        ) : (
          /* Empty state: Drag and drop dropzone */
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`h-full border-2 border-dashed rounded-xl flex flex-col items-center justify-center p-8 text-center cursor-pointer transition-colors ${
              isDragging
                ? 'border-[#14452F] bg-emerald-50/50'
                : 'border-gray-300 hover:border-[#14452F] bg-white'
            }`}
          >
            <div className="w-16 h-16 bg-emerald-50 text-[#14452F] rounded-full flex items-center justify-center mb-4">
              <FileUp size={32} />
            </div>
            <h2 className="text-base font-semibold text-gray-800 mb-1">
              Kéo thả tệp PDF vào đây hoặc bấm để chọn tệp
            </h2>
            <p className="text-xs text-gray-400 max-w-sm">
              Ứng dụng hỗ trợ các tài liệu PDF văn bản, công thức toán học và bảng biểu.
            </p>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
