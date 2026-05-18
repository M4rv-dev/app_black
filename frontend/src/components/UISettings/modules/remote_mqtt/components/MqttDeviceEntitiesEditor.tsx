/**
 * MqttDeviceEntitiesEditor — declares per-entity MQTT wiring on a generic
 * MQTT remote device (mirrors how ESPHome devices declare their
 * binary_sensors/switches/lights catalog).
 *
 * Renders three editable tables (Inputs / Outputs / Sensors). Each section
 * has its own "Scan broker…" button — they share one dialog (cached scan
 * results per topic_prefix) so the second click on a different section
 * reuses what was already discovered. The import handler dispatches to the
 * section the user opened the scan from, with auto-templates tuned per
 * section (binary on/off for inputs, command_template for outputs, value
 * extraction for sensors).
 *
 * All state is owned by the parent (RemoteDeviceForm). This component
 * is pure presentational — value/onChange pattern, swappable.
 */
import React, { useMemo, useState } from 'react';
import { FaPlus, FaTrash, FaSearch } from 'react-icons/fa';
import { useTranslation } from '@/hooks/useTranslation';

import { useMqttScan } from '../hooks/useMqttScan';
import { isValidPublicationTopic } from '../helpers/topicValidation';
import type { ScanResult } from '../types/scan';
import MqttTopicTree, { type ImportSection } from './MqttTopicTree';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export interface MqttDeviceInputRow {
  id: string;
  name?: string;
  topic?: string;
  value_template?: string;
  payload_on?: string;
  payload_off?: string;
}

export interface MqttDeviceOutputRow {
  id: string;
  name?: string;
  topic?: string;
  command_template?: string;
  state_topic?: string;
  state_value_template?: string;
  state_payload_on?: string;
  state_payload_off?: string;
  qos?: 0 | 1 | 2;
  retain?: boolean;
  output_type?: 'switch' | 'light' | 'valve';
}

export interface MqttDeviceSensorRow {
  id: string;
  name?: string;
  topic?: string;
  value_template?: string;
  unit_of_measurement?: string;
  device_class?: string;
  state_class?: 'measurement' | 'total' | 'total_increasing';
}

export interface MqttDeviceConfig {
  topic_prefix?: string;
  inputs?: MqttDeviceInputRow[];
  outputs?: MqttDeviceOutputRow[];
  sensors?: MqttDeviceSensorRow[];
}

export interface MqttDeviceEntitiesEditorProps {
  value: MqttDeviceConfig;
  onChange: (next: MqttDeviceConfig) => void;
}

type Section = 'inputs' | 'outputs' | 'sensors';

/** Derive a sensible value_template + payload_on/off from the scanner classifier. */
function autoInputTemplate(result: ScanResult): Pick<MqttDeviceInputRow, 'value_template' | 'payload_on' | 'payload_off'> {
  if (result.payload_type === 'binary') {
    return { value_template: '{{ value }}', payload_on: '1', payload_off: '0' };
  }
  if (result.payload_type === 'json') {
    return { value_template: '{{ value_json }}' };
  }
  return { value_template: '{{ value }}' };
}

/** Derive a sensible value_template for numeric sensors. */
function autoSensorTemplate(result: ScanResult): Pick<MqttDeviceSensorRow, 'value_template'> {
  if (result.payload_type === 'json') {
    // Most JSON sensors have a `val` or `value` field. Default to `val` — easy edit.
    return { value_template: '{{ value_json.val }}' };
  }
  return { value_template: '{{ value }}' };
}

/** Derive defaults for an output row imported from a topic. */
function autoOutputDefaults(_result: ScanResult): Pick<MqttDeviceOutputRow, 'command_template' | 'output_type'> {
  return { command_template: '{{ state }}', output_type: 'switch' };
}

/** Derive a short id slug from a topic — the last segment, sanitised. */
function idFromTopic(topic: string): string {
  const last = topic.split('/').filter(Boolean).pop() || topic;
  return last.replace(/[^A-Za-z0-9_]+/g, '_');
}

