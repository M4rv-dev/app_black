/**
 * MqttDevicePicker
 *
 * Dialog for selecting (or changing) the MQTT device prefix.
 * Shows a tree of broker topics; each node has a radio button so the
 * user can pick any depth as the device prefix.
 *
 * On confirm → calls onSelect(prefix) with the chosen prefix string.
 * Used in MqttDeviceEntitiesEditor for both initial setup and "Zmień".
 */
import React, { useState, useCallback, useEffect } from 'react';
import { FaChevronRight, FaChevronDown, FaCircle } from 'react-icons/fa';
import { useTranslation } from '@/hooks/useTranslation';
import { useMqttScan } from '../hooks/useMqttScan';

interface TreeNode {
  segment: string;
  fullPath: string;
  children: Map<string, TreeNode>;
  isLeaf: boolean;
}

function buildTree(topics: string[]): TreeNode {
  const root: TreeNode = { segment: '', fullPath: '', children: new Map(), isLeaf: false };
  for (const topic of topics) {
    const parts = topic.split('/');
    let node = root;
    let path = '';
    for (const part of parts) {
      path = path ? `${path}/${part}` : part;
      if (!node.children.has(part)) {
        node.children.set(part, { segment: part, fullPath: path, children: new Map(), isLeaf: false });
      }
      node = node.children.get(part)!;
    }
    node.isLeaf = true;
  }
  return root;
}

interface TreeNodeViewProps {
  node: TreeNode;
  selected: string;
  onSelect: (path: string) => void;
  depth?: number;
}

const TreeNodeView: React.FC<TreeNodeViewProps> = ({ node, selected, onSelect, depth = 0 }) => {
  const [expanded, setExpanded] = useState(depth < 2);
  const hasChildren = node.children.size > 0;
  const childCount = countTopics(node);

  return (
    <div className="select-none">
      <div
        className={`flex items-center gap-1 py-0.5 px-1 rounded cursor-pointer hover:bg-base-200 ${
          selected === node.fullPath ? 'bg-primary/10' : ''
        }`}
        style={{ paddingLeft: `${depth * 16 + 4}px` }}
      >
        {/* expand/collapse */}
        <button
          type="button"
          className="w-4 h-4 flex items-center justify-center text-base-content/40 hover:text-base-content"
          onClick={() => hasChildren && setExpanded((e) => !e)}
        >
          {hasChildren ? (
            expanded ? <FaChevronDown size={10} /> : <FaChevronRight size={10} />
          ) : (
            <FaCircle size={6} className="opacity-30" />
          )}
        </button>

        {/* radio */}
        <input
          type="radio"
          className="radio radio-primary radio-xs"
          checked={selected === node.fullPath}
          onChange={() => onSelect(node.fullPath)}
          onClick={(e) => e.stopPropagation()}
        />

        {/* label */}
        <span
          className="text-sm flex-1"
          onClick={() => onSelect(node.fullPath)}
        >
          {node.segment}
          {childCount > 0 && (
            <span className="ml-1 text-xs text-base-content/40">({childCount})</span>
          )}
        </span>
      </div>

      {hasChildren && expanded && (
        <div>
          {Array.from(node.children.values()).map((child) => (
            <TreeNodeView
              key={child.segment}
              node={child}
              selected={selected}
              onSelect={onSelect}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
};

function countTopics(node: TreeNode): number {
  if (node.isLeaf && node.children.size === 0) return 1;
  let count = 0;
  for (const child of node.children.values()) {
    count += countTopics(child);
  }
  return count;
}

interface Props {
  onSelect: (prefix: string) => void;
  onClose: () => void;
}

export const MqttDevicePicker: React.FC<Props> = ({ onSelect, onClose }) => {
  const { t } = useTranslation();
  const scan = useMqttScan();
  const [selected, setSelected] = useState('');
  const [hasScanned, setHasScanned] = useState(false);

  const handleScan = useCallback(async () => {
    await scan.scan({ pattern: '#', duration_s: 5 });
    setHasScanned(true);
  }, [scan]);

  useEffect(() => {
    void handleScan();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const topicStrings = scan.results.map((r) => r.topic);
  const tree = buildTree(topicStrings);

  const childCount = selected ? (() => {
    const parts = selected.split('/');
    let node = tree;
    for (const part of parts) {
      const child = node.children.get(part);
      if (!child) return 0;
      node = child;
    }
    return countTopics(node);
  })() : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-base-100 rounded-xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-base-200">
          <h3 className="font-semibold text-lg">
            {t('remote_mqtt.picker_title') || 'Wybierz urządzenie MQTT'}
          </h3>
          <p className="text-sm text-base-content/60 mt-1">
            {t('remote_mqtt.picker_hint') || 'Skanuj broker, następnie wybierz gałąź jako prefix urządzenia.'}
          </p>
        </div>

        {/* Toolbar: rescan + count */}
        <div className="px-4 py-2 border-b border-base-200 flex items-center gap-3">
          <button
            type="button"
            className="btn btn-outline btn-xs"
            onClick={handleScan}
            disabled={scan.isScanning}
          >
            {t('remote_mqtt.picker_scan_btn') || 'Skanuj ponownie'}
          </button>
          {hasScanned && !scan.isScanning && (
            <span className="text-sm text-base-content/60">
              {topicStrings.length} {t('remote_mqtt.picker_topics_found') || 'tematów znalezionych'}
            </span>
          )}
          {scan.error && (
            <span className="text-sm text-error">{scan.error}</span>
          )}
        </div>

        {/* Tree */}
        <div className="flex-1 overflow-y-auto p-2">
          {scan.isScanning && (
            <div className="flex flex-col items-center justify-center gap-3 mt-16">
              <span className="loading loading-spinner loading-md text-primary" />
              <p className="text-sm text-base-content/50">
                {t('remote_mqtt.scanning_network') || 'Trwa przeszukiwanie sieci…'}
              </p>
            </div>
          )}
          {!scan.isScanning && !hasScanned && (
            <p className="text-sm text-base-content/40 text-center mt-8">
              {t('remote_mqtt.picker_scan_prompt') || 'Kliknij „Skanuj ponownie” aby odświeżyć.'}
            </p>
          )}
          {hasScanned && topicStrings.length === 0 && !scan.isScanning && (
            <p className="text-sm text-base-content/40 text-center mt-8">
              {t('remote_mqtt.picker_no_topics') || 'Brak tematów na brokerze.'}
            </p>
          )}
          {Array.from(tree.children.values()).map((child) => (
            <TreeNodeView
              key={child.segment}
              node={child}
              selected={selected}
              onSelect={setSelected}
              depth={0}
            />
          ))}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-base-200 flex items-center justify-between">
          <div className="text-sm text-base-content/60">
            {selected ? (
              <span>
                <span className="font-mono font-semibold text-base-content">{selected}</span>
                {' '}({childCount} {t('remote_mqtt.picker_subtopics') || 'tematów'})
              </span>
            ) : (
              t('remote_mqtt.picker_none_selected') || 'Nie wybrano gałęzi'
            )}
          </div>
          <div className="flex gap-2">
            <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
              {t('common.cancel') || 'Anuluj'}
            </button>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={!selected}
              onClick={() => { onSelect(selected); onClose(); }}
            >
              {t('remote_mqtt.picker_confirm') || 'Użyj tego prefixu'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
