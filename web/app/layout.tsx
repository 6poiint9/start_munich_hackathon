import type {Metadata, Viewport} from 'next';
import localFont from 'next/font/local';
import type {ReactNode} from 'react';

import './globals.css';

// The font files live in the repository, so the build needs no network.
const plexSans = localFont({
  src: './fonts/IBMPlexSans-Variable-latin.woff2',
  variable: '--font-plex-sans',
  weight: '100 700',
  display: 'swap',
});

const plexMono = localFont({
  src: [
    {path: './fonts/IBMPlexMono-400-latin.woff2', weight: '400'},
    {path: './fonts/IBMPlexMono-500-latin.woff2', weight: '500'},
    {path: './fonts/IBMPlexMono-600-latin.woff2', weight: '600'},
  ],
  variable: '--font-plex-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Lineguard',
  description:
    'Eine Seite pro Tag: Was kann die Linie stoppen, und was ist jetzt zu entscheiden.',
};

export const viewport: Viewport = {
  themeColor: '#f3f2ed',
};

interface RootLayoutProps {
  children: ReactNode;
}

// Next.js needs the layout as the default export.
export default function RootLayout({children}: RootLayoutProps) {
  return (
    <html lang="de" className={`${plexSans.variable} ${plexMono.variable}`}>
      <body className="min-h-dvh bg-paper text-ink">
        <a
          href="#inhalt"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-ctl focus:bg-ink focus:px-3 focus:py-2 focus:text-white"
        >
          Zum Inhalt springen
        </a>
        {children}
      </body>
    </html>
  );
}
