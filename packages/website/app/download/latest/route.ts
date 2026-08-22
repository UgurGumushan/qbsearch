import { NextResponse } from "next/server";

const RELEASE_API = "https://api.github.com/repos/UgurGumushan/qbsearch/releases/latest";
const RELEASES_URL = "https://github.com/UgurGumushan/qbsearch/releases/latest";

type ReleaseAsset = {
  name: string;
  browser_download_url: string;
};

type LatestRelease = {
  html_url?: string;
  assets?: ReleaseAsset[];
};

export const revalidate = 300;

/** Resolve the ZIP built and uploaded by the release workflow. */
export async function GET() {
  try {
    const response = await fetch(RELEASE_API, {
      headers: {
        Accept: "application/vnd.github+json",
        "User-Agent": "qbsearch-website",
      },
      next: { revalidate },
    });

    if (!response.ok) {
      return NextResponse.redirect(RELEASES_URL);
    }

    const release = (await response.json()) as LatestRelease;
    const asset =
      release.assets?.find((candidate) => candidate.name === "qbsearch-latest.zip") ??
      release.assets?.find((candidate) => /^qbsearch-.+\.zip$/u.test(candidate.name));

    return NextResponse.redirect(asset?.browser_download_url ?? release.html_url ?? RELEASES_URL);
  } catch {
    return NextResponse.redirect(RELEASES_URL);
  }
}
