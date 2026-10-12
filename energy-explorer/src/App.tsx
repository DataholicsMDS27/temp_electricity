import { useEffect, useRef, useState } from 'react';
import * as Slider from '@radix-ui/react-slider';
import * as RadioGroup from '@radix-ui/react-radio-group';
import * as Dialog from '@radix-ui/react-dialog';
import {
  ArrowUpRight,
  Check,
  CircleHelp,
  CloudSun,
  FlaskConical,
  LoaderCircle,
  Moon,
  Search,
  Sun,
  Thermometer,
  X,
  Zap,
  CalendarDays,
  RotateCcw,
} from 'lucide-react';
import type { FeatureCollection, Geometry } from 'geojson';
import { EnergyMap } from './components/EnergyMap';
import { Sky, skyPeriod } from './components/Sky';
import { getMetadata, getPredictions } from './api';
import {
  intervalLabel,
  sameScenario,
  type FsaEntry,
  type FsaIndex,
  type Metadata,
  type PredictionResponse,
  type Scenario,
  type Theme,
} from './types';

const INITIAL: Scenario = {
  temperature_c: 22,
  day_type: 'weekday',
  hour: 14,
  customer_type: 1,
};

const themes = [
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'dark', label: 'Dark', Icon: Moon },
  { value: 'daylight', label: 'Daylight', Icon: CloudSun },
] as const;

const temperatureDescription = (temperature: number) =>
  temperature < 0
    ? 'A little on the cold side.'
    : temperature < 15
      ? 'A cooler kind of day.'
      : temperature < 26
        ? 'A comfortable kind of day.'
        : 'Turning up the heat.';

function storedTheme(): Theme {
  try {
    const t = localStorage.getItem('energy-theme');
    return t === 'dark' || t === 'daylight' ? t : 'light';
  } catch {
    return 'light';
  }
}

