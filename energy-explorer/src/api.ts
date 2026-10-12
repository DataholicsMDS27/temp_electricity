import type { CurveResponse, Metadata, PredictionResponse, Scenario } from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const timeout = AbortSignal.timeout(30000);
  let response: Response;
  try { response = await fetch(`${API_BASE}${path}`, { ...init, signal: timeout }); }
  catch { throw new Error('Could not reach the prediction service. Check that the backend is running, then try again.'); }
  if (!response.ok) {
    throw new Error(response.status === 422 ? 'These inputs are not supported by the model.' : 'The prediction service is unavailable. Please try again.');
  }
  return response.json();
}
export const getMetadata = () => request<Metadata>('/api/v1/metadata');
export const getPredictions = (scenario: Scenario) => request<PredictionResponse>('/api/v1/predictions', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(scenario),
});
export const getCurve = (scenario: Scenario, fsa: string | null) => {
  const params = new URLSearchParams({ day_type: scenario.day_type, hour: String(scenario.hour), customer_type: String(scenario.customer_type) });
  if (fsa) params.set('fsa', fsa);
  return request<CurveResponse>(`/api/v1/curve?${params}`);
};
