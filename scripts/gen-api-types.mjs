import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { mkdtemp, rm } from "node:fs/promises";

const OPENAPI_URL = process.env.API_OPENAPI_URL ?? "http://127.0.0.1:8000/openapi.json";

const OUTPUT_FILE = process.env.API_TYPES_OUTFILE ?? "src/api/generated/openapi.ts";

const OPENAPI_FILE = process.env.API_OPENAPI_FILE;
const PYTHON_EXE = process.env.API_PYTHON_EXE ?? "backend/.venv/Scripts/python";
const DUMP_SCRIPT = "backend/dump_openapi.py";

function resolvePythonExe() {
  if (fs.existsSync(PYTHON_EXE)) return PYTHON_EXE;
  if (process.platform === "win32" && fs.existsSync(`${PYTHON_EXE}.exe`)) {
    return `${PYTHON_EXE}.exe`;
  }
  return null;
}

async function spawnAndWait(command, args, options) {
  const child = spawn(command, args, options);
  return await new Promise((resolve) => {
    child.on("exit", (code) => resolve(code ?? 1));
  });
}

async function canFetchOpenApi(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 750);

  try {
    const res = await fetch(url, { signal: controller.signal });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

async function main() {
  const cliPath = path.resolve(
    process.cwd(),
    "node_modules",
    "openapi-typescript",
    "bin",
    "cli.js",
  );

  if (!fs.existsSync(cliPath)) {
    console.error(
      "openapi-typescript not found. Run `vp install` first, then re-run `vp run gen:api`.",
    );
    process.exitCode = 1;
    return;
  }

  let schemaSource = OPENAPI_URL;
  let tmpDir = null;

  if (OPENAPI_FILE) {
    schemaSource = OPENAPI_FILE;
  } else {
    const urlOk = await canFetchOpenApi(OPENAPI_URL);
    if (!urlOk) {
      const pythonExe = resolvePythonExe();
      if (!pythonExe) {
        console.error(
          `OpenAPI URL not reachable (${OPENAPI_URL}) and Python not found at ${PYTHON_EXE}.\n` +
            "Start the backend (`vp run dev:backend`) or create the backend venv, then re-run `vp run gen:api`.",
        );
        process.exitCode = 1;
        return;
      }

      tmpDir = await mkdtemp(path.join(os.tmpdir(), "card-game-sim-openapi-"));
      const tmpSchemaFile = path.join(tmpDir, "openapi.json");

      const dumpExit = await spawnAndWait(pythonExe, [DUMP_SCRIPT, "--out", tmpSchemaFile], {
        stdio: "inherit",
      });
      if (dumpExit !== 0) {
        await rm(tmpDir, { recursive: true, force: true });
        process.exitCode = dumpExit;
        return;
      }

      schemaSource = tmpSchemaFile;
    }
  }

  const exitCode = await spawnAndWait(
    process.execPath,
    [cliPath, schemaSource, "-o", OUTPUT_FILE],
    { stdio: "inherit" },
  );

  if (tmpDir) {
    await rm(tmpDir, { recursive: true, force: true });
  }

  if (exitCode !== 0) {
    console.error(
      "\nType generation failed. Start the backend (`vp run dev:backend`) or ensure the backend venv exists (for local OpenAPI dump), then re-run `vp run gen:api`.",
    );
  }

  process.exitCode = exitCode;
}

await main();
