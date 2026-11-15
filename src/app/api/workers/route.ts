import { NextResponse } from "next/server";
import { getActiveWorkers, clearStaleWorkers } from "@/lib/store";

export async function GET() {
  const workers = getActiveWorkers(7000);

  return NextResponse.json({
    ok: true,
    count: workers.length,
    workers,
    serverTime: Date.now(),
  });
}

export async function DELETE() {
  const cleared = clearStaleWorkers();
  return NextResponse.json({
    ok: true,
    clearedCount: cleared,
    message: "Active fleet storage cleared.",
  });
}
