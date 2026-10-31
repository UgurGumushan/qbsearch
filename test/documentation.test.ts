/**
 * Verify documentation requirements against the real lint configuration and scaffold gate.
 * @file
 */
import { expect, test } from "bun:test";
import { ESLint, Linter } from "eslint";
import { resolve } from "node:path";
import { ROOT } from "../tool/core/repo";
import { documentationSource, lintPluginDocumentation } from "../tool/checks/python_documentation";
import { renderPlugin } from "../tool/harden/render_plugin";
import { checkTasks } from "../tool/checks/tasks";

const eslint = new ESLint({ cwd: ROOT });
const linter = new Linter();
const overview = "/** Explain the fixture module.\n * @file\n */\n\n";

/** Run only documentation rules from the actual file configuration on an isolated snippet. */
async function documentationMessages(source: string, path = "tool/core/repo.ts") {
  const config = (await eslint.calculateConfigForFile(resolve(ROOT, path))) as Linter.Config;
  const languageOptions = config.languageOptions as Linter.LanguageOptions;
  return linter.verify(source, {
    plugins: config.plugins,
    settings: config.settings ?? {},
    languageOptions: {
      ...languageOptions,
      parserOptions: {
        ...languageOptions.parserOptions,
        projectService: false,
        project: false,
      },
    },
    rules: Object.fromEntries(
      Object.entries(config.rules ?? {}).filter(([name]) => name.startsWith("jsdoc/")),
    ),
  });
}

test("documentation gates are included in both fast and full checks", () => {
  for (const mode of ["fast", "full"] as const) {
    const labels = checkTasks({ mode, strict: false }).map((task) => task.label);
    expect(labels).toContain("ESLint");
    expect(labels).toContain("Ruff lint");
    expect(labels).toContain("Plugin documentation");
  }
});

test("TypeScript requires documentation across declaration forms and rejects empty blocks", async () => {
  for (const declaration of [
    "function example() {}",
    "export function example() {}",
    "const example = () => 1;",
    "const example = function () { return 1; };",
    "class Example {}",
    "const Example = class {};",
    "/** Describe the class. */ class Example { method() {} }",
    "/** Describe the class. */ class Example { field = () => 1; }",
    "const example = { method() {} };",
    "interface Example { value: string; }",
    "type Example = string;",
  ]) {
    const messages = await documentationMessages(overview + declaration);
    expect({
      declaration,
      missing: messages.some((message) => message.ruleId === "jsdoc/require-jsdoc"),
    }).toEqual({ declaration, missing: true });
  }
  for (const declaration of [
    "function example() {}",
    "interface Example {}",
    "type Example = string;",
    "class Example {}",
  ]) {
    const messages = await documentationMessages(overview + "/** */\n" + declaration);
    expect(messages.some((message) => message.ruleId === "jsdoc/require-description")).toBe(true);
  }
  const noOverview = await documentationMessages(
    "/** Return a fixture value. */ function example() { return 1; }",
  );
  expect(noOverview.some((message) => message.ruleId === "jsdoc/require-file-overview")).toBe(true);
  const emptyOverview = await documentationMessages("/** @file */\nexport const value = 1;");
  expect(emptyOverview.some((message) => message.ruleId === "jsdoc/require-description")).toBe(
    true,
  );
}, 20_000);

test("TypeScript accepts useful descriptions and the documented exemptions", async () => {
  const source =
    overview +
    `
/** Return a constant fixture value. */
function example() { return 1; }
/** Compute a constant fixture value. */
const assigned = () => 1;
/** Store the label used by a fixture. */
interface Example { label: string; method(): void; }
/** Represent the fixture's string label. */
type Label = string;
/** Group fixture operations. */
class Fixture {
  constructor() {}
  /** Return the fixture value. */
  method() { return 1; }
}
[1].map((value) => value + 1);
[1].map(function (value) { return value + 1; });
`;
  expect(await documentationMessages(source)).toEqual([]);
  expect(
    await documentationMessages("function undocumented() {}", "test/plugin_sources.ts"),
  ).toEqual([]);
  expect(
    await documentationMessages(
      "declare function undocumented(): void;",
      "test/python-source.d.ts",
    ),
  ).toEqual([]);
});

test("Python catches public engine omissions hidden by the generated helper exports", async () => {
  const source = renderPlugin(`"""Example engine module."""
from __future__ import annotations
from helpers import retrieve_url
from novaprinter import prettyPrinter
# QBSEARCH-PREAMBLE-ANCHOR
class example:
    def search(self, what, cat="all"):
        pass
`);
  const path = resolve(ROOT, "plugins/example.py");
  const masked = documentationSource(source);
  expect(masked.split("\n")).toHaveLength(source.split("\n").length);
  expect(masked.indexOf("class example:")).toBe(source.indexOf("class example:"));
  expect(masked).not.toContain("__all__");
  expect(source).toContain("__all__");
  const result = await lintPluginDocumentation(path, source);
  expect(result.code).toBe(1);
  expect(result.output).toContain("D101");
  expect(result.output).toContain("D102");
  const line = source.slice(0, source.indexOf("class example:")).split("\n").length;
  expect(result.output).toContain(`:${line}:7`);
  expect(() => documentationSource("# BEGIN GENERATED QBITT SAFETY PREAMBLE")).toThrow(
    "no end marker",
  );
});

test("Python rejects missing and empty documentation while allowing private helpers and stubs", async () => {
  const path = resolve(ROOT, "plugins/example.py");
  const missing = await lintPluginDocumentation(path, "def example():\n    pass\n");
  expect(missing.code).toBe(1);
  expect(missing.output).toContain("D100");
  expect(missing.output).toContain("D103");
  const empty = await lintPluginDocumentation(
    path,
    '"""Example module."""\ndef example():\n    """ """\n',
  );
  expect(empty.code).toBe(1);
  expect(empty.output).toContain("D419");
  const members = await lintPluginDocumentation(
    path,
    `"""Example module."""
class Example:
    """Expose the fixture contract."""
    def __init__(self):
        pass
    def __str__(self):
        return "fixture"
    class Nested:
        pass
`,
  );
  expect(members.code).toBe(1);
  for (const code of ["D105", "D106", "D107"]) expect(members.output).toContain(code);
  const packageResult = await lintPluginDocumentation(
    resolve(ROOT, "test/__init__.py"),
    "value = 1\n",
  );
  expect(packageResult.output).toContain("D104");
  const valid = await lintPluginDocumentation(
    path,
    `"""Example module."""
def _private():
    pass
class Example:
    """Expose the fixture search contract."""
    def __init__(self):
        """Initialize a fixture without network access."""
    def search(self):
        """Emit the fixture search results."""
`,
  );
  expect(valid.code).toBe(0);
  const stub = await lintPluginDocumentation(
    resolve(ROOT, "typings/example.pyi"),
    "class Example:\n    def search(self) -> None: ...\n",
  );
  expect(stub.code).toBe(0);
});
