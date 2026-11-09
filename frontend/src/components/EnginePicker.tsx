import React from 'react';
import { CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react';
import type { CapabilitiesResponse, ProcessingProfile } from '../services/api.ts';

const LEVELS = [
  { id: 'fast', label: 'Nhanh', description: 'Ưu tiên tốc độ, ít tài nguyên.' },
  { id: 'balanced', label: 'Cân bằng', description: 'Cân bằng thời gian và độ đầy đủ.' },
  { id: 'quality', label: 'Chất lượng cao', description: 'Xử lý kỹ hơn, có thể chậm hơn.' },
] as const;

interface Props {
  profile: ProcessingProfile;
  info: CapabilitiesResponse | null;
  checking: boolean;
  disabled: boolean;
  onChange: (profile: ProcessingProfile) => void;
  onRefresh: () => void;
}

export const ProfilePicker: React.FC<Props> = ({ profile, info, checking, disabled, onChange, onRefresh }) => (
  <div className="flex items-center gap-2">
    <label htmlFor="processing-profile" className="sr-only xl:not-sr-only text-xs font-semibold text-gray-600">Mức xử lý:</label>
    <select id="processing-profile" aria-label="Mức xử lý" title="Mức xử lý" value={profile}
      onChange={event => onChange(event.target.value as ProcessingProfile)} disabled={disabled}
      className="w-32 xl:w-auto text-sm bg-white border border-gray-300 rounded-md px-2 py-1.5 lg:px-3 focus:outline-none focus:ring-2 focus:ring-[#14452F] disabled:opacity-50 font-medium">
      {LEVELS.map(level => {
        const state = info?.profiles.find(item => item.id === level.id);
        return <option key={level.id} value={level.id}>{level.label}{state && !state.available ? ' — chưa sẵn sàng' : ''}</option>;
      })}
    </select>
    <button type="button" onClick={onRefresh} disabled={checking || disabled}
      title="Kiểm tra dữ liệu cục bộ" className="p-1.5 text-gray-500 rounded-md hover:bg-gray-100 disabled:opacity-50">
      <RefreshCw size={14} className={checking ? 'animate-spin' : ''} />
    </button>
  </div>
);

export const LocalStatusNotice: React.FC<{info: CapabilitiesResponse | null; profile: ProcessingProfile}> = ({info, profile}) => {
  const level = info?.profiles.find(item => item.id === profile);
  if (!level) return <p role="status" className="mt-2 lg:mt-3 text-xs text-gray-600">Đang kiểm tra dữ liệu cục bộ…</p>;
  return <div role="status" className={'mt-2 lg:mt-3 flex items-start gap-2 text-xs ' + (level.available ? 'text-emerald-700 short:hidden' : 'text-amber-800')}>
    {level.available ? <CheckCircle2 size={14} className="shrink-0" /> : <AlertTriangle size={14} className="shrink-0" />}
    <span>{level.available ? 'Sẵn sàng · Xử lý hoàn toàn trên máy. ' + level.description : level.message}
      {!level.available && level.reason_code && <span className="block mt-1">Mã hỗ trợ: {level.reason_code}</span>}
    </span>
  </div>;
};
