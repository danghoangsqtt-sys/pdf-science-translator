import React, { useState } from 'react';
import { CheckCircle2, AlertTriangle, RefreshCw, Copy, Check } from 'lucide-react';
import type { EnginesResponse, OllamaState } from '../services/api.ts';

const FALLBACK_ENGINES = [
  { id: 'ollama', label: 'Ngoại tuyến (Ollama)' },
  { id: 'azure', label: 'Azure' },
  { id: 'google', label: 'Google (dự phòng)' },
];

const MODEL_LABELS: Record<string, string> = {
  'translategemma:12b': 'TranslateGemma 12B (chất lượng cao)',
  'translategemma:4b': 'TranslateGemma 4B (máy yếu)',
};

const STATE_TITLES: Record<OllamaState, string> = {
  ready: 'Ollama sẵn sàng',
  not_installed: 'Chưa cài Ollama',
  not_running: 'Ollama chưa chạy',
  model_missing: 'Chưa tải mô hình',
};

interface EnginePickerProps {
  engine: string;
  model: string;
  info: EnginesResponse | null;
  checking: boolean;
  disabled: boolean;
  onEngineChange: (engine: string) => void;
  onModelChange: (model: string) => void;
  onRefresh: () => void;
}

const selectClass =
  'text-sm bg-white border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-[#14452F] disabled:opacity-50 font-medium';

export const EnginePicker: React.FC<EnginePickerProps> = ({
  engine,
  model,
  info,
  checking,
  disabled,
  onEngineChange,
  onModelChange,
  onRefresh,
}) => {
  const engines = info?.engines ?? FALLBACK_ENGINES;
  const ollama = info?.ollama;
  const models = ollama?.models ?? Object.keys(MODEL_LABELS);

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="engine" className="text-xs font-semibold text-gray-600">
        Bộ dịch:
      </label>
      <select
        id="engine"
        value={engine}
        onChange={(e) => onEngineChange(e.target.value)}
        disabled={disabled}
        className={selectClass}
      >
        {engines.map((item) => (
          <option key={item.id} value={item.id}>
            {item.label}
          </option>
        ))}
      </select>
      {engine === 'ollama' && (
        <select
          id="ollama-model"
          aria-label="Mô hình Ollama"
          value={model}
          onChange={(e) => onModelChange(e.target.value)}
          disabled={disabled}
          className={selectClass}
        >
          {models.map((name) => (
            <option key={name} value={name}>
              {MODEL_LABELS[name] ?? name}
              {ollama && !ollama.installed_models.includes(name) ? ' – chưa tải' : ''}
            </option>
          ))}
        </select>
      )}
      {engine === 'ollama' && (
        <button
          type="button"
          onClick={onRefresh}
          disabled={checking}
          title="Kiểm tra lại trạng thái Ollama"
          className="p-1.5 text-gray-500 hover:text-[#14452F] rounded-md hover:bg-gray-100 disabled:opacity-50"
        >
          <RefreshCw size={14} className={checking ? 'animate-spin' : ''} />
        </button>
      )}
    </div>
  );
};

interface RemoteEngineNoticeProps {
  engine: string;
  info: EnginesResponse | null;
}

