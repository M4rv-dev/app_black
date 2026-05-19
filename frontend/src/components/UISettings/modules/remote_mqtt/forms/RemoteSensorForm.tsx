/**
 * RemoteSensorForm — dedicated form for editing remote sensor entries
 * (numeric/string sensors from generic MQTT devices).
 *
 * Lets the user:
 *   1. Pick a remote device (only generic MQTT devices with mqtt.sensors[])
 *   2. Pick a sensor from that device
 *   3. Optionally override name, id, area, show_in_ha
 *   4. Optionally override unit / device_class / state_class
 *
 * The sensor's topic + value_template come from the device's mqtt.sensors[]
 * catalog; this form only carries routing + display overrides.
 */
import React, { useState } from 'react';
import { useTranslation } from '@/hooks/useTranslation';
import AreaSelect from '../../../widgets/AreaSelect';
import { sanitizeId } from '../../../helpers/idValidation';
import { TabsBox } from '@/components/ui/tabs-box';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type {
  AreaEntity,
  RemoteDeviceEntity,
} from '@/types/config';

/* ------------------------------------------------------------------ */
/*  UnitPicker — predefined units (grouped) + custom fallback           */
/* ------------------------------------------------------------------ */
interface UnitPickerProps {
  value: string | undefined;
  onChange: (v: string | undefined) => void;
  deviceDefault?: string;
  groups: Array<{ group: string; values: string[] }>;
  flatList: string[];
}
const UnitPicker: React.FC<UnitPickerProps> = ({ value, onChange, deviceDefault, groups, flatList }) => {
  const current = value || '';
  const isCustom = !!current && !flatList.includes(current);
  // Local "custom mode" toggle so the user can switch to custom even when value is empty
  const [customMode, setCustomMode] = React.useState(isCustom);
  const selectValue = customMode ? '_custom_' : (current || '_none_');

  const handlePick = (v: string) => {
    if (v === '_none_') { setCustomMode(false); onChange(undefined); return; }
    if (v === '_custom_') { setCustomMode(true); return; }
    setCustomMode(false);
    onChange(v);
  };

  return (
    <div className="form-control">
      <label className="label py-1">
        <span className="label-text font-medium">Unit (override)</span>
      </label>
      <Select value={selectValue} onValueChange={handlePick}>
        <SelectTrigger className="select select-bordered select-sm">
          <SelectValue placeholder={deviceDefault || 'Pick a unit…'} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="_none_">
            {deviceDefault ? `Use device value (${deviceDefault})` : '— (none)'}
          </SelectItem>
          {groups.map(g => (
            <React.Fragment key={g.group}>
              <div className="px-2 py-1 text-xs text-base-content/50 font-semibold uppercase tracking-wide">
                {g.group}
              </div>
              {g.values.map(u => (
                <SelectItem key={u} value={u}>{u}</SelectItem>
              ))}
            </React.Fragment>
          ))}
          <SelectItem value="_custom_">Custom…</SelectItem>
        </SelectContent>
      </Select>
      {customMode && (
        <input
          type="text"
          className="input input-bordered input-sm font-mono mt-2"
          value={current}
          onChange={e => onChange(e.target.value || undefined)}
          placeholder="e.g. mol/m³, kgCO2e"
          autoFocus
        />
      )}
      <label className="label py-0">
        <span className="label-text-alt">
          Overrides the unit declared on the device. Leave empty to use the device value.
        </span>
      </label>
    </div>
  );
};

interface RemoteSensorFormProps {
  data: any;
  onChange: (data: any) => void;
  isNew: boolean;
  schema?: any;
  allAreas?: AreaEntity[];
  allRemoteDevices?: RemoteDeviceEntity[];
  existingItems?: any[];
  editingIndex?: number | null;
  onValidationChange?: (hasErrors: boolean) => void;
  attemptedSubmit?: boolean;
}

