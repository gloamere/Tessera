import { spawn } from "node:child_process";

const npmCli = process.env.npm_execpath;

if (!npmCli) {
  throw new Error("npm_execpath is required; run this script through npm.");
}

const child = spawn(process.execPath, [npmCli, "run", "build"], {
  stdio: "inherit",
  env: {
    ...process.env,
    GLOAMERE_STATIC_EXPORT: "1",
  },
});

child.on("error", (error) => {
  throw error;
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exitCode = code ?? 1;
});
