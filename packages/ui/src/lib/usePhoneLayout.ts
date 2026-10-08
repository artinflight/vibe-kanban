import { useSyncExternalStore } from 'react';

const query = '(max-width: 767px)';
const subscribe = (notify: () => void) => {
  const media = window.matchMedia(query);
  media.addEventListener('change', notify);
  return () => media.removeEventListener('change', notify);
};

/** Presentation breakpoint shared by the phone-specific component layouts. */
export function usePhoneLayout() {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => false
  );
}
