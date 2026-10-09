import { useEffect, useMemo, useRef, useState } from 'react';
import Map, { Source, Layer, NavigationControl, ScaleControl, Popup, type MapRef, type MapMouseEvent } from 'react-map-gl/maplibre';
import type { FeatureCollection, Geometry } from 'geojson';
import type { ExpressionSpecification, StyleSpecification } from 'maplibre-gl';
import { Expand, LocateFixed, MapPin, X, Layers2 } from 'lucide-react';
import type { FsaEntry, PredictionResponse } from '../types';
import { intervalLabel } from '../types';

const ALL: [[number, number], [number, number]] = [[-95.2, 41.65], [-74.2, 57.05]];
const SOUTH: [[number, number], [number, number]] = [[-83.8, 41.65], [-74.2, 46.5]];
export const PALETTE = ['#d9f0e7', '#a3d8c4', '#60b29d', '#258c7e', '#12665f', '#103f43'];

const fallbackStyle = (dark: boolean): StyleSpecification => ({ version: 8, sources: {
  land: { type: 'geojson', data: '/data/context-land.geojson' },
  lakes: { type: 'geojson', data: '/data/context-lakes.geojson' },
}, layers: [
  { id: 'background', type: 'background', paint: { 'background-color': dark ? '#182b36' : '#dfeaf0' } },
  { id: 'land', type: 'fill', source: 'land', paint: { 'fill-color': dark ? '#232c31' : '#edf0ee' } },
  { id: 'coast', type: 'line', source: 'land', paint: { 'line-color': dark ? '#35434b' : '#c6d1d1', 'line-width': 1 } },
  { id: 'lakes', type: 'fill', source: 'lakes', paint: { 'fill-color': dark ? '#182b36' : '#dfeaf0' } },
] });

interface Props {
  geometry: FeatureCollection<Geometry, { fsa: string }>;
  dark: boolean; result: PredictionResponse | null; selected: FsaEntry | null;
  onSelect: (fsa: string | null) => void; legend: { min: number; max: number };
}

