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
};
