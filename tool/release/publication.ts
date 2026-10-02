/** Keep published tags aligned with the first versioned changelog entry. */
export function publicationTag(explicitTag: string | undefined, changelog: string): string {
  const version = /^## (\d+\.\d+\.\d+)\s*$/m.exec(changelog)?.[1];
  if (!version) throw new Error("changelog has no release version");
  const expected = `v${version}`;
  const selected = explicitTag === "" ? expected : (explicitTag ?? expected);
  if (!/^v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$/.test(selected))
    throw new Error("release tag must be a stable semantic version");
  if (selected !== expected) throw new Error("release tag does not match the changelog");
  return selected;
}
