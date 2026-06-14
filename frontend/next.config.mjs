/**
 * Next.js configuration.
 *
 * Mostly defaults for now. The API base URL is NOT hardcoded here — it's read
 * from NEXT_PUBLIC_API_URL in .env.local (see lib/api.ts).
 *
 * TODO (optional): if you'd rather proxy API calls through Next.js to avoid CORS
 * entirely in dev, add a rewrites() block here pointing /api/* at the backend.
 */
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
