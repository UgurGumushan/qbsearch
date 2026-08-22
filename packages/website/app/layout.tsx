import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "qbsearch — qBittorrent search, expanded",
    template: "%s — qbsearch",
  },
  description:
    "A maintained collection of standalone nova3 search engines for qBittorrent, packaged with cross-platform installers.",
  keywords: ["qBittorrent", "nova3", "search plugins", "torrent search"],
  openGraph: {
    title: "qbsearch — qBittorrent search, expanded",
    description: "A focused plugin pack for qBittorrent's built-in search.",
    type: "website",
  },
  icons: {
    icon: "/icon.svg",
  },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
