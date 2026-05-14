/** @type {import('next').NextConfig} */
const isDev = process.env.NODE_ENV !== 'production';

const nextConfig = {
  // Static export — produces ./out for FastAPI to serve.
  output: 'export',
  // The Next.js Image optimizer requires a server; disable for static export.
  images: { unoptimized: true },
  reactStrictMode: true,
  trailingSlash: false,
};

// Note: rewrites are ignored by `output: 'export'`. They are useful in dev so
// `next dev` can proxy /api/* to the FastAPI server running on :8000. We attach
// them only outside of production builds to keep the static-export build clean
// (no "rewrites won't apply" warnings).
if (isDev) {
  nextConfig.rewrites = async () => {
    const target = process.env.BACKEND_URL || 'http://localhost:8000';
    return [
      { source: '/api/:path*', destination: `${target}/api/:path*` },
    ];
  };
}

module.exports = nextConfig;
