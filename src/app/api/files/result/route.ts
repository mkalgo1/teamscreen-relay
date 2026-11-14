import { NextRequest, NextResponse } from "next/server";
import { setFileResult, getFileResult } from "@/lib/store";

// Worker posts directory listing or upload confirmation
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { workerId, currentPath, items, statusMessage } = body;

    if (!workerId || !currentPath) {
      return NextResponse.json({ error: "workerId and currentPath required" }, { status: 400 });
    }

    setFileResult({
      workerId,
      currentPath,
      items: Array.isArray(items) ? items : [],
      statusMessage: typeof statusMessage === "string" ? statusMessage : undefined,
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