export default function App() {
  const [theme, setTheme] = useState<Theme>(storedTheme);
  const [scenario, setScenario] = useState<Scenario>(INITIAL);
  const [geometry, setGeometry] =
    useState<FeatureCollection<Geometry, { fsa: string }> | null>(null);
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
  const [temperatureDraft, setTemperatureDraft] =
    useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const appRef = useRef<HTMLDivElement>(null);

  const dark =
    theme === 'dark' ||
    (theme === 'daylight' &&
      (scenario.hour < 6 || scenario.hour >= 18));

  const dirty =
    result !== null && !sameScenario(scenario, result.scenario);

  const temperature = metadata?.temperature ?? {
    min: -30,
    max: 30,
    step: 1,
  };

  const legend = metadata?.legend ?? { min: 0, max: 4 };

  const filtered = search.trim()
    ? index
        .filter((f) =>
          f.fsa.startsWith(search.trim().toUpperCase())
        )
        .slice(0, 7)
    : [];

  const selectedEntry =
    index.find((f) => f.fsa === selected) ?? null;

  const visibleMock = result?.is_mock ?? metadata?.is_mock;

  // Save the selected appearance theme.
  useEffect(() => {
    try {
      localStorage.setItem('energy-theme', theme);
    } catch {
      // Unavailable storage does not affect theme.
    }
  }, [theme]);

  // Load the Ontario map data and prediction metadata once.
  useEffect(() => {
    let active = true;

    const load = async () => {
      try {
        const [geo, idx] = await Promise.all([
          fetch('/data/ontario-fsas.geojson').then((r) => {
            if (!r.ok) throw new Error();
            return r.json();
          }),
          fetch('/data/fsa-index.json').then((r) => {
            if (!r.ok) throw new Error();
            return r.json() as Promise<FsaIndex>;
          }),
        ]);

        if (active) {
          setGeometry(geo);
          setIndex(idx.fsas);
        }
      } catch {
        if (active) {
          setDataError(
            'Ontario boundaries could not load. Refresh the page to try again.'
          );
        }
      }
    };

    void load();

    getMetadata()
      .then((m) => {
        if (active) setMetadata(m);
      })
      .catch(() => {
        // Prediction requests will display service errors.
      });

    return () => {
      active = false;
    };
  }, []);

  // Automatically fetch predictions whenever the scenario changes.
  const {
    temperature_c,
    day_type,
    hour,
    customer_type,
  } = scenario;

  useEffect(() => {
    if (!metadata) return;

    let active = true;

    // Briefly wait for the user to finish moving a slider.
    const timer = window.setTimeout(async () => {
      if (!active) return;

      setPending(true);
      setError(null);

      try {
        const prediction = await getPredictions({
          temperature_c,
          day_type,
          hour,
          customer_type,
        });

        if (active) {
          setResult(prediction);
        }
      } catch (e) {
        if (active) {
          setError(
            e instanceof Error
              ? e.message
              : 'Prediction failed. Please try again.'
          );
        }
      } finally {
        if (active) {
          setPending(false);
        }
      }
    }, 60);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [
    metadata,
    temperature_c,
    day_type,
    hour,
    customer_type,
    retryCount,
  ]);

  const selectFsa = (fsa: string) => {
    setSelected(fsa);
    setSearch('');
    setSearchFocused(false);
  };

  const commitTemperature = () => {
    if (
      temperatureDraft !== null &&
      temperatureDraft.trim() &&
      Number.isFinite(Number(temperatureDraft))
    ) {
      setScenario((s) => ({
        ...s,
        temperature_c: Math.max(
          temperature.min,
          Math.min(
            temperature.max,
            Math.round(Number(temperatureDraft))
          )
        ),
      }));
    }

    setTemperatureDraft(null);
  };

  return (
    <div
      ref={appRef}
      className={`app ${dark ? 'theme-dark' : 'theme-light'} mode-${theme}`}
      data-theme={theme}
      data-hour={scenario.hour}
    >
      {theme === 'daylight' && <Sky hour={scenario.hour} />}

      <header className="app-header">
        <a
          className="brand"
          href="/"
          aria-label="Ontario Energy Explorer home"
        >
          <span className="brand-mark">
            <Zap size={21} fill="currentColor" />
          </span>
          <span>
            <strong>
              Ontario<span className="brand-dot">.</span>
            </strong>
            <span className="brand-subtitle">Energy Explorer</span>
          </span>
        </a>

        <div className="header-middle">
          <span className="province-dot" /> A province of possibilities.
        </div>

        <div className="header-actions">
          <RadioGroup.Root
            className="theme-selector"
            value={theme}
            onValueChange={(v) => setTheme(v as Theme)}
            aria-label="Appearance"
          >
            {themes.map(({ value, label, Icon }) => (
              <RadioGroup.Item
                key={value}
                value={value}
                className="theme-option"
                aria-label={`${label} mode`}
              >
                <Icon size={15} />
                {label}
              </RadioGroup.Item>
            ))}
          </RadioGroup.Root>

          <button
            className="info-button"
            aria-label="About this explorer"
            onClick={() => setInfo(true)}
          >
            <CircleHelp size={19} />
          </button>
        </div>
      </header>

      <main className="workspace">
        <aside className="scenario-panel" aria-label="Scenario controls">
          <div className="panel-heading">
            <div className="eyebrow">YOUR SCENARIO</div>
            <h1>What if?</h1>
            <p>
              A temperature. A moment.
              <br />
              An energy picture of Ontario.
            </p>
          </div>

          {/* Temperature */}
          <section
            className="input-section temperature-section"
            aria-labelledby="temperature-label"
          >
            <div className="section-label">
              <span id="temperature-label">
                <Thermometer size={15} /> Temperature
              </span>
            </div>

            <div className="temperature-value">
              <input
                aria-label="Temperature in degrees Celsius"
                type="number"
                min={temperature.min}
                max={temperature.max}
                step={temperature.step}
                value={temperatureDraft ?? scenario.temperature_c}
                onChange={(e) =>
                  setTemperatureDraft(e.target.value)
                }
                onBlur={commitTemperature}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.currentTarget.blur();
                  }
                }}
              />
              <span>°C</span>
            </div>

            <Slider.Root
              className="temperature-slider"
              aria-label="Temperature"
              min={-30}
              max={30}
              step={1}
              value={[scenario.temperature_c]}
              onValueChange={([value]) => {
                setTemperatureDraft(null);
                setScenario((s) => ({
                  ...s,
                  temperature_c: value,
                }));
              }}
            >
              <Slider.Track className="slider-track">
                <Slider.Range className="slider-range" />
              </Slider.Track>
              <Slider.Thumb className="slider-thumb" />
            </Slider.Root>

            <div className="slider-labels">
              <span>-30°</span>
              <span>0°</span>
              <span>30°</span>
            </div>

            <p className="temperature-description">
              {temperatureDescription(scenario.temperature_c)}
            </p>
          </section>

          {/* Day type: readable labels, string values in the API. */}
          <section
            className="input-section"
            aria-labelledby="day-label"
          >
            <div className="section-label">
              <span id="day-label">
                <CalendarDays size={15} /> Day type
              </span>
            </div>

            <RadioGroup.Root
              className="day-selector"
              value={scenario.day_type}
              onValueChange={(v) =>
                setScenario((s) => ({
                  ...s,
                  day_type: v as Scenario['day_type'],
                }))
              }
              aria-label="Day type"
            >
              <RadioGroup.Item
                className="day-option"
                value="weekday"
              >
                Weekday
              </RadioGroup.Item>

              <RadioGroup.Item
                className="day-option"
                value="weekend"
              >
                Weekend / holiday
              </RadioGroup.Item>
            </RadioGroup.Root>
          </section>

          {/* Customer type: readable labels, numeric values in the API. */}
          <section
            className="input-section"
            aria-labelledby="customer-label"
          >
            <div className="section-label">
              <span id="customer-label">Customer type</span>
            </div>

            <RadioGroup.Root
              className="day-selector"
              value={String(scenario.customer_type)}
              onValueChange={(v) =>
                setScenario((s) => ({
                  ...s,
                  customer_type: Number(
                    v
                  ) as Scenario['customer_type'],
                }))
              }
              aria-label="Customer type"
            >
              <RadioGroup.Item
                className="day-option"
                value="1"
              >
                Residential
              </RadioGroup.Item>

              <RadioGroup.Item
                className="day-option"
                value="2"
              >
                Business
              </RadioGroup.Item>
            </RadioGroup.Root>
          </section>

          {/* Hour of day */}
          <section
            className="input-section"
            aria-labelledby="hour-label"
          >
            <div className="section-label">
              <span id="hour-label">Hour of day</span>
              <span className="tiny-tag">24 HOUR</span>
            </div>

            <div className="temperature-value">
              <span>
                {String(scenario.hour).padStart(2, '0')}:00
              </span>
            </div>

            <Slider.Root
              className="temperature-slider"
              aria-label="Hour of day"
              min={0}
              max={23}
              step={1}
              value={[scenario.hour]}
              onValueChange={([value]) =>
                setScenario((s) => ({
                  ...s,
                  hour: value,
                }))
              }
            >
              <Slider.Track className="slider-track">
                <Slider.Range className="slider-range" />
              </Slider.Track>
              <Slider.Thumb className="slider-thumb" />
            </Slider.Root>

            <div className="slider-labels">
              <span>00:00</span>
              <span>12:00</span>
              <span>23:00</span>
            </div>
          </section>

          {/* Automatic prediction status and retry. */}
          <div className="scenario-submit">
            <div
              className={`prediction-status ${
                dirty ? 'is-dirty' : ''
              }`}
              role="status"
              aria-live="polite"
            >
              {pending
                ? 'Updating consumption predictions…'
                : error
                  ? 'Prediction update failed'
                  : result && !dirty
                    ? 'Scenario up to date'
                    : 'Select a scenario to begin'}
            </div>

            {error && (
              <div className="api-error" role="alert">
                {error}
                <button
                  onClick={() =>
                    setRetryCount((n) => n + 1)
                  }
                >
                  Try again <RotateCcw size={13} />
                </button>
              </div>
            )}
          </div>

          <div className="sidebar-footer">
            <FlaskConical size={16} />
            <p>
              A what-if explorer.
              <br />
              <span>One temperature across Ontario.</span>
            </p>
          </div>
        </aside>

        <section
          className="map-panel"
          aria-label="Ontario consumption map"
        >
          <div className="map-toolbar">
            <div className="map-heading">
              <span className="eyebrow">THE BIG PICTURE</span>
              <h2>
                Ontario, hour by hour
                <span className="map-title-dot">.</span>
              </h2>
            </div>

            <div className="fsa-search">
              <Search size={17} />

              <input
                aria-label="Search FSA"
                placeholder="Find an FSA, e.g. M5V"
                value={search}
                onChange={(e) =>
                  setSearch(e.target.value.toUpperCase().slice(0, 3))
                }
                onFocus={() => setSearchFocused(true)}
                onBlur={() =>
                  window.setTimeout(
                    () => setSearchFocused(false),
                    150
                  )
                }
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && filtered.length) {
                    selectFsa(filtered[0].fsa);
                  }
                  if (e.key === 'Escape') {
                    setSearch('');
                    setSearchFocused(false);
                  }
                }}
              />

              {search && (
                <button
                  aria-label="Clear search"
                  onClick={() => setSearch('')}
                >
                  <X size={14} />
                </button>
              )}

              {searchFocused && search && (
                <div className="search-results">
                  {filtered.length ? (
                    filtered.map((f) => (
                      <button
                        key={f.fsa}
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => selectFsa(f.fsa)}
                      >
                        <span>{f.fsa}</span>
                        <span>
                          View area <ArrowUpRight size={14} />
                        </span>
                      </button>
                    ))
                  ) : (
                    <p>No matching Ontario FSA.</p>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="map-canvas">
            {geometry ? (
              <EnergyMap
                geometry={geometry}
                dark={dark}
                result={result}
                selected={selectedEntry}
                onSelect={setSelected}
                legend={legend}
              />
            ) : (
              <div className="map-loading">
                {dataError ?? (
                  <>
                    <LoaderCircle className="spin" />
                    {' '}Loading Ontario boundaries…
                  </>
                )}
              </div>
            )}

            <div className="scenario-caption">
              {result ? (
                <>
                  <span className="caption-dot" />
                  {result.scenario.temperature_c}°C
                  <span className="caption-divider">/</span>
                  {result.scenario.day_type === 'weekday'
                    ? 'Weekday'
                    : 'Weekend / holiday'}
                  <span className="caption-divider">/</span>
                  {result.scenario.customer_type === 1
                    ? 'Residential'
                    : 'Business'}
                  <span className="caption-divider">/</span>
                  {intervalLabel(result.scenario.hour)}
                  {dirty && (
                    <span className="previous-label">
                      Previous result
                    </span>
                  )}
                </>
              ) : (
                <>
                  <span className="caption-dot" />
                  Ontario FSAs
                  <span className="caption-divider">/</span>
                  Select a scenario to begin
                </>
              )}
            </div>
          </div>

          <footer className="map-footer">
            <span>
              {visibleMock === true ? (
                <>
                  <FlaskConical size={13} />
                  {' '}Demo predictions · synthetic, not measured
                </>
              ) : visibleMock === false ? (
                <>
                  <Check size={13} />
                  {' '}Model predictions
                </>
              ) : (
                'Prediction service awaiting connection'
              )}
            </span>

            <span>
              {index.length || '…'} FSAs <i /> Census boundaries · 2021
            </span>
          </footer>
        </section>
      </main>

      <footer className="app-footer">
        <span>Exploring energy. Understanding Ontario.</span>

        <span>
          {theme === 'daylight' ? (
            <>
              <CloudSun size={13} /> {skyPeriod(scenario.hour)} sky ·{' '}
              {intervalLabel(scenario.hour)}
            </>
          ) : (
            <>
              <span className="footer-dot" /> Built for a clearer view
            </>
          )}
        </span>
      </footer>

      <Dialog.Root open={info} onOpenChange={setInfo}>
        <Dialog.Portal container={appRef.current}>
          <Dialog.Overlay className="modal-backdrop">
            <Dialog.Content className="about-dialog">
              <Dialog.Close
                className="dialog-close"
                aria-label="Close about"
              >
                <X size={20} />
              </Dialog.Close>

              <span className="brand-mark">
                <Zap size={21} />
              </span>

              <Dialog.Title>
                A clearer view of energy.
              </Dialog.Title>

              <Dialog.Description>
                Explore typical weekday and weekend scenarios. Each
                FSA shows average electricity consumption per
                customer, in kWh over the selected hour.
              </Dialog.Description>

              <p>
                Temperature is a hypothetical input applied to every
                FSA. This is a scenario explorer, rather than a
                forecast for a specific date.
              </p>

              <p>
                <strong>
                  {visibleMock === false
                    ? 'Model provider connected.'
                    : 'Demo predictions are synthetic.'}
                </strong>{' '}
                {visibleMock === false
                  ? `Model: ${
                      result?.model_version ?? metadata?.model_version
                    }`
                  : 'The demo formula is not trained on consumption data and should only be used to demonstrate the interface.'}
              </p>

              <p>
                Boundaries are census-derived 2021 FSAs. Daylight
                mode is a playful sky cycle, with a dark map from
                18:00 to 06:00.
              </p>

              <p className="about-time">
                {metadata?.time_convention ??
                  'Training timezone convention will be confirmed at model integration.'}
              </p>

              <a
                href="https://www150.statcan.gc.ca/n1/en/catalogue/92-179-X2021001"
                target="_blank"
                rel="noreferrer"
              >
                Statistics Canada boundary source{' '}
                <ArrowUpRight size={14} />
              </a>
            </Dialog.Content>
          </Dialog.Overlay>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}