import { useEffect, useRef, useState } from 'react';
import { getCurve } from '../api';
import type { CurvePoint, Scenario } from '../types';
import { intervalLabel } from '../types';

const W = 270, H = 96, L = 30, R = 8, T = 10, B = 20;

interface Props { scenario: Scenario; fsa: string | null }

// Consumption against temperature for the chosen hour, with the current temperature marked.
export function TempCurve({ scenario, fsa }: Props) {
  const [points, setPoints] = useState<CurvePoint[] | null>(null);
  const cache = useRef(new Map<string, CurvePoint[]>());
  const { day_type, hour, customer_type, temperature_c } = scenario;

  useEffect(() => {
    const key = `${day_type}|${hour}|${customer_type}|${fsa ?? ''}`;
    const hit = cache.current.get(key);
    if (hit) { setPoints(hit); return; }
    let active = true;
    // Short delay so dragging the hour slider does not fire a request per step.
    const timer = window.setTimeout(() => {
      getCurve({ day_type, hour, customer_type, temperature_c: 0 }, fsa)
        .then((r) => { cache.current.set(key, r.points); if (active) setPoints(r.points); })
        .catch(() => { if (active) setPoints(null); });
    }, 120);
    return () => { active = false; window.clearTimeout(timer); };
  }, [day_type, hour, customer_type, fsa]);

  if (!points || points.length < 2) return null;

  const values = points.map((p) => p.value);
  const lo = Math.min(...values), hi = Math.max(...values);
  const pad = (hi - lo) * 0.12 || 0.1;
  const yMin = Math.max(0, lo - pad), yMax = hi + pad;
  const tMin = points[0].temperature_c, tMax = points[points.length - 1].temperature_c;
  const x = (t: number) => L + ((t - tMin) / (tMax - tMin)) * (W - L - R);
  const y = (v: number) => T + (1 - (v - yMin) / (yMax - yMin)) * (H - T - B);
  const path = points.map((p, i) => `${i ? 'L' : 'M'}${x(p.temperature_c).toFixed(1)} ${y(p.value).toFixed(1)}`).join(' ');
  const here = points.find((p) => p.temperature_c === temperature_c);
  const low = points.reduce((a, b) => (b.value < a.value ? b : a));

  return <section className="curve-section" aria-label="Consumption across temperatures">
    <div className="section-label">
      <span>Across temperatures</span>
      <span className="tiny-tag">{fsa ?? 'TYPICAL FSA'}</span>
    </div>
    <svg viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Consumption for ${intervalLabel(hour)}: lowest near ${low.temperature_c} degrees, ${low.value.toFixed(1)} kilowatt-hours.`}>
      <line className="curve-grid" x1={L} x2={W - R} y1={y(lo)} y2={y(lo)} />
      <line className="curve-grid" x1={L} x2={W - R} y1={y(hi)} y2={y(hi)} />
      {tMin < 0 && tMax > 0 && <line className="curve-grid" x1={x(0)} x2={x(0)} y1={T} y2={H - B} />}
      <path className="curve-line" d={path} />
      {here && <>
        <line className="curve-marker-line" x1={x(here.temperature_c)} x2={x(here.temperature_c)} y1={y(here.value)} y2={H - B} />
        <circle className="curve-marker" cx={x(here.temperature_c)} cy={y(here.value)} r="4" />
      </>}
      <text className="curve-text" x={L - 5} y={y(hi) + 3} textAnchor="end">{hi.toFixed(1)}</text>
      <text className="curve-text" x={L - 5} y={y(lo) + 3} textAnchor="end">{lo.toFixed(1)}</text>
      {[tMin, 0, tMax].map((t) => <text key={t} className="curve-text" x={x(t)} y={H - 5} textAnchor="middle">{t}°</text>)}
    </svg>
    <p className="curve-caption">
      {here ? `${here.value.toFixed(2)} kWh at ${temperature_c}°` : ''}
      {here ? ' · ' : ''}lowest near {low.temperature_c}°
    </p>
  </section>;
}
