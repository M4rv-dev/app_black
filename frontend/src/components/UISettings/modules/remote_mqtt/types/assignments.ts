/**
 * Shared types and helpers for MQTT topic assignment flow.
 * Used by MqttTopicAssigner, TopicAdvancedModal and MqttDeviceEntitiesEditor.
 */

export type TopicRole = 'input' | 'output' | 'sensor' | 'ignore';

/** Advanced per-role settings stored alongside each topic assignment. */
export interface TopicAdvanced {
  /* input / sensor */
  value_template?: string;
  /* input */
  payload_on?: string;
  payload_off?: string;
  /* output */
  cmd_topic?: string;
  command_template?: string;
  state_topic?: string;
  state_value_template?: string;
  output_type?: 'switch' | 'light' | 'valve';
  /* sensor */
  unit_of_measurement?: string;
  device_class?: string;
  state_class?: 'measurement' | 'total' | 'total_increasing';
}

export interface TopicAssignment {
  topic: string;
  role: TopicRole;
  /** Short ID used as entity identifier. */
  id: string;
  advanced?: TopicAdvanced;
}

export const ROLE_OPTIONS: { value: TopicRole; label: string }[] = [
  { value: 'input',  label: 'Input'   },
  { value: 'output', label: 'Output'  },
  { value: 'sensor', label: 'Sensor'  },
  { value: 'ignore', label: 'Ignoruj' },
];

/**
 * Convert a flat list of broker topics to initial assignments.
 * Each topic defaults to role 'input'; the ID is derived from the
 * relative path (after stripping the device prefix).
 */
export function topicsToAssignments(topics: string[], prefix: string): TopicAssignment[] {
  return topics.map((topic) => {
    const relative =
      prefix && topic.startsWith(prefix + '/')
        ? topic.slice(prefix.length + 1)
        : topic;
    const id = relative.replace(/\//g, '_').replace(/^_+|_+$/g, '');
    return { topic, role: 'input', id };
  });
}
