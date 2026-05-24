import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  // Project-wide rule overrides.
  {
    rules: {
      // The set-state-in-effect rule flags the standard data-fetching pattern
      // `setLoading(true)` at the top of a useEffect. This is intentional and
      // correct — the rule is too aggressive for this codebase's pattern.
      "react-hooks/set-state-in-effect": "off",
      // Unused vars are warnings, not errors — keep visibility but don't fail.
      "@typescript-eslint/no-unused-vars": "warn",
    },
  },
]);

export default eslintConfig;
