/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    // mongodb là native Node module — không bundle vào client; chỉ dùng trong API routes (Node runtime).
    serverComponentsExternalPackages: ["mongodb"],
  },
};

export default nextConfig;
