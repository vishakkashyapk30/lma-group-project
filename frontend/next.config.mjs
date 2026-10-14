/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // TODO: rewrites to the FastAPI backend (NEXT_PUBLIC_API_BASE_URL); demo reaches Ada through an SSH tunnel (plan §13.1)
};
export default nextConfig;
