/**
 * MqttTopicTree — collapsible tree view of scanned MQTT topics.
 *
 * Groups topics by their path segments (split on '/'). Branches are
 * collapsed by default — only the root segments show. Click a branch
 * to expand its children. Each branch has a "Use as prefix" button
 * that wires the path into the device's topic_prefix (and closes the
 * dialog upstream). Leaves are interactive too: per-leaf import buttons
 * push the topic into Inputs / Outputs / Sensors.
 *
 * Design: the user sees the broker the way they think about it — as a
 * tree of devices, not a flat list of topics.
 */
import React, { useMemo, useState } from 'react';
import { FaFolder, FaFolderOpen, FaArrowRight, FaCircle, FaPlus } from 'react-icons/fa';
import type { ScanResult, PayloadType } from '../types/scan';

const TYPE_BADGE_CLASS: Record<PayloadType, string> = {
  json:    'badge-info',
  binary:  'badge-success',
  numeric: 'badge-warning',
  string:  'badge-ghost',
  empty:   'badge-neutral',
};

export type ImportSection = 'inputs' | 'outputs' | 'sensors';

export interface MqttTopicTreeProps {
  /** Flat list of scan results — tree is built from these. */
  results: ScanResult[];
  /** Map of topic → which section it's already used in (for badging). */
  topicUsage: Map<string, ImportSection>;
  /** Fired when user clicks "Use as prefix" on a branch. */
  onUsePrefix: (path: string) => void;
  /** Fired when user clicks "Import as X" on a leaf. */
  onImportLeaf: (topic: string, result: ScanResult, section: ImportSection) => void;
}

interface TreeNode {
  /** Display segment (e.g. "n64") */
  segment: string;
  /** Full path from root (e.g. "n64/99") */
  path: string;
  /** If this node is a leaf — corresponding ScanResult */
  leaf?: ScanResult;
  /** Children keyed by segment */
  children: Map<string, TreeNode>;
  /** How many leaves live under this branch (recursive) */
  leafCount: number;
}

function buildTree(results: ScanResult[]): TreeNode {
  const root: TreeNode = { segment: '', path: '', children: new Map(), leafCount: 0 };
  for (const r of results) {
    const segs = r.topic.split('/').filter(Boolean);
    let cursor = root;
    let pathAcc = '';
    for (let i = 0; i < segs.length; i++) {
      const seg = segs[i];
      pathAcc = pathAcc ? `${pathAcc}/${seg}` : seg;
      let next = cursor.children.get(seg);
      if (!next) {
        next = { segment: seg, path: pathAcc, children: new Map(), leafCount: 0 };
        cursor.children.set(seg, next);
      }
      next.leafCount += 1;
      if (i === segs.length - 1) {
        next.leaf = r;
      }
      cursor = next;
    }
  }
  return root;
}

const MqttTopicTree: React.FC<MqttTopicTreeProps> = ({ results, topicUsage, onUsePrefix, onImportLeaf }) => {
  const tree = useMemo(() => buildTree(results), [results]);
  // Roots are auto-expanded if there's only one (typical case: single device prefix).
  const initialExpanded = new Set<string>();
  if (tree.children.size === 1) {
    const onlyRoot = Array.from(tree.children.values())[0];
    initialExpanded.add(onlyRoot.path);
  }
  const [expanded, setExpanded] = useState<Set<string>>(initialExpanded);

  const toggle = (path: string) =>
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path); else next.add(path);
      return next;
    });

  // Roots sorted alphabetically — predictable order.
  const roots = Array.from(tree.children.values()).sort((a, b) => a.segment.localeCompare(b.segment));

  if (roots.length === 0) {
    return (
      <div className="text-sm text-base-content/60 italic py-4 text-center">
        No topics matched the scan pattern.
      </div>
    );
  }

  return (
    <div className="border border-base-300 rounded-box overflow-auto">
      {roots.map(node => (
        <TreeBranch
          key={node.path}
          node={node}
          depth={0}
          expanded={expanded}
          toggle={toggle}
          topicUsage={topicUsage}
          onUsePrefix={onUsePrefix}
          onImportLeaf={onImportLeaf}
        />
      ))}
    </div>
  );
};

interface TreeBranchProps {
  node: TreeNode;
  depth: number;
  expanded: Set<string>;
  toggle: (path: string) => void;
  topicUsage: Map<string, ImportSection>;
  onUsePrefix: (path: string) => void;
  onImportLeaf: (topic: string, result: ScanResult, section: ImportSection) => void;
}

