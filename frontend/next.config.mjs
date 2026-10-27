// When NEXT_PUBLIC_API_BASE is a path such as "/backend" (the Docker default), the browser calls the Next server on its own
// origin and the rewrite below forwards to the FastAPI backend (BACKEND_INTERNAL_URL, resolved at build time, so it is a
// build arg in the Docker image). Any absolute URL (or unset) leaves the app calling the backend directly, as in `npm run dev`.
const apiBase = (process.env.NEXT_PUBLIC_API_BASE ?? "").trim().replace(/\/+$/, "");
const proxyPrefix = apiBase.startsWith("/") ? apiBase : null;
const backendInternal = (process.env.BACKEND_INTERNAL_URL ?? "http://backend:8000").replace(/\/+$/, "");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // NEXT_DIST_DIR lets a build run beside a dev server in the same checkout (default .next, which the Docker image uses).
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // React's <ViewTransition> for route crossfades and the case-title morph (components/motion/PageTransition.tsx).
  // Next 15 ships it behind this flag; browsers without the View Transitions API swap pages instantly.
  experimental: { viewTransition: true },
  // Self-contained server bundle for the Docker image (copies only the traced node_modules).
  output: "standalone",
  // gzip in Next's server would buffer the proxied SSE event stream, so it is off in proxy mode (put a CDN/proxy in front if needed).
  compress: proxyPrefix ? false : true,
  async rewrites() {
    return proxyPrefix ? [{ source: `${proxyPrefix}/:path*`, destination: `${backendInternal}/:path*` }] : [];
  },
};
export default nextConfig;
