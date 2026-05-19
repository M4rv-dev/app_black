/**
 * EntitySummaryCard
 *
 * Read-only summary of committed inputs / outputs / sensors.
 * Shows each category as a badge + comma-separated ID list.
 * Provides an "Edit" button that re-opens the assigner table.
 * New topics (from a background scan) appear inline in the assigner
 * with a "New" badge — no separate add-new button needed here.
 */
import React from 'react';
import { FaEdit } from 'react-icons/fa';
import { useTranslation } from '@/hooks/useTranslation';
import type {
  MqttDeviceInputRow,
  MqttDeviceOutputRow,
  MqttDeviceSensorRow,
} from './MqttDeviceEntitiesEditor';

interface Props {
  inputs: MqttDeviceInputRow[];
  outputs: MqttDeviceOutputRow[];
  sensors: MqttDeviceSensorRow[];
  onEdit: () => void;
}

const Row: React.FC<{ label: string; ids: string[] }> = ({ label, ids }) => (
  <p className="text-sm">
    <span className="badge badge-sm badge-outline mr-2">{label}</span>
    {ids.join(', ')}
  </p>
);

export const EntitySummaryCard: React.FC<Props> = ({ inputs, outputs, sensors, onEdit }) => {
  const { t } = useTranslation();

  return (
    <div className="card bg-base-200 p-3 space-y-1">
      <p className="text-xs text-base-content/60 uppercase tracking-wide mb-1">
        {t('remote_mqtt.entities_summary') || 'Przypisane encje'}
      </p>

      {inputs.length  > 0 && <Row label="Input"  ids={inputs.map(i => i.id)} />}
      {outputs.length > 0 && <Row label="Output" ids={outputs.map(o => o.id)} />}
      {sensors.length > 0 && <Row label="Sensor" ids={sensors.map(s => s.id)} />}

      <button type="button" className="btn btn-outline btn-xs mt-2 gap-1" onClick={onEdit}>
        <FaEdit size={10} />
        {t('remote_mqtt.edit_assignments') || 'Edytuj encje'}
      </button>
    </div>
  );
};
