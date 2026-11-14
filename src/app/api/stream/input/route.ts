import { NextRequest, NextResponse } from "next/server";
import { queueInputEvent, popInputEvents } from "@/lib/store";

// CEO dispatches input event (click, type, key)
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { workerId, eventType, xRatio, yRatio, text, key } = body;

    if (!workerId || !eventType) {
      return NextResponse.json({ error: "workerId and eventType required" }, { status: 400 });
    }

    const event = queueInputEvent({
      workerId,
      eventType,
      xRatio: typeof xRatio === "number" ? xRatio : undefined,
      yRatio: typeof yRatio === "number" ? yRatio : undefined,
      text: typeof text === "string" ? text : undefined,
      key: typeof key === "string" ? key : undefined,
    });

    return NextResponse.json({ ok: true, event });
  } catch (error) {
    return NextResponse.json({ error: "Invalid input payload" }, { status: 400 });
  }
}

// Worker polls pending input events
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const workerId = searchParams.get("workerId");

  if (!workerId) {
    return NextResponse.json({ error: "workerId parameter required" }, { status: 400 });
  }

  const events = popInputEvents(workerId);
  return NextResponse.json({ ok: true, events, count: events.length });
}
