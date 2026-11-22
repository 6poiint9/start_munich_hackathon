import type {Metadata, Viewport} from 'next';
import localFont from 'next/font/local';
import type {ReactNode} from 'react';

import {themeBootScript} from '../lib/theme';

import './globals.css';

// The font file lives in the repository, so the build needs no network.
const inter = localFont({
  src: './fonts/InterVariable.woff2',
  variable: '--font-inter',
  weight: '100 900',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Lineguard',
  description:
    'Eine Seite pro Tag: Was kann die Linie stoppen, und was ist jetzt zu entscheiden.',
};

export const viewport: Viewport = {
  themeColor: [
    {media: '(prefers-color-scheme: light)', color: '#f6f6f7'},
    {media: '(prefers-color-scheme: dark)', color: '#0a0a0b'},
  ],
};

interface RootLayoutProps {
  children: ReactNode;
}

// Next.js needs the layout as the default export.
export default function RootLayout({children}: RootLayoutProps) {
  return (
    <html lang="de" className={inter.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{__html: themeBootScript}} />
      </head>
      <body className="lg-app min-h-dvh">
        <a
          href="#inhalt"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-[6px] focus:bg-[var(--accent)] focus:px-3 focus:py-2 focus:font-medium focus:text-[var(--accent-fg)]"
        >
          Zum Inhalt springen
        </a>
        {children}
      </body>
    </html>
  );
}
