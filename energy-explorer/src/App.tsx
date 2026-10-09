import { useEffect, useRef, useState } from 'react';
import * as Slider from '@radix-ui/react-slider';
import * as RadioGroup from '@radix-ui/react-radio-group';
import * as Dialog from '@radix-ui/react-dialog';
import { ArrowRight, ArrowUpRight, Check, CircleHelp, CloudSun, FlaskConical, LoaderCircle, Moon, Search, Sun, Thermometer, X, Zap, CalendarDays, RotateCcw } from 'lucide-react';
import type { FeatureCollection, Geometry } from 'geojson';
import { EnergyMap } from './components/EnergyMap';
import { TimeWheel } from './components/TimeWheel';
import { Sky, skyPeriod } from './components/Sky';
import { getMetadata, getPredictions } from './api';
import { intervalLabel, sameScenario, type FsaEntry, type FsaIndex, type Metadata, type PredictionResponse, type Scenario, type Theme } from './types';

const INITIAL: Scenario = { temperature_c: 22, day_type: 'weekday', hour: 14 };
const themes = [{ value: 'light', label: 'Light', Icon: Sun }, { value: 'dark', label: 'Dark', Icon: Moon }, { value: 'daylight', label: 'Daylight', Icon: CloudSun }] as const;
const temperatureDescription = (temperature: number) => temperature < 0 ? 'A little on the cold side.' : temperature < 15 ? 'A cooler kind of day.' : temperature < 26 ? 'A comfortable kind of day.' : 'Turning up the heat.';
function storedTheme(): Theme {
  try { const t = localStorage.getItem('energy-theme'); return t === 'dark' || t === 'daylight' ? t : 'light'; } catch { return 'light'; }
}

