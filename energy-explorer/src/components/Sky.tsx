import type { CSSProperties } from 'react';

export function skyPeriod(hour: number) {
  if (hour < 5 || hour >= 21) return 'night';
  if (hour < 8) return 'dawn';
  if (hour < 16) return 'day';
  if (hour < 19) return 'sunset';
  return 'dusk';
}

export function Sky({ hour }: { hour: number }) {
  const night = hour < 6 || hour >= 18;
  const bodyStyle = (active: boolean, progress: number) => ({
    '--celestial-x': active ? `${8 + progress * 80}%` : 'calc(100% + 80px)',
    '--celestial-y': `${active ? (1 - Math.sin(progress * Math.PI)) * 14 : 14}px`,
  }) as CSSProperties;
  return <div className={`sky sky-${skyPeriod(hour)}`} aria-hidden="true">
    <div className="sky-stars">{Array.from({ length: 35 }, (_, i) => <i key={i} style={{ left: `${(i * 37 + 9) % 100}%`, top: `${(i * 19 + 4) % 78}%`, animationDelay: `${i % 5}s` }} />)}</div>
    <div className={`celestial pixel-sun${!night ? ' celestial-active' : ''}`} style={bodyStyle(!night, (hour - 6) / 12)} />
    <div className={`celestial pixel-moon${night ? ' celestial-active' : ''}`} style={bodyStyle(night, ((hour + 6) % 24) / 12)} />
    <div className="pixel-cloud cloud-one" /><div className="pixel-cloud cloud-two" /><div className="pixel-cloud cloud-three" />
    <div className="pixel-horizon horizon-back" /><div className="pixel-horizon horizon-front" />
  </div>;
}
