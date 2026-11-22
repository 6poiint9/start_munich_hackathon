/** The choice stored in the browser. `system` follows the operating system. */
export type ThemeChoice = 'light' | 'dark' | 'system';

export const THEME_KEY = 'lineguard-theme';

export function isThemeChoice(value: string | null): value is ThemeChoice {
  return value === 'light' || value === 'dark' || value === 'system';
}

/**
 * Runs before first paint. It sets `data-theme` and `data-resolved` on
 * `<html>` so the colors are correct on the first frame.
 */
export const themeBootScript =
  "(function(){try{var k='lineguard-theme';var s=localStorage.getItem(k);var t=s==='light'||s==='dark'||s==='system'?s:'system';var d=t==='dark'||(t!=='light'&&matchMedia('(prefers-color-scheme: dark)').matches);var h=document.documentElement;h.dataset.theme=t;h.dataset.resolved=d?'dark':'light';}catch(e){}})();";
