import { NextRequest, NextResponse } from "next/server";
import { pushAudioChunk, getAudioChunks } from "@/lib/store";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { workerId, channel, chunk } = body;

    if (!workerId || !channel || !chunk) {
      return NextResponse.json(
        { error: "workerId, channel, and chunk are required" },
        { status: 400 }
      );
    }

    if (channel !== "worker_to_ceo" && channel !== "ceo_to_worker") {
      return NextResponse.json(
        { error: "channel must be worker_to_ceo or ceo_to_worker" },
        { status: 400 }
      );
    }

    const packet = pushAudioChunk(workerId, channel, chunk);
    return NextResponse.json({ ok: true, seq: packet.seq, timestamp: packet.timestamp });
  } catch (error) {
    return NextResponse.json({ error: "Failed to push audio chunk" }, { status: 400 });
  }
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const workerId = searchParams.get("workerId");
    const channel = searchParams.get("channel") as "worker_to_ceo" | "ceo_to_worker" | null;
    const afterSeq = parseInt(searchParams.get("afterSeq") || "0", 10);

    if (!workerId || !channel) {
      return NextResponse.json(
        { error: "workerId and channel query params are required" },
        { status: 400 }
      );
    }

    const packets = getAudioChunks(workerId, channel, isNaN(afterSeq) ? 0 : afterSeq);
    return NextResponse.json({ ok: true, packets });
  } catch (error) {
    return NextResponse.json({ error: "Failed to fetch audio chunks" }, { status: 400 });
  }
}
