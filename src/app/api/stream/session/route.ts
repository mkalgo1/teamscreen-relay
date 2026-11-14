import { NextRequest, NextResponse } from "next/server";
import { setStreamSession } from "@/lib/store";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { workerId, streamRequested, guidanceMessage } = body;

    if (!workerId) {
      return NextResponse.json({ error: "workerId is required" }, { status: 400 });
    }

    const updated = setStreamSession(workerId, streamRequested, guidanceMessage);

    if (!updated) {
      return NextResponse.json({ error: "Worker not found or expired" }, { status: 404 });
    }

    return NextResponse.json({
      ok: true,
      workerId: updated.workerId,
      streamRequested: !!updated.streamRequested,
      guidanceMessage: updated.guidanceMessage || "",
    });
  } catch (error) {
    return NextResponse.json({ error: "Invalid session payload" }, { status: 400 });
  }
}
