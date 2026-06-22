import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const configDir = dirname(fileURLToPath(import.meta.url));
const astGrepConfig = join(configDir, "sgconfig.yml");

export default {
  "*.{ts,tsx,js,jsx,mjs,cjs,json,jsonc}": [
    "biome check --write --no-errors-on-unmatched",
    `npx -y --package @ast-grep/cli ast-grep scan --config ${astGrepConfig}`,
  ],
};
