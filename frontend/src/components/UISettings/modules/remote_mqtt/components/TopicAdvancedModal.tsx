/**
 * TopicAdvancedModal
 *
 * Small modal with role-specific advanced fields for a single topic assignment.
 * Opens when the user clicks the ⚙️ button in MqttTopicAssigner.
 *
 * Fields shown depend on the assignment's current role:
 *   input  → value_template, payload_on, payload_off
 *   output → cmd_topic, command_template, state_topic, state_value_template, output_type
 *   sensor → value_template, unit_of_measurement, device_class, state_class
 */
import React, { useState } from 'react';
import { useTranslation } from '@/hooks/useTranslation';
import type { TopicAssignment, TopicAdvanced } from '../types/assignments';

const UNIT_GROUPS: Array<{ group: string; values: string[] }> = [
  { group: 'Temperature',   values: ['\u00b0C', '\u00b0F', 'K'] },
  { group: 'Percent',       values: ['%'] },
  { group: 'Power',         values: ['W', 'kW', 'VA', 'kVA'] },
  { group: 'Energy',        values: ['Wh', 'kWh', 'MWh', 'J'] },
  { group: 'Voltage',       values: ['mV', 'V'] },
  { group: 'Current',       values: ['mA', 'A'] },
  { group: 'Pressure',      values: ['Pa', 'hPa', 'kPa', 'bar', 'mbar', 'psi'] },
  { group: 'Distance',      values: ['mm', 'cm', 'm', 'km'] },
  { group: 'Illuminance',   values: ['lx'] },
  { group: 'Concentration', values: ['ppm', 'ppb', '\u00b5g/m\u00b3'] },
  { group: 'Time',          values: ['ms', 's', 'min', 'h'] },
  { group: 'Signal',        values: ['dB', 'dBm'] },
];
const UNIT_FLAT = UNIT_GROUPS.flatMap(g => g.values);

const UnitPickerInline: React.FC<{
  value: string | undefined;
  onChange: (v: string | undefined) => void;
  label: string;
}> = ({ value, onChange, label }) => {
  const current = value ?? '';
  const isCustom = !!current && !UNIT_FLAT.includes(current);
  const [customMode, setCustomMode] = React.useState(isCustom);
  const selectValue = customMode ? '_custom_' : (current || '_none_');

  const handlePick = (v: string) => {
    if (v === '_none_') { setCustomMode(false); onChange(undefined); return; }
    if (v === '_custom_') { setCustomMode(true); return; }
    setCustomMode(false);
    onChange(v);
  };

  return (
    <div className="form-control gap-0.5">
      <label className="label py-0.5">
        <span className="label-text text-xs font-medium">{label}</span>
      </label>
      <select
        className="select select-bordered select-sm"
        value={selectValue}
        onChange={e => handlePick(e.target.value)}
      >
        <option value="_none_">\u2014 (brak)</option>
        {UNIT_GROUPS.map(g => (
          <optgroup key={g.group} label={g.group}>
            {g.values.map(u => <option key={u} value={u}>{u}</option>)}
          </optgroup>
        ))}
        <option value="_custom_">W\u0142asna\u2026</option>
      </select>
      {customMode && (
        <input
          type="text"
          className="input input-bordered input-sm font-mono mt-1"
          value={current}
          onChange={e => onChange(e.target.value || undefined)}
          placeholder="np. mol/m\u00b3, kgCO2e"
          autoFocus
        />
      )}
    </div>
  );
};

interface Props {
  assignment: TopicAssignment;
  onSave: (adv: TopicAdvanced) => void;
  onClose: () => void;
}

