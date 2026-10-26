import axios from 'axios';

export const API_BASE_URL = 'http://127.0.0.1:8089/api';
export const API_TOKEN_HEADER = 'X-PDFTranslate-Token';
export const POLL_INTERVAL_MS = 750;

export interface JobProgress {
  done: number;
  total: number;
}

export type JobStatus =
  | 'queued'
  | 'running'
  | 'complete'
  | 'complete_with_warnings'
  | 'cancelled'
  | 'error';

export interface JobSegments {
  total: number;
  translated: number;
  // service: engine failed; formula: markers damaged; fit: did not fit its
  // region; too_long: longer than one request may carry.
  kept: { service: number; formula: number; fit: number; too_long: number };
}

export interface JobStatusResponse {
  status: JobStatus;
  progress: JobProgress;
  error?: string | null;
  engine?: string;
  model?: string | null;
  translated_ratio?: number | null;
  segments?: JobSegments | null;
  warnings?: string[];
}

export type OllamaState = 'ready' | 'not_installed' | 'not_running' | 'model_missing';

export interface OllamaInfo {
  state: OllamaState;
  ready: boolean;
  model: string;
  base_url: string;
  message: string;
  pull_command: string;
  download_url: string;
  models: string[];
  installed_models: string[];
}

export interface EnginesResponse {
  default: string;
  engines: { id: string; label: string }[];
  ollama: OllamaInfo;
}

const getApiToken = (): string => {
  return window.pdftranslate?.apiToken || 'dev-token';
};

const authHeaders = () => ({
  [API_TOKEN_HEADER]: getApiToken(),
});

export const checkHealth = async (): Promise<{ status: string }> => {
  const res = await axios.get<{ status: string }>(`${API_BASE_URL}/health`, {
    timeout: 3000,
  });
  return res.data;
};

export const fetchEngines = async (model: string = ''): Promise<EnginesResponse> => {
  const res = await axios.get<EnginesResponse>(`${API_BASE_URL}/engines`, {
    headers: authHeaders(),
    params: model ? { model } : undefined,
    timeout: 10000,
  });
  return res.data;
};

export const createTranslationJob = async (
  file: File,
  targetLanguage: string = 'vi',
  domain: string = '',
  engine: string = 'ollama',
  model: string = '',
): Promise<{ job_id: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('target_language', targetLanguage);
  // Empty string means "no domain selected" - the backend treats it the
  // same as omitting the field entirely (see webui/backend/main.py).
  if (domain) {
    formData.append('domain', domain);
  }
  formData.append('engine', engine);
  // Only Ollama has a model choice; the backend refuses one for other engines.
  if (engine === 'ollama' && model) {
    formData.append('model', model);
  }

  const res = await axios.post<{ job_id: string }>(`${API_BASE_URL}/jobs`, formData, {
    headers: {
      ...authHeaders(),
      'Content-Type': 'multipart/form-data',
    },
    timeout: 30000,
  });

  return res.data;
};

export const fetchJobStatus = async (jobId: string): Promise<JobStatusResponse> => {
  const res = await axios.get<JobStatusResponse>(`${API_BASE_URL}/jobs/${jobId}`, {
    headers: authHeaders(),
    timeout: 10000,
  });
  return res.data;
};

export const cancelTranslationJob = async (jobId: string): Promise<JobStatusResponse> => {
  const res = await axios.post<JobStatusResponse>(
    `${API_BASE_URL}/jobs/${jobId}/cancel`,
    null,
    { headers: authHeaders(), timeout: 10000 },
  );
  return res.data;
};

export const fetchJobResultBlob = async (jobId: string): Promise<Blob> => {
  const res = await axios.get(`${API_BASE_URL}/jobs/${jobId}/result`, {
    headers: authHeaders(),
    responseType: 'blob',
    timeout: 60000,
  });
  return res.data;
};
