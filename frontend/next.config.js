/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // En local : pointe vers localhost:8000
    // En production Vercel : les rewrites viennent de vercel.json (pas besoin d'apiUrl)
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
      {
        source: "/outputs/:path*",
        destination: `${apiUrl}/outputs/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
