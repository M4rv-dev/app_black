import { useState, useCallback, useEffect } from 'react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
  /** Auto-dismiss after ms (default 4000, 0 = sticky) */
  duration?: number;
}

let globalListeners = new Set<(toasts: Toast[]) => void>();
let globalToasts: Toast[] = [];
let idCounter = 0;

const notify = () => {
  globalListeners.forEach(l => l([...globalToasts]));
};

/**
 * Push a toast notification from anywhere (outside React tree too).
 * Returns a dismiss function for that specific toast.
 */
export const pushToast = (message: string, type: ToastType = 'info', duration = 4000): (() => void) => {
  const id = `t${++idCounter}`;
  globalToasts = [...globalToasts, { id, message, type, duration }];
  notify();

  const dismiss = () => {
    globalToasts = globalToasts.filter(t => t.id !== id);
    notify();
  };

  if (duration > 0) {
    setTimeout(dismiss, duration);
  }

  return dismiss;
};

/**
 * React hook — subscribe to the global toast list.
 * Safe to call in multiple components; only one <ToastContainer> should render.
 */
export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>(globalToasts);

  useEffect(() => {
    globalListeners.add(setToasts);
    setToasts([...globalToasts]);
    return () => {
      globalListeners.delete(setToasts);
    };
  }, []);

  const dismiss = useCallback((id: string) => {
    globalToasts = globalToasts.filter(t => t.id !== id);
    notify();
  }, []);

  const toast = useCallback((message: string, type: ToastType = 'info', duration = 4000) => {
    return pushToast(message, type, duration);
  }, []);

  return { toasts, dismiss, toast };
}
