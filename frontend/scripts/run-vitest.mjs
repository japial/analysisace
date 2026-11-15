// Runs Vitest from a working directory with an upper-case drive letter.
// On Windows, a lower-case drive (d:\...) makes Vitest load its modules twice and every
// test file fails with "Cannot read properties of undefined (reading 'config')".
import { spawnSync } from "node:child_process";

const cwd = process.cwd().replace(/^[a-z]:/, (drive) => drive.toUpperCase());
const result = spawnSync(
  process.execPath,
  ["node_modules/vitest/vitest.mjs", ...process.argv.slice(2)],
  { cwd, stdio: "inherit" },
);
process.exit(result.status ?? 1);
