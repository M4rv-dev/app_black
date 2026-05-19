/**
 * DevicePrefixCard
 *
 * Shows the current device topic prefix with a "Change" button,
 * or a prompt to scan and pick one if none is set yet.
 */
import React from 'react';
import { FaEdit, FaSearch } from 'react-icons/fa';
import { useTranslation } from '@/hooks/useTranslation';

interface Props {
  prefix: string;
  onOpenPicker: () => void;
}

export const DevicePrefixCard: React.FC<Props> = ({ prefix, onOpenPicker }) => {
  const { t } = useTranslation();

  if (prefix) {
    return (
      <div className="card bg-base-200 p-3">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex-1 min-w-0">
            <p className="text-xs text-base-content/60 uppercase tracking-wide">
              {t('remote_mqtt.field_topic_prefix') || 'Prefix urządzenia'}
            </p>
            <p className="font-mono font-semibold text-sm mt-0.5">{prefix}</p>
          </div>
          <button type="button" className="btn btn-outline btn-xs gap-1" onClick={onOpenPicker}>
            <FaEdit size={10} />
            {t('remote_mqtt.change_device') || 'Zmień'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="card bg-base-200 p-3">
      <div className="flex flex-col sm:flex-row sm:items-center gap-2">
        <p className="flex-1 text-sm text-base-content/60">
          {t('remote_mqtt.picker_hint') || 'Skanuj broker i wybierz gałąź jako prefix urządzenia.'}
        </p>
        <button type="button" className="btn btn-primary btn-sm gap-1" onClick={onOpenPicker}>
          <FaSearch size={12} />
          {t('remote_mqtt.picker_open_btn') || 'Szukaj urządzenia w sieci MQTT'}
        </button>
      </div>
    </div>
  );
};
