import { Component } from "react";

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error("[ErrorBoundary]", error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div
        role="alert"
        aria-live="assertive"
        aria-label="Application error"
        className="min-h-screen flex items-center justify-center p-6 bg-background"
      >
        <div className="w-full max-w-md rounded-3xl p-8 text-center border border-border/50 bg-card petal-shadow">
          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-destructive"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>

          <h2 className="mb-2 font-headline text-xl font-semibold text-foreground">
            Something went wrong
          </h2>
          <p className="mb-6 text-sm leading-relaxed text-muted-foreground">
            The app encountered an unexpected error. Your conversations are saved
            and will be here when you come back.
          </p>

          {this.state.error?.message && (
            <p
              className="mb-6 rounded-xl px-4 py-3 text-xs font-mono text-left break-anywhere bg-muted/50 text-muted-foreground border border-border/40"
              aria-label="Error details"
            >
              {this.state.error.message}
            </p>
          )}

          <button
            type="button"
            onClick={() => window.location.reload()}
            className="w-full rounded-2xl px-6 py-3 text-sm font-semibold bg-primary text-primary-foreground transition-all duration-200 hover:bg-primary/90 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 petal-shadow"
          >
            Reload app
          </button>

          <button
            type="button"
            onClick={() => this.setState({ hasError: false, error: null })}
            className="mt-3 w-full rounded-2xl px-6 py-3 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            Try to continue
          </button>
        </div>
      </div>
    );
  }
}
