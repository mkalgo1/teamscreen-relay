import { NextRequest, NextResponse } from "next/server";
import { updateWorkerPing } from "@/lib/store";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { workerId, name, department, hostname, platform, deviceType, status, screenResolution, location } = body;

    if (!workerId) {
      return NextResponse.json({ error: "workerId is required" }, { status: 400 });
    }

    const ip = req.headers.get("x-forwarded-for") || req.headers.get("x-real-ip") || "";

    const worker = updateWorkerPing({
      workerId,
      name,
      department,
      hostname,
      platform,
      deviceType,
      status,
      screenResolution,
      ip: typeof ip === "string" ? ip.split(",")[0].trim() : "",
      location: location && typeof location.latitude === "number" && typeof location.longitude === "number" ? location : undefined,
    });

    return NextResponse.json({
      ok: true,
      workerId: worker.workerId,
      streamRequested: !!worker.streamRequested,
      guidanceMessage: worker.guidanceMessage || "",
      serverTime: Date.now(),
    });
  } catch (error) {
    return NextResponse.json({ error: "Invalid ping payload" }, { status: 400 });
  }
}

export async function GET() {
  return NextResponse.json({
    status: "ok",
    service: "TeamScreen Live Ping Relay",
    time: Date.now(),
  });
}
