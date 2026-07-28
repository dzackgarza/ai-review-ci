// ESLint flat config for TypeScript QC

import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import tsPlugin from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";
import diffPlugin from "eslint-plugin-diff";
import fpPlugin from "eslint-plugin-fp";
import promisePlugin from "eslint-plugin-promise";
import reactHooksPlugin from "eslint-plugin-react-hooks";
import reactRefreshPlugin from "eslint-plugin-react-refresh";
import vuePlugin from "eslint-plugin-vue";
import globals from "globals";
import { parse as parseToml } from "smol-toml";
import vueParser from "vue-eslint-parser";

const configDir = dirname(fileURLToPath(import.meta.url));
const qcExcludeConfig = parseToml(
  readFileSync(join(configDir, "qc-excludes.toml"), "utf8"),
);
const centralExcludeDirs = qcExcludeConfig.directories;
if (!Array.isArray(centralExcludeDirs)) {
  throw new Error("qc-excludes.toml directories must be an array");
}
const centralIgnoreGlobs = centralExcludeDirs.map((directory, index) => {
  if (typeof directory !== "string") {
    throw new Error(`qc-excludes.toml directories[${index}] must be a string`);
  }
  if (directory.length === 0) {
    throw new Error(`qc-excludes.toml directories[${index}] must be a non-empty string`);
  }
  return `**/${directory}/**`;
});
const diffBase = process.env.ESLINT_PLUGIN_DIFF_COMMIT;
const diffConfigs = diffBase === undefined
  ? []
  : diffPlugin.configs["flat/diff"].map((config) => ({
      ...config,
      ignores: [...(config.ignores ?? []), "**/*.vue"],
    }));
const vueProcessor = vuePlugin.processors.vue ?? vuePlugin.processors[".vue"];
if (vueProcessor === undefined) {
  throw new Error("eslint-plugin-vue does not expose a Vue processor");
}
const targetTsconfigPath = join(process.cwd(), "tsconfig.json");
const targetTsconfigText = existsSync(targetTsconfigPath)
  ? readFileSync(targetTsconfigPath, "utf8")
  : "";
const isAgsProject =
  targetTsconfigText.includes('"jsxImportSource": "ags/gtk4"')
  || targetTsconfigText.includes('"gi://Astal?version=4.0"');
const agsTsxOverrides = isAgsProject
  ? [
      {
        // AGS/GJS files: Gtk runtime types cannot be statically resolved by TSC.
        // This exception is activated only by the project's declared AGS
        // tsconfig contract; ordinary React TSX retains typed linting.
        files: ["**/*.tsx"],
        languageOptions: {
          parser: tsParser,
          parserOptions: {
            ecmaVersion: "latest",
            sourceType: "module",
            projectService: false,
          },
          globals: {
            ...globals.node,
          },
        },
        plugins: {
          "@typescript-eslint": tsPlugin,
          fp: fpPlugin,
          "react-hooks": reactHooksPlugin,
          "react-refresh": reactRefreshPlugin,
        },
        rules: {
          "@typescript-eslint/no-unsafe-call": "off",
          "@typescript-eslint/no-unsafe-member-access": "off",
          "@typescript-eslint/no-unsafe-assignment": "off",
          "@typescript-eslint/no-unsafe-return": "off",
          "@typescript-eslint/no-unsafe-argument": "off",
          "@typescript-eslint/no-floating-promises": "off",
          "@typescript-eslint/no-misused-promises": "off",
          "@typescript-eslint/await-thenable": "off",
          "@typescript-eslint/no-unnecessary-type-assertion": "off",
          "@typescript-eslint/prefer-nullish-coalescing": "off",
          "@typescript-eslint/prefer-optional-chain": "off",
          "fp/no-nil": "off",
          "fp/no-this": "off",
          "react-hooks/rules-of-hooks": "off",
          "react-hooks/exhaustive-deps": "off",
          "react-refresh/only-export-components": "off",
        },
      },
    ]
  : [];

