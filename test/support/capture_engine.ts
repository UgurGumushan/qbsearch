import {
  replayParserFixture,
  assertUsableParserResults,
  usableMagnet,
  type ParserCase,
  type ParserReport,
} from "./parser_replay";

export interface DownloadProof {
  link: string;
  resolvedUrl: string;
  kind: "magnet" | "torrent";
  replayPath: string;
}

/** Discover requests by replaying the engine; Python never performs live I/O. */
export async function captureEngine(
  fixture: ParserCase,
  get: (url: string) => Promise<string>,
  verifyTorrent: (url: string) => Promise<void>,
  archive: (fixture: ParserCase, report: ParserReport) => Promise<string>,
): Promise<DownloadProof[]> {
  const verified = new Set<string>();
  const replay = async (
    action: "search" | "download",
    detailUrl?: string,
  ): Promise<{ report: ParserReport; replayPath: string }> => {
    for (let round = 0; round < 8; round += 1) {
      const current = { ...fixture, action, detailUrl, verifiedDownloads: [...verified] };
      const report = await replayParserFixture(current);
      const missing = [...new Set(report.requests)].filter((url) => !(url in fixture.responses));
      const downloads = [...new Set(report.downloadRequests)].filter((url) => !verified.has(url));
      const replayPath = await archive(current, report);
      if (report.errors.some((error) => error.includes("network or download attempted")))
        throw new Error(`offline network guard failed: ${report.errors.join("; ")}`);
      if (
        !missing.length &&
        !downloads.length &&
        report.errors.some(
          (error) =>
            !error.startsWith("unexpected request:") &&
            !error.startsWith("unverified torrent download:"),
        )
      ) {
        throw new Error(`engine replay failed: ${report.errors.join("; ")}`);
      }
      if (
        Object.keys(fixture.responses).length + verified.size + missing.length + downloads.length >
        32
      ) {
        throw new Error("capture exceeds the bounded URL budget");
      }
      if (!missing.length && !downloads.length) {
        if (report.code !== 0 || report.errors.length)
          throw new Error("engine replay did not complete");
        return { report, replayPath };
      }
      for (const url of missing) fixture.responses[url] = await get(url);
      for (const url of downloads) {
        await verifyTorrent(url);
        verified.add(url);
      }
    }
    throw new Error("capture exceeds the bounded resolution depth");
  };
  const { report } = await replay("search");
  // Empty output is retained as a completed negative parser observation.
  if (!report.records.length) return [];
  if (report.records.length > (fixture.maxDetails ?? 5))
    throw new Error("engine exceeds the result budget");
  assertUsableParserResults(report, true);
  const proofs: DownloadProof[] = [];
  for (const row of report.records) {
    const link = row.link as string;
    if (usableMagnet(link)) continue;
    const { report: download, replayPath } = await replay("download", link);
    const output = download.output.filter((line) => line.trim());
    if (output.length !== 1) throw new Error(`${link}: expected one resolved download output`);
    const resolved = output[0].split(" ")[0];
    if (usableMagnet(resolved)) {
      proofs.push({ link, resolvedUrl: resolved, kind: "magnet", replayPath });
    } else if (
      resolved === "/offline/verified.torrent" &&
      download.downloadRequests.length === 1 &&
      verified.has(download.downloadRequests[0])
    ) {
      proofs.push({ link, resolvedUrl: download.downloadRequests[0], kind: "torrent", replayPath });
    } else throw new Error(`${link}: no verified magnet or torrent download`);
  }
  return proofs;
}
