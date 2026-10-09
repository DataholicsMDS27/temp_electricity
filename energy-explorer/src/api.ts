import type { Metadata, PredictionResponse, Scenario } from './types';

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
