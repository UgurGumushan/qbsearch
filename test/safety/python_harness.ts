import { resolve } from "node:path";
import { FIXTURES_DIR } from "../../tool/core/repo";
import { runPythonCaptured } from "../../tool/core/run";

const PYTHON_HELPER_FIXTURE = resolve(FIXTURES_DIR, "safety_helper.py");

export async function runSafetyPythonHarness(helperPath: string, baseUrl: string): Promise<void> {
  const result = await runPythonCaptured([PYTHON_HELPER_FIXTURE, helperPath, baseUrl]);
  if (result.code !== 0) {
    throw new Error(
      `Python safety helper test failed with exit code ${result.code}.\n${result.output}`,
    );
  }
  process.stdout.write(result.output);
}