export const TopicAdvancedModal: React.FC<Props> = ({ assignment, onSave, onClose }) => {
  const { t } = useTranslation();
  const [adv, setAdv] = useState<TopicAdvanced>(assignment.advanced ?? {});
  const { role, topic } = assignment;

  /** Generic text field helper. */
  const field = (label: string, key: keyof TopicAdvanced, placeholder?: string, hint?: string) => (
    <div className="form-control gap-0.5">
      <label className="label py-0.5">
        <span className="label-text text-xs font-medium">{label}</span>
      </label>
      <input
        type="text"
        className="input input-bordered input-sm font-mono"
        value={(adv[key] as string) ?? ''}
        onChange={e => setAdv(prev => ({ ...prev, [key]: e.target.value || undefined }))}
        placeholder={placeholder}
      />
      {hint && <span className="label-text-alt text-xs text-base-content/50">{hint}</span>}
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-base-100 rounded-xl shadow-2xl w-full max-w-sm p-5 space-y-4">

        {/* Header */}
        <div>
          <h3 className="font-semibold text-base">
            {t('remote_mqtt.advanced_modal_title') || 'Ustawienia encji'}
          </h3>
          <p className="font-mono text-xs text-base-content/50 mt-0.5 truncate">{topic}</p>
        </div>

        {/* Input fields */}
        {role === 'input' && (
          <fieldset className="fieldset border border-base-300 rounded-box p-3 space-y-3">
            <legend className="fieldset-legend text-xs">
              {t('remote_mqtt.adv_input_group') || 'Konfiguracja wejścia'}
            </legend>
            {field(t('remote_mqtt.adv_value_template_label') || 'value_template', 'value_template', '{{ value }}')}
            {field(t('remote_mqtt.adv_payload_on_label') || 'Payload ON', 'payload_on', '1')}
            {field(t('remote_mqtt.adv_payload_off_label') || 'Payload OFF', 'payload_off', '0')}
          </fieldset>
        )}

        {/* Output fields */}
        {role === 'output' && (
          <div className="space-y-3">
            <fieldset className="fieldset border border-base-300 rounded-box p-3 space-y-3">
              <legend className="fieldset-legend text-xs">
                {t('remote_mqtt.adv_output_group') || 'Sterowanie wyjściem'}
              </legend>
              {field(
                t('remote_mqtt.adv_cmd_topic_label') || 'Temat komend (cmd_topic)',
                'cmd_topic',
                topic,
                t('remote_mqtt.adv_cmd_topic_hint') || 'Temat na który boneIO wysyła ON/OFF.',
              )}
              {field(t('remote_mqtt.adv_command_template_label') || 'command_template', 'command_template', '{{ state }}')}
              <div className="form-control gap-0.5">
                <label className="label py-0.5">
                  <span className="label-text text-xs font-medium">
                    {t('remote_mqtt.adv_output_type_label') || 'output_type'}
                  </span>
                </label>
                <select
                  className="select select-bordered select-sm"
                  value={adv.output_type ?? 'switch'}
                  onChange={e =>
                    setAdv(prev => ({ ...prev, output_type: e.target.value as TopicAdvanced['output_type'] }))
                  }
                >
                  <option value="switch">switch</option>
                  <option value="light">light</option>
                  <option value="valve">valve</option>
                </select>
              </div>
            </fieldset>
            <fieldset className="fieldset border border-base-300 rounded-box p-3 space-y-3">
              <legend className="fieldset-legend text-xs">
                {t('remote_mqtt.adv_output_state_group') || 'Odczyt stanu'}
              </legend>
              {field(
                t('remote_mqtt.adv_state_topic_label') || 'Temat stanu (state_topic)',
                'state_topic',
                topic,
                t('remote_mqtt.adv_state_topic_hint') || 'Temat z którego czytany jest stan wyjścia.',
              )}
              {field(t('remote_mqtt.adv_state_value_template_label') || 'state_value_template', 'state_value_template', '{{ value }}')}
            </fieldset>
          </div>
        )}

        {/* Sensor fields */}
        {role === 'sensor' && (
          <fieldset className="fieldset border border-base-300 rounded-box p-3 space-y-3">
            <legend className="fieldset-legend text-xs">
              {t('remote_mqtt.adv_sensor_group') || 'Konfiguracja sensora'}
            </legend>
            {field(t('remote_mqtt.adv_value_template_label') || 'value_template', 'value_template', '{{ value }}')}
            <UnitPickerInline
              value={adv.unit_of_measurement as string | undefined}
              onChange={v => setAdv(prev => ({ ...prev, unit_of_measurement: v }))}
              label={t('remote_mqtt.adv_unit_label') || 'Jednostka (unit_of_measurement)'}
            />
            {field(t('remote_mqtt.adv_device_class_label') || 'device_class', 'device_class', 'temperature')}
            <div className="form-control gap-0.5">
              <label className="label py-0.5">
                <span className="label-text text-xs font-medium">
                  {t('remote_mqtt.adv_state_class_label') || 'state_class'}
                </span>
              </label>
              <select
                className="select select-bordered select-sm"
                value={adv.state_class ?? ''}
                onChange={e =>
                  setAdv(prev => ({
                    ...prev,
                    state_class: (e.target.value || undefined) as TopicAdvanced['state_class'],
                  }))
                }
              >
                <option value="">—</option>
                <option value="measurement">measurement</option>
                <option value="total">total</option>
                <option value="total_increasing">total_increasing</option>
              </select>
            </div>
          </fieldset>
        )}

        {/* Ignore message */}
        {role === 'ignore' && (
          <p className="text-sm text-base-content/50">
            {t('remote_mqtt.adv_ignored') || 'Ten temat jest ignorowany — nie zostanie zapisany.'}
          </p>
        )}

        {/* Footer */}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            {t('common.cancel') || 'Anuluj'}
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => { onSave(adv); onClose(); }}
          >
            {t('common.save') || 'Zapisz'}
          </button>
        </div>

      </div>
    </div>
  );
};
