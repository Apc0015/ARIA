import { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  context?: string; // e.g. "Dashboard", "Monitor" — shown in the error message
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

/**
 * React error boundary that catches rendering errors and shows a friendly
 * recovery UI instead of a blank white screen.
 *
 * Usage:
 *   <ErrorBoundary context="Monitor">
 *     <MonitorPage />
 *   </ErrorBoundary>
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    // In production you'd send this to an error tracking service
    console.error(`[ARIA ErrorBoundary${this.props.context ? ` — ${this.props.context}` : ""}]`, error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    if (this.props.fallback) {
      return this.props.fallback;
    }

    return (
      <div className="flex min-h-[40vh] flex-col items-center justify-center gap-4 p-8 text-center">
        <div className="rounded-full bg-red-100 p-4 dark:bg-red-900/20">
          <svg
            className="h-8 w-8 text-red-600 dark:text-red-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>

        <div className="max-w-md">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Something went wrong
            {this.props.context && (
              <span className="text-gray-500"> in {this.props.context}</span>
            )}
          </h2>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {this.state.error?.message || "An unexpected error occurred."}
          </p>
        </div>

        <div className="flex gap-3">
          <button
            onClick={this.handleReset}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Try again
          </button>
          <button
            onClick={() => window.location.reload()}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            Reload page
          </button>
        </div>

        {import.meta.env.DEV && this.state.errorInfo && (
          <details className="mt-4 w-full max-w-2xl rounded border border-red-200 bg-red-50 p-3 text-left dark:border-red-800 dark:bg-red-950/30">
            <summary className="cursor-pointer text-xs font-medium text-red-700 dark:text-red-400">
              Stack trace (dev only)
            </summary>
            <pre className="mt-2 overflow-auto text-xs text-red-600 dark:text-red-400">
              {this.state.errorInfo.componentStack}
            </pre>
          </details>
        )}
      </div>
    );
  }
}
