/**
 * NewTopicsPickerModal
 *
 * Shows a list of topics discovered on the broker that are not yet assigned.
 * User selects which ones to add via checkboxes, then confirms.
 */
import React, { useState } from 'react';
import { useTranslation } from '@/hooks/useTranslation';

interface Props {
  /** Unassigned topics to pick from (relative labels + full topic). */
  topics: { topic: string; label: string }[];
  onAdd: (selected: string[]) => void;
  onClose: () => void;
}

export const NewTopicsPickerModal: React.FC<Props> = ({ topics, onAdd, onClose }) => {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<Set<string>>(new Set(topics.map(t => t.topic)));

  const toggle = (topic: string) =>
    setSelected(prev => {
      const next = new Set(prev);
      next.has(topic) ? next.delete(topic) : next.add(topic);
      return next;
    });

  const toggleAll = () =>
    setSelected(
      selected.size === topics.length ? new Set() : new Set(topics.map(t => t.topic)),
    );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-base-100 rounded-xl shadow-2xl w-full max-w-md p-5 space-y-4">

        {/* Header */}
        <div>
          <h3 className="font-semibold text-base">
            {t('remote_mqtt.new_picker_title') || 'Wybierz tematy do dodania'}
          </h3>
          <p className="text-xs text-base-content/50 mt-0.5">
            {(t('remote_mqtt.new_picker_hint') || 'Znaleziono {n} nowych tematów na brokerze.')
              .replace('{n}', String(topics.length))}
          </p>
        </div>

        {/* Select all toggle */}
        <label className="flex items-center gap-2 cursor-pointer text-sm font-medium">
          <input
            type="checkbox"
            className="checkbox checkbox-sm"
            checked={selected.size === topics.length}
            onChange={toggleAll}
          />
          {t('remote_mqtt.select_all') || 'Zaznacz wszystkie'}
        </label>

        <div className="divider my-0" />

        {/* Topic list */}
        <ul className="space-y-1 max-h-64 overflow-y-auto">
          {topics.map(({ topic, label }) => (
            <li key={topic}>
              <label className="flex items-center gap-2 cursor-pointer hover:bg-base-200 rounded px-1 py-0.5">
                <input
                  type="checkbox"
                  className="checkbox checkbox-sm"
                  checked={selected.has(topic)}
                  onChange={() => toggle(topic)}
                />
                <span className="font-mono text-xs truncate" title={topic}>{label}</span>
              </label>
            </li>
          ))}
        </ul>

        {/* Footer */}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            {t('common.cancel') || 'Anuluj'}
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={selected.size === 0}
            onClick={() => { onAdd([...selected]); onClose(); }}
          >
            {(t('remote_mqtt.new_picker_confirm') || 'Dodaj zaznaczone ({n})')
              .replace('{n}', String(selected.size))}
          </button>
        </div>

      </div>
    </div>
  );
};
