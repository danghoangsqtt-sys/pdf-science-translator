import React, { useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { ChevronLeft, ChevronRight, Download, ZoomIn, ZoomOut } from 'lucide-react';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

interface PdfViewerBoxProps {
  title: string;
  file: File | Blob | string | null;
  onDownload?: () => void;
  downloadFilename?: string;
}

export const PdfViewerBox: React.FC<PdfViewerBoxProps> = ({
  title,
  file,
  onDownload,
  downloadFilename,
}) => {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1.0);

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setPageNumber(1);
  };

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
              onClick={() => setPageNumber((p) => Math.max(1, p - 1))}
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
              onClick={() => setPageNumber((p) => (numPages ? Math.min(numPages, p + 1) : p + 1))}
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
              onClick={() => setScale((s) => Math.max(0.4, Number((s - 0.2).toFixed(1))))}
              className="p-1 text-gray-600 hover:text-gray-900 rounded disabled:opacity-30"
              title="Thu nhỏ"
            >
              <ZoomOut size={15} />
            </button>
            <span className="text-xs text-gray-600 font-medium w-12 text-center">
              {Math.round(scale * 100)}%
            </span>
            <button
              onClick={() => setScale((s) => Math.min(2.5, Number((s + 0.2).toFixed(1))))}
              className="p-1 text-gray-600 hover:text-gray-900 rounded disabled:opacity-30"
              title="Phóng to"
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
      <div className="flex-1 overflow-auto relative flex justify-center bg-gray-100 p-4">
        <div className="shadow-md rounded-sm overflow-hidden h-fit bg-white">
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
            <Page
              pageNumber={pageNumber}
              scale={scale}
              renderTextLayer={false}
              renderAnnotationLayer={false}
              className="bg-white"
            />
          </Document>
        </div>
      </div>
    </div>
  );
};
