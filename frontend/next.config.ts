import type { NextConfig } from "next";
import { createRequire } from "module";
import { withSerwist } from "@serwist/turbopack";

const _require = createRequire(import.meta.url);
const { version } = _require("./package.json") as { version: string };

const nextConfig: NextConfig = {
  // Self-contained server bundle for local/on-premise packaging (Phase 0).
  output: "standalone",
  env: {
    NEXT_PUBLIC_APP_VERSION: version,
    // Stamped by install-and-run scripts at build time; empty in `npm run dev`
    NEXT_PUBLIC_GIT_COMMIT:  process.env.NEXT_PUBLIC_GIT_COMMIT  ?? "",
    NEXT_PUBLIC_BUILD_DATE:  process.env.NEXT_PUBLIC_BUILD_DATE  ?? new Date().toISOString(),
  },
  // Allow HMR from the WSL2 network IP so the app works when accessed
  // from a Windows browser via the WSL2 VM address (e.g. 172.28.52.3).
  allowedDevOrigins: ["172.28.52.3"],
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

export default withSerwist(nextConfig);
