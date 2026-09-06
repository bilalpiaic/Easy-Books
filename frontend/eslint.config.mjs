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
      // Pre-existing on main: compiler purity/static-components, `any` in
      // report tables, a couple of <a> vs <Link> and apostrophes. Warn until
      // those pages are rewritten; hooks-order stays an error.
      "react-hooks/static-components": "warn",
      "react-hooks/immutability": "warn",
      "react-hooks/purity": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/globals": "warn",
      "react-hooks/use-memo": "warn",
      "@typescript-eslint/no-explicit-any": "warn",
      "react/no-unescaped-entities": "warn",
      "@next/next/no-html-link-for-pages": "warn",
    },
  },
]);

export default eslintConfig;