const MqttDeviceEntitiesEditor: React.FC<MqttDeviceEntitiesEditorProps> = ({ value, onChange }) => {
  const { t } = useTranslation();
  const [scanOpen, setScanOpen] = useState(false);
  // Remember which pattern the cached results were scanned for. If user changes
  // topic_prefix, re-scan; otherwise re-open just reuses cached results.
  const [cachedPrefix, setCachedPrefix] = useState<string | null>(null);
  const scan = useMqttScan();

  const inputs = value.inputs || [];
  const outputs = value.outputs || [];
  const sensors = value.sensors || [];
  const prefix = value.topic_prefix || '';

  // Build a set of all entity IDs across all sections and flag duplicates.
  const idCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const it of [...inputs, ...outputs, ...sensors]) {
      if (!it.id) continue;
      counts.set(it.id, (counts.get(it.id) || 0) + 1);
    }
    return counts;
  }, [inputs, outputs, sensors]);
  const isDuplicateId = (id: string) => !!id && (idCounts.get(id) || 0) > 1;

  // Map topic -> the section it's currently used in (for the scan dialog badge).
  const topicUsage = useMemo(() => {
    const m = new Map<string, Section>();
    for (const it of inputs) if (it.topic) m.set(it.topic, 'inputs');
    for (const it of outputs) if (it.topic) m.set(it.topic, 'outputs');
    for (const it of sensors) if (it.topic) m.set(it.topic, 'sensors');
    return m;
  }, [inputs, outputs, sensors]);

  // --- Inputs editing ---
  const addInput = () => onChange({
    ...value,
    inputs: [...inputs, { id: `in_${inputs.length + 1}`, topic: prefix ? `${prefix}/` : '' }],
  });
  const updateInput = (idx: number, patch: Partial<MqttDeviceInputRow>) =>
    onChange({ ...value, inputs: inputs.map((it, i) => i === idx ? { ...it, ...patch } : it) });
  const removeInput = (idx: number) =>
    onChange({ ...value, inputs: inputs.filter((_, i) => i !== idx) });

  // --- Outputs editing ---
  const addOutput = () => onChange({
    ...value,
    outputs: [...outputs, { id: `out_${outputs.length + 1}`, topic: prefix ? `${prefix}/` : '', output_type: 'switch' }],
  });
  const updateOutput = (idx: number, patch: Partial<MqttDeviceOutputRow>) =>
    onChange({ ...value, outputs: outputs.map((it, i) => i === idx ? { ...it, ...patch } : it) });
  const removeOutput = (idx: number) =>
    onChange({ ...value, outputs: outputs.filter((_, i) => i !== idx) });

  // --- Sensors editing ---
  const addSensor = () => onChange({
    ...value,
    sensors: [...sensors, { id: `sensor_${sensors.length + 1}`, topic: prefix ? `${prefix}/` : '' }],
  });
  const updateSensor = (idx: number, patch: Partial<MqttDeviceSensorRow>) =>
    onChange({ ...value, sensors: sensors.map((it, i) => i === idx ? { ...it, ...patch } : it) });
  const removeSensor = (idx: number) =>
    onChange({ ...value, sensors: sensors.filter((_, i) => i !== idx) });

  // --- Scan / browse workflow ---
  // No prefix → scan the whole broker (`#`). With prefix → scope to it (`<prefix>/#`).
  // Either way, results are cached for the lifetime of the dialog so accordion
  // exploration doesn't trigger re-scans.
  const scanPattern = prefix ? `${prefix}/#` : '#';
  const openScan = (_target?: Section) => {
    setScanOpen(true);
    const needsScan = cachedPrefix !== scanPattern || scan.results.length === 0;
    if (needsScan) {
      setCachedPrefix(scanPattern);
      void scan.scan({ pattern: scanPattern, duration_s: 5 });
    }
  };
  const rescan = () => {
    setCachedPrefix(scanPattern);
    void scan.scan({ pattern: scanPattern, duration_s: 5 });
  };
  /** One-shot import of a single topic into the chosen section (from the tree). */
  const importLeaf = (topic: string, result: ScanResult, section: ImportSection) => {
    const allIds = new Set([...inputs.map(i => i.id), ...outputs.map(o => o.id), ...sensors.map(s => s.id)]);
    const uniqId = (base: string): string => {
      let id = base; let n = 2;
      while (allIds.has(id)) { id = `${base}_${n++}`; }
      return id;
    };
    if (section === 'inputs') {
      if (inputs.some(i => i.topic === topic)) return;
      const row: MqttDeviceInputRow = {
        id: uniqId(idFromTopic(topic)), name: topic, topic, ...autoInputTemplate(result),
      };
      onChange({ ...value, inputs: [...inputs, row] });
    } else if (section === 'outputs') {
      if (outputs.some(o => o.topic === topic)) return;
      const row: MqttDeviceOutputRow = {
        id: uniqId(idFromTopic(topic)), name: topic, topic, ...autoOutputDefaults(result),
      };
      onChange({ ...value, outputs: [...outputs, row] });
    } else {
      if (sensors.some(s => s.topic === topic)) return;
      const row: MqttDeviceSensorRow = {
        id: uniqId(idFromTopic(topic)), name: topic, topic, ...autoSensorTemplate(result),
      };
      onChange({ ...value, sensors: [...sensors, row] });
    }
  };

  /** From tree: user picked a branch → become this device's topic_prefix. */
  const usePrefixFromTree = (path: string) => {
    onChange({ ...value, topic_prefix: path });
    setScanOpen(false);
  };

  const sectionLabel: Record<Section, string> = {
    inputs:  t('remote_mqtt.section_inputs') || 'Inputs',
    outputs: t('remote_mqtt.section_outputs') || 'Outputs',
    sensors: t('remote_mqtt.section_sensors') || 'Sensors',
  };

  return (
    <div className="space-y-4">
      {/* Topic prefix + global "browse broker" entry point */}
      {/* Topic prefix — sets the search scope for the broker discovery below */}
      <div className="form-control">
        <label className="label py-1">
          <span className="label-text font-medium">
            {t('remote_mqtt.field_topic_prefix') || 'Topic prefix'}
          </span>
        </label>
        <input
          type="text"
          className="input input-bordered input-sm font-mono"
          value={prefix}
          onChange={e => onChange({ ...value, topic_prefix: e.target.value || undefined })}
          placeholder="e.g. n64/88"
        />
        <span className="label-text-alt text-xs text-base-content/60 mt-0.5">
          {t('remote_mqtt.topic_prefix_hint') ||
            'Common prefix of all topics for this device (e.g. n64/88). Per-entity topics are stored individually below.'}
        </span>
      </div>

      {/* Primary CTA — discover what the broker is publishing.
          Promoted to its own row (left-aligned, full-width on mobile) so it
          reads as the happy-path entry point, not a secondary tool. */}
      <div className="card bg-primary/5 border border-primary/20 p-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm">
            {t('remote_mqtt.discover_title') || 'Discover entities from broker'}
          </div>
          <div className="text-xs text-base-content/60 mt-0.5">
            {t('remote_mqtt.discover_hint') ||
              'Listens on the prefix above for ~5s and lists topics in a tree so you can add them as inputs, outputs or sensors.'}
          </div>
        </div>
        <button
          type="button"
          className="btn btn-primary btn-sm w-full sm:w-auto"
          onClick={() => openScan('inputs')}
        >
          <FaSearch className="mr-1" />
          {t('remote_mqtt.browse_broker') || 'Browse MQTT broker…'}
        </button>
      </div>

      {/* Inputs table */}
      <div className="collapse collapse-arrow bg-base-200">
        <input type="checkbox" defaultChecked={inputs.length > 0} />
        <div className="collapse-title font-medium text-sm">
          {sectionLabel.inputs}
          <span className="badge badge-sm ml-2">{inputs.length}</span>
        </div>
        <div className="collapse-content">
          {inputs.length > 0 && (
            <div className="overflow-x-auto">
              <table className="table table-xs">
                <thead>
                  <tr>
                    <th>id</th>
                    <th>name</th>
                    <th>topic</th>
                    <th>value_template</th>
                    <th>on</th>
                    <th>off</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {inputs.map((it, idx) => {
                    const topicValid = !it.topic || isValidPublicationTopic(it.topic);
                    const dupId = isDuplicateId(it.id);
                    return (
                      <tr key={idx} className={dupId ? 'bg-error/10' : undefined}>
                        <td>
                          <input
                            type="text"
                            className={`input input-bordered input-xs w-24 font-mono ${dupId ? 'input-error' : ''}`}
                            value={it.id}
                            onChange={e => updateInput(idx, { id: e.target.value })}
                            title={dupId ? (t('remote_mqtt.duplicate_id') || 'Duplicate ID — entity IDs must be unique on a device') : undefined}
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            className="input input-bordered input-xs w-32"
                            value={it.name || ''}
                            onChange={e => updateInput(idx, { name: e.target.value || undefined })}
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            className={`input input-bordered input-xs w-48 font-mono ${!topicValid ? 'input-error' : ''}`}
                            value={it.topic || ''}
                            onChange={e => updateInput(idx, { topic: e.target.value })}
                            placeholder="n64/88/in1"
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            className="input input-bordered input-xs w-44 font-mono"
                            value={it.value_template || ''}
                            onChange={e => updateInput(idx, { value_template: e.target.value || undefined })}
                            placeholder="{{ value }}"
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            className="input input-bordered input-xs w-16 font-mono"
                            value={it.payload_on || ''}
                            onChange={e => updateInput(idx, { payload_on: e.target.value || undefined })}
                            placeholder="1"
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            className="input input-bordered input-xs w-16 font-mono"
                            value={it.payload_off || ''}
                            onChange={e => updateInput(idx, { payload_off: e.target.value || undefined })}
                            placeholder="0"
                          />
                        </td>
                        <td>
                          <button
                            type="button"
                            className="btn btn-ghost btn-xs text-error"
                            onClick={() => removeInput(idx)}
                          >
                            <FaTrash />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <div className="flex gap-2 mt-2">
            <button type="button" className="btn btn-outline btn-xs" onClick={addInput}>
              <FaPlus className="mr-1" /> {t('remote_mqtt.add_input') || 'Add input'}
            </button>
          </div>
        </div>
      </div>

      {/* Outputs table */}
      <div className="collapse collapse-arrow bg-base-200">
        <input type="checkbox" defaultChecked={outputs.length > 0} />
        <div className="collapse-title font-medium text-sm">
          {sectionLabel.outputs}
          <span className="badge badge-sm ml-2">{outputs.length}</span>
        </div>
        <div className="collapse-content">
          {outputs.length > 0 && (
            <div className="overflow-x-auto">
              <table className="table table-xs">
                <thead>
                  <tr>
                    <th>id</th>
                    <th>name</th>
                    <th>cmd topic</th>
                    <th>cmd template</th>
                    <th>state topic</th>
                    <th>state template</th>
                    <th>type</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {outputs.map((it, idx) => {
                    const dupId = isDuplicateId(it.id);
                    return (
                    <tr key={idx} className={dupId ? 'bg-error/10' : undefined}>
                      <td>
                        <input
                          type="text"
                          className={`input input-bordered input-xs w-24 font-mono ${dupId ? 'input-error' : ''}`}
                          value={it.id}
                          onChange={e => updateOutput(idx, { id: e.target.value })}
                          title={dupId ? (t('remote_mqtt.duplicate_id') || 'Duplicate ID — entity IDs must be unique on a device') : undefined}
                        />
                      </td>
                      <td>
                        <input
                          type="text"
                          className="input input-bordered input-xs w-28"
                          value={it.name || ''}
                          onChange={e => updateOutput(idx, { name: e.target.value || undefined })}
                        />
                      </td>
                      <td>
                        <input
                          type="text"
                          className="input input-bordered input-xs w-40 font-mono"
                          value={it.topic || ''}
                          onChange={e => updateOutput(idx, { topic: e.target.value })}
                          placeholder="n64/88/out_1/cmd"
                        />
                      </td>
                      <td>
                        <input
                          type="text"
                          className="input input-bordered input-xs w-36 font-mono"
                          value={it.command_template || ''}
                          onChange={e => updateOutput(idx, { command_template: e.target.value || undefined })}
                          placeholder="{{ state }}"
                        />
                      </td>
                      <td>
                        <input
                          type="text"
                          className="input input-bordered input-xs w-40 font-mono"
                          value={it.state_topic || ''}
                          onChange={e => updateOutput(idx, { state_topic: e.target.value || undefined })}
                          placeholder="(optional)"
                        />
                      </td>
                      <td>
                        <input
                          type="text"
                          className="input input-bordered input-xs w-36 font-mono"
                          value={it.state_value_template || ''}
                          onChange={e => updateOutput(idx, { state_value_template: e.target.value || undefined })}
                          placeholder="{{ value }}"
                          disabled={!it.state_topic}
                        />
                      </td>
                      <td>
                        <select
                          className="select select-bordered select-xs"
                          value={it.output_type || 'switch'}
                          onChange={e => updateOutput(idx, { output_type: e.target.value as MqttDeviceOutputRow['output_type'] })}
                        >
                          <option value="switch">switch</option>
                          <option value="light">light</option>
                          <option value="valve">valve</option>
                        </select>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-ghost btn-xs text-error"
                          onClick={() => removeOutput(idx)}
                        >
                          <FaTrash />
                        </button>
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <div className="flex gap-2 mt-2">
            <button type="button" className="btn btn-outline btn-xs" onClick={addOutput}>
              <FaPlus className="mr-1" /> {t('remote_mqtt.add_output') || 'Add output'}
            </button>
          </div>
        </div>
      </div>

      {/* Sensors table */}
      <div className="collapse collapse-arrow bg-base-200">
        <input type="checkbox" defaultChecked={sensors.length > 0} />
        <div className="collapse-title font-medium text-sm">
          {sectionLabel.sensors}
          <span className="badge badge-sm ml-2">{sensors.length}</span>
        </div>
        <div className="collapse-content">
          {sensors.length > 0 && (
            <div className="overflow-x-auto">
              <table className="table table-xs">
                <thead>
                  <tr>
                    <th>id</th>
                    <th>name</th>
                    <th>topic</th>
                    <th>value_template</th>
                    <th>unit</th>
                    <th>device_class</th>
                    <th>state_class</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {sensors.map((it, idx) => {
                    const dupId = isDuplicateId(it.id);
                    const topicValid = !it.topic || isValidPublicationTopic(it.topic);
                    return (
                      <tr key={idx} className={dupId ? 'bg-error/10' : undefined}>
                        <td>
                          <input
                            type="text"
                            className={`input input-bordered input-xs w-24 font-mono ${dupId ? 'input-error' : ''}`}
                            value={it.id}
                            onChange={e => updateSensor(idx, { id: e.target.value })}
                            title={dupId ? (t('remote_mqtt.duplicate_id') || 'Duplicate ID — entity IDs must be unique on a device') : undefined}
                            aria-label={`Sensor ${idx + 1} id`}
                            aria-invalid={dupId || undefined}
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            className="input input-bordered input-xs w-32"
                            value={it.name || ''}
                            onChange={e => updateSensor(idx, { name: e.target.value || undefined })}
                            aria-label={`Sensor ${idx + 1} name`}
                            placeholder="Friendly name"
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            className={`input input-bordered input-xs w-44 font-mono ${!topicValid ? 'input-error' : ''}`}
                            value={it.topic || ''}
                            onChange={e => updateSensor(idx, { topic: e.target.value })}
                            placeholder="n64/88/temp1"
                            aria-label={`Sensor ${idx + 1} topic`}
                            aria-invalid={!topicValid || undefined}
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            className="input input-bordered input-xs w-44 font-mono"
                            value={it.value_template || ''}
                            onChange={e => updateSensor(idx, { value_template: e.target.value || undefined })}
                            placeholder="{{ value_json.val }}"
                            aria-label={`Sensor ${idx + 1} value template`}
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            className="input input-bordered input-xs w-20 font-mono"
                            value={it.unit_of_measurement || ''}
                            onChange={e => updateSensor(idx, { unit_of_measurement: e.target.value || undefined })}
                            placeholder="°C"
                            list="common-units"
                            aria-label={`Sensor ${idx + 1} unit`}
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            className="input input-bordered input-xs w-28"
                            value={it.device_class || ''}
                            onChange={e => updateSensor(idx, { device_class: e.target.value || undefined })}
                            placeholder="temperature"
                            list="common-device-classes"
                            aria-label={`Sensor ${idx + 1} device class`}
                          />
                        </td>
                        <td>
                          <select
                            className="select select-bordered select-xs"
                            value={it.state_class || ''}
                            onChange={e => updateSensor(idx, { state_class: (e.target.value || undefined) as MqttDeviceSensorRow['state_class'] })}
                          >
                            <option value="">—</option>
                            <option value="measurement">measurement</option>
                            <option value="total">total</option>
                            <option value="total_increasing">total_increasing</option>
                          </select>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="btn btn-ghost btn-xs text-error"
                            onClick={() => removeSensor(idx)}
                          >
                            <FaTrash />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <div className="flex gap-2 mt-2">
            <button type="button" className="btn btn-outline btn-xs" onClick={addSensor}>
              <FaPlus className="mr-1" /> {t('remote_mqtt.add_sensor') || 'Add sensor'}
            </button>
          </div>
        </div>
      </div>

      {/* Browse MQTT broker — tree view of topics + per-leaf import buttons */}
      <Dialog open={scanOpen} onOpenChange={setScanOpen}>
        <DialogContent className="max-w-5xl max-h-[85vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>
              {t('remote_mqtt.browse_broker_title') || 'MQTT broker — devices and topics'}
            </DialogTitle>
            <DialogDescription>
              {t('remote_mqtt.browse_broker_description') ||
                'Click a branch to set it as this device\'s topic prefix, or use the per-topic + buttons to add a single topic as input / output / sensor.'}
            </DialogDescription>
          </DialogHeader>

          {scan.isScanning && (
            <div className="alert alert-info py-2 text-sm">
              {(t('remote_mqtt.scanning_status') || 'Listening on `{pattern}` for {duration}s …')
                .replace('{pattern}', scan.lastPattern ?? '')
                .replace('{duration}', String(scan.lastDuration ?? ''))}
            </div>
          )}

          {scan.error && (
            <div className="alert alert-error py-2 text-sm">{scan.error}</div>
          )}

          {!scan.isScanning && !scan.error && scan.results.length > 0 && (
            <div className="flex items-center justify-between gap-2 my-1 text-xs text-base-content/60">
              <span>
                {(t('remote_mqtt.tree_results_summary') || '{n} topics on `{pattern}`')
                  .replace('{n}', String(scan.results.length))
                  .replace('{pattern}', scan.lastPattern ?? '')}
              </span>
              <button
                type="button"
                className="btn btn-ghost btn-xs"
                onClick={rescan}
                disabled={scan.isScanning}
              >
                {t('remote_mqtt.rescan') || 'Re-scan'}
              </button>
            </div>
          )}

          {!scan.isScanning && (
            <div className="flex-1 overflow-auto min-h-[200px]">
              <MqttTopicTree
                results={scan.results}
                topicUsage={topicUsage as Map<string, ImportSection>}
                onUsePrefix={usePrefixFromTree}
                onImportLeaf={importLeaf}
              />
            </div>
          )}

          <DialogFooter>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setScanOpen(false)}>
              {t('common.close') || 'Close'}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Shared datalists — referenced by `list=` on free-text inputs that benefit
          from autocomplete (units, device classes). Cheap UX win without the
          weight of a full Select widget per cell. */}
      <datalist id="common-units">
        {[
          '°C', '°F', 'K', '%', 'W', 'kW', 'Wh', 'kWh', 'V', 'mV', 'A', 'mA',
          'Hz', 'Pa', 'hPa', 'bar', 'psi', 'mm', 'cm', 'm', 'km',
          'l', 'ml', 'm³', 'l/min', 'l/h', 'g', 'kg', 'lx', 'dB', 'dBm', 'ppm', 'µg/m³',
        ].map(u => <option key={u} value={u} />)}
      </datalist>
      <datalist id="common-device-classes">
        {[
          'temperature', 'humidity', 'pressure', 'illuminance', 'power', 'energy',
          'current', 'voltage', 'frequency', 'gas', 'water', 'battery',
          'signal_strength', 'pm25', 'pm10', 'carbon_dioxide', 'carbon_monoxide',
          'moisture', 'distance', 'speed', 'wind_speed', 'volume', 'weight',
          'duration', 'timestamp', 'date',
        ].map(c => <option key={c} value={c} />)}
      </datalist>
    </div>
  );
};

export default MqttDeviceEntitiesEditor;
