import type {NextConfig} from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Builds a small server for the Docker image (web/Dockerfile).
  output: 'standalone',
};

// Next.js reads the configuration from the default export.
export default nextConfig;
