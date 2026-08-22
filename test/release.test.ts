import { expect, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { unzipSync } from "fflate";
import { catalogEntries, loadCatalog } from "../generate/catalog";
import { buildRelease } from "../release/command";

test("release archives contain canonical documentation and installers", async () => {
  const directory = await mkdtemp(join(tmpdir(), "qbsearch-release-"));
  const output = join(directory, "qbsearch-test.zip");

  try {
    expect(await buildRelease(["--version", "test", "--output", output])).toBe(0);

    const archive = unzipSync(await Bun.file(output).bytes());
    const names = Object.keys(archive);
    const prefix = "qbsearch-test/";
    const manifestPath = `${prefix}release-manifest.json`;
    const manifest = JSON.parse(new TextDecoder().decode(archive[manifestPath])) as {
      plugin_count: number;
      installers: string[];
    };

    expect(names).toContain(`${prefix}documentation/INSTALL.md`);
    expect(names).toContain(`${prefix}documentation/PLUGINS.md`);
    expect(names).toContain(`${prefix}documentation/CHANGELOG.md`);
    expect(names).toContain(`${prefix}documentation/ATTRIBUTIONS.md`);
    expect(names).toContain(`${prefix}install/macos.sh`);
    expect(names).toContain(`${prefix}install/linux.sh`);
    expect(names).toContain(`${prefix}install/windows.ps1`);
    expect(names.some((name) => name.includes("documentaion"))).toBe(false);
    expect(manifest.plugin_count).toBe(catalogEntries(await loadCatalog()).length);
    expect(manifest.installers).toEqual([
      "install/macos.sh",
      "install/linux.sh",
      "install/windows.ps1",
    ]);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
