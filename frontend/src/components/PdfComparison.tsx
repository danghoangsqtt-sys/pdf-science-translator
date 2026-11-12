import React, { useEffect, useRef, useState } from 'react';
import { Columns2, FileText, Languages, Link2, Unlink2 } from 'lucide-react';
import { PdfViewerBox } from './PdfViewerBox.tsx';
import type { ReadingPosition, ZoomMode } from './pdfViewport.ts';
import {
  readStoredMode, storeMode, useViewportLayout, type ComparisonMode,
} from './useViewportLayout.ts';

interface Props {
  original: File;
  translated: Blob | null;
  language: string;
  onDownload: () => void;
}

const MODES: { id: ComparisonMode; label: string; icon: React.ReactNode }[] = [
  { id: 'source', label: 'Bản gốc', icon: <FileText size={14} /> },
  { id: 'translated', label: 'Bản dịch', icon: <Languages size={14} /> },
  { id: 'both', label: 'Song song', icon: <Columns2 size={14} /> },
];

export const PdfComparison: React.FC<Props> = ({ original, translated, language, onDownload }) => {
  const layout = useViewportLayout();
  const [sync, setSync] = useState(true);
  const [leftScale, setLeftScale] = useState(1);
  const [rightScale, setRightScale] = useState(1);
  // A new document (this component remounts per file) starts fitted to width.
  const [leftZoomMode, setLeftZoomMode] = useState<ZoomMode>('fit');
  const [rightZoomMode, setRightZoomMode] = useState<ZoomMode>('fit');
  const [leftPosition, setLeftPosition] = useState<ReadingPosition | null>(null);
  const [rightPosition, setRightPosition] = useState<ReadingPosition | null>(null);
  // A mode the user picked by hand wins over the one the window size suggests.
  const [chosenMode, setChosenMode] = useState<ComparisonMode | null>(readStoredMode);
  // A result that has just arrived is shown once, even in single-pane mode.
  const [showArrival, setShowArrival] = useState(false);
  const active = useRef<'left' | 'right'>('left');
  const lastPosition = useRef<ReadingPosition>({ page: 1, offset: 0, x: 0 });

  const preferred: ComparisonMode = chosenMode ?? (layout.sideBySide ? 'both' : 'source');
  const mode: ComparisonMode = showArrival && preferred !== 'both' ? 'translated' : preferred;
  const showLeft = mode !== 'translated';
  const showRight = mode !== 'source';

  useEffect(() => { setShowArrival(Boolean(translated)); }, [translated]);

  const move = (side: 'left' | 'right', position: ReadingPosition) => {
    active.current = side;
    lastPosition.current = position;
    if (sync) { setLeftPosition(position); setRightPosition(position); }
  };
  const zoom = (side: 'left' | 'right', scale: number) => {
    active.current = side;
    if (sync || side === 'left') setLeftScale(scale);
    if (sync || side === 'right') setRightScale(scale);
  };
  const setZoomMode = (side: 'left' | 'right', next: ZoomMode) => {
    if (sync || side === 'left') setLeftZoomMode(next);
    if (sync || side === 'right') setRightZoomMode(next);
  };
  const choose = (next: ComparisonMode) => {
    setShowArrival(false);
    setChosenMode(next);
    storeMode(next);
    if (sync) {
      // The pane being opened starts where the reader is, not at page 1.
      setLeftPosition({ ...lastPosition.current });
      setRightPosition({ ...lastPosition.current });
    }
  };

  return <div className="flex flex-col h-full min-h-0">
    <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 pb-2 text-xs text-gray-500">
      <div role="group" aria-label="Chế độ xem" className="flex items-center rounded-full border border-gray-300 bg-white p-0.5">
        {MODES.map((item) => (
          <button key={item.id} type="button" aria-pressed={mode === item.id}
            data-view-mode={item.id}
            onClick={() => choose(item.id)}
            title={item.id === 'both' ? 'Xem bản gốc và bản dịch cạnh nhau' : 'Chỉ xem ' + item.label.toLowerCase()}
            className={'flex items-center gap-1 rounded-full px-2.5 py-1 ' + (mode === item.id
              ? 'bg-brand text-white' : 'text-gray-600 hover:bg-gray-100')}>
            {item.icon}<span>{item.label}</span>
          </button>
        ))}
      </div>
      <span className="hidden xl:inline">Cuộn để đọc · Ctrl + lăn chuột để thu phóng · Giữ chuột trái để kéo</span>
      <button type="button" aria-pressed={sync} onClick={() => {
        if (!sync) {
          const scale = active.current === 'left' ? leftScale : rightScale;
          const mode = active.current === 'left' ? leftZoomMode : rightZoomMode;
          setLeftScale(scale); setRightScale(scale);
          setLeftZoomMode(mode); setRightZoomMode(mode);
          setLeftPosition({ ...lastPosition.current }); setRightPosition({ ...lastPosition.current });
        } else { setLeftPosition(null); setRightPosition(null); }
        setSync(!sync);
      }} title="Đồng bộ vị trí đọc và thu phóng giữa bản gốc với bản dịch"
        className={'flex items-center gap-1.5 rounded-full border px-3 py-1 ' + (sync ? 'border-brand bg-brand/10 text-brand' : 'border-gray-300 text-gray-600')}>
        {sync ? <Link2 size={14} /> : <Unlink2 size={14} />}
        {sync ? 'Đồng bộ 2 khung: Bật' : 'Đồng bộ 2 khung: Tắt'}
      </button>
    </div>
    <div className={'grid gap-2 lg:gap-4 flex-1 min-h-0 min-w-0 ' + (mode === 'both' ? 'grid-cols-2' : 'grid-cols-1')}>
      {showLeft && <PdfViewerBox title="Tài liệu gốc (Original)" file={original} scale={leftScale}
        onScaleChange={(scale) => zoom('left', scale)} position={leftPosition}
        zoomMode={leftZoomMode} onZoomModeChange={(next) => setZoomMode('left', next)}
        onPositionChange={(position) => move('left', position)} />}
      {showRight && <PdfViewerBox title={'Tài liệu đã dịch (' + language.toUpperCase() + ')'} file={translated} scale={rightScale}
        onScaleChange={(scale) => zoom('right', scale)} position={rightPosition}
        zoomMode={rightZoomMode} onZoomModeChange={(next) => setZoomMode('right', next)}
        onPositionChange={(position) => move('right', position)} onDownload={translated ? onDownload : undefined} />}
    </div>
  </div>;
};