export function EnergyMap({ geometry, dark, result, selected, onSelect, legend }: Props) {
  const ref = useRef<MapRef>(null);
  const [loaded, setLoaded] = useState(false);
  const [fallback, setFallback] = useState(false);
  const [firstSymbol, setFirstSymbol] = useState<string>();
  const [hover, setHover] = useState<{ fsa: string; lng: number; lat: number } | null>(null);
  const values = useMemo(() => new MapValues(result), [result]);
  const data = useMemo(() => ({ ...geometry, features: geometry.features.map(f => ({ ...f, properties: { ...f.properties, value: values.get(f.properties.fsa)?.value ?? null } })) }), [geometry, values]);
  const color = useMemo<ExpressionSpecification>(() => ['case', ['==', ['get', 'value'], null], dark ? '#647078' : '#c6ced1', ['interpolate', ['linear'], ['get', 'value'], ...PALETTE.flatMap((c, i) => [legend.min + i * (legend.max - legend.min) / (PALETTE.length - 1), c])]], [dark, legend]);
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fit = (bounds: [[number, number], [number, number]]) => ref.current?.fitBounds(bounds, { padding: { top: 50, bottom: 80, left: 30, right: 30 }, duration: reducedMotion ? 0 : 700 });
  useEffect(() => {
    if (!selected || !loaded) return;
    const [west, south, east, north] = selected.bounds;
    ref.current?.fitBounds([[west, south], [east, north]], { padding: 120, maxZoom: 11, duration: reducedMotion ? 0 : 850 });
  }, [selected, loaded, reducedMotion]);
  const selectPoint = (event: MapMouseEvent) => {
    const fsa = event.features?.[0]?.properties?.fsa;
    if (typeof fsa === 'string') onSelect(fsa);
  };
  const hoverPoint = (event: MapMouseEvent) => {
    const fsa = event.features?.[0]?.properties?.fsa;
    setHover(typeof fsa === 'string' ? { fsa, lng: event.lngLat.lng, lat: event.lngLat.lat } : null);
  };
  const style = useMemo(() => fallback ? fallbackStyle(dark) : `/data/basemap-${dark ? 'dark' : 'light'}.json`, [dark, fallback]);
  return <>
    <Map ref={ref} mapStyle={style} initialViewState={{ bounds: ALL, fitBoundsOptions: { padding: { top: 50, bottom: 80, left: 30, right: 30 } } }}
      minZoom={3} maxZoom={13} maxPitch={0} dragRotate={false} touchZoomRotate={false}
      interactiveLayerIds={['fsa-fill']} cursor={hover ? 'pointer' : 'grab'}
      onLoad={() => setLoaded(true)} onStyleData={() => {
        const layers = ref.current?.getStyle()?.layers;
        setFirstSymbol((layers?.find(l => l.type === 'symbol' && /^(place_|label_)/.test(l.id)) ?? layers?.find(l => l.type === 'symbol'))?.id);
      }}
      onError={(event) => { if (event.error.message.includes('tiles.openfreemap.org') || event.error.message.includes('basemap-')) setFallback(true); }}
      onClick={selectPoint} onMouseMove={hoverPoint} onMouseLeave={() => setHover(null)} attributionControl={{ compact: true }}>
      <Source id="ontario-fsas" type="geojson" data={data} attribution="FSA boundaries: Statistics Canada, 2021 Census">
        <Layer id="fsa-fill" type="fill" beforeId={firstSymbol} paint={{ 'fill-color': color, 'fill-opacity': result ? 0.85 : 0.32 }} />
        <Layer id="fsa-outline" type="line" beforeId={firstSymbol} paint={{ 'line-color': dark ? '#b9cfcb' : '#ffffff', 'line-width': ['interpolate', ['linear'], ['zoom'], 4, 0.45, 9, 1], 'line-opacity': 0.7 }} />
        <Layer id="fsa-selected" type="line" filter={['==', ['get', 'fsa'], selected?.fsa ?? '']} paint={{ 'line-color': dark ? '#d4f783' : '#043f42', 'line-width': 3 }} />
        <Layer id="fsa-hover" type="line" filter={['==', ['get', 'fsa'], hover?.fsa ?? '']} paint={{ 'line-color': dark ? '#ffffff' : '#123d40', 'line-width': 1.5 }} />
      </Source>
      <NavigationControl position="bottom-right" showCompass={false} />
      <ScaleControl position="bottom-left" unit="metric" />
      {hover && hover.fsa !== selected?.fsa && <Popup longitude={hover.lng} latitude={hover.lat} closeButton={false} closeOnClick={false} anchor="bottom" offset={12} className="energy-popup">
        <strong>{hover.fsa}</strong><span>{values.get(hover.fsa)?.value?.toFixed(2) ?? '—'} <small>kWh / customer</small></span>
        <p>{result ? 'Click to inspect this FSA' : 'Run a scenario to see consumption'}</p>
      </Popup>}
    </Map>
    <div className="map-view-controls">
      <button onClick={() => { onSelect(null); fit(ALL); }}><Expand size={14} /> All Ontario</button>
      <button onClick={() => { onSelect(null); fit(SOUTH); }}><LocateFixed size={14} /> Southern Ontario</button>
    </div>
    {!result && <div className="map-intro"><Layers2 size={19} /><div><strong>A different perspective on energy.</strong><p>Set a scenario to explore consumption across Ontario.</p></div></div>}
    <div className="map-bottom">
      <div className="legend-panel">
        <div className="legend-title">Average consumption <span>kWh / customer</span></div>
        <div className="legend-ramp" style={{ background: `linear-gradient(to right, ${PALETTE.join(',')})` }} />
        <div className="legend-ticks">{[0, 1, 2, 3, 4].map(i => <span key={i}>{(legend.min + (legend.max - legend.min) * i / 4).toFixed(0)}{i === 4 ? '+' : ''}</span>)}</div>
        <div className="legend-footer"><span><i /> No prediction</span><span>Fixed scale · 1-hour interval</span></div>
      </div>
      {selected && <div className="selection-panel" aria-live="polite">
        <div className="selection-title"><span><MapPin size={15} /> {selected.fsa}</span><button aria-label="Close FSA details" onClick={() => onSelect(null)}><X size={16} /></button></div>
        <p>Average per customer</p>
        <div className="selection-value">{values.get(selected.fsa)?.value?.toFixed(2) ?? '—'} <span>kWh</span></div>
        <div className="selection-caption">{result ? `${result.scenario.day_type === 'weekday' ? 'Weekday' : 'Weekend'} · ${intervalLabel(result.scenario.hour)} · ${result.scenario.temperature_c}°C` : 'Run a scenario to see a prediction'}</div>
        {result && values.get(selected.fsa)?.status !== 'ok' && <p className="unavailable">Prediction unavailable for this FSA.</p>}
        {result?.is_mock && <div className="selection-demo">Illustrative demo value</div>}
      </div>}
    </div>
    {fallback && <span className="map-fallback-note">Offline atlas · Natural Earth context</span>}
  </>;
}

// Avoid shadowing the React map component with the JavaScript Map constructor.
class MapValues extends globalThis.Map<string, { value: number | null; status: string }> {
  constructor(result: PredictionResponse | null) { super(result?.predictions.map(p => [p.fsa, p]) ?? []); }
}
