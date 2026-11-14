import { NextResponse } from "next/server";
import { getActiveWorkers } from "@/lib/store";


export async function GET() {
  const workers = getActiveWorkers(12000);

  return NextResponse.json({
    ok: true,
    count: workers.length,
    workers,
    serverTime: Date.now(),
  });
}
