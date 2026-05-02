/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Static export -- FastAPI will serve `out/` directly so the whole app
  // (UI + API) lives behind a single URL on Render.
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};
module.exports = nextConfig;
