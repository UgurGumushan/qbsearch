import { NextResponse } from "next/server";
import { DOWNLOAD_URL } from "../../../lib/links";

export const dynamic = "force-static";

export function GET() {
  return NextResponse.redirect(DOWNLOAD_URL, 307);
}
