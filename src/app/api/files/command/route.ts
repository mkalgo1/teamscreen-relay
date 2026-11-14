import { NextRequest, NextResponse } from "next/server";
import { queueFileCommand, popFileCommands } from "@/lib/store";

// CEO queues a file command (e.g. browse directory, upload file)
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { workerId, action, path, fileName, fileData } = body;

    if (!workerId || !action) {
      return NextResponse.json({ error: "workerId and action required" }, { status: 400 });
    }

    const cmd = queueFileCommand({
      workerId,
      action,
      path: typeof path === "string" ? path : undefined,
      fileName: typeof fileName === "string" ? fileName : undefined,
      fileData: typeof fileData === "string" ? fileData : undefined,
    });

    return NextResponse.json({ ok: true, command: cmd });
  } catch (error) {
    return NextResponse.json({ error: "Invalid command payload" }, { status: 400 });
  }
}

// Worker fetches pending file commands
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const workerId = searchParams.get("workerId");

  if (!workerId) {
    return NextResponse.json({ error: "workerId parameter required" }, { status: 400 });
  }

  const commands = popFileCommands(workerId);
  return NextResponse.json({ ok: true, commands, count: commands.length });
}
