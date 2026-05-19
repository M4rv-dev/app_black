/**
 * MqttDeviceEntitiesEditor
 *
 * Orchestrates the MQTT device setup wizard:
 *  1. DevicePrefixCard     — pick / change the device topic prefix
 *  2. MqttDevicePicker     — broker scan + tree with radio buttons
 *  3. Scan status banner   — while broker is being scanned
 *  4. Import prompt card   — after scan: "N topics found, assign roles?"
 *  5. AssignerCard         — MqttTopicAssigner wrapped with Confirm / Cancel
 *  6. EntitySummaryCard    — committed entities summary with Edit button
 *
 * All conversion logic (assignments → rows) lives in assignmentsToConfig().
 * All sub-components handle their own presentation.
 */
import React, { useState } from 'react';
import { FaExclamationTriangle, FaSearch } from 'react-icons/fa';
import { useTranslation } from '@/hooks/useTranslation';

import { useMqttScan } from '../hooks/useMqttScan';
import { topicsToAssignments, type TopicAssignment } from '../types/assignments';
import { MqttDevicePicker } from './MqttDevicePicker';
import { MqttTopicAssigner } from './MqttTopicAssigner';
import { DevicePrefixCard } from './DevicePrefixCard';
import { EntitySummaryCard } from './EntitySummaryCard';
import { NewTopicsPickerModal } from './NewTopicsPickerModal';

// ─── Domain types ─────────────────────────────────────────────────────────────

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
  /** Explicit command topic; falls back to topic if absent. */
  cmd_topic?: string;
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

// ─── Conversion helpers ───────────────────────────────────────────────────────

/** Convert committed rows back to TopicAssignment[] for re-editing. */
function configToAssignments(
  inputs: MqttDeviceInputRow[],
  outputs: MqttDeviceOutputRow[],
  sensors: MqttDeviceSensorRow[],
): TopicAssignment[] {
  return [
    ...inputs.map(i => ({
      topic: i.topic || '', role: 'input' as const, id: i.id,
      advanced: { value_template: i.value_template, payload_on: i.payload_on, payload_off: i.payload_off },
    })),
    ...outputs.map(o => ({
      topic: o.state_topic || o.topic || '', role: 'output' as const, id: o.id,
      advanced: {
        cmd_topic: o.topic,
        command_template: o.command_template,
        state_topic: o.state_topic,
        state_value_template: o.state_value_template,
        output_type: o.output_type,
      },
    })),
    ...sensors.map(s => ({
      topic: s.topic || '', role: 'sensor' as const, id: s.id,
      advanced: {
        value_template: s.value_template, unit_of_measurement: s.unit_of_measurement,
        device_class: s.device_class, state_class: s.state_class,
      },
    })),
  ];
}

/**
 * Convert TopicAssignment[] to typed row arrays.
 * Topics with role 'ignore' are excluded from the output.
 */
function assignmentsToConfig(assignments: TopicAssignment[]): {
  inputs: MqttDeviceInputRow[];
  outputs: MqttDeviceOutputRow[];
  sensors: MqttDeviceSensorRow[];
} {
  return {
    inputs: assignments.filter(a => a.role === 'input').map(a => ({
      id: a.id, name: a.topic, topic: a.topic,
      value_template: a.advanced?.value_template || '{{ value }}',
      payload_on: a.advanced?.payload_on,
      payload_off: a.advanced?.payload_off,
    })),
    outputs: assignments.filter(a => a.role === 'output').map(a => ({
      id: a.id, name: a.topic, topic: a.advanced?.cmd_topic || a.topic,
      command_template: a.advanced?.command_template || '{{ state }}',
      state_topic: a.advanced?.state_topic || a.topic,
      state_value_template: a.advanced?.state_value_template,
      output_type: a.advanced?.output_type || 'switch',
    })),
    sensors: assignments.filter(a => a.role === 'sensor').map(a => ({
      id: a.id, name: a.topic, topic: a.topic,
      value_template: a.advanced?.value_template || '{{ value }}',
      unit_of_measurement: a.advanced?.unit_of_measurement,
      device_class: a.advanced?.device_class,
      state_class: a.advanced?.state_class,
    })),
  };
}

// ─── Component ────────────────────────────────────────────────────────────────

