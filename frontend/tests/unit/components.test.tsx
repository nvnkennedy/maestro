import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBadge } from '../../src/components/common/Badge';
import { Spinner } from '../../src/components/common/Spinner';

describe('StatusBadge', () => {
  it('renders the status text', () => {
    render(<StatusBadge status="passed" />);
    expect(screen.getByText('passed')).toBeInTheDocument();
  });
  it('renders unknown statuses with fallback style', () => {
    render(<StatusBadge status="weird" />);
    expect(screen.getByText('weird')).toBeInTheDocument();
  });
});

describe('Spinner', () => {
  it('shows its label', () => {
    render(<Spinner label="Loading dashboard…" />);
    expect(screen.getByText('Loading dashboard…')).toBeInTheDocument();
  });
});
