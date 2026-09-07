/** @type {import('next').NextConfig} */
const backendUrl = process.env.SATQUERY_BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  // Playwright and local proxies often hit the dev server via 127.0.0.1 rather than localhost.
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    return [
      { source: "/health", destination: `${backendUrl}/health` },
      { source: "/api/:path*", destination: `${backendUrl}/api/:path*` },
    ];
  },
};

module.exports = nextConfig;
