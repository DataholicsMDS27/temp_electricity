export type DayType = 'weekday' | 'weekend';
export type Theme = 'light' | 'dark' | 'daylight';
export interface Scenario { temperature_c: number; day_type: DayType; hour: number }
export interface Prediction { fsa: string; value: number | null; status: 'ok' | 'unsupported' | 'unavailable' }
export interface PredictionResponse {
  request_id: string; scenario: Scenario; model_version: string; is_mock: boolean;
  boundary_version: string; metric: 'average_energy_per_customer'; unit: 'kWh';
  interval_minutes: number; time_convention: string; predictions: Prediction[];
}
export interface FsaEntry { fsa: string; bounds: [number, number, number, number] }
export interface FsaIndex { boundary_version: string; fsas: FsaEntry[] }
export interface Metadata {
  model_version: string; is_mock: boolean; supported_fsas: string[];
  temperature: { min: number; max: number; step: number };
  interval_minutes: number; unit: string; metric: string;
  time_convention: string; legend: { min: number; max: number };
}
export const hourLabel = (hour: number) => `${String(hour).padStart(2, '0')}:00`;
export const intervalLabel = (hour: number) => `${hourLabel(hour)}–${hourLabel((hour + 1) % 24)}`;
export const sameScenario = (a: Scenario, b: Scenario) => a.hour === b.hour && a.day_type === b.day_type && a.temperature_c === b.temperature_c;
