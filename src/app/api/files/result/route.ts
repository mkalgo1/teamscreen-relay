import { NextRequest, NextResponse } from "next/server";
import { setFileResult, getFileResult } from "@/lib/store";

// Worker posts directory listing, download data, or operation confirmation
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { workerId, action, currentPath, items, fileName, fileData, statusMessage, success } = body;

    if (!workerId) {
      return NextResponse.json({ error: "workerId required" }, { status: 400 });
    }

    setFileResult({
      workerId,
      action: typeof action === "string" ? action : undefined,
      currentPath: typeof currentPath === "string" ? currentPath : "",
      items: Array.isArray(items) ? items : [],
      fileName: typeof fileName === "string" ? fileName : undefined,
      fileData: typeof fileData === "string" ? fileData : undefined,
      statusMessage: typeof statusMessage === "string" ? statusMessage : undefined,
      success: typeof success === "boolean" ? success : true,
      timestamp: Date.now(),
    });

    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json({ error: "Invalid result payload" }, { status: 400 });
  }
}

// CEO gets directory listing or transfer status
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const workerId = searchParams.get("workerId");

  if (!workerId) {
    return NextResponse.json({ error: "workerId parameter required" }, { status: 400 });
  }

  const result = getFileResult(workerId);
  if (!result) {
    return NextResponse.json({ ok: false, result: null });
  }

  return NextResponse.json({ ok: true, result });
}
