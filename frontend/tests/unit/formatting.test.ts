import { describe, expect, it } from 'vitest';
import { formatDuration, truncate } from '../../src/utils/formatting';

describe('formatDuration', () => {
  it('handles null', () => {
    expect(formatDuration(null)).toBe('—');
  });
  it('formats milliseconds', () => {
    expect(formatDuration(0.25)).toBe('250ms');
  });
  it('formats seconds', () => {
    expect(formatDuration(12.34)).toBe('12.3s');
  });
  it('formats minutes', () => {
    expect(formatDuration(125)).toBe('2m 5s');
  });
});

describe('truncate', () => {
  it('keeps short strings', () => {
    expect(truncate('abc', 10)).toBe('abc');
  });
  it('truncates long strings', () => {
    expect(truncate('a'.repeat(20), 10)).toBe(`${'a'.repeat(10)}…`);
  });
});