export default [
  // Global ignores: apply before any rule config
  {
    ignores: [
      "**/env.d.ts",
      ...centralIgnoreGlobs,
    ],
  },
  ...vuePlugin.configs["flat/recommended"],
  ...diffConfigs,
  {
    files: ["**/*.ts", "**/*.tsx"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        // projectService: true uses TypeScript's project service, which handles
        // files not explicitly listed in tsconfig.json without a hard parse error.
        projectService: true,
        tsconfigRootDir: process.cwd(),
      },
      globals: {
        ...globals.node,
      },
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
      promise: promisePlugin,
      fp: fpPlugin,
    },
    rules: {
      // @typescript-eslint full suite
      "@typescript-eslint/no-unsafe-assignment": "error",
      "@typescript-eslint/no-unsafe-call": "error",
      "@typescript-eslint/no-unsafe-member-access": "error",
      "@typescript-eslint/no-unsafe-return": "error",
      "@typescript-eslint/no-unsafe-argument": "error",
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/no-misused-promises": "error",
      "@typescript-eslint/await-thenable": "error",
      "@typescript-eslint/no-unnecessary-type-assertion": "error",
      "@typescript-eslint/no-unnecessary-boolean-literal-compare": "error",
      "@typescript-eslint/consistent-type-imports": [
        "error",
        { prefer: "type-imports", fixStyle: "separate-type-imports" },
      ],
      "@typescript-eslint/no-base-to-string": "error",
      "@typescript-eslint/no-dynamic-delete": "error",
      "@typescript-eslint/no-unused-expressions": "error",
      "@typescript-eslint/strict-boolean-expressions": "error",
      "@typescript-eslint/prefer-nullish-coalescing": "off",
      "@typescript-eslint/prefer-optional-chain": "off",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      curly: ["error", "all"],

      // eslint-plugin-promise
      "promise/always-return": "off",
      "promise/no-return-wrap": "error",
      "promise/param-names": "error",
      "promise/catch-or-return": "off",
      "promise/no-native": "off",
      // Nesting/callback rules are intentionally off to avoid over-constraining
      // promise composition in application code.
      "promise/no-nesting": "off",
      "promise/no-promise-in-callback": "off",
      "promise/no-callback-in-promise": "off",

      // eslint-plugin-fp (functional programming)
      // Bridge-burning policy is enforced by semantic QC rules, not generic
      // functional-style bans. These rules over-fire on legitimate TypeScript
      // surfaces: void callbacks, declarations, classes, Express handlers, and
      // React state.
      "fp/no-nil": "off",
      "fp/no-this": "off",
      "fp/no-mutating-assign": "error",
      "fp/no-mutating-methods": "off", // too strict for most codebases
      // fp/no-let: disabled because global QC permits local mutable bindings
      // when they make state transitions explicit.

    },
  },
  {
    files: ["**/*.tsx"],
    plugins: {
      "react-hooks": reactHooksPlugin,
      "react-refresh": reactRefreshPlugin,
    },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    },
  },
  {
    files: ["**/*.vue"],
    processor: diffBase === undefined
      ? vueProcessor
      : diffPlugin.composeProcessor(vueProcessor, "diff"),
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: tsParser,
        ecmaVersion: "latest",
        sourceType: "module",
        projectService: true,
        extraFileExtensions: [".vue"],
        tsconfigRootDir: process.cwd(),
      },
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
      promise: promisePlugin,
      fp: fpPlugin,
      vue: vuePlugin,
    },
    rules: {
      "@typescript-eslint/no-unsafe-assignment": "error",
      "@typescript-eslint/no-unsafe-call": "error",
      "@typescript-eslint/no-unsafe-member-access": "error",
      "@typescript-eslint/no-unsafe-return": "error",
      "@typescript-eslint/no-unsafe-argument": "error",
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/no-misused-promises": "error",
      "@typescript-eslint/await-thenable": "error",
      "@typescript-eslint/no-unnecessary-type-assertion": "error",
      "@typescript-eslint/no-unnecessary-boolean-literal-compare": "error",
      "@typescript-eslint/consistent-type-imports": [
        "error",
        { prefer: "type-imports", fixStyle: "separate-type-imports" },
      ],
      "@typescript-eslint/no-base-to-string": "error",
      "@typescript-eslint/no-dynamic-delete": "error",
      "@typescript-eslint/no-unused-expressions": "error",
      "@typescript-eslint/strict-boolean-expressions": "error",
      "@typescript-eslint/prefer-nullish-coalescing": "off",
      "@typescript-eslint/prefer-optional-chain": "off",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "promise/always-return": "off",
      "promise/no-return-wrap": "error",
      "promise/param-names": "error",
      "promise/catch-or-return": "off",
      "promise/no-native": "off",
      "promise/no-nesting": "off",
      "promise/no-promise-in-callback": "off",
      "promise/no-callback-in-promise": "off",
      "fp/no-nil": "off",
      "fp/no-this": "off",
      "fp/no-mutating-assign": "error",
      "fp/no-mutating-methods": "off",
      "vue/no-v-html": "error",
      curly: ["error", "all"],
    },
  },
  {
    // Test files: relax LWC and fp rules. Async/await and void-returning callbacks
    // are idiomatic in test suites (bun:test, jest, etc.) and pre-exist in most PRs.
    // This block comes LAST so it overrides the main config above.
    files: ["tests/**/*.ts", "**/*.test.ts", "**/*.spec.ts"],
    rules: {
      "fp/no-nil": "off",
      "@typescript-eslint/no-floating-promises": "off",
      "@typescript-eslint/no-unsafe-call": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
      "@typescript-eslint/no-unsafe-assignment": "off",
      "@typescript-eslint/no-unsafe-return": "off",
      "@typescript-eslint/prefer-nullish-coalescing": "off",
      "promise/always-return": "off",
      "promise/catch-or-return": "off",
      "promise/no-native": "off",
      "no-undef": "off",
    },
  },
  ...agsTsxOverrides,
];
