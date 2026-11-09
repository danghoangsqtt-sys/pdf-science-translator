import axios from 'axios';

export const API_BASE_URL = window.pdftranslate?.apiBaseUrl || 'http://127.0.0.1:8089/api';
export const API_TOKEN_HEADER = 'X-PDFTranslate-Token';
export const POLL_INTERVAL_MS = 750;
// While a status request keeps failing, wait longer between tries, up to this.
export const POLL_MAX_BACKOFF_MS = 5000;
// Stop following a job only after the backend has not answered for this long.
// Finishing a large PDF can hold the backend for tens of seconds.
export const POLL_GIVE_UP_MS = 120000;

/** How a failed request should be treated by a caller that is polling. */
export type RequestFailure = 'transient' | 'not_found' | 'other';

export const classifyRequestError = (error: unknown): RequestFailure => {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    if (status === 404) return 'not_found';
    // No response at all: timeout, refused connection, backend restarting.
    if (status === undefined || status === 408 || status === 429 || status >= 500) {
      return 'transient';
    }
  }
  return 'other';
};

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
  profile?: ProcessingProfile;
  error_code?: string | null;
  translated_ratio?: number | null;
  segments?: JobSegments | null;
  warnings?: string[];
}

export type ProcessingProfile = 'fast' | 'balanced' | 'quality';
export interface ProfileInfo {
  id: ProcessingProfile;
  label: string;
  description: string;
  available: boolean;
  reason_code?: string | null;
  message: string;
}
export interface CapabilitiesResponse {
  offline: boolean;
  default_profile: ProcessingProfile;
  profiles: ProfileInfo[];
}

// Electron's preload supplies a per-launch token. Only a Vite dev build falls
// back to the dev token, which the backend accepts only with PDFTRANSLATE_DEV=1.
const getApiToken = (): string => {
  return window.pdftranslate?.apiToken || (import.meta.env.DEV ? 'dev-token' : '');
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

export const fetchCapabilities = async (): Promise<CapabilitiesResponse> => {
  const res = await axios.get<CapabilitiesResponse>(`${API_BASE_URL}/capabilities`, {
    headers: authHeaders(), timeout: 10000,
  });
  return res.data;
};

export const createTranslationJob = async (
  file: File,
  targetLanguage: string = 'vi',
  domain: string = '',
  profile: ProcessingProfile = 'balanced',
): Promise<{ job_id: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('target_language', targetLanguage);
  // Empty string means "no domain selected" - the backend treats it the
  // same as omitting the field entirely (see webui/backend/main.py).
  if (domain) {
    formData.append('domain', domain);
  }
  formData.append('profile', profile);

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
