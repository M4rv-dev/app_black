/**
 * MqttOutputSelector
 *
 * Renders the MQTT-outputs section of the output dropdown inside
 * RemoteOutputForm. Extracted here so upstream RemoteOutputForm
 * stays free of remote_mqtt imports.
 *
 * Props mirror the data already computed in RemoteOutputForm.
 */
import React from 'react';
import { SelectItem } from '@/components/ui/select';
export interface MqttOutput {
  id: string;
  name?: string;
  output_type?: string;
}

interface Props {
  mqttOutputs: MqttOutput[];
}

export const MqttOutputSelector: React.FC<Props> = ({ mqttOutputs }) => {
  if (mqttOutputs.length === 0) return null;

  return (
    <>
      <SelectItem value="_header_mqtt" disabled>
        📡 MQTT
      </SelectItem>
      {mqttOutputs.map((mo) => (
        <SelectItem key={`mq_${mo.id}`} value={mo.id}>
          📡 {mo.name ? `${mo.name} (${mo.id})` : mo.id}
        </SelectItem>
      ))}
    </>
  );
};
