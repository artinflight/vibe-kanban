import { useContext } from 'react';
import { createHmrContext } from '@/shared/lib/hmrContext';

export interface SupervisorLauncherState {
  enabled: boolean;
  open: boolean;
  show: () => void;
}

export const SupervisorContext =
  createHmrContext<SupervisorLauncherState | null>('SupervisorContext', null);

// Remote web has no local supervisor provider until principal mapping exists.
export function useSupervisor() {
  return useContext(SupervisorContext);
}
