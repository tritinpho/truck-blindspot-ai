import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

// Allow importing the single-source zone config (repo-root config/zones.example.json),
// so the HMI geometry stays driven by config/ rather than a duplicated copy (FR-03).
const repoRoot = fileURLToPath(new URL("../..", import.meta.url));

export default defineConfig({
  server: { fs: { allow: [repoRoot] } },
});
