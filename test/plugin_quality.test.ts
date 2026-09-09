import { describe, expect, test } from "bun:test";
import { auditPluginQuality } from "../tool/checks/plugin_quality";

const preamble = `# BEGIN GENERATED QBITT SAFETY PREAMBLE\n# END GENERATED QBITT SAFETY PREAMBLE\n`;

describe("plugin quality audit", () => {
  test("accepts bounded transport and parallel helpers", () => {
    const report = auditPluginQuality(
      "safe",
      `${preamble}from helpers import retrieve_url\n\n` +
        "with _qbt_safe_urlopen(request) as response:\n    body = response.read(1024)\n",
    );

    expect(report.issues.filter((issue) => issue.severity === "error")).toHaveLength(0);
    expect(report.metrics.networkCalls).toBe(1);
    expect(report.metrics.directTransportCalls).toBe(0);
  });

  test("flags unsafe transport and unbounded concurrency", () => {
    const report = auditPluginQuality(
      "unsafe",
      `${preamble}from urllib.request import urlopen\n` +
        "from threading import Thread\n" +
        "import ssl\n\n" +
        "ssl_context.verify_mode = ssl.CERT_NONE\n" +
        "urlopen(url)\nThread(target=search).start()\nwhile True:\n    pass\n",
    );

    expect(report.issues.map((issue) => issue.kind)).toEqual([
      "direct-network",
      "raw-thread",
      "unbounded-loop",
      "insecure-tls",
    ]);
    expect(report.metrics.directTransportWithoutTimeouts).toBe(1);
    expect(report.metrics.rawThreads).toBe(1);
    expect(report.metrics.unboundedLoops).toBe(1);
    expect(report.metrics.tlsBypasses).toBe(1);
  });

  test("reports post-preamble dead assignments as warnings", () => {
    const report = auditPluginQuality("dead-code", `${preamble}_qbt_helper_retrieve_url = None\n`);

    expect(report.issues).toHaveLength(1);
    expect(report.issues[0]?.kind).toBe("dead-helper-assignment");
    expect(report.issues[0]?.severity).toBe("warning");
    expect(report.metrics.duplicateHelperAssignments).toBe(0);
    expect(report.metrics.deadHelperAssignments).toBe(1);
  });

  test("recognizes timeout and deadline-aware sleep aliases", () => {
    const report = auditPluginQuality(
      "aliases",
      `${preamble}from time import sleep
from urllib.request import urlopen as fetch

fetch(url, timeout=HTTP_TIMEOUT)
fetch(url)
sleep(_qbt_remaining())
sleep(1)
`,
    );

    expect(report.metrics.directTransportCalls).toBe(2);
    expect(report.metrics.directTransportWithoutTimeouts).toBe(1);
    expect(report.metrics.sleeps).toBe(2);
    expect(report.metrics.deadlineIgnoringSleeps).toBe(1);
    expect(
      report.issues.filter((issue) => issue.severity === "error").map((issue) => issue.kind),
    ).toEqual(["direct-network", "fixed-sleep"]);
  });

  test("reports unbounded pagination and detail-fetch loops", () => {
    const report = auditPluginQuality(
      "loops",
      `${preamble}from urllib.request import urlopen

def search():
    for page in range(total_pages):
        for detail in details:
            urlopen(detail)
`,
    );

    expect(
      report.issues.filter((issue) => issue.severity === "error").map((issue) => issue.kind),
    ).toEqual(["direct-network", "unbounded-pagination", "unbounded-detail"]);
    expect(report.metrics.paginationLoops).toBe(1);
    expect(report.metrics.unboundedPaginationLoops).toBe(1);
    expect(report.metrics.detailLoops).toBe(1);
    expect(report.metrics.unboundedDetailLoops).toBe(1);
  });
});
