import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import { ChevronLeft, ChevronRight, Download, ZoomIn, ZoomOut } from 'lucide-react';
import { clampScale, pageAtOffset, type ReadingPosition } from './pdfViewport.ts';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url,
).toString();

interface Props {
  title: string;
  file: File | Blob | string | null;
  onDownload?: () => void;
  scale: number;
  onScaleChange: (scale: number) => void;
  position: ReadingPosition | null;
  onPositionChange: (position: ReadingPosition) => void;
}
interface PageSize { width: number; height: number }

export const PdfViewerBox: React.FC<Props> = ({
  title, file, onDownload, scale, onScaleChange, position, onPositionChange,
}) => {
  const [sizes, setSizes] = useState<PageSize[]>([]);
  const [visible, setVisible] = useState(new Set([1]));
  const [pageNumber, setPageNumber] = useState(1);
  const [dragging, setDragging] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const viewport = useRef<HTMLDivElement>(null);
  const pages = useRef(new Map<number, HTMLDivElement>());
  const loadedPdf = useRef<PDFDocumentProxy | null>(null);
  const pan = useRef<{ id: number; x: number; y: number; left: number; top: number } | null>(null);
  const applied = useRef<{ left: number; top: number } | null>(null);
  const current = useRef<ReadingPosition>({ page: 1, offset: 0, x: 0 });
  const anchor = useRef<{
    page: number; offset: number; pageX: number; clientX: number; clientY: number;
  } | null>(null);
  const frame = useRef<number | null>(null);
  const latest = useRef({ scale, onScaleChange, onPositionChange });
  latest.current = { scale, onScaleChange, onPositionChange };

  useEffect(() => {
    setSizes([]);
    setPageNumber(1);
    setLoadError(false);
    setVisible(new Set([1]));
    current.current = { page: 1, offset: 0, x: 0 };
    anchor.current = null;
    applied.current = null;
    viewport.current?.scrollTo(0, 0);
    return () => {
      loadedPdf.current = null;
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      frame.current = null;
    };
  }, [file]);

  const loadPages = useCallback(async (pdf: PDFDocumentProxy) => {
    loadedPdf.current = pdf;
    try {
      // Read geometry once, with bounded concurrency. Only nearby pages get
      // canvases, so scrolling a book does not render the entire book at once.
      const result: PageSize[] = new Array(pdf.numPages);
      let next = 0;
      await Promise.all(Array.from({ length: Math.min(8, pdf.numPages) }, async () => {
        while (next < pdf.numPages && loadedPdf.current === pdf) {
          const index = next++;
          const page = await pdf.getPage(index + 1);
          const size = page.getViewport({ scale: 1 });
          result[index] = { width: size.width, height: size.height };
        }
      }));
      if (loadedPdf.current === pdf) setSizes(result);
    } catch {
      if (loadedPdf.current === pdf) setLoadError(true);
    }
  }, []);

  useEffect(() => {
    if (!viewport.current || !sizes.length) return;
    const observer = new IntersectionObserver((entries) => {
      setVisible((previous) => {
        const next = new Set(previous);
        for (const entry of entries) {
          const page = Number((entry.target as HTMLElement).dataset.pageNumber);
          if (entry.isIntersecting) next.add(page);
          else next.delete(page);
        }
        return next;
      });
    }, { root: viewport.current, rootMargin: '800px', threshold: 0 });
    pages.current.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [sizes]);

  const geometry = () => Array.from(pages.current.values(), (element) => ({
    top: element.offsetTop, height: element.offsetHeight,
  }));
  const read = (): ReadingPosition => {
    const container = viewport.current!;
    const at = pageAtOffset(geometry(), container.scrollTop + 16);
    const maxX = container.scrollWidth - container.clientWidth;
    return { ...at, x: maxX > 0 ? container.scrollLeft / maxX : 0 };
  };
  const publish = () => {
    if (!viewport.current || !pages.current.size) return;
    const value = read();
    current.current = value;
    setPageNumber(value.page);
    latest.current.onPositionChange(value);
  };
  const rememberScroll = () => {
    const container = viewport.current!;
    applied.current = { left: container.scrollLeft, top: container.scrollTop };
  };
  const apply = (value: ReadingPosition) => {
    const container = viewport.current;
    const element = pages.current.get(value.page);
    if (!container || !element) return;
    container.scrollTop = element.offsetTop + element.offsetHeight * value.offset - 16;
    container.scrollLeft = (container.scrollWidth - container.clientWidth) * value.x;
    rememberScroll();
    current.current = read();
    setPageNumber(current.current.page);
  };
  const zoom = (next: number, clientX?: number, clientY?: number) => {
    const container = viewport.current;
    const value = clampScale(next);
    if (!container || value === latest.current.scale || !pages.current.size) return;
    const x = clientX ?? container.clientWidth / 2;
    const y = clientY ?? container.clientHeight / 2;
    const at = pageAtOffset(geometry(), container.scrollTop + y);
    const element = pages.current.get(at.page)!;
    anchor.current = {
      ...at, clientX: x, clientY: y,
      pageX: (container.scrollLeft + x - element.offsetLeft) / element.offsetWidth,
    };
    latest.current.onScaleChange(value);
  };
  const zoomHandler = useRef(zoom);
  zoomHandler.current = zoom;

  useEffect(() => {
    const container = viewport.current;
    if (!container) return;
    const wheel = (event: WheelEvent) => {
      if (!event.ctrlKey) return;
      // React delegates wheel events passively in Chromium. Prevent the native
      // default here so Ctrl+wheel zooms the PDF instead of the entire app.
      event.preventDefault();
      const rect = container.getBoundingClientRect();
      const units = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? container.clientHeight : 1;
      const factor = Math.exp(-Math.max(-300, Math.min(300, event.deltaY * units)) * 0.002);
      zoomHandler.current(latest.current.scale * factor, event.clientX - rect.left, event.clientY - rect.top);
    };
    container.addEventListener('wheel', wheel, { passive: false });
    return () => container.removeEventListener('wheel', wheel);
  }, [file]);

  useLayoutEffect(() => {
    const container = viewport.current;
    if (!container || !sizes.length) return;
    const point = anchor.current;
    if (point) {
      const element = pages.current.get(point.page);
      if (element) {
        container.scrollTop = element.offsetTop + element.offsetHeight * point.offset - point.clientY;
        container.scrollLeft = element.offsetLeft + element.offsetWidth * point.pageX - point.clientX;
        rememberScroll();
      }
      anchor.current = null;
      publish();
    } else apply(position ?? current.current);
  }, [scale, sizes]);

  useLayoutEffect(() => {
    if (position && !anchor.current) apply(position);
  }, [position]);

  const scroll = () => {
    const container = viewport.current!;
    const target = applied.current;
    // Ignore the exact mirrored event. New user input can take over at once.
    if (target && Math.abs(container.scrollLeft - target.left) < 1
      && Math.abs(container.scrollTop - target.top) < 1) return;
    if (frame.current !== null) return;
    frame.current = requestAnimationFrame(() => { frame.current = null; publish(); });
  };
  const goTo = (page: number) => {
    apply({ page, offset: 0, x: current.current.x });
    publish();
  };
  const stopPan = () => { pan.current = null; setDragging(false); };

  return (
    <section className="flex flex-col h-full min-h-0 min-w-0 bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 p-3 border-b border-gray-100 bg-white">
        <span className="text-gray-800 text-sm font-semibold">{title}</span>
        {file && <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center bg-gray-50 rounded border border-gray-200">
            <button disabled={pageNumber <= 1} onClick={() => goTo(pageNumber - 1)}
              className="p-1 text-gray-600 disabled:opacity-30" title="Trang trước"><ChevronLeft size={16} /></button>
            <span className="text-xs text-gray-600 px-1">Trang {pageNumber} / {sizes.length || '?'}</span>
            <button disabled={!sizes.length || pageNumber >= sizes.length} onClick={() => goTo(pageNumber + 1)}
              className="p-1 text-gray-600 disabled:opacity-30" title="Trang sau"><ChevronRight size={16} /></button>
          </div>
          <div className="flex items-center bg-gray-50 rounded border border-gray-200">
            <button disabled={scale <= 0.4} onClick={() => zoom(scale - 0.2)}
              className="p-1 text-gray-600 disabled:opacity-30" title="Thu nhỏ (Ctrl + lăn chuột)"><ZoomOut size={15} /></button>
            <span className="text-xs text-gray-600 w-10 text-center" aria-label="Mức thu phóng">{Math.round(scale * 100)}%</span>
            <button disabled={scale >= 4} onClick={() => zoom(scale + 0.2)}
              className="p-1 text-gray-600 disabled:opacity-30" title="Phóng to (Ctrl + lăn chuột)"><ZoomIn size={15} /></button>
          </div>
          {onDownload && <button onClick={onDownload}
            className="flex items-center gap-1 bg-brand hover:bg-brand-hover text-white text-xs px-2 py-1 rounded" title="Tải tệp PDF đã dịch">
            <Download size={14} /> Tải xuống
          </button>}
        </div>}
      </div>
      {file ? <div ref={viewport} data-pdf-viewport aria-label={title} tabIndex={0}
        onScroll={scroll}
        onPointerDown={(event) => {
          if (event.button !== 0 || event.pointerType === 'touch') return;
          const container = event.currentTarget;
          const rect = container.getBoundingClientRect();
          if (event.clientX - rect.left >= container.clientWidth || event.clientY - rect.top >= container.clientHeight) return;
          event.preventDefault();
          container.focus({ preventScroll: true });
          container.setPointerCapture(event.pointerId);
          pan.current = { id: event.pointerId, x: event.clientX, y: event.clientY, left: container.scrollLeft, top: container.scrollTop };
          setDragging(true);
        }}
        onPointerMove={(event) => {
          const start = pan.current;
          if (!start || start.id !== event.pointerId) return;
          event.currentTarget.scrollLeft = start.left - (event.clientX - start.x);
          event.currentTarget.scrollTop = start.top - (event.clientY - start.y);
        }}
        onPointerUp={(event) => {
          if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
          stopPan();
        }}
        onPointerCancel={stopPan} onLostPointerCapture={stopPan}
        className={'flex-1 min-h-0 overflow-auto relative bg-gray-100 p-4 select-none overscroll-contain ' + (dragging ? 'cursor-grabbing' : 'cursor-grab')}
        style={{ overflowAnchor: 'none' }}>
        <Document file={file} onLoadSuccess={loadPages} onLoadError={() => setLoadError(true)}
          className="flex flex-col items-center gap-4 w-max min-w-full"
          loading={<p className="p-8 text-sm text-gray-500">Đang tải tệp PDF...</p>}
          error={<p className="p-8 text-sm text-red-600">Không thể đọc tệp PDF.</p>}>
          {loadError && <p className="p-8 text-sm text-red-600">Không thể đọc các trang PDF. Hãy chọn lại tệp.</p>}
          {!sizes.length && !loadError && <p className="p-8 text-sm text-gray-500">Đang chuẩn bị các trang...</p>}
          {sizes.map((size, index) => <div key={index} data-page-number={index + 1}
            ref={(element) => {
              if (element) pages.current.set(index + 1, element);
              else pages.current.delete(index + 1);
            }}
            style={{ width: size.width * scale, height: size.height * scale }}
            className="shrink-0 overflow-hidden bg-white shadow-md">
            {visible.has(index + 1)
              ? <Page pageNumber={index + 1} scale={scale} renderTextLayer={false} renderAnnotationLayer={false}
                loading={<span className="p-4 text-xs text-gray-400">Trang {index + 1}</span>} />
              : <span className="p-4 text-xs text-gray-400">Trang {index + 1}</span>}
          </div>)}
        </Document>
      </div> : <div className="flex-1 flex items-center justify-center bg-gray-50 text-gray-400 text-sm">Chưa có tệp PDF để hiển thị</div>}
    </section>
  );
};
