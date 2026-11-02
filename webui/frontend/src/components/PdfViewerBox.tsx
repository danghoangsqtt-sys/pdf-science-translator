import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { ChevronLeft, ChevronRight, Download, ZoomIn, ZoomOut } from 'lucide-react';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

const MIN_SCALE = 0.4;
const MAX_SCALE = 4;

export interface ScrollRatio {
  x: number;
  y: number;
}

interface PdfViewerBoxProps {
  title: string;
  file: File | Blob | string | null;
  onDownload?: () => void;
  downloadFilename?: string;
  scale: number;
  onScaleChange: (scale: number) => void;
  onScrollRatioChange?: (ratio: ScrollRatio) => void;
  scrollRatioTarget?: ScrollRatio | null;
}

const clampScale = (value: number) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, Number(value.toFixed(2))));

export const PdfViewerBox: React.FC<PdfViewerBoxProps> = ({
  title,
  file,
  onDownload,
  downloadFilename,
  scale,
  onScaleChange,
  onScrollRatioChange,
  scrollRatioTarget,
}) => {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [isDragging, setIsDragging] = useState(false);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const suppressScrollEvent = useRef(false);
  const panState = useRef({ x: 0, y: 0, scrollLeft: 0, scrollTop: 0 });

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setPageNumber(1);
    pageRefs.current.clear();
  };

  // Track which page is most visible while scrolling, to drive the page indicator.
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !numPages) return;

    const observer = new IntersectionObserver(
      (entries) => {
        let best: { page: number; ratio: number } | null = null;
        for (const entry of entries) {
          const page = Number((entry.target as HTMLElement).dataset.pageNumber);
          if (!page || entry.intersectionRatio <= 0) continue;
          if (!best || entry.intersectionRatio > best.ratio) {
            best = { page, ratio: entry.intersectionRatio };
          }
        }
        if (best) setPageNumber(best.page);
      },
      { root: container, threshold: [0.1, 0.25, 0.5, 0.75, 1] },
    );

    pageRefs.current.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [numPages]);

  const scrollToPage = (page: number) => {
    const el = pageRefs.current.get(page);
    if (!el) return;
    el.scrollIntoView({ block: 'start', behavior: 'smooth' });
  };

  // Ctrl + wheel: smooth zoom centered on cursor intent, like a browser.
  const handleWheel = useCallback(
    (e: React.WheelEvent<HTMLDivElement>) => {
      if (!e.ctrlKey) return;
      e.preventDefault();
      const delta = -e.deltaY * 0.0015;
      onScaleChange(clampScale(scale + delta * scale));
    },
    [scale, onScaleChange],
  );

  // Hold left mouse button to pan/drag the view when zoomed in.
  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    const container = containerRef.current;
    if (!container) return;
    setIsDragging(true);
    panState.current = {
      x: e.clientX,
      y: e.clientY,
      scrollLeft: container.scrollLeft,
      scrollTop: container.scrollTop,
    };
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDragging) return;
    const container = containerRef.current;
    if (!container) return;
    container.scrollLeft = panState.current.scrollLeft - (e.clientX - panState.current.x);
    container.scrollTop = panState.current.scrollTop - (e.clientY - panState.current.y);
  };

  const stopPanning = () => {
    if (isDragging) setIsDragging(false);
  };

  // Broadcast this viewer's scroll position (as a ratio) so a paired viewer can mirror it.
  const handleScroll = () => {
    if (suppressScrollEvent.current) return;
    const container = containerRef.current;
    if (!container || !onScrollRatioChange) return;
    const maxX = container.scrollWidth - container.clientWidth;
    const maxY = container.scrollHeight - container.clientHeight;
    onScrollRatioChange({
      x: maxX > 0 ? container.scrollLeft / maxX : 0,
      y: maxY > 0 ? container.scrollTop / maxY : 0,
    });
  };

  // Apply an incoming scroll ratio from the paired (synced) viewer.
  useEffect(() => {
    if (!scrollRatioTarget) return;
    const container = containerRef.current;
    if (!container) return;
    const maxX = container.scrollWidth - container.clientWidth;
    const maxY = container.scrollHeight - container.clientHeight;
    suppressScrollEvent.current = true;
    container.scrollLeft = maxX * scrollRatioTarget.x;
    container.scrollTop = maxY * scrollRatioTarget.y;
    const id = window.setTimeout(() => {
      suppressScrollEvent.current = false;
    }, 60);
    return () => window.clearTimeout(id);
  }, [scrollRatioTarget]);

  if (!file) {
    return (
      <div className="flex flex-col h-full bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
        <div className="p-3 border-b border-gray-100 bg-gray-50/50 flex items-center justify-between">
          <span className="text-gray-700 text-sm font-semibold">{title}</span>
        </div>
        <div className="flex-1 flex items-center justify-center bg-gray-50 text-gray-400 text-sm">
          Chưa có tệp PDF để hiển thị
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
      {/* Toolbar */}
      <div className="flex items-center justify-between p-3 border-b border-gray-100 bg-white">
        <div className="flex items-center gap-4">
          <span className="text-gray-800 text-sm font-semibold">{title}</span>
          <div className="flex items-center gap-1 bg-gray-50 px-2 py-0.5 rounded border border-gray-200">
            <button
              disabled={pageNumber <= 1}
              onClick={() => scrollToPage(pageNumber - 1)}
              className="text-gray-500 hover:text-gray-800 disabled:opacity-30 transition-colors p-1"
              title="Trang trước"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="text-xs text-gray-600 font-medium px-2">
              Trang {pageNumber} / {numPages || '?'}
            </span>
            <button
              disabled={numPages === null || pageNumber >= numPages}
              onClick={() => scrollToPage(pageNumber + 1)}
              className="text-gray-500 hover:text-gray-800 disabled:opacity-30 transition-colors p-1"
              title="Trang sau"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Zoom controls */}
          <div className="flex items-center gap-1 bg-gray-50 px-1 py-0.5 rounded border border-gray-200">
            <button
              onClick={() => onScaleChange(clampScale(scale - 0.2))}
              className="p-1 text-gray-600 hover:text-gray-900 rounded disabled:opacity-30"
              title="Thu nhỏ (hoặc giữ Ctrl + lăn chuột)"
            >
              <ZoomOut size={15} />
            </button>
            <span className="text-xs text-gray-600 font-medium w-12 text-center">
              {Math.round(scale * 100)}%
            </span>
            <button
              onClick={() => onScaleChange(clampScale(scale + 0.2))}
              className="p-1 text-gray-600 hover:text-gray-900 rounded disabled:opacity-30"
              title="Phóng to (hoặc giữ Ctrl + lăn chuột)"
            >
              <ZoomIn size={15} />
            </button>
          </div>

          {/* Download button if provided */}
          {onDownload && (
            <button
              onClick={onDownload}
              className="flex items-center gap-1.5 bg-brand hover:bg-brand-hover text-white text-xs font-medium px-3 py-1.5 rounded transition-colors"
              title="Tải tệp PDF đã dịch"
            >
              <Download size={14} />
              <span>Tải xuống</span>
            </button>
          )}
        </div>
      </div>

      {/* PDF Viewport */}
      <div
        ref={containerRef}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={stopPanning}
        onMouseLeave={stopPanning}
        onScroll={handleScroll}
        className={`flex-1 overflow-auto relative flex flex-col items-center bg-gray-100 p-4 gap-4 ${
          isDragging ? 'cursor-grabbing select-none' : 'cursor-grab'
        }`}
      >
        <Document
          file={file}
          onLoadSuccess={onDocumentLoadSuccess}
          loading={
            <div className="text-gray-500 p-12 text-sm flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-brand border-t-transparent rounded-full animate-spin"></div>
              Đang tải tệp PDF...
            </div>
          }
          error={
            <div className="text-red-500 p-8 text-sm">
              Không thể đọc nội dung file PDF.
            </div>
          }
        >
          {Array.from({ length: numPages ?? 0 }, (_, i) => i + 1).map((page) => (
            <div
              key={page}
              data-page-number={page}
              ref={(el) => {
                if (el) pageRefs.current.set(page, el);
                else pageRefs.current.delete(page);
              }}
              className="shadow-md rounded-sm overflow-hidden h-fit bg-white"
            >
              <Page
                pageNumber={page}
                scale={scale}
                renderTextLayer={false}
                renderAnnotationLayer={false}
                className="bg-white"
              />
            </div>
          ))}
        </Document>
      </div>
    </div>
  );
};
