import { NextRequest, NextResponse } from "next/server";
import { addCustomerLog, getCustomerLogs } from "@/lib/store";

// Add a customer service interaction log
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { workerId, workerName, type, customerName, customerPhone, direction, status, duration, notes } = body;

    if (!workerId || !customerPhone) {
      return NextResponse.json({ error: "workerId and customerPhone required" }, { status: 400 });
    }

    const log = addCustomerLog({
      workerId,
      workerName: typeof workerName === "string" ? workerName : "CS Worker",
      type: type === "message" ? "message" : "call",
      customerName: typeof customerName === "string" ? customerName : "Unknown",
      customerPhone: String(customerPhone),
      direction: direction === "incoming" ? "incoming" : "outgoing",
      status: status === "missed" ? "missed" : status === "followup" ? "followup" : "completed",
      duration: typeof duration === "string" ? duration : undefined,
      notes: typeof notes === "string" ? notes : "",
    });

    return NextResponse.json({ ok: true, log });
  } catch (error) {
    return NextResponse.json({ error: "Invalid log payload" }, { status: 400 });
  }
}

// Retrieve customer service interaction logs (filtered by workerId or all)
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const workerId = searchParams.get("workerId") || undefined;

  const logs = getCustomerLogs(workerId);
  return NextResponse.json({ ok: true, logs, count: logs.length });
}
