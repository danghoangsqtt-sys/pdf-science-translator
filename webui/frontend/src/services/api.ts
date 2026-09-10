import axios from 'axios';

export const API_BASE_URL = 'http://127.0.0.1:8089/api';
export const API_TOKEN_HEADER = 'X-PDFTranslate-Token';
export const POLL_INTERVAL_MS = 750;

export interface JobProgress {
  done: number;
  total: number;
}

export interface JobStatusResponse {
  status: 'queued' | 'running' | 'complete' | 'error';
  progress: JobProgress;
  error?: string | null;
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

export const createTranslationJob = async (
  file: File,
  targetLanguage: string = 'vi',
  domain: string = '',
): Promise<{ job_id: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('target_language', targetLanguage);
  // Empty string means "no domain selected" - the backend treats it the
  // same as omitting the field entirely (see webui/backend/main.py).
  if (domain) {
    formData.append('domain', domain);
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

export const fetchJobResultBlob = async (jobId: string): Promise<Blob> => {
  const res = await axios.get(`${API_BASE_URL}/jobs/${jobId}/result`, {
    headers: authHeaders(),
    responseType: 'blob',
    timeout: 60000,
  });
  return res.data;
};
