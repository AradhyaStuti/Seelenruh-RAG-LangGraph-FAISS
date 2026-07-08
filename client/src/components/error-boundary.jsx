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
        className="min-h-screen flex items-center justify-center p-6"
        style={{ background: "hsl(var(--background))" }}
      >
        <div
          className="w-full max-w-md rounded-3xl p-8 text-center shadow-xl"
          style={{
            background: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
          }}
        >
          <div
            className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full"
            style={{ background: "hsl(var(--primary) / 0.12)" }}
          >
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
              stroke="hsl(var(--primary))"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <h2
            className="mb-2 text-xl font-semibold"
            style={{ color: "hsl(var(--foreground))" }}
          >
            Something went wrong
          </h2>
          <p
            className="mb-6 text-sm leading-relaxed"
            style={{ color: "hsl(var(--muted-foreground))" }}
          >
            The app encountered an unexpected error. Your conversations are saved
            and will be here when you come back.
          </p>
          {this.state.error?.message && (
            <p
              className="mb-6 rounded-xl px-4 py-3 text-xs font-mono text-left break-all"
              style={{
                background: "hsl(var(--muted) / 0.5)",
                color: "hsl(var(--muted-foreground))",
              }}
            >
              {this.state.error.message}
            </p>
          )}
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="w-full rounded-2xl px-6 py-3 text-sm font-semibold transition active:scale-95"
            style={{
              background: "hsl(var(--primary))",
              color: "hsl(var(--primary-foreground))",
            }}
          >
            Reload app
          </button>
        </div>
      </div>
    );
  }
}
