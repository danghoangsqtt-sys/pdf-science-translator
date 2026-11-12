import React, { useEffect, useRef, useState } from 'react';
import { Check, Copy, Phone, X } from 'lucide-react';
// Small enough that Vite inlines it as a data URI, so it shows under file://
// in the packaged app as well as on the dev server. Generated with segno for
// https://zalo.me/84343019101 and checked by decoding it back.
import zaloQr from '../assets/zalo-qr.svg';

const AUTHOR = 'LÊ BÁ ĐĂNG HOÀNG';
const PHONE = '0343019101';
const ZALO_URL = 'https://zalo.me/84343019101';
const COPYRIGHT = '© 2026 DHsystem';

/** Opens in the system browser inside Electron, a new tab elsewhere. */
const openExternal = (event: React.MouseEvent, url: string) => {
  if (window.pdftranslate?.openExternal) {
    event.preventDefault();
    window.pdftranslate.openExternal(url);
  }
};

/** Copyright line along the bottom edge, with the way into the author card. */
export const AuthorFooter: React.FC<{ hidden?: boolean }> = ({ hidden = false }) => {
  const [open, setOpen] = useState(false);

  return (
    <>
      <footer className={(hidden ? 'hidden ' : 'flex ') + 'items-center justify-between gap-3 border-t border-gray-200 bg-white px-3 lg:px-5 py-1 lg:py-1.5 text-xs text-gray-500 whitespace-nowrap'}>
        <span className="truncate">{COPYRIGHT}<span className="hidden sm:inline">. Bảo lưu mọi quyền.</span></span>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="font-medium text-gray-600 hover:text-[#14452F] hover:underline"
        >
          Tác giả: {AUTHOR}
        </button>
      </footer>
      {open && <AuthorDialog onClose={() => setOpen(false)} />}
    </>
  );
};

const AuthorDialog: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const [copied, setCopied] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const copyPhone = async () => {
    try {
      await navigator.clipboard.writeText(PHONE);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="author-title"
        onClick={(event) => event.stopPropagation()}
        className="relative w-full max-w-sm rounded-xl bg-white p-6 shadow-xl"
      >
        <button
          ref={closeRef}
          type="button"
          onClick={onClose}
          aria-label="Đóng"
          className="absolute right-3 top-3 rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
        >
          <X size={16} />
        </button>

        <p className="text-xs font-semibold uppercase tracking-wide text-[#14452F]">Giới thiệu tác giả</p>
        <h2 id="author-title" className="mt-1 text-lg font-bold text-gray-900">
          {AUTHOR}
        </h2>
        <p className="text-sm text-gray-500">Tác giả PDF Translate · DHsystem</p>

        <div className="mt-4 flex items-center gap-2 rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm">
          <Phone size={15} className="text-[#14452F]" />
          <span className="font-medium tabular-nums text-gray-800">{PHONE}</span>
          <button
            type="button"
            onClick={copyPhone}
            className="ml-auto inline-flex items-center gap-1 rounded border border-gray-300 bg-white px-2 py-0.5 text-xs text-gray-600 hover:bg-gray-100"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? 'Đã chép' : 'Chép số'}
          </button>
        </div>

        <div className="mt-4 flex flex-col items-center rounded-lg border border-gray-200 p-4">
          <img src={zaloQr} alt={`Mã QR Zalo của ${AUTHOR}`} className="h-44 w-44" />
          <p className="mt-2 text-xs text-gray-500">Quét mã để kết nối Zalo</p>
          <a
            href={ZALO_URL}
            target="_blank"
            rel="noreferrer"
            onClick={(event) => openExternal(event, ZALO_URL)}
            className="mt-1 text-sm font-medium text-[#14452F] underline"
          >
            zalo.me/84343019101
          </a>
        </div>

        <p className="mt-4 text-center text-xs text-gray-400">{COPYRIGHT}. Bảo lưu mọi quyền.</p>
      </div>
    </div>
  );
};
