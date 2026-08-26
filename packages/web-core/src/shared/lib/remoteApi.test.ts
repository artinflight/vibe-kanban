import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/shared/lib/relayBackendApi', () => ({
  syncRelayApiBaseWithRemote: vi.fn(),
}));

import { getRemoteApiUrl, setRemoteApiBase } from './remoteApi';

describe('remote API runtime base', () => {
  beforeEach(() => {
    setRemoteApiBase(null);
  });

  it('allows local-only sessions to disable a configured remote base', () => {
    setRemoteApiBase('https://api.example.com');
    expect(getRemoteApiUrl()).toBe('https://api.example.com');

    setRemoteApiBase(null);
    expect(getRemoteApiUrl()).toBe('');
  });

  it('treats an empty runtime base as disabled', () => {
    setRemoteApiBase('https://api.example.com');
    setRemoteApiBase('');

    expect(getRemoteApiUrl()).toBe('');
  });
});
