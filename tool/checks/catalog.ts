/**
 * Expose maintenance-log checks to the command layer.
 * @file
 */
import { generatePluginCatalog } from "../catalog/command";
import { validateMaintenanceLog } from "./maintenance_log";

/** Print maintenance-log validation errors and return the check status. */
export async function checkMaintenanceLog(): Promise<number> {
  const issues = await validateMaintenanceLog();
  for (const issue of issues) console.error("ERROR: " + issue);
  return issues.length > 0 ? 1 : 0;
}

/** Ensure catalog JSON, documentation, and maintenance evidence are current. */
export async function checkCatalog(): Promise<number> {
  const exit = await generatePluginCatalog({ mode: "check" });
  return exit === 0 ? checkMaintenanceLog() : exit;
}