const TreeBranch: React.FC<TreeBranchProps> = ({ node, depth, expanded, toggle, topicUsage, onUsePrefix, onImportLeaf }) => {
  const hasChildren = node.children.size > 0;
  const isExpanded = expanded.has(node.path);
  const isLeafOnly = !hasChildren && !!node.leaf;
  const isBranchWithLeaf = hasChildren && !!node.leaf;
  const indent = { paddingLeft: `${depth * 1.25 + 0.5}rem` };

  const usedIn = node.leaf ? topicUsage.get(node.leaf.topic) : undefined;

  return (
    <div>
      {/* Row for this node — wraps actions onto a second line at narrow widths */}
      <div
        className={`flex flex-wrap items-center gap-x-2 gap-y-1 py-1.5 px-2 border-b border-base-300/50 hover:bg-base-200/60 ${isLeafOnly ? '' : 'cursor-pointer'}`}
        style={indent}
        onClick={() => hasChildren && toggle(node.path)}
        role={hasChildren ? 'button' : undefined}
        tabIndex={hasChildren ? 0 : undefined}
        onKeyDown={(e) => {
          if (hasChildren && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault();
            toggle(node.path);
          }
        }}
        aria-expanded={hasChildren ? isExpanded : undefined}
      >
        {/* Folder / leaf icon */}
        {hasChildren ? (
          isExpanded
            ? <FaFolderOpen className="text-warning shrink-0" />
            : <FaFolder className="text-warning shrink-0" />
        ) : (
          <FaCircle className="text-base-content/30 text-[6px] shrink-0 mx-1" />
        )}

        {/* Segment name + leaf-count badge */}
        <span className="font-mono text-sm break-all min-w-0 flex-1">
          {node.segment}
          {hasChildren && (
            <span className="ml-2 badge badge-ghost badge-xs">
              {node.leafCount}
            </span>
          )}
        </span>

        {/* Leaf payload preview — hidden on narrow screens to make room for actions */}
        {node.leaf && (
          <>
            <span className={`badge badge-xs ${TYPE_BADGE_CLASS[node.leaf.payload_type]}`}>
              {node.leaf.payload_type}
            </span>
            <span className="hidden md:inline font-mono text-xs text-base-content/60 truncate max-w-[14rem]">
              {node.leaf.last_payload.slice(0, 40)}
            </span>
            {usedIn && (
              <span className="badge badge-xs badge-warning">
                in {usedIn}
              </span>
            )}
          </>
        )}

        {/* Actions — flex-wrap parent handles narrow widths gracefully */}
        <div className="flex flex-wrap gap-1 shrink-0 ml-auto" onClick={e => e.stopPropagation()}>
          {(hasChildren || isBranchWithLeaf) && depth >= 0 && (
            <button
              type="button"
              className="btn btn-ghost btn-xs gap-1"
              onClick={() => onUsePrefix(node.path)}
              title={`Set "${node.path}" as the device's topic_prefix`}
              aria-label={`Set "${node.path}" as the device's topic prefix`}
            >
              <FaArrowRight aria-hidden /> Use as prefix
            </button>
          )}
          {node.leaf && (
            <>
              <button
                type="button"
                className="btn btn-outline btn-xs gap-1"
                onClick={() => onImportLeaf(node.leaf!.topic, node.leaf!, 'inputs')}
                disabled={usedIn === 'inputs'}
                aria-label={`Add ${node.leaf.topic} as input`}
              >
                <FaPlus aria-hidden /> Input
              </button>
              <button
                type="button"
                className="btn btn-outline btn-xs gap-1"
                onClick={() => onImportLeaf(node.leaf!.topic, node.leaf!, 'outputs')}
                disabled={usedIn === 'outputs'}
                aria-label={`Add ${node.leaf.topic} as output`}
              >
                <FaPlus aria-hidden /> Output
              </button>
              <button
                type="button"
                className="btn btn-outline btn-xs gap-1"
                onClick={() => onImportLeaf(node.leaf!.topic, node.leaf!, 'sensors')}
                disabled={usedIn === 'sensors'}
                aria-label={`Add ${node.leaf.topic} as sensor`}
              >
                <FaPlus aria-hidden /> Sensor
              </button>
            </>
          )}
        </div>
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div>
          {Array.from(node.children.values())
            .sort((a, b) => a.segment.localeCompare(b.segment))
            .map(child => (
              <TreeBranch
                key={child.path}
                node={child}
                depth={depth + 1}
                expanded={expanded}
                toggle={toggle}
                topicUsage={topicUsage}
                onUsePrefix={onUsePrefix}
                onImportLeaf={onImportLeaf}
              />
            ))}
        </div>
      )}
    </div>
  );
};

export default MqttTopicTree;
