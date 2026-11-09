import React, { useRef, useState } from 'react';
import { Link2, Unlink2 } from 'lucide-react';
import { PdfViewerBox } from './PdfViewerBox.tsx';
import type { ReadingPosition } from './pdfViewport.ts';

interface Props {
  original: File;
  translated: Blob | null;
  language: string;
  onDownload: () => void;
}
export const PdfComparison: React.FC<Props> = ({ original, translated, language, onDownload }) => {
  const [sync, setSync] = useState(true);
  const [leftScale, setLeftScale] = useState(1);
  const [rightScale, setRightScale] = useState(1);
  const [leftPosition, setLeftPosition] = useState<ReadingPosition | null>(null);
  const [rightPosition, setRightPosition] = useState<ReadingPosition | null>(null);
  const active = useRef<'left' | 'right'>('left');
  const lastPosition = useRef<ReadingPosition>({ page: 1, offset: 0, x: 0 });

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
  return <div className="flex flex-col h-full min-h-0">
    <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 pb-2 text-xs text-gray-500">
      <span>Cuộn để đọc · Ctrl + lăn chuột để thu phóng · Giữ chuột trái để kéo</span>
      <button type="button" aria-pressed={sync} onClick={() => {
        if (!sync) {
          const scale = active.current === 'left' ? leftScale : rightScale;
          setLeftScale(scale); setRightScale(scale);
          setLeftPosition({ ...lastPosition.current }); setRightPosition({ ...lastPosition.current });
        } else { setLeftPosition(null); setRightPosition(null); }
        setSync(!sync);
      }} title="Đồng bộ vị trí đọc và thu phóng giữa bản gốc với bản dịch"
        className={'flex items-center gap-1.5 rounded-full border px-3 py-1 ' + (sync ? 'border-brand bg-brand/10 text-brand' : 'border-gray-300 text-gray-600')}>
        {sync ? <Link2 size={14} /> : <Unlink2 size={14} />}
        {sync ? 'Đồng bộ 2 khung: Bật' : 'Đồng bộ 2 khung: Tắt'}
      </button>
    </div>
    <div className="grid grid-cols-2 gap-4 flex-1 min-h-0 min-w-0">
      <PdfViewerBox title="Tài liệu gốc (Original)" file={original} scale={leftScale}
        onScaleChange={(scale) => zoom('left', scale)} position={leftPosition}
        onPositionChange={(position) => move('left', position)} />
      <PdfViewerBox title={'Tài liệu đã dịch (' + language.toUpperCase() + ')'} file={translated} scale={rightScale}
        onScaleChange={(scale) => zoom('right', scale)} position={rightPosition}
        onPositionChange={(position) => move('right', position)} onDownload={translated ? onDownload : undefined} />
    </div>
  </div>;
};

