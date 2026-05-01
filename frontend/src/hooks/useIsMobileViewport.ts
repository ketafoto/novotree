import { useEffect, useState } from 'react';

const MOBILE_VIEWPORT_BREAKPOINT_PX = 768;
const MOBILE_VIEWPORT_MEDIA_QUERY = `(max-width: ${MOBILE_VIEWPORT_BREAKPOINT_PX - 1}px)`;

/**
 * True when the viewport is narrow enough to be treated as mobile
 * (below Tailwind's md breakpoint). Reactive to resize and DevTools
 * device-mode toggling.
 */
export function useIsMobileViewport(): boolean {
  const [isMobileViewport, setIsMobileViewport] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia(MOBILE_VIEWPORT_MEDIA_QUERY).matches;
  });

  useEffect(() => {
    const mql = window.matchMedia(MOBILE_VIEWPORT_MEDIA_QUERY);
    const handler = (e: MediaQueryListEvent) => setIsMobileViewport(e.matches);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, []);

  return isMobileViewport;
}
