/**
 * MqttOutputTypeBadge
 *
 * For MQTT generic outputs the output_type is declared in the device's
 * mqtt.outputs catalog. This read-only badge replaces the editable Select
 * that upstream RemoteOutputForm renders for ESPHome outputs — editing here
 * would duplicate the source of truth.
 *
 * Rendered by RemoteOutputForm only when remote_source === 'mqtt'.
 */
import React from 'react';
import { useTranslation } from '@/hooks/useTranslation';

interface Props {
  outputType?: string;
}

export const MqttOutputTypeBadge: React.FC<Props> = ({ outputType }) => {
  const { t } = useTranslation();

  return (
    <div className="flex items-center gap-2 py-2">
      <span className="badge badge-info badge-lg">
        {outputType || 'switch'}
      </span>
      <span className="text-xs text-base-content/60">
        {t('remote_mqtt.output_type_from_device_hint') ||
          "Set on the device's output catalog. Edit there to change."}
      </span>
    </div>
  );
};