const RemoteSensorForm: React.FC<RemoteSensorFormProps> = ({
  data,
  onChange,
  allAreas = [],
  allRemoteDevices = [],
  existingItems = [],
  editingIndex = null,
  onValidationChange,
  attemptedSubmit = false,
}) => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<'basic' | 'advanced'>('basic');

  const updateField = (field: string, value: any) => {
    onChange({ ...data, [field]: value });
  };

  /* ---------- validation ---------- */
  const getValidationErrors = (): string[] => {
    const errors: string[] = [];
    if (!data.device_id) errors.push(t('validation.required') + ': ' + (t('remote_devices.device') || 'Device'));
    if (!data.sensor_id) errors.push(t('validation.required') + ': ' + (t('remote_sensors.sensor_entity') || 'Sensor'));
    // Unique id (if custom id provided)
    if (data.id) {
      const dup = existingItems.some((it, idx) => idx !== editingIndex && it.id === data.id);
      if (dup) errors.push(t('validation.duplicate_id') || 'ID already in use');
    }
    return errors;
  };
  const validationErrors = getValidationErrors();
  React.useEffect(() => {
    onValidationChange?.(validationErrors.length > 0);
  }, [validationErrors.length, onValidationChange]);

  /* ---------- device + sensor lookups ---------- */
  // Only generic MQTT devices declare sensors[] in this stack.
  const devicesWithSensors = allRemoteDevices.filter((d: any) =>
    d.protocol === 'mqtt' && Array.isArray(d?.mqtt?.sensors) && d.mqtt.sensors.length > 0
  );
  const selectedDevice = allRemoteDevices.find(d => d.id === data.device_id);
  const availableSensors: Array<{
    id: string; name?: string; unit_of_measurement?: string;
    device_class?: string; state_class?: string;
  }> = (selectedDevice as any)?.mqtt?.sensors || [];

  const selectedSensor = availableSensors.find(s => s.id === data.sensor_id);

  // When sensor is picked, pre-fill name if empty.
  const handleSensorChange = (sensorId: string) => {
    const found = availableSensors.find(s => s.id === sensorId);
    onChange({
      ...data,
      sensor_id: sensorId,
      remote_source: 'mqtt',
      name: data.name || found?.name || sensorId,
    });
  };

  /* ---------- HA unit_of_measurement common values (grouped) ---------- */
  // Flat list — used by Select dropdown. "Custom…" option lets the user
  // type their own unit when the predefined list isn't enough.
  const UNIT_OPTIONS: Array<{ group: string; values: string[] }> = [
    { group: 'Temperature',    values: ['°C', '°F', 'K'] },
    { group: 'Percent',        values: ['%'] },
    { group: 'Power',          values: ['W', 'kW', 'MW', 'VA', 'kVA'] },
    { group: 'Energy',         values: ['Wh', 'kWh', 'MWh', 'J', 'kJ'] },
    { group: 'Voltage',        values: ['mV', 'V', 'kV'] },
    { group: 'Current',        values: ['mA', 'A'] },
    { group: 'Frequency',      values: ['Hz', 'kHz', 'MHz', 'GHz'] },
    { group: 'Pressure',       values: ['Pa', 'hPa', 'kPa', 'MPa', 'bar', 'mbar', 'psi', 'inHg', 'mmHg'] },
    { group: 'Distance',       values: ['mm', 'cm', 'm', 'km', 'in', 'ft', 'mi'] },
    { group: 'Speed',          values: ['m/s', 'km/h', 'mph', 'ft/s', 'kn'] },
    { group: 'Volume',         values: ['ml', 'l', 'm³', 'gal', 'ft³'] },
    { group: 'Flow rate',      values: ['l/min', 'l/h', 'm³/h', 'gal/min'] },
    { group: 'Mass / Weight',  values: ['g', 'kg', 't', 'oz', 'lb'] },
    { group: 'Illuminance',    values: ['lx', 'lm'] },
    { group: 'Concentration',  values: ['ppm', 'ppb', 'µg/m³', 'mg/m³'] },
    { group: 'Time',           values: ['ms', 's', 'min', 'h', 'd'] },
    { group: 'Data',           values: ['B', 'kB', 'MB', 'GB', 'TB', 'bit/s', 'kbit/s', 'Mbit/s'] },
    { group: 'Signal',         values: ['dB', 'dBm'] },
  ];
  const UNIT_FLAT = UNIT_OPTIONS.flatMap(g => g.values);

  /* ---------- HA device_class enum (loose — user can type anything too) ---------- */
  const DEVICE_CLASS_OPTIONS = [
    'apparent_power', 'aqi', 'atmospheric_pressure', 'battery', 'carbon_dioxide',
    'carbon_monoxide', 'current', 'data_rate', 'data_size', 'date', 'distance',
    'duration', 'energy', 'energy_storage', 'enum', 'frequency', 'gas', 'humidity',
    'illuminance', 'irradiance', 'moisture', 'monetary', 'nitrogen_dioxide',
    'nitrogen_monoxide', 'nitrous_oxide', 'ozone', 'ph', 'pm1', 'pm10', 'pm25',
    'power', 'power_factor', 'precipitation', 'precipitation_intensity',
    'pressure', 'reactive_power', 'signal_strength', 'sound_pressure', 'speed',
    'sulphur_dioxide', 'temperature', 'timestamp',
    'volatile_organic_compounds', 'voltage', 'volume', 'water', 'weight',
    'wind_speed',
  ];

  return (
    <div className="space-y-4">
      {attemptedSubmit && validationErrors.length > 0 && (
        <div className="alert alert-error py-2 text-sm">
          <ul className="list-disc list-inside">
            {validationErrors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}

      <TabsBox
        name="remote_sensor_tabs"
        tabs={[
          { id: 'basic', label: t('common.basic') || 'Basic', content: null },
          { id: 'advanced', label: t('common.advanced') || 'Advanced', content: null },
        ]}
        activeTab={activeTab}
        onTabChange={(id) => setActiveTab(id as 'basic' | 'advanced')}
      />

      {activeTab === 'basic' && (
        <fieldset className="fieldset border border-base-300 rounded-box p-4 space-y-3">
          <legend className="fieldset-legend">{t('settings.basic_settings') || 'Podstawowe'}</legend>
          {/* Display name */}
          <div className="form-control">
            <label className="label py-1">
              <span className="label-text font-medium">{t('common.name') || 'Name'}</span>
            </label>
            <input
              type="text"
              className="input input-bordered input-sm"
              value={data.name || ''}
              onChange={e => updateField('name', e.target.value || undefined)}
              placeholder={t('remote_sensors.name_placeholder') || 'Friendly name (defaults to sensor id)'}
            />
          </div>

          {/* Custom ID */}
          <div className="form-control">
            <label className="label py-1">
              <span className="label-text font-medium">{t('remote_sensors.custom_id') || 'Custom entity ID'}</span>
            </label>
            <input
              type="text"
              className="input input-bordered input-sm font-mono"
              value={data.id || ''}
              onChange={e => updateField('id', sanitizeId(e.target.value) || undefined)}
              placeholder={t('remote_sensors.custom_id_placeholder') || 'auto: <device>_<sensor>'}
            />
            <label className="label py-0">
              <span className="label-text-alt">
                {t('remote_sensors.custom_id_hint') ||
                 'Leave empty to auto-generate from device + sensor IDs.'}
              </span>
            </label>
          </div>

          {/* Device */}
          <div className="form-control">
            <label className="label py-1">
              <span className="label-text font-medium">{t('remote_devices.device') || 'Device'}</span>
            </label>
            <Select
              value={data.device_id || '_none_'}
              onValueChange={(v) => onChange({
                ...data,
                device_id: v === '_none_' ? undefined : v,
                sensor_id: undefined,
                remote_source: 'mqtt',
              })}
            >
              <SelectTrigger className="select select-bordered select-sm">
                <SelectValue placeholder={t('remote_sensors.select_device') || 'Select device…'} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="_none_">{t('remote_sensors.select_device') || 'Select device…'}</SelectItem>
                {devicesWithSensors.map(d => (
                  <SelectItem key={d.id} value={d.id}>
                    {d.name || d.id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {devicesWithSensors.length === 0 && (
              <label className="label py-0">
                <span className="label-text-alt text-warning">
                  {t('remote_sensors.no_devices_hint') ||
                    'No generic MQTT devices with sensors. Add sensors to a device first.'}
                </span>
              </label>
            )}
          </div>

          {/* Sensor on device */}
          <div className="form-control">
            <label className="label py-1">
              <span className="label-text font-medium">{t('remote_sensors.sensor_entity') || 'Sensor'}</span>
            </label>
            <Select
              value={data.sensor_id || '_none_'}
              onValueChange={(v) => handleSensorChange(v === '_none_' ? '' : v)}
              disabled={!data.device_id || availableSensors.length === 0}
            >
              <SelectTrigger className="select select-bordered select-sm">
                <SelectValue placeholder={t('remote_sensors.select_sensor') || 'Select sensor…'} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="_none_">{t('remote_sensors.select_sensor') || 'Select sensor…'}</SelectItem>
                {availableSensors.map(s => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name || s.id}
                    {s.unit_of_measurement ? ` · ${s.unit_of_measurement}` : ''}
                    {s.device_class ? ` (${s.device_class})` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Selected sensor info */}
          {selectedSensor && (
            <div className="alert alert-info py-2 text-xs">
              <div className="space-y-0.5">
                <div>
                  <strong>{t('remote_sensors.from_device') || 'From device'}:</strong>{' '}
                  <code>{(selectedDevice as any)?.mqtt?.sensors?.find((s: any) => s.id === selectedSensor.id)?.topic}</code>
                </div>
                <div>
                  <strong>value_template:</strong>{' '}
                  <code>{(selectedDevice as any)?.mqtt?.sensors?.find((s: any) => s.id === selectedSensor.id)?.value_template || '{{ value }}'}</code>
                </div>
                <div className="text-base-content/60">
                  {t('remote_sensors.from_device_hint') ||
                   'Topic and template live on the device. Edit them in the Remote Devices form.'}
                </div>
              </div>
            </div>
          )}

          {/* Area */}
          <div className="form-control">
            <label className="label py-1">
              <span className="label-text font-medium">{t('common.area') || 'Area'}</span>
            </label>
            <AreaSelect
              value={data.area || ''}
              onChange={(v: string | undefined) => updateField('area', v || undefined)}
              areas={allAreas}
            />
          </div>

          {/* show_in_ha */}
          <fieldset className="fieldset bg-base-100 border-base-300 rounded-box border p-3">
            <legend className="fieldset-legend">{t('inputs.forward_to_ha') || 'Forward to HA'}</legend>
            <label className="label cursor-pointer justify-start gap-2 py-1">
              <input
                type="checkbox"
                className="toggle toggle-primary toggle-sm"
                checked={!!data.show_in_ha}
                onChange={e => updateField('show_in_ha', e.target.checked || undefined)}
              />
              <span className="label-text wrap-break-word">
                {t('remote_sensors.show_in_ha_hint') ||
                 'Publish HA autodiscovery so the sensor appears in Home Assistant.'}
              </span>
            </label>
          </fieldset>
        </fieldset>
      )}

      {activeTab === 'advanced' && (
        <fieldset className="fieldset border border-base-300 rounded-box p-4 space-y-3">
          <legend className="fieldset-legend">{t('settings.advanced_settings') || 'Zaawansowane'}</legend>
          {/* Unit override — predefined list, fallback to custom input */}
          <UnitPicker
            value={data.unit_of_measurement}
            onChange={(v) => updateField('unit_of_measurement', v)}
            deviceDefault={selectedSensor?.unit_of_measurement}
            groups={UNIT_OPTIONS}
            flatList={UNIT_FLAT}
          />

          {/* Device class override */}
          <div className="form-control">
            <label className="label py-1">
              <span className="label-text font-medium">{t('remote_sensors.device_class') || 'device_class (override)'}</span>
            </label>
            <Select
              value={data.device_class || '_none_'}
              onValueChange={(v) => updateField('device_class', v === '_none_' ? undefined : v)}
            >
              <SelectTrigger className="select select-bordered select-sm">
                <SelectValue placeholder={selectedSensor?.device_class || (t('remote_sensors.select_device_class') || 'Select device_class…')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="_none_">{t('common.none') || '—'}</SelectItem>
                {DEVICE_CLASS_OPTIONS.map(opt => (
                  <SelectItem key={opt} value={opt}>{opt}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* State class override */}
          <div className="form-control">
            <label className="label py-1">
              <span className="label-text font-medium">{t('remote_sensors.state_class') || 'state_class (override)'}</span>
            </label>
            <Select
              value={data.state_class || '_none_'}
              onValueChange={(v) => updateField('state_class', v === '_none_' ? undefined : v)}
            >
              <SelectTrigger className="select select-bordered select-sm">
                <SelectValue placeholder={selectedSensor?.state_class || '—'} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="_none_">{t('common.none') || '—'}</SelectItem>
                <SelectItem value="measurement">measurement</SelectItem>
                <SelectItem value="total">total</SelectItem>
                <SelectItem value="total_increasing">total_increasing</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </fieldset>
      )}
    </div>
  );
};

export default RemoteSensorForm;
