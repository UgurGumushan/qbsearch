import { generatePluginCatalog } from "../catalog/command";
import { validateMaintenanceLog } from "./maintenance_log";

/** Ensure catalog JSON and generated documentation are current before dependent jobs. */
export function checkCatalog(): Promise<number> {
  return (async () => {
    const catalogExit = await generatePluginCatalog(["--check"]);
    if (catalogExit !== 0) {
      return catalogExit;
    }
    const maintenanceIssues = await validateMaintenanceLog();
    for (const issue of maintenanceIssues) {
      console.error("ERROR: " + issue);
    }
    return maintenanceIssues.length > 0 ? 1 : 0;
  })();
}