const MqttDeviceEntitiesEditor: React.FC<MqttDeviceEntitiesEditorProps> = ({ value, onChange }) => {
  const { t } = useTranslation();
  const [pickerOpen, setPickerOpen]       = useState(false);
  const [pendingPrefix, setPendingPrefix] = useState<string | null>(null);
  const [assignments, setAssignments]     = useState<TopicAssignment[]>([]);
  const scan = useMqttScan();

  const inputs  = value.inputs  || [];
  const outputs = value.outputs || [];
  const sensors = value.sensors || [];
  const prefix  = value.topic_prefix || '';
  const totalEntities = inputs.length + outputs.length + sensors.length;

  // ── Prefix selection ──────────────────────────────────────────────────────

  const handlePickerSelect = (newPrefix: string) => {
    setPickerOpen(false);
    if (prefix && prefix !== newPrefix && totalEntities > 0) {
      setPendingPrefix(newPrefix);
    } else {
      applyNewPrefix(newPrefix);
    }
  };

  const applyNewPrefix = (newPrefix: string) => {
    onChange({ ...value, topic_prefix: newPrefix, inputs: [], outputs: [], sensors: [] });
    setPendingPrefix(null);
    setAssignments([]);
  };

  // ── Open assigner ─────────────────────────────────────────────────────────

  /** Open the assigner pre-loaded with all currently committed topics only.
   *  For a brand-new device (no entities yet) trigger a broker scan instead. */
  const openAssigner = () => {
    if (totalEntities === 0) {
      triggerPickerScan();
    } else {
      scan.reset();
      setAssignments(configToAssignments(inputs, outputs, sensors));
    }
  };

  /**
   * Kick off a scan when user clicks "Add from broker".
   * When done, opens NewTopicsPickerModal with unassigned topics.
   */
  const [pickerTopics, setPickerTopics] = useState<{ topic: string; label: string }[] | null>(null);
  const [awaitingPickerScan, setAwaitingPickerScan] = useState(false);
  const [allAssigned, setAllAssigned] = useState(false);

  // When the scan finishes (triggered by the button), collect unassigned topics and open modal.
  const triggerPickerScan = () => {
    setAllAssigned(false);
    setAwaitingPickerScan(true);
    void scan.scan({ pattern: `${prefix}/#`, duration_s: 5 });
  };

  React.useEffect(() => {
    if (!awaitingPickerScan || scan.isScanning) return;
    setAwaitingPickerScan(false);
    if (scan.results.length === 0) return;
    const existingTopics = new Set(assignments.map(a => a.topic));
    const fresh = scan.results
      .map(r => r.topic)
      .filter(t => !existingTopics.has(t))
      .map(topic => ({
        topic,
        label: prefix && topic.startsWith(prefix + '/')
          ? topic.slice(prefix.length + 1)
          : topic,
      }));
    if (fresh.length === 0) { setAllAssigned(true); return; }
    setPickerTopics(fresh);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scan.isScanning, awaitingPickerScan]);

  // ── Live-propagate assignment changes ────────────────────────────────

  const handleAssignmentsChange = (next: TopicAssignment[]) => {
    setAssignments(next);
    const { inputs: ni, outputs: no, sensors: ns } = assignmentsToConfig(next);
    onChange({ ...value, inputs: ni, outputs: no, sensors: ns });
  };

  const addPickedTopics = (selected: string[]) => {
    handleAssignmentsChange([...assignments, ...topicsToAssignments(selected, prefix)]);
  };

  // ── Derived state ─────────────────────────────────────────────────────────

  /** Topics found by the last scan that are not yet committed. */
  const assignedTopicsSet = new Set([
    ...inputs.map(i => i.topic),
    ...outputs.map(o => o.topic),
    ...sensors.map(s => s.topic),
  ]);
  const newTopicsSet = new Set(
    scan.results.map(r => r.topic).filter(t => !assignedTopicsSet.has(t)),
  );

  const hasEntities = totalEntities > 0 && assignments.length === 0;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">

      {/* 1. Prefix card */}
      <DevicePrefixCard prefix={prefix} onOpenPicker={() => setPickerOpen(true)} />

      {/* Picker dialog */}
      {pickerOpen && (
        <MqttDevicePicker onSelect={handlePickerSelect} onClose={() => setPickerOpen(false)} />
      )}

      {/* 2. Prefix change warning */}
      {pendingPrefix && (
        <div className="alert alert-warning">
          <FaExclamationTriangle />
          <div className="flex-1">
            <p className="font-medium">
              {t('remote_mqtt.change_device_warning_title') || 'Zmiana urządzenia'}
            </p>
            <p className="text-sm mt-0.5">
              {(t('remote_mqtt.change_device_warning_body') ||
                'Zmiana prefixu na "{prefix}" usunie {n} encji. Kontynuować?')
                .replace('{prefix}', pendingPrefix)
                .replace('{n}', String(totalEntities))}
            </p>
          </div>
          <div className="flex gap-2">
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => setPendingPrefix(null)}>
              {t('common.cancel') || 'Anuluj'}
            </button>
            <button type="button" className="btn btn-sm btn-warning" onClick={() => applyNewPrefix(pendingPrefix)}>
              {t('remote_mqtt.change_device_confirm') || 'Zmień i wyczyść'}
            </button>
          </div>
        </div>
      )}

      {/* 3. Error from scan */}
      {scan.error && (
        <div className="alert alert-error py-2 text-sm">{scan.error}</div>
      )}

      {/* 3b. Empty state — prefix set but no entities yet */}
      {prefix && !hasEntities && assignments.length === 0 && (
        <div className="card bg-base-200 p-4 flex flex-col sm:flex-row sm:items-center gap-3">
          {scan.isScanning ? (
            <span className="flex items-center gap-2 text-sm text-base-content/60 flex-1">
              <span className="loading loading-spinner loading-sm text-primary" />
              {t('remote_mqtt.scanning_network') || 'Trwa przeszukiwanie sieci…'}
            </span>
          ) : (
            <>
              <p className="flex-1 text-sm text-base-content/60">
                {t('remote_mqtt.no_entities_hint') || 'Brak encji. Kliknij poniżej aby skonfigurować encje tego urządzenia.'}
              </p>
              <button type="button" className="btn btn-primary btn-sm" onClick={openAssigner}>
                {t('remote_mqtt.add_entities_btn') || 'Konfiguruj encje urządzenia'}
              </button>
            </>
          )}
        </div>
      )}


      {/* Picker modal — select which new topics to add */}
      {pickerTopics !== null && (
        <NewTopicsPickerModal
          topics={pickerTopics}
          onAdd={addPickedTopics}
          onClose={() => setPickerTopics(null)}
        />
      )}

      {/* 5. Assigner card */}
      {assignments.length > 0 && (
        <div className="card bg-base-200 p-3 space-y-3">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <p className="text-sm font-medium">
              {t('remote_mqtt.assigner_title') || 'Edycja encji'}
            </p>
            <div className="flex gap-2 flex-wrap">
              <button
                type="button"
                className="btn btn-outline btn-xs gap-1"
                onClick={triggerPickerScan}
                disabled={scan.isScanning}
              >
                {scan.isScanning
                  ? <span className="loading loading-spinner loading-xs" />
                  : <FaSearch size={10} />}
                {t('remote_mqtt.assigner_scan_new') || 'Dodaj nową encję urządzenia'}
              </button>
              <button type="button" className="btn btn-ghost btn-xs" onClick={() => setAssignments([])}>
                {t('remote_mqtt.assigner_close') || 'Zamknij'}
              </button>
            </div>
          </div>
          {allAssigned && !scan.isScanning && (
            <div className="alert alert-success py-2 text-sm gap-2">
              <span>✓</span>
              {t('remote_mqtt.all_entities_assigned') || 'Wszystkie encje tego urządzenia są już na liście — nic więcej do dodania.'}
            </div>
          )}
          {!scan.isScanning && newTopicsSet.size > 0 && (
            <p className="text-xs text-primary">
              {(t('remote_mqtt.assigner_new_found') || '{n} nowych encji dodanych na dole.')
                .replace('{n}', String(newTopicsSet.size))}
            </p>
          )}
          <MqttTopicAssigner
            topicPrefix={prefix}
            assignments={assignments}
            onChange={handleAssignmentsChange}
            newTopics={newTopicsSet}
          />
        </div>
      )}

      {/* 6. Summary card */}
      {hasEntities && (
        <EntitySummaryCard
          inputs={inputs}
          outputs={outputs}
          sensors={sensors}
          onEdit={openAssigner}
        />
      )}

    </div>
  );
};

export default MqttDeviceEntitiesEditor;

