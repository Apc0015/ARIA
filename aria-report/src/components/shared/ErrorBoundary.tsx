import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { GlassCard } from "@/components/glass/GlassCard";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
  /** Page name shown in the message, e.g. "Monitor". */
  context?: string;
}

interface State {
  error: Error | null;
  componentStack: string | null;
}

/**
 * Catches rendering errors (including a failed lazy route chunk) and shows a
 * recovery card instead of a blank screen. Key it by route so navigating
 * away resets it.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, componentStack: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    this.setState({ componentStack: info.componentStack ?? null });
    console.error(`[ARIA] Render error${this.props.context ? ` in ${this.props.context}` : ""}`, error, info);
  }

  private reset = () => this.setState({ error: null, componentStack: null });

  render() {
    const { error, componentStack } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="flex flex-1 items-center justify-center p-5">
        <GlassCard className="w-full max-w-md p-6 text-center space-y-4" role="alert">
          <AlertTriangle size={22} className="mx-auto text-aria-text3" aria-hidden="true" />
          <div className="space-y-1">
            <p className="text-[15px] font-medium text-aria-text1">
              Something went wrong{this.props.context ? ` in ${this.props.context}` : ""}
            </p>
            <p className="text-[12px] text-aria-text4">{error.message || "An unexpected error occurred."}</p>
          </div>
          <div className="flex justify-center gap-2">
            <Button size="sm" variant="primary" onClick={this.reset}>
              Try again
            </Button>
            <Button size="sm" variant="outline" onClick={() => window.location.reload()}>
              Reload page
            </Button>
          </div>
          {import.meta.env.DEV && componentStack && (
            <details className="text-left">
              <summary className="cursor-pointer text-[11px] text-aria-text4">Component stack (dev only)</summary>
              <pre className="mt-2 max-h-48 overflow-auto text-[10px] text-aria-text4">{componentStack}</pre>
            </details>
          )}
        </GlassCard>
      </div>
    );
  }
}