/** Azure: configured or how to configure it. Google: what the fallback risks. */
export const RemoteEngineNotice: React.FC<RemoteEngineNoticeProps> = ({ engine, info }) => {
  if (engine === 'google') {
    return (
      <div className="mt-3 flex items-start gap-2 text-xs text-amber-800">
        <AlertTriangle size={14} className="text-amber-600 shrink-0 mt-0.5" />
        <span>
          Google là dịch vụ web miễn phí, dùng làm dự phòng: tài liệu được gửi qua Internet và
          Google có thể tạm chặn máy khi dịch nhiều trang. Khi bị chặn, ứng dụng dừng ngay và báo
          lỗi.
        </span>
      </div>
    );
  }
  if (engine !== 'azure' || !info) return null;
  const azure = info.azure;
  if (azure.configured) {
    return (
      <div className="mt-3 flex items-center gap-2 text-xs text-emerald-700">
        <CheckCircle2 size={14} />
        <span>
          {azure.message}
          {azure.region ? ` Vùng: ${azure.region}.` : ''} Tài liệu được gửi tới Azure qua
          Internet.
        </span>
      </div>
    );
  }
  return (
    <div className="mt-3 p-3 bg-amber-50 border border-amber-300 rounded-md text-xs text-amber-900">
      <div className="flex items-center gap-2 font-semibold">
        <AlertTriangle size={14} className="text-amber-600" />
        <span>Chưa cấu hình khóa Azure Translator</span>
      </div>
      <ol className="mt-2 ml-5 list-decimal space-y-1 leading-relaxed">
        <li>Tạo tài nguyên Translator trên Azure Portal và lấy khóa (Key) cùng vùng (Region).</li>
        <li>
          Đặt biến môi trường <code className="font-mono">{azure.key_env}</code> và{' '}
          <code className="font-mono">{azure.region_env}</code>, hoặc tạo tệp{' '}
          <code className="font-mono break-all">{azure.config_path}</code> với nội dung{' '}
          <code className="font-mono">{'{"azure": {"key": "...", "region": "..."}}'}</code>.
        </li>
        <li>Khởi động lại ứng dụng.</li>
      </ol>
    </div>
  );
};

interface OllamaStatusNoticeProps {
  info: EnginesResponse | null;
}

/** One line when Ollama is ready; what to do, step by step, when it is not. */
export const OllamaStatusNotice: React.FC<OllamaStatusNoticeProps> = ({ info }) => {
  const [copied, setCopied] = useState(false);
  if (!info) return null;
  const ollama = info.ollama;

  if (ollama.ready) {
    return (
      <div className="mt-3 flex items-center gap-2 text-xs text-emerald-700">
        <CheckCircle2 size={14} />
        <span>
          {STATE_TITLES.ready} – dịch ngoại tuyến bằng <b>{ollama.model}</b>, không gửi tài liệu
          ra Internet.
        </span>
      </div>
    );
  }

  const copyCommand = async () => {
    try {
      await navigator.clipboard.writeText(ollama.pull_command);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="mt-3 p-3 bg-amber-50 border border-amber-300 rounded-md text-xs text-amber-900">
      <div className="flex items-center gap-2 font-semibold">
        <AlertTriangle size={14} className="text-amber-600" />
        <span>{STATE_TITLES[ollama.state]}</span>
      </div>
      <ol className="mt-2 ml-5 list-decimal space-y-1 leading-relaxed">
        {ollama.state === 'not_installed' && (
          <li>
            Tải và cài Ollama tại{' '}
            <a
              href={ollama.download_url}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => {
                // Inside Electron, open the system browser instead of a new app window.
                if (window.pdftranslate?.openExternal) {
                  e.preventDefault();
                  window.pdftranslate.openExternal(ollama.download_url);
                }
              }}
              className="underline font-medium"
            >
              {ollama.download_url}
            </a>
            .
          </li>
        )}
        {ollama.state !== 'model_missing' && (
          <li>Mở ứng dụng Ollama (biểu tượng con lạc đà ở khay hệ thống).</li>
        )}
        <li>
          {ollama.state === 'model_missing'
            ? 'Mở cửa sổ dòng lệnh và chạy '
            : 'Nếu chưa tải mô hình: mở cửa sổ dòng lệnh và chạy '}
          <code className="bg-white border border-amber-300 rounded px-1.5 py-0.5 font-mono">
            {ollama.pull_command}
          </code>{' '}
          <button
            type="button"
            onClick={copyCommand}
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-amber-300 bg-white hover:bg-amber-100 align-middle"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? 'Đã chép' : 'Chép lệnh'}
          </button>
        </li>
        <li>Bấm nút làm mới bên cạnh ô chọn mô hình để kiểm tra lại.</li>
      </ol>
      <p className="mt-2 text-amber-800/80">
        Hoặc chọn bộ dịch khác ở ô "Bộ dịch" – khi đó tài liệu sẽ được gửi qua Internet.
      </p>
    </div>
  );
};
