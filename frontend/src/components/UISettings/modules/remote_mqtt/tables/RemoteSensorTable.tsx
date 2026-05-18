/**
 * RemoteSensorTable — dedicated table for remote sensor entries.
 *
 * Columns: Name/ID | Device | Sensor Entity | Unit | device_class | Area | Actions
 */
import React, { useState, useMemo } from 'react';
import { useTranslation } from '@/hooks/useTranslation';
import { useTableSort } from '@/hooks/useTableSort';
import TableActions from '../../../tables/TableActions';
import FilterInput from '../../../tables/FilterInput';
import MobileCard from '../../../tables/MobileCard';
import SortableHeader, { ResetSortButton } from '../../../tables/SortableHeader';
import { Table, Td, Tr, Th, Thead, Tbody } from '@/components/ui/table';
import { FaWifi } from 'react-icons/fa';

interface Area {
  id: string;
  name: string;
}

interface RemoteSensorTableProps {
  items: any[];
  allAreas: Area[];
  allRemoteDevices: any[];
  onEdit: (index: number) => void;
  onDelete: (index: number) => void;
}

const RemoteSensorTable: React.FC<RemoteSensorTableProps> = ({
  items,
  allAreas,
  allRemoteDevices,
  onEdit,
  onDelete,
}) => {
  const { t } = useTranslation();
  const [filter, setFilter] = useState('');
  const { sortConfig, toggleSort, resetSort, sortItems, isSorted } = useTableSort('remote_sensors');

  const getDeviceName = (deviceId: string) => {
    const device = allRemoteDevices.find((d: any) => d.id === deviceId);
    return device?.name || deviceId || '-';
  };

  const getSensorDef = (deviceId: string, sensorId: string) => {
    const device = allRemoteDevices.find((d: any) => d.id === deviceId) as any;
    return device?.mqtt?.sensors?.find((s: any) => s.id === sensorId);
  };

  const filteredItems = useMemo(() => {
    if (!filter.trim()) return items.map((item, index) => ({ item, originalIndex: index }));
    const lowerFilter = filter.toLowerCase();
    return items
      .map((item, index) => ({ item, originalIndex: index }))
      .filter(({ item }) =>
        (item.name?.toLowerCase().includes(lowerFilter)) ||
        (item.id?.toLowerCase().includes(lowerFilter)) ||
        (item.device_id?.toLowerCase().includes(lowerFilter)) ||
        (item.sensor_id?.toLowerCase().includes(lowerFilter)) ||
        (getDeviceName(item.device_id)?.toLowerCase().includes(lowerFilter))
      );
  }, [items, filter, allRemoteDevices]);

  const sortedItems = useMemo(() => {
    return sortItems(filteredItems, {
      name: (item: any) => (item.name || item.id || '').toLowerCase(),
      device: (item: any) => getDeviceName(item.device_id).toLowerCase(),
      sensor_id: (item: any) => (item.sensor_id || '').toLowerCase(),
      device_class: (item: any) => (item.device_class || getSensorDef(item.device_id, item.sensor_id)?.device_class || '').toLowerCase(),
      unit: (item: any) => (item.unit_of_measurement || getSensorDef(item.device_id, item.sensor_id)?.unit_of_measurement || '').toLowerCase(),
      area: (item: any) => {
        const area = allAreas.find(a => a.id === item.area);
        return (area?.name || item.area || '').toLowerCase();
      },
    });
  }, [filteredItems, sortItems, allAreas, allRemoteDevices]);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <div className="flex-1">
          <FilterInput
            filter={filter}
            setFilter={setFilter}
            totalCount={items.length}
            filteredCount={sortedItems.length}
          />
        </div>
        <ResetSortButton isSorted={isSorted} onReset={resetSort} />
      </div>

      {/* Mobile card view */}
      <div className="sm:hidden space-y-2">
        {sortedItems.map(({ item, originalIndex }) => {
          const displayName = item.name || item.id || `Item ${originalIndex + 1}`;
          const sensorDef = getSensorDef(item.device_id, item.sensor_id);
          const unit = item.unit_of_measurement || sensorDef?.unit_of_measurement;
          const dc = item.device_class || sensorDef?.device_class;
          const areaName = item.area
            ? allAreas.find(a => a.id === item.area)?.name || item.area
            : '';
          return (
            <MobileCard
              key={originalIndex}
              title={displayName}
              subtitle={`📡 ${getDeviceName(item.device_id)}`}
              onEdit={() => onEdit(originalIndex)}
              onDelete={() => onDelete(originalIndex)}
              fields={[
                { label: t('remote_sensors.sensor_entity') || 'Sensor', value: item.sensor_id || '-' },
                ...(unit ? [{ label: t('remote_sensors.unit') || 'Unit', value: unit }] : []),
                ...(dc ? [{ label: t('remote_sensors.device_class') || 'device_class', value: dc }] : []),
                ...(areaName ? [{ label: t('outputs.area') || 'Area', value: areaName }] : []),
              ]}
            />
          );
        })}
      </div>

      {/* Desktop table view */}
      <div className="hidden sm:block overflow-x-auto">
        <Table className="table table-zebra w-full">
          <Thead>
            <Tr>
              <SortableHeader column="name" sortConfig={sortConfig} onToggleSort={toggleSort}>
                {t('outputs.name') || 'Name'} / ID
              </SortableHeader>
              <SortableHeader column="device" sortConfig={sortConfig} onToggleSort={toggleSort}>
                {t('remote_devices.device') || 'Device'}
              </SortableHeader>
              <SortableHeader column="sensor_id" sortConfig={sortConfig} onToggleSort={toggleSort}>
                {t('remote_sensors.sensor_entity') || 'Sensor'}
              </SortableHeader>
              <SortableHeader column="unit" sortConfig={sortConfig} onToggleSort={toggleSort}>
                {t('remote_sensors.unit') || 'Unit'}
              </SortableHeader>
              <SortableHeader column="device_class" sortConfig={sortConfig} onToggleSort={toggleSort}>
                {t('remote_sensors.device_class') || 'device_class'}
              </SortableHeader>
              <SortableHeader column="area" sortConfig={sortConfig} onToggleSort={toggleSort}>
                {t('outputs.area') || 'Area'}
              </SortableHeader>
              <Th>{t('outputs.actions') || 'Actions'}</Th>
            </Tr>
          </Thead>
          <Tbody>
            {sortedItems.map(({ item, originalIndex }) => {
              const effectiveId = item.id || `${item.device_id}_${item.sensor_id}`;
              const displayName = item.name || effectiveId || `Item ${originalIndex + 1}`;
              const sensorDef = getSensorDef(item.device_id, item.sensor_id);
              const unit = item.unit_of_measurement || sensorDef?.unit_of_measurement;
              const dc = item.device_class || sensorDef?.device_class;
              const areaName = item.area
                ? allAreas.find(a => a.id === item.area)?.name || item.area
                : '-';
              return (
                <Tr key={originalIndex}>
                  <Td>
                    <div>
                      <div className="font-medium flex items-center gap-1.5">
                        <FaWifi className="text-xs text-primary opacity-60" />
                        {displayName}
                      </div>
                      {item.name && effectiveId && (
                        <div className="text-xs text-base-content/60">ID: {effectiveId}</div>
                      )}
                    </div>
                  </Td>
                  <Td>
                    <span className="text-sm">{getDeviceName(item.device_id)}</span>
                  </Td>
                  <Td>
                    <code className="text-xs bg-base-200 px-1.5 py-0.5 rounded">{item.sensor_id || '-'}</code>
                  </Td>
                  <Td>
                    {unit ? <span className="badge badge-ghost badge-sm font-mono">{unit}</span> : <span className="text-base-content/40">-</span>}
                  </Td>
                  <Td>
                    {dc ? <span className="badge badge-info badge-sm">{dc}</span> : <span className="text-base-content/40">-</span>}
                  </Td>
                  <Td>{areaName}</Td>
                  <Td>
                    <TableActions
                      onEdit={() => onEdit(originalIndex)}
                      onDelete={() => onDelete(originalIndex)}
                      editTitle={t('outputs.edit') || 'Edit'}
                      deleteTitle={t('outputs.delete') || 'Delete'}
                    />
                  </Td>
                </Tr>
              );
            })}
          </Tbody>
        </Table>
      </div>
    </div>
  );
};

export default RemoteSensorTable;
