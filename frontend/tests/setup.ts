import '@testing-library/jest-dom';

// jsdom does not implement window.matchMedia. Components using
// useIsMobileViewport (or any media-query hook) crash on mount without
// this stub. Defaults to "no match" so tests render the desktop layout.
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  });
}
