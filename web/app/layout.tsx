import type {Metadata, Viewport} from 'next';
import localFont from 'next/font/local';
import type {ReactNode} from 'react';

import './globals.css';

// The font files live in the repository, so the build needs no network.
const hanken = localFont({
  src: './fonts/HankenGrotesk-Variable-latin.woff2',
  variable: '--font-hanken',
  weight: '300 700',
  display: 'swap',
});

const newsreader = localFont({
  src: './fonts/Newsreader-Variable-latin.woff2',
  variable: '--font-newsreader',
  weight: '300 500',
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
    'One page per day: what can stop the line, and what a person must decide now.',
};

export const viewport: Viewport = {
  themeColor: '#fdfefc',
};

interface RootLayoutProps {
  children: ReactNode;
}

// Next.js needs the layout as the default export.
export default function RootLayout({children}: RootLayoutProps) {
  return (
    <html lang="en" className={`${hanken.variable} ${newsreader.variable} ${plexMono.variable}`}>
      <body className="min-h-dvh">
        <a
          href="#content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-ctl focus:bg-ink focus:px-3 focus:py-2 focus:font-medium focus:text-paper"
        >
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
