import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorBannerProps {
  message: string;
  onRetry?: () => void;
}

/**
 * Full-screen error banner displayed when a critical WebSocket or API error occurs.
 * Provides a user-friendly message and an optional retry action.
 */
const ErrorBanner = ({ message, onRetry }: ErrorBannerProps) => {
  return (
    <div className="fixed inset-0 flex items-center justify-center z-50">
      <div className="p-8 text-center max-w-md">
        <AlertTriangle className="w-12 h-12 text-error mx-auto mb-4" />
        <h2 className="text-xl font-bold mb-2">Connection error</h2>
        <p className="text-base-content/70 mb-6 text-sm font-mono break-all">{message}</p>
        {onRetry && (
          <button onClick={onRetry} className="btn btn-primary gap-2">
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        )}
      </div>
    </div>
  );
};

export default ErrorBanner;
