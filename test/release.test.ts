import { expect, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { unzipSync } from "fflate";
import { catalogEntries, loadCatalog } from "../tool/catalog";
import { buildRelease } from "../tool/release/command";
import { publicationTag } from "../tool/release/publication";

test("publication selects the current changelog version and rejects mismatched or unsafe tags", () => {
  const changelog = "# Changelog\n\n## 0.1.11\n\n- Current changes.\n\n## 0.1.10\n";
  expect(publicationTag(undefined, changelog)).toBe("v0.1.11");
  expect(publicationTag("", changelog)).toBe("v0.1.11");
  expect(publicationTag("v0.1.11", changelog)).toBe("v0.1.11");
  for (const tag of ["v0.1.10", "v0.1.12", "../notes", "v0.1.11-beta", "v00.1.11"])
    expect(() => publicationTag(tag, changelog)).toThrow();
  expect(() => publicationTag(undefined, "# Changelog\n\n## Unreleased\n")).toThrow();
});

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
    expect(names).toContain(`${prefix}documentation/PERFORMANCE.md`);
    expect(names).toContain(`${prefix}documentation/ATTRIBUTIONS.md`);
    expect(names).toContain(`${prefix}documentation/LICENSE_PROVENANCE.md`);
    for (const notice of [
      "LightDestory-GPL-3.0",
      "iordic-MIT",
      "Cycloctane-MIT",
      "tolotp-MIT",
      "imDMG-MIT",
      "Douman-MIT",
    ]) {
      const path = `documentation/licenses/${notice}.txt`;
      expect(archive[`${prefix}${path}`]).toEqual(await Bun.file(path).bytes());
    }
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
