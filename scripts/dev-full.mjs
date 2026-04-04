import { spawn } from "node:child_process";
import process from "node:process";

const backendCommand = "backend/.venv/Scripts/python";
const backendArgs = ["backend/run_dev.py"];
const frontendCommand = "vp";
const frontendArgs = ["dev"];
let shuttingDown = false;

function startProcess(label, command, args) {
  const child = spawn(command, args, {
    stdio: "inherit",
    shell: false,
  });

  child.on("exit", (code, signal) => {
    if (signal) {
      console.log(`${label} exited with signal ${signal}`);
    } else {
      console.log(`${label} exited with code ${code ?? 0}`);
    }

    if (!shuttingDown) {
      shuttingDown = true;
      stopChildren();
      process.exitCode = code ?? 1;
    }
  });

  child.on("error", (error) => {
    console.error(`${label} failed to start:`, error);
    process.exitCode = 1;
  });

  return child;
}

const backend = startProcess("backend", backendCommand, backendArgs);
const frontend = startProcess("frontend", frontendCommand, frontendArgs);

const children = [backend, frontend];

function stopChildren() {
  shuttingDown = true;
  for (const child of children) {
    if (!child.killed) {
      child.kill();
    }
  }
}

process.on("SIGINT", () => {
  stopChildren();
  process.exit(130);
});

process.on("SIGTERM", () => {
  stopChildren();
  process.exit(143);
});

void Promise.all([
  new Promise((resolve) => backend.on("exit", resolve)),
  new Promise((resolve) => frontend.on("exit", resolve)),
]).finally(() => {
  stopChildren();
  if (typeof process.exitCode === "number" && process.exitCode !== 0) {
    process.exit(process.exitCode);
  }
});
