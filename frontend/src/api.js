// Centralized API client – all requests go through here
const BASE = import.meta.env.DEV ? '' : '';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || 'Request failed');
  }
  return res.json();
}

export const api = {
  health: () => request('/health'),
  modelInfo: () => request('/model/info'),
  modelMetrics: () => request('/model/metrics'),
  predict: (payload) =>
    request('/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  /** Upload a file for preview (first 5 rows + auto column mapping) */
  uploadPreview: (file) => {
    const form = new FormData();
    form.append('file', file);
    return request('/upload/preview', { method: 'POST', body: form });
  },

  /** Upload a file and score all transactions */
  uploadAndScore: (file, columnMapping) => {
    const form = new FormData();
    form.append('file', file);
    if (columnMapping) {
      form.append('mapping_json', JSON.stringify(columnMapping));
    }
    return request('/upload', { method: 'POST', body: form });
  },

  /** Deep autonomous investigation & SAR report generation */
  investigate: (transaction) =>
    request('/agent/investigate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(transaction),
    }),

  /** Interactive Compliance Copilot chat */
  chat: (payload) =>
    request('/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  /** Start automated transaction stream */
  startStream: (speedTps = 1.0) =>
    request(`/pipeline/stream/start?speed_tps=${speedTps}`, { method: 'POST' }),

  /** Stop automated transaction stream */
  stopStream: () => request('/pipeline/stream/stop', { method: 'POST' }),

  /** Reset stream stats and events */
  resetStream: () => request('/pipeline/stream/reset', { method: 'POST' }),

  /** Poll pipeline stream status and events */
  getStreamStatus: () => request('/pipeline/stream/status'),

  /** Process a batch through the agentic pipeline */
  processPipelineBatch: (transactions) =>
    request('/pipeline/process-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transactions }),
    }),
};

