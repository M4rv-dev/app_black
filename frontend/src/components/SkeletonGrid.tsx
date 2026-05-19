/**
 * Generic skeleton loader displayed while WebSocket data is loading.
 * Shows a responsive grid of pulsing placeholder cards matching
 * the target view layout (outputs grid, inputs list, sensors, etc.).
 */

interface SkeletonCardProps {
  wide?: boolean;
}

function SkeletonCard({ wide = false }: SkeletonCardProps) {
  return (
    <div className={`card bg-base-200 animate-pulse ${wide ? 'col-span-full sm:col-span-2' : ''}`}>
      <div className="card-body p-4 gap-3">
        <div className="h-4 bg-base-300 rounded w-2/3" />
        <div className="h-3 bg-base-300 rounded w-1/3" />
        <div className="h-8 bg-base-300 rounded w-full mt-1" />
      </div>
    </div>
  );
}

interface SkeletonGridProps {
  /** Number of skeleton cards to render */
  count?: number;
  /** Use list layout (single column) instead of grid */
  list?: boolean;
}

export default function SkeletonGrid({ count = 8, list = false }: SkeletonGridProps) {
  return (
    <div
      className={
        list
          ? 'flex flex-col gap-2'
          : 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3'
      }
      aria-busy="true"
      aria-label="Loading…"
    >
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}
