import React from 'react';
import { AlertTriangle } from 'lucide-react';
import type { JobStatusResponse } from '../services/api.ts';

interface TranslationWarningBannerProps {
  result: JobStatusResponse;
}

/**
 * Yellow banner for a delivered but partial translation. A result that left
 * text in the source language must say so, with how much and why, instead
 * of looking finished.
 */
export const TranslationWarningBanner: React.FC<TranslationWarningBannerProps> = ({ result }) => {
  const ratio = result.translated_ratio ?? 1;
  const warnings = result.warnings ?? [];
  if (ratio >= 1 && warnings.length === 0) return null;

  const percent = Math.floor(ratio * 100);
  const segments = result.segments;
  const mostlyUntranslated = result.status === 'complete_with_warnings';

  return (
    <div
      role="status"
      className="mt-3 p-3 bg-yellow-50 border border-yellow-400 rounded-md text-xs text-yellow-900"
    >
      <div className="flex items-center gap-2 font-semibold text-sm">
        <AlertTriangle size={16} className="text-yellow-600 shrink-0" />
        <span>
          Đã dịch {percent}%
          {segments ? ` (${segments.translated}/${segments.total} đoạn)` : ''}
          {mostlyUntranslated
            ? ' – phần lớn tài liệu vẫn là bản gốc.'
            : ' – một phần tài liệu vẫn là bản gốc.'}
        </span>
      </div>
      {warnings.length > 0 && (
        <ul className="mt-2 ml-6 list-disc space-y-0.5 leading-relaxed">
          {warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
    </div>
  );
};
