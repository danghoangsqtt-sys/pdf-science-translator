import React, { useState, useEffect, useRef, useTransition } from 'react';
import {
  FileUp,
  Loader2,
  AlertCircle,
  FileText,
  CheckCircle2,
  RefreshCw,
  XCircle,
  ChevronUp,
  ChevronDown,
  ArrowLeftRight,
} from 'lucide-react';
import { PdfComparison } from './components/PdfComparison.tsx';
import { ProfilePicker, LocalStatusNotice } from './components/EnginePicker.tsx';
import { TranslationWarningBanner } from './components/TranslationWarningBanner.tsx';
import { AuthorFooter } from './components/AuthorInfo.tsx';
import { useCollapsibleChrome } from './components/useCollapsibleChrome.ts';
import {
  createTranslationJob,
  cancelTranslationJob,
  fetchCapabilities,
  fetchJobStatus,
  fetchJobResultBlob,
  checkHealth,
  POLL_INTERVAL_MS,
  POLL_MAX_BACKOFF_MS,
  POLL_GIVE_UP_MS,
  classifyRequestError,
  type CapabilitiesResponse,
  type ProcessingProfile,
  type JobProgress,
  type JobStatusResponse,
} from './services/api.ts';

// Refresh local resource readiness without any remote service.
const ENGINE_RECHECK_MS = 2500;

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

