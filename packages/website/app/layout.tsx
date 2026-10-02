import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "qbsearch — Download qBittorrent search plugins",
    template: "%s — qbsearch",
  },
  description:
    "Download qBittorrent search plugins in one ZIP, with icons and installers for Windows, macOS, and Linux.",
  keywords: ["qBittorrent", "nova3", "search plugins", "torrent search"],
  openGraph: {
    title: "qbsearch — Download qBittorrent search plugins",
    description:
      "Download qBittorrent search plugins in one ZIP, with icons and installers for Windows, macOS, and Linux.",
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
