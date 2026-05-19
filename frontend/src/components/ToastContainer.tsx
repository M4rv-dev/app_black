import { X } from 'lucide-react';
import clsx from 'clsx';
import { useToast } from '../hooks/useToast';
import type { Toast } from '../hooks/useToast';

/**
 * Global toast container — render once inside App, outside Routes.
 * Displays DaisyUI alert toasts in the top-right corner with auto-dismiss.
 */

const ALERT_CLASS: Record<Toast['type'], string> = {
  success: 'alert-success',
  error:   'alert-error',
  warning: 'alert-warning',
  info:    'alert-info',
};

export default function ToastContainer() {
  const { toasts, dismiss } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="toast toast-top toast-end z-[200] max-w-sm w-full pointer-events-none">
      {toasts.map(t => (
        <div
          key={t.id}
          className={clsx(
            'alert shadow-lg pointer-events-auto flex items-start gap-3 animate-in slide-in-from-right-4 fade-in duration-200',
            ALERT_CLASS[t.type]
          )}
          role="alert"
        >
          <span className="flex-1 text-sm">{t.message}</span>
          <button
            onClick={() => dismiss(t.id)}
            className="btn btn-ghost btn-xs btn-circle shrink-0 -mr-1 -mt-1"
            aria-label="Dismiss"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      ))}
    </div>
  );
}
