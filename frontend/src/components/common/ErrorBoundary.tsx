import { Component, type ReactNode } from 'react';
import { notify } from '../../services/notify';

interface State {
  error: Error | null;
}

/** Catches uncaught render errors so a single bad component can't white-screen
 *  the whole app — shows a recoverable fallback and raises a popup. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error): void {
    notify('error', `Something broke: ${error.message}`);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-8 text-center">
          <h1 className="text-lg font-bold text-error">Something went wrong</h1>
          <p className="max-w-md text-sm text-text-secondary">{this.state.error.message}</p>
          <div className="flex gap-2">
            <button className="btn-outline" onClick={() => this.setState({ error: null })}>
              Try again
            </button>
            <button className="btn-primary" onClick={() => window.location.reload()}>
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
