/**
 * MqttTopicAssigner
 *
 * Table: discovered topic → ID (editable) → role dropdown → ⚙️ / 🗑️
 *
 * Responsibilities:
 *   - Display and mutate the list of TopicAssignment objects.
 *   - Delegate advanced-settings editing to TopicAdvancedModal.
 *
 * Types and helpers live in ../types/assignments.ts.
 */
import React, { useState } from 'react';
import { FaCog, FaTrash } from 'react-icons/fa';
import { useTranslation } from '@/hooks/useTranslation';

import {
  ROLE_OPTIONS,
  type TopicAdvanced,
  type TopicAssignment,
  type TopicRole,
} from '../types/assignments';
import { TopicAdvancedModal } from './TopicAdvancedModal';

// Re-export types and helpers so existing imports keep working.
export type { TopicRole, TopicAdvanced, TopicAssignment };
export { topicsToAssignments } from '../types/assignments';

interface Props {
  topicPrefix: string;
  assignments: TopicAssignment[];
  onChange: (assignments: TopicAssignment[]) => void;
  /** Topics discovered by the last scan but not yet committed — shown with a "New" badge. */
  newTopics?: Set<string>;
}

export const MqttTopicAssigner: React.FC<Props> = ({ topicPrefix, assignments, onChange, newTopics }) => {
  const { t } = useTranslation();
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  const updateRole = (index: number, role: TopicRole) =>
    onChange(assignments.map((a, i) => (i === index ? { ...a, role } : a)));

  const updateId = (index: number, id: string) =>
    onChange(assignments.map((a, i) => (i === index ? { ...a, id } : a)));

  const remove = (index: number) =>
    onChange(assignments.filter((_, i) => i !== index));

  const saveAdvanced = (index: number, adv: TopicAdvanced) =>
    onChange(assignments.map((a, i) => (i === index ? { ...a, advanced: adv } : a)));

  if (assignments.length === 0) {
    return (
      <p className="text-sm text-base-content/40 text-center py-4">
        {t('remote_mqtt.assigner_empty') || 'Brak tematów. Najpierw wybierz urządzenie.'}
      </p>
    );
  }

  return (
    <>
      {editingIndex !== null && (
        <TopicAdvancedModal
          assignment={assignments[editingIndex]}
          onSave={adv => saveAdvanced(editingIndex, adv)}
          onClose={() => setEditingIndex(null)}
        />
      )}

      <div className="overflow-x-auto">
        <table className="table table-sm w-full">
          <thead>
            <tr>
              <th className="text-xs w-full">{t('remote_mqtt.assigner_col_topic') || 'Temat'}</th>
              <th className="text-xs whitespace-nowrap">{t('remote_mqtt.assigner_col_id') || 'ID'}</th>
              <th className="text-xs whitespace-nowrap">{t('remote_mqtt.assigner_col_role') || 'Typ'}</th>
              <th className="w-16"></th>
            </tr>
          </thead>
          <tbody>
            {assignments.map((a, i) => {
              const relative =
                topicPrefix && a.topic.startsWith(topicPrefix + '/')
                  ? a.topic.slice(topicPrefix.length + 1)
                  : a.topic;
              const hasAdvanced = a.advanced && Object.values(a.advanced).some(Boolean);

              const isNew = newTopics?.has(a.topic);

              return (
                <tr key={i} className={a.role === 'ignore' ? 'opacity-40' : ''}>
                  <td className="font-mono text-xs truncate max-w-[180px]" title={a.topic}>
                    <span className="flex items-center gap-1.5">
                      {relative}
                      {isNew && (
                        <span className="badge badge-xs badge-primary shrink-0">
                          {t('remote_mqtt.badge_new') || 'Nowy'}
                        </span>
                      )}
                    </span>
                  </td>
                  <td>
                    <input
                      type="text"
                      className="input input-xs w-24"
                      value={a.id}
                      onChange={e => updateId(i, e.target.value)}
                      disabled={a.role === 'ignore'}
                    />
                  </td>
                  <td>
                    <select
                      className="select select-xs w-24"
                      value={a.role}
                      onChange={e => updateRole(i, e.target.value as TopicRole)}
                    >
                      {ROLE_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </td>
                  <td className="flex gap-1 justify-end">
                    {a.role !== 'ignore' && (
                      <button
                        type="button"
                        className={`btn btn-ghost btn-xs ${hasAdvanced ? 'text-primary' : 'text-base-content/40'}`}
                        onClick={() => setEditingIndex(i)}
                        title={t('remote_mqtt.adv_btn_title') || 'Ustawienia zaawansowane'}
                      >
                        <FaCog size={12} />
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn-ghost btn-xs text-error"
                      onClick={() => remove(i)}
                      title={t('common.delete') || 'Usuń'}
                    >
                      <FaTrash size={11} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
};
