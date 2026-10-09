import { WheelPicker, WheelPickerWrapper } from '@ncdai/react-wheel-picker';
import { ChevronUp, ChevronDown, Clock3 } from 'lucide-react';
import { intervalLabel } from '../types';

const options = Array.from({ length: 24 }, (_, hour) => ({ value: hour, label: intervalLabel(hour), textValue: intervalLabel(hour) }));

export function TimeWheel({ hour, onChange }: { hour: number; onChange: (hour: number) => void }) {
  return <section className="input-section time-section" aria-labelledby="time-label">
    <div className="section-label"><span id="time-label"><Clock3 size={15} /> Time of day</span><span className="tiny-tag">24 HOUR</span></div>
    <div className="time-wheel" role="group" aria-label="Select a one-hour interval">
      <button className="wheel-arrow" aria-label="Previous hour" onClick={() => onChange((hour + 23) % 24)}><ChevronUp size={17} /></button>
      <WheelPickerWrapper className="hour-picker">
        <WheelPicker options={options} value={hour} onValueChange={onChange} infinite visibleCount={12} optionItemHeight={34} scrollSensitivity={2} dragSensitivity={1.5} classNames={{ optionItem: 'hour-option', highlightWrapper: 'hour-highlight', highlightItem: 'hour-selected' }} />
      </WheelPickerWrapper>
      <button className="wheel-arrow" aria-label="Next hour" onClick={() => onChange((hour + 1) % 24)}><ChevronDown size={17} /></button>
    </div>
    <p className="wheel-hint">Scroll or drag to explore the day</p>
    <span className="sr-only" role="status">Selected interval {intervalLabel(hour)}</span>
  </section>;
}
