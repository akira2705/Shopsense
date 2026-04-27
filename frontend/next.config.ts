import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // Allow images from any external domain (CarWale, OLX, Amazon, Flipkart CDNs)
    remotePatterns: [
      { protocol: "https", hostname: "**" },
      { protocol: "http",  hostname: "**" },
    ],
  },
};

export default nextConfig;