export default function App() {
  const [theme, setTheme] = useState<Theme>(storedTheme);
  const [scenario, setScenario] = useState<Scenario>(INITIAL);
  const [geometry, setGeometry] = useState<FeatureCollection<Geometry, { fsa: string }> | null>(null);
  const [index, setIndex] = useState<FsaEntry[]>([]);
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dataError, setDataError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const [info, setInfo] = useState(false);
  const [temperatureDraft, setTemperatureDraft] = useState<string | null>(null);
  const requestInFlight = useRef(false);
  const appRef = useRef<HTMLDivElement>(null);
  const dark = theme === 'dark' || (theme === 'daylight' && (scenario.hour < 6 || scenario.hour >= 18));
  const dirty = result !== null && !sameScenario(scenario, result.scenario);
  const temperature = metadata?.temperature ?? { min: -40, max: 35, step: 1 };
  const legend = metadata?.legend ?? { min: 0, max: 4 };
  const filtered = search.trim() ? index.filter(f => f.fsa.startsWith(search.trim().toUpperCase())).slice(0, 7) : [];
  const selectedEntry = index.find(f => f.fsa === selected) ?? null;
  const visibleMock = result?.is_mock ?? metadata?.is_mock;

  useEffect(() => { try { localStorage.setItem('energy-theme', theme); } catch { /* unavailable storage does not affect theme */ } }, [theme]);
  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const [geo, idx] = await Promise.all([fetch('/data/ontario-fsas.geojson').then(r => { if (!r.ok) throw new Error(); return r.json(); }), fetch('/data/fsa-index.json').then(r => { if (!r.ok) throw new Error(); return r.json() as Promise<FsaIndex>; })]);
        if (active) { setGeometry(geo); setIndex(idx.fsas); }
      } catch { if (active) setDataError('Ontario boundaries could not load. Refresh the page to try again.'); }
    };
    void load();
    getMetadata().then(m => { if (active) setMetadata(m); }).catch(() => { /* Predict displays actionable service errors */ });
    return () => { active = false; };
  }, []);

  const submit = async () => {
    if (requestInFlight.current) return;
    requestInFlight.current = true; setPending(true); setError(null);
    try {
      const submitted = { ...scenario };
      if (!metadata) setMetadata(await getMetadata());
      const prediction = await getPredictions(submitted);
      setResult(prediction);
    } catch (e) { setError(e instanceof Error ? e.message : 'Prediction failed. Please try again.'); }
    finally { requestInFlight.current = false; setPending(false); }
  };
  const selectFsa = (fsa: string) => { setSelected(fsa); setSearch(''); setSearchFocused(false); };
  const commitTemperature = () => {
    if (temperatureDraft !== null && temperatureDraft.trim() && Number.isFinite(Number(temperatureDraft))) {
      setScenario(s => ({ ...s, temperature_c: Math.max(temperature.min, Math.min(temperature.max, Math.round(Number(temperatureDraft)))) }));
    }
    setTemperatureDraft(null);
  };

  return <div ref={appRef} className={`app ${dark ? 'theme-dark' : 'theme-light'} mode-${theme}`} data-theme={theme} data-hour={scenario.hour}>
    {theme === 'daylight' && <Sky hour={scenario.hour} />}
    <header className="app-header">
      <a className="brand" href="/" aria-label="Ontario Energy Explorer home"><span className="brand-mark"><Zap size={21} fill="currentColor" /></span><span><strong>Ontario<span className="brand-dot">.</span></strong><span className="brand-subtitle">Energy Explorer</span></span></a>
      <div className="header-middle"><span className="province-dot" /> A province of possibilities.</div>
      <div className="header-actions">
        <RadioGroup.Root className="theme-selector" value={theme} onValueChange={v => setTheme(v as Theme)} aria-label="Appearance">
          {themes.map(({ value, label, Icon }) => <RadioGroup.Item key={value} value={value} className="theme-option" aria-label={`${label} mode`}><Icon size={15} />{label}</RadioGroup.Item>)}
        </RadioGroup.Root>
        <button className="info-button" aria-label="About this explorer" onClick={() => setInfo(true)}><CircleHelp size={19} /></button>
      </div>
    </header>
    <main className="workspace">
      <aside className="scenario-panel" aria-label="Scenario controls">
        <div className="panel-heading"><div className="eyebrow">YOUR SCENARIO</div><h1>What if?</h1><p>A temperature. A moment.<br />An energy picture of Ontario.</p></div>
        <section className="input-section temperature-section" aria-labelledby="temperature-label">
          <div className="section-label"><span id="temperature-label"><Thermometer size={15} /> Temperature</span></div>
          <div className="temperature-value"><input aria-label="Temperature in degrees Celsius" type="number" min={temperature.min} max={temperature.max} step={temperature.step} value={temperatureDraft ?? scenario.temperature_c} onChange={e => setTemperatureDraft(e.target.value)} onBlur={commitTemperature} onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur(); }} /><span>°C</span></div>
          <Slider.Root className="temperature-slider" aria-label="Temperature" min={temperature.min} max={temperature.max} step={temperature.step} value={[scenario.temperature_c]} onValueChange={([value]) => { setTemperatureDraft(null); setScenario(s => ({ ...s, temperature_c: value })); }}>
            <Slider.Track className="slider-track"><Slider.Range className="slider-range" /></Slider.Track><Slider.Thumb className="slider-thumb" />
          </Slider.Root>
          <div className="slider-labels"><span>{temperature.min}°</span><span>0°</span><span>{temperature.max}°</span></div>
          <p className="temperature-description">{temperatureDescription(scenario.temperature_c)}</p>
        </section>
        <section className="input-section" aria-labelledby="day-label">
          <div className="section-label"><span id="day-label"><CalendarDays size={15} /> Day type</span></div>
          <RadioGroup.Root className="day-selector" value={scenario.day_type} onValueChange={v => setScenario(s => ({ ...s, day_type: v as Scenario['day_type'] }))} aria-label="Day type">
            <RadioGroup.Item className="day-option" value="weekday">Weekday</RadioGroup.Item><RadioGroup.Item className="day-option" value="weekend">Weekend</RadioGroup.Item>
          </RadioGroup.Root>
        </section>
        <TimeWheel hour={scenario.hour} onChange={hour => setScenario(s => ({ ...s, hour }))} />
        <div className="scenario-submit">
          <button className="predict-button" onClick={() => void submit()} disabled={pending || !geometry}><span>{pending ? <LoaderCircle className="spin" size={17} /> : <Zap size={17} />}{pending ? 'Predicting…' : 'Predict consumption'}</span>{!pending && <ArrowRight size={18} />}</button>
          <div className={`prediction-status ${dirty ? 'is-dirty' : ''}`} role="status">{pending ? 'Calculating your scenario' : dirty ? 'Inputs changed · update prediction' : result ? <><Check size={13} /> Scenario up to date</> : 'One scenario. Every Ontario FSA.'}</div>
          {error && <div className="api-error" role="alert">{error}<button onClick={() => void submit()}>Try again <RotateCcw size={13} /></button></div>}
        </div>
        <div className="sidebar-footer"><FlaskConical size={16} /><p>A what-if explorer.<br /><span>One temperature across Ontario.</span></p></div>
      </aside>
      <section className="map-panel" aria-label="Ontario consumption map">
        <div className="map-toolbar">
          <div className="map-heading"><span className="eyebrow">THE BIG PICTURE</span><h2>Ontario, hour by hour<span className="map-title-dot">.</span></h2></div>
          <div className="fsa-search">
            <Search size={17} />
            <input aria-label="Search FSA" placeholder="Find an FSA, e.g. M5V" value={search} onChange={e => setSearch(e.target.value.toUpperCase().slice(0, 3))} onFocus={() => setSearchFocused(true)} onBlur={() => window.setTimeout(() => setSearchFocused(false), 150)} onKeyDown={e => { if (e.key === 'Enter' && filtered.length) selectFsa(filtered[0].fsa); if (e.key === 'Escape') { setSearch(''); setSearchFocused(false); } }} />
            {search && <button aria-label="Clear search" onClick={() => setSearch('')}><X size={14} /></button>}
            {searchFocused && search && <div className="search-results">{filtered.length ? filtered.map(f => <button key={f.fsa} onMouseDown={e => e.preventDefault()} onClick={() => selectFsa(f.fsa)}><span>{f.fsa}</span><span>View area <ArrowUpRight size={14} /></span></button>) : <p>No matching Ontario FSA.</p>}</div>}
          </div>
        </div>
        <div className="map-canvas">
          {geometry ? <EnergyMap geometry={geometry} dark={dark} result={result} selected={selectedEntry} onSelect={setSelected} legend={legend} /> : <div className="map-loading">{dataError ?? <><LoaderCircle className="spin" /> Loading Ontario boundaries…</>}</div>}
          <div className="scenario-caption">{result ? <><span className="caption-dot" /> {result.scenario.temperature_c}°C <span className="caption-divider">/</span> {result.scenario.day_type === 'weekday' ? 'Weekday' : 'Weekend'} <span className="caption-divider">/</span> {intervalLabel(result.scenario.hour)}{dirty && <span className="previous-label">Previous result</span>}</> : <><span className="caption-dot" /> Ontario FSAs <span className="caption-divider">/</span> Select a scenario to begin</>}</div>
        </div>
        <footer className="map-footer"><span>{visibleMock === true ? <><FlaskConical size={13} /> Demo predictions · synthetic, not measured</> : visibleMock === false ? <><Check size={13} /> Model predictions</> : 'Prediction service awaiting connection'}</span><span>{index.length || '…'} FSAs <i /> Census boundaries · 2021</span></footer>
      </section>
    </main>
    <footer className="app-footer"><span>Exploring energy. Understanding Ontario.</span><span>{theme === 'daylight' ? <><CloudSun size={13} /> {skyPeriod(scenario.hour)} sky · {intervalLabel(scenario.hour)}</> : <><span className="footer-dot" /> Built for a clearer view</>}</span></footer>
    <Dialog.Root open={info} onOpenChange={setInfo}><Dialog.Portal container={appRef.current}><Dialog.Overlay className="modal-backdrop"><Dialog.Content className="about-dialog">
      <Dialog.Close className="dialog-close" aria-label="Close about"><X size={20} /></Dialog.Close><span className="brand-mark"><Zap size={21} /></span><Dialog.Title>A clearer view of energy.</Dialog.Title>
      <Dialog.Description>Explore typical weekday and weekend scenarios. Each FSA shows average electricity consumption per customer, in kWh over the selected hour.</Dialog.Description>
      <p>Temperature is a hypothetical input applied to every FSA. This is a scenario explorer, rather than a forecast for a specific date.</p>
      <p><strong>{visibleMock === false ? 'Model provider connected.' : 'Demo predictions are synthetic.'}</strong> {visibleMock === false ? `Model: ${result?.model_version ?? metadata?.model_version}` : 'The demo formula is not trained on consumption data and should only be used to demonstrate the interface.'}</p>
      <p>Boundaries are census-derived 2021 FSAs. Daylight mode is a playful sky cycle, with a dark map from 18:00 to 06:00.</p>
      <p className="about-time">{metadata?.time_convention ?? 'Training timezone convention will be confirmed at model integration.'}</p>
      <a href="https://www150.statcan.gc.ca/n1/en/catalogue/92-179-X2021001" target="_blank" rel="noreferrer">Statistics Canada boundary source <ArrowUpRight size={14} /></a>
    </Dialog.Content></Dialog.Overlay></Dialog.Portal></Dialog.Root>
  </div>;
}
