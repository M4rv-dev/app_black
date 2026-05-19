import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * Route-level error boundary that catches unhandled React render errors
 * and displays a styled fallback instead of crashing the whole SPA.
 * Wrap each route's Layout with this component.
 */
class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (import.meta.env.DEV) {
      console.error('[ErrorBoundary]', error, info.componentStack);
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center h-full min-h-64 p-8">
          <div className="text-center max-w-md">
            <AlertTriangle className="w-10 h-10 text-error mx-auto mb-3" />
            <h2 className="text-lg font-bold mb-2">Something went wrong</h2>
            {import.meta.env.DEV && this.state.error && (
              <p className="text-xs text-base-content/60 font-mono mb-4 break-all">
                {this.state.error.message}
              </p>
            )}
            <button onClick={this.handleReset} className="btn btn-sm btn-primary gap-2">
              <RefreshCw className="w-3 h-3" />
              Try again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
