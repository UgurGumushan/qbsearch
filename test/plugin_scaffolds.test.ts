import { expect, spyOn, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { runPluginCommand } from "../tool/commands/plugin";
import { renderPluginTemplate } from "../tool/generators/plugin-template";
import { renderPlugin } from "../tool/harden/render_plugin";
import { pythonCommand, runCapturedCommand } from "../tool/core/run";

const REPLAY = `
import ast, importlib.util, json, socket, sys
from unittest.mock import patch
from test.engine_harness import load_qbitt_modules
path, body = sys.argv[1:]
ast.parse(open(path, encoding="utf-8").read(), feature_version=(3, 9))
load_qbitt_modules(prefer_profile=False)
records = []
requests = []
def retrieve(url, *args, **kwargs):
    requests.append(url)
    return "" if len(requests) == 1 else body
def forbidden(*args, **kwargs):
    raise RuntimeError("network or download attempted")
vars(sys.modules["helpers"]).update(retrieve_url=retrieve, download_file=forbidden)
vars(sys.modules["novaprinter"])["prettyPrinter"] = records.append
spec = importlib.util.spec_from_file_location("scaffold", path)
module = importlib.util.module_from_spec(spec)
with patch("socket.create_connection", forbidden), patch("socket.socket.connect", forbidden):
    spec.loader.exec_module(module)
    module.MAX_DETAILS = 2
    module.RETRY_DELAY = 0
    module.scaffold().search("public query")
print(json.dumps({"records": records, "requests": requests, "site": module.scaffold.url}))
`;

const magnet = `magnet:?xt=urn:btih:${"a".repeat(40)}`;

test("invalid scaffold arguments fail before filesystem writes or validation", async () => {
  const write = spyOn(Bun, "write").mockImplementation(() => {
    throw new Error("invalid scaffold must not write");
  });
  try {
    for (const args of [
      ["--new", "1engine"],
      ["--new", "class"],
      ["--new", "../escape"],
      ["--new", "valid", "--kind"],
      ["--new", "valid", "--site"],
      ["--new", "valid", "--kind", "unknown"],
      ["--kind", "json"],
      ["--new", "valid", "--unknown", "value"],
      ["--validate", "--new", "valid"],
      ["--new", "valid", "--new", "other"],
      ["--new", "valid", "--site", "file:///tmp/test"],
      ["--new", "valid", "--site", "https://user:secret@example.org"],
      ["--new", "valid", "--site", "https://example.org/\ncode"],
    ])
      expect(await runPluginCommand(args)).toBe(2);
    expect(write).not.toHaveBeenCalled();
  } finally {
    write.mockRestore();
  }
});

for (const kind of ["json", "html"] as const) {
  test(`${kind} scaffold installs on Python 3.9 and uses bounded, retrying helpers`, async () => {
    const directory = await mkdtemp(resolve(tmpdir(), "qbsearch-scaffold-"));
    const site = 'https://example.org/a"b\\c';
    const source = renderPlugin(renderPluginTemplate(kind, "scaffold", site));
    const body =
      kind === "json"
        ? JSON.stringify({
            results: [
              null,
              { link: "javascript:alert(1)", name: "bad" },
              { link: magnet },
              { link: magnet, name: "First", seeds: "invalid", leech: true },
              { link: magnet, name: "Duplicate" },
              { link: "https://example.org/second.torrent", name: "Second", seeds: 7, leech: "2" },
              { link: "https://example.org/third.torrent", name: "Third" },
            ],
          })
        : `<a href="/navigation">Navigation</a>
      <a href='javascript:alert(1)'>Bad</a>
      <a href='${magnet}'><b>First</b></a>
      <a href='${magnet}'>Duplicate</a>
      <a href='https://example.org/second.TORRENT?token=public'>Second &amp; title</a>
      <a href='/third.torrent'>Third</a>`;
    try {
      const path = resolve(directory, "scaffold.py");
      await Bun.write(path, source);
      const result = await runCapturedCommand([...pythonCommand(), "-c", REPLAY, path, body], {
        timeoutSeconds: 10,
      });
      expect(result.code).toBe(0);
      const report = JSON.parse(result.output) as {
        records: { name: string; seeds: number; leech: number }[];
        requests: string[];
        site: string;
      };
      expect(report.site).toBe(site);
      expect(report.requests).toHaveLength(2);
      expect(report.records.map((row) => row.name)).toEqual([
        "First",
        kind === "json" ? "Second" : "Second & title",
      ]);
      expect(report.records[0]).toMatchObject({ seeds: -1, leech: -1 });
      if (kind === "json") expect(report.records[1]).toMatchObject({ seeds: 7, leech: 2 });
      // Generated Python must satisfy the same formatting/lint contract as maintained engines.
      const lint = await runCapturedCommand(["ruff", "check", path]);
      expect(lint.code).toBe(0);
    } finally {
      await rm(directory, { recursive: true, force: true });
    }
  });
}
