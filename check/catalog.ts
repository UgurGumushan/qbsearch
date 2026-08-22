import { generatePluginCatalog } from "../generate/catalog/command";

/** Ensure catalog JSON and generated documentation are current before dependent jobs. */
export function checkCatalog(): Promise<number> {
  return generatePluginCatalog(["--check"]);
}