// Mirrors pdf2zh.translator.SUPPORTED_DOMAINS (see docs/ke-hoach/implementation-plan-2026-09-10.md
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
  // 'auto' lets the translator recognise Vietnamese per paragraph and treat
  // anything else as English; naming the source is better for other languages.
  const [sourceLanguage, setSourceLanguage] = useState<string>('auto');
  const chooseSource = (code: string) => {
    setSourceLanguage(code);
    if (code === targetLanguage) setTargetLanguage(code === 'vi' ? 'en' : 'vi');
  };
  const chooseTarget = (code: string) => {
    setTargetLanguage(code);
    if (code === sourceLanguage) setSourceLanguage('auto');
  };
  const swapLanguages = () => {
    if (sourceLanguage === 'auto') return;
    setSourceLanguage(targetLanguage);
    setTargetLanguage(sourceLanguage);
  };
  const [domain, setDomain] = useState<string>('');
  const [backendReady, setBackendReady] = useState<boolean>(false);
  const [isTranslating, setIsTranslating] = useState<boolean>(false);
  const [progress, setProgress] = useState<JobProgress>({ done: 0, total: 0 });
  const [errorText, setErrorText] = useState<string | null>(null);
  const [resultBlob, setResultBlob] = useState<Blob | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [profile, setProfile] = useState<ProcessingProfile>('balanced');
  const [engineInfo, setEngineInfo] = useState<CapabilitiesResponse | null>(null);
  const [checkingEngines, setCheckingEngines] = useState<boolean>(false);
  const [finishedJob, setFinishedJob] = useState<JobStatusResponse | null>(null);
  const [isCancelling, setIsCancelling] = useState<boolean>(false);
  const [noticeText, setNoticeText] = useState<string | null>(null);
  // The reader collapses the toolbar with the ▲/▼ button; nothing to read yet,
  // or a cancel in progress, keeps it on screen.
  const chrome = useCollapsibleChrome(!selectedFile || isCancelling);
  const { expand: expandChrome } = chrome;
  // Anything the user must read opens it again: an error, a notice, or a
  // finished job's result and warnings.
  useEffect(() => {
    if (errorText || noticeText || finishedJob) expandChrome();
  }, [errorText, noticeText, finishedJob, expandChrome]);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingTimerRef = useRef<number | null>(null);
  const jobIdRef = useRef<string | null>(null);
  // Until the user picks a level, follow the pack's own default: the lite
  // edition has only Nhanh, so a fixed 'balanced' start would open blocked.
  const profileChosenRef = useRef<boolean>(false);
  const refreshCapabilities = async () => {
    setCheckingEngines(true);
    try {
      const info = await fetchCapabilities();
      setEngineInfo(info);
      if (!profileChosenRef.current) setProfile(info.default_profile);
    }
    catch { setEngineInfo(null); }
    finally { setCheckingEngines(false); }
  };
  const chooseProfile = (value: ProcessingProfile) => {
    profileChosenRef.current = true;
    setProfile(value);
  };

  useEffect(() => {
    if (!backendReady || isTranslating) return;
    refreshCapabilities();
    const timer = window.setInterval(refreshCapabilities, ENGINE_RECHECK_MS);
    return () => window.clearInterval(timer);
  }, [backendReady, isTranslating]);

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
        profile,
        sourceLanguage,
      );
      jobIdRef.current = job_id;

      // A single failed status request must not end the job on screen: the
      // backend can be busy for tens of seconds finishing a large PDF, or be
      // restarted by Electron. Retry with backoff; stop only when the job is
      // gone (404), the request is refused, or nothing answers for too long.
      let failures = 0;
      let failingSince = 0;
      const stopFollowing = (message: string) => {
        setErrorText(message);
        setNoticeText(null);
        setIsTranslating(false);
        setIsCancelling(false);
        jobIdRef.current = null;
      };

      const poll = async () => {
        try {
          const statusRes = await fetchJobStatus(job_id);
          if (failures > 0) setNoticeText(null);
          failures = 0;
          failingSince = 0;
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
        } catch (err: unknown) {
          const kind = classifyRequestError(err);
          if (kind === 'not_found') {
            stopFollowing('Bộ xử lý đã khởi động lại nên tác vụ bị gián đoạn. Hãy bấm "Dịch ngay" để dịch lại.');
            return;
          }
          if (kind === 'transient') {
            failures += 1;
            if (!failingSince) failingSince = Date.now();
            if (Date.now() - failingSince < POLL_GIVE_UP_MS) {
              setNoticeText('Đang chờ bộ xử lý phản hồi... Tác vụ vẫn tiếp tục.');
              const delay = Math.min(POLL_INTERVAL_MS * 2 ** failures, POLL_MAX_BACKOFF_MS);
              pollingTimerRef.current = window.setTimeout(poll, delay);
              return;
            }
          }
          stopFollowing('Không thể kiểm tra tiến độ. Vui lòng kiểm tra lại trạng thái ứng dụng.');
        }
      };

      pollingTimerRef.current = window.setTimeout(poll, POLL_INTERVAL_MS);
    } catch (err: any) {
      const msg = 'Không thể bắt đầu xử lý. Hãy kiểm tra dữ liệu cục bộ và thử lại.';
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
      setErrorText('Không thể gửi yêu cầu hủy. Vui lòng thử lại.');
      setIsCancelling(false);
    }
  };

  const engineBlocked = !engineInfo?.profiles.some(item => item.id === profile && item.available);

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
    <div className="flex flex-col h-screen min-w-0 overflow-hidden bg-gray-50 text-gray-900">
      {/* While the toolbar is hidden a translation still shows its progress. */}
      {chrome.hidden && isTranslating && (
        <div data-reading-progress role="progressbar" aria-label="Tiến độ dịch"
          aria-valuenow={progressPercent} aria-valuemin={0} aria-valuemax={100}
          title={progress.total > 0 ? `Đã dịch ${progress.done} / ${progress.total} trang (${progressPercent}%)` : 'Đang chuẩn bị bộ xử lý...'}
          className="fixed inset-x-0 top-0 z-50 h-[3px] bg-gray-200">
          <div className="h-full bg-[#14452F] transition-all duration-300"
            style={{ width: progress.total > 0 ? `${progressPercent}%` : '20%' }} />
        </div>
      )}
      {/* Header and toolbar collapse together; a grid row animates to 0. */}
      <div data-chrome data-hidden={chrome.hidden ? 'true' : 'false'}
        inert={chrome.hidden}
        className={'grid shrink-0 transition-[grid-template-rows,opacity] duration-200 ease-out motion-reduce:transition-none '
          + (chrome.hidden ? 'grid-rows-[0fr] opacity-0' : 'grid-rows-[1fr] opacity-100')}>
      <div className="min-h-0 overflow-hidden">
      {/* Top Navigation Bar */}
      <header className="bg-[#14452F] text-white px-3 py-2 lg:px-5 lg:py-3 short:py-1.5 shadow-md flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 lg:w-9 lg:h-9 rounded-lg overflow-hidden bg-white shrink-0">
            <img src="./icon.png" alt="" className="w-full h-full object-cover" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight leading-tight">PDF Translate</h1>
            <p className="hidden md:block short:hidden text-xs text-emerald-100/70">Bảo toàn bố cục, bảng biểu & công thức</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs bg-black/20 px-2.5 py-1 rounded-full whitespace-nowrap">
            <span
              className={`w-2 h-2 rounded-full ${
                backendReady && !engineBlocked ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            <span className="text-emerald-50">
              {backendReady && !engineBlocked ? 'Bộ xử lý sẵn sàng' : backendReady ? 'Đang chuẩn bị dữ liệu...' : 'Đang kết nối bộ xử lý...'}
            </span>
          </div>
          <img src="./icon.png" alt="PDF Translate" className="hidden xl:block w-8 h-8 rounded-md object-cover" />
        </div>
      </header>

      {/* Action & Configuration Panel */}
      <div className="bg-white border-b border-gray-200 px-3 py-2 lg:px-5 lg:py-3 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 lg:gap-4">
          {/* File Picker */}
          <div className="flex min-w-0 items-center gap-2 lg:gap-3">
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
              className="flex shrink-0 items-center gap-2 bg-gray-100 hover:bg-gray-200 text-gray-800 text-sm font-medium px-3 py-1.5 lg:px-3.5 lg:py-2 rounded-md border border-gray-300 transition-colors disabled:opacity-50"
            >
              <FileUp size={16} />
              <span>{selectedFile ? 'Chọn file khác' : 'Chọn file PDF'}</span>
            </button>

            {selectedFile ? (
              <div className="flex min-w-0 items-center gap-2 text-sm text-gray-700 bg-gray-50 border border-gray-200 px-2 py-1 lg:px-3 lg:py-1.5 rounded-md" title={selectedFile.name}>
                <FileText size={16} className="text-[#14452F]" />
                <span className="font-medium truncate max-w-[9rem] md:max-w-[14rem] xl:max-w-xs">{selectedFile.name}</span>
                <span className="hidden lg:inline text-xs text-gray-400">
                  ({(selectedFile.size / 1024).toFixed(1)} KB)
                </span>
              </div>
            ) : (
              <span className="hidden md:inline text-xs text-gray-400">Chưa chọn tệp tin (Kéo thả hoặc bấm nút)</span>
            )}
          </div>

          {/* Language Selection & Translate Button */}
          <div className="flex flex-wrap items-center gap-2 lg:gap-3">
            <div className="flex items-center gap-1 lg:gap-2">
              <label htmlFor="source-lang" className="sr-only xl:not-sr-only text-xs font-semibold text-gray-600">
                Dịch từ:
              </label>
              <select
                id="source-lang"
                value={sourceLanguage}
                onChange={(e) => chooseSource(e.target.value)}
                disabled={isTranslating}
                title="Ngôn ngữ của tài liệu gốc. Tự nhận diện: tiếng Việt hoặc tiếng Anh; ngôn ngữ khác hãy chọn đúng tên."
                className="w-32 lg:w-36 xl:w-auto max-w-[16rem] text-sm bg-white border border-gray-300 rounded-md px-2 py-1.5 lg:px-3 focus:outline-none focus:ring-2 focus:ring-[#14452F] disabled:opacity-50 font-medium"
              >
                <option value="auto">Tự nhận diện</option>
                {TARGET_LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={swapLanguages}
                disabled={isTranslating || sourceLanguage === 'auto'}
                title={sourceLanguage === 'auto' ? 'Chọn ngôn ngữ nguồn để đảo chiều dịch' : 'Đảo chiều: dịch ngược lại'}
                aria-label="Đảo chiều ngôn ngữ"
                className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 disabled:opacity-40"
              >
                <ArrowLeftRight size={15} />
              </button>
              <label htmlFor="target-lang" className="sr-only xl:not-sr-only text-xs font-semibold text-gray-600">
                sang:
              </label>
              <select
                id="target-lang"
                value={targetLanguage}
                onChange={(e) => chooseTarget(e.target.value)}
                disabled={isTranslating}
                title="Ngôn ngữ đích"
                className="w-32 lg:w-36 xl:w-auto max-w-[16rem] text-sm bg-white border border-gray-300 rounded-md px-2 py-1.5 lg:px-3 focus:outline-none focus:ring-2 focus:ring-[#14452F] disabled:opacity-50 font-medium"
              >
                {TARGET_LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <label htmlFor="domain" className="sr-only xl:not-sr-only text-xs font-semibold text-gray-600">
                Lĩnh vực:
              </label>
              <select
                id="domain"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                disabled={isTranslating}
                title="Ép đúng thuật ngữ chuyên ngành thay vì để bộ xử lý tự dịch (tùy chọn)"
                className="w-32 lg:w-36 xl:w-auto max-w-[16rem] text-sm bg-white border border-gray-300 rounded-md px-2 py-1.5 lg:px-3 focus:outline-none focus:ring-2 focus:ring-[#14452F] disabled:opacity-50 font-medium"
              >
                {DOMAINS.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.name}
                  </option>
                ))}
              </select>
            </div>

            <ProfilePicker profile={profile} info={engineInfo} checking={checkingEngines}
              disabled={isTranslating} onChange={chooseProfile} onRefresh={refreshCapabilities} />

            <button
              onClick={startTranslation}
              disabled={!selectedFile || isTranslating || !backendReady || engineBlocked}
              title={engineBlocked ? 'Mức xử lý chưa sẵn sàng – xem thông báo bên dưới' : undefined}
              className="flex shrink-0 items-center gap-2 bg-[#14452F] hover:bg-[#0f3624] text-white text-sm font-medium px-4 py-1.5 lg:px-6 lg:py-2 rounded-md shadow transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
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
          <div className="mt-2 pt-2 lg:mt-3 lg:pt-3 border-t border-gray-100">
            <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-xs text-gray-600 mb-1 font-medium">
              <span className="flex items-center gap-1.5 text-[#14452F]">
                <Loader2 size={13} className="animate-spin" />
                Đang xử lý dịch tài liệu...
              </span>
              <span>
                {progress.total > 0
                  ? `Đã dịch ${progress.done} / ${progress.total} trang (${progressPercent}%)`
                  : 'Đang chuẩn bị bộ xử lý...'}
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

        {/* Notices scroll inside a capped band so a short projector screen keeps room for the PDF. */}
        <div className="max-h-[22vh] overflow-y-auto">
        {!isTranslating && <LocalStatusNotice info={engineInfo} profile={profile} />}

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
      </div>
      </div>
      </div>

      {/* Outside the collapsing area, so it stays reachable when collapsed. */}
      {chrome.canCollapse && (
        <div className="flex shrink-0 justify-center">
          <button
            type="button"
            data-chrome-toggle
            onClick={chrome.toggle}
            aria-expanded={!chrome.hidden}
            aria-label={chrome.hidden ? 'Mở rộng thanh công cụ' : 'Thu gọn thanh công cụ'}
            title={chrome.hidden ? 'Mở rộng thanh công cụ' : 'Thu gọn thanh công cụ'}
            className="flex h-4 w-14 items-center justify-center rounded-b-md border border-t-0 border-gray-200 bg-white text-gray-500 shadow-sm hover:bg-gray-100 hover:text-[#14452F] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#14452F]"
          >
            {chrome.hidden ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
          </button>
        </div>
      )}

      {/* Main Workspace (Dual PDF Viewers or Drag & Drop Area) */}
      <main className="flex-1 min-h-0 p-2 lg:p-4 overflow-hidden">
        {selectedFile ? (
          <PdfComparison
            key={selectedFile.name + ':' + selectedFile.lastModified}
            original={selectedFile}
            translated={resultBlob}
            language={targetLanguage}
            onDownload={handleDownload}
          />
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

      <AuthorFooter hidden={chrome.hidden} />
    </div>
  );
};

export default App;
