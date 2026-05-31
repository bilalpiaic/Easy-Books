import type { NextConfig } from "next";
import { createRequire } from "module";

const _require = createRequire(import.meta.url);
const { version } = _require("./package.json") as { version: string };

const nextConfig: NextConfig = {
  // Self-contained server bundle for local/on-premise packaging (Phase 0).
  output: "standalone",
  env: { NEXT_PUBLIC_APP_VERSION: version },
  turbopack: {
    root: __dirname,
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
