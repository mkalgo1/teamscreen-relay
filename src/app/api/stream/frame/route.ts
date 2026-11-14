import { NextRequest, NextResponse } from "next/server";
import { setFrame, getFrame } from "@/lib/store";


// Worker uploads frame
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { workerId, frame } = body;

    if (!workerId || !frame) {
      return NextResponse.json({ error: "workerId and frame required" }, { status: 400 });
    }

    setFrame(workerId, frame);
    return NextResponse.json({ ok: true, timestamp: Date.now() });
  } catch (error) {
    return NextResponse.json({ error: "Failed to process frame" }, { status: 400 });
  }
}

// Admin / Web client gets frame
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const workerId = searchParams.get("workerId");

  if (!workerId) {
    return NextResponse.json({ error: "workerId parameter required" }, { status: 400 });
  }

  const frameData = getFrame(workerId);

  if (!frameData) {
    return NextResponse.json({ ok: false, frame: null }, { status: 404 });
  }

  return NextResponse.json({
    ok: true,
    workerId: frameData.workerId,
    frame: frameData.frame,
    timestamp: frameData.timestamp,
  });
}
