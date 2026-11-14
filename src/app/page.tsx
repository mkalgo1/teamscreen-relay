"use client";

import { useEffect, useState, useRef } from "react";

interface WorkerInfo {
  workerId: string;
  name: string;
  department: string;
  hostname: string;
  status: "online" | "streaming" | "idle";
  screenResolution: string;
  lastPing: number;
  streamRequested?: boolean;
  guidanceMessage?: string;
  ip?: string;
}

export default function Home() {
  const [workers, setWorkers] = useState<WorkerInfo[]>([]);
  const [selectedWorkerId, setSelectedWorkerId] = useState<string | null>(null);
  const [currentFrame, setCurrentFrame] = useState<string | null>(null);
  const [fps, setFps] = useState(0);
  const [guidanceText, setGuidanceText] = useState("");
  const [copied, setCopied] = useState(false);
  const [relayOrigin, setRelayOrigin] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);

  const frameCountRef = useRef(0);
  const lastFpsTimeRef = useRef(0);

  useEffect(() => {
    lastFpsTimeRef.current = Date.now();
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setRelayOrigin(window.location.origin);
    }
  }, []);

  // Poll workers list every 2 seconds
  useEffect(() => {
    const fetchWorkers = async () => {
      try {
        const res = await fetch("/api/workers");
        if (res.ok) {
          const data = await res.json();
          setWorkers(data.workers || []);
        }
      } catch (err) {
        console.error("Failed to fetch workers:", err);
      }
    };

    fetchWorkers();
    const interval = setInterval(fetchWorkers, 2000);
    return () => clearInterval(interval);
  }, []);

  // Poll frames when a worker is selected
  useEffect(() => {
    if (!selectedWorkerId || !isStreaming) {
      setCurrentFrame(null);
      setFps(0);
      return;
    }

    let active = true;

    const pullFrame = async () => {
      if (!active) return;
      try {
        const res = await fetch(`/api/stream/frame?workerId=${selectedWorkerId}`);
        if (res.ok) {
          const data = await res.json();
          if (data.frame) {
            setCurrentFrame(`data:image/jpeg;base64,${data.frame}`);
            frameCountRef.current++;
            const now = Date.now();
            if (now - lastFpsTimeRef.current >= 1000) {
              setFps(frameCountRef.current);
              frameCountRef.current = 0;
              lastFpsTimeRef.current = now;
            }
          }
        }
      } catch (e) {
        // frame miss
      }
      if (active) {
        setTimeout(pullFrame, 40); // target ~25 FPS
      }
    };

    pullFrame();

    return () => {
      active = false;
    };
  }, [selectedWorkerId, isStreaming]);

  const handleSelectWorker = async (workerId: string) => {
    setSelectedWorkerId(workerId);
    setIsStreaming(true);
    try {
      await fetch("/api/stream/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workerId, streamRequested: true }),
      });
    } catch (e) {
      console.error(e);
    }
  };

  const handleStopStream = async () => {
    if (!selectedWorkerId) return;
    setIsStreaming(false);
    try {
      await fetch("/api/stream/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workerId: selectedWorkerId, streamRequested: false }),
      });
    } catch (e) {
      console.error(e);
    }
  };

  const handleSendGuidance = async () => {
    if (!selectedWorkerId || !guidanceText.trim()) return;
    try {
      await fetch("/api/stream/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workerId: selectedWorkerId, guidanceMessage: guidanceText }),
      });
      setGuidanceText("");
    } catch (e) {
      console.error(e);
    }
  };

  const copyRelayUrl = () => {
    if (relayOrigin) {
      navigator.clipboard.writeText(relayOrigin);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const activeWorker = workers.find((w) => w.workerId === selectedWorkerId);

  return (
    <div className="min-h-screen bg-[#070B14] text-slate-100 flex flex-col font-sans selection:bg-emerald-500 selection:text-black">
      {/* Top Navbar */}
      <header className="border-b border-slate-800/80 bg-[#0A0F1D]/90 backdrop-blur-md sticky top-0 z-50 px-6 py-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <svg className="w-6 h-6 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold tracking-tight text-lg text-white">TEAMSCREEN</span>
              <span className="text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                Live Relay
              </span>
            </div>
            <p className="text-xs text-slate-400">CEO Executive Observation & Guidance Hub</p>
          </div>
        </div>

        {/* Live Ping Relay URL Box */}
        <div className="flex items-center gap-2 bg-[#0F172A] border border-slate-700/60 rounded-xl p-1.5 px-3">
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-xs text-slate-400 font-medium">Relay Ping URL:</span>
          <code className="text-xs font-mono text-emerald-300 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-500/20">
            {relayOrigin || "https://teamscreen-relay.vercel.app"}
          </code>
          <button
            onClick={copyRelayUrl}
            className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-black transition-colors"
          >
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
      </header>

      {/* Main Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Fleet List */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          <div className="bg-[#0F172A]/70 border border-slate-800 rounded-2xl p-5 backdrop-blur-sm">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300">Connected Fleet</h2>
                <span className="text-xs bg-slate-800 text-emerald-400 px-2 py-0.5 rounded-full font-mono font-bold">
                  {workers.length}
                </span>
              </div>
              <span className="text-xs text-slate-500">Auto-refresh 2s</span>
            </div>

            {workers.length === 0 ? (
              <div className="py-12 px-4 text-center border border-dashed border-slate-800 rounded-xl bg-slate-900/30">
                <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center mx-auto mb-3 text-slate-400">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <p className="text-sm font-medium text-slate-300">No Workers Connected Yet</p>
                <p className="text-xs text-slate-500 mt-1">
                  Launch <span className="text-emerald-400 font-mono">WorkerRelay.exe</span> on any workstation to link it live.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-2.5 max-h-[540px] overflow-y-auto pr-1">
                {workers.map((w) => {
                  const isSelected = w.workerId === selectedWorkerId;
                  const isLive = w.status === "streaming";
                  return (
                    <button
                      key={w.workerId}
                      onClick={() => handleSelectWorker(w.workerId)}
                      className={`text-left p-3.5 rounded-xl border transition-all duration-200 relative overflow-hidden ${
                        isSelected
                          ? "bg-slate-800/90 border-emerald-500/80 shadow-lg shadow-emerald-500/10 ring-1 ring-emerald-500/40"
                          : "bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-800/40"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-2">
                            <span
                              className={`w-2.5 h-2.5 rounded-full ${
                                isLive ? "bg-cyan-400 animate-pulse" : "bg-emerald-400"
                              }`}
                            />
                            <span className="font-semibold text-sm text-slate-100">{w.name}</span>
                          </div>
                          <p className="text-xs text-slate-400 mt-0.5 ml-4.5">
                            {w.department} • <span className="font-mono text-slate-400">{w.hostname}</span>
                          </p>
                        </div>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider ${
                            isLive
                              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                              : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          }`}
                        >
                          {isLive ? "STREAMING" : "ONLINE"}
                        </span>
                      </div>
                      <div className="mt-2.5 flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-800/60 pt-2">
                        <span>Res: {w.screenResolution}</span>
                        <span className="text-emerald-400 font-mono">
                          active ping
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Quick System Info Card */}
          <div className="bg-[#0F172A]/70 border border-slate-800 rounded-2xl p-5 backdrop-blur-sm text-xs text-slate-400 space-y-2">
            <div className="flex justify-between">
              <span>Relay Engine</span>
              <span className="text-slate-200 font-mono">Next.js Edge / Vercel</span>
            </div>
            <div className="flex justify-between">
              <span>Screen Protocol</span>
              <span className="text-emerald-400 font-mono">MSS Low-CPU Turbo</span>
            </div>
            <div className="flex justify-between">
              <span>Native Binaries</span>
              <span className="text-slate-200 font-mono">WorkerRelay.exe & CEOAdmin.exe</span>
            </div>
          </div>
        </div>

        {/* Right Column: Screen Viewport & Guidance Console */}
        <div className="lg:col-span-8 flex flex-col gap-4">
          <div className="bg-[#0F172A]/80 border border-slate-800 rounded-2xl overflow-hidden flex flex-col flex-1 min-h-[580px] shadow-2xl">
            {/* Viewport Header */}
            <div className="bg-[#0B101E] px-5 py-3.5 border-b border-slate-800 flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 rounded-full bg-emerald-500" />
                <div>
                  <h3 className="text-sm font-bold text-white">
                    {activeWorker ? `${activeWorker.name} (${activeWorker.department})` : "CEO Observation Viewport"}
                  </h3>
                  <p className="text-xs text-slate-400">
                    {activeWorker ? `Host: ${activeWorker.hostname} | Resolution: ${activeWorker.screenResolution}` : "Click any worker from the fleet roster to initiate real-time stream"}
                  </p>
                </div>
              </div>

              {activeWorker && (
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono px-2 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">
                    {fps} FPS
                  </span>
                  {isStreaming ? (
                    <button
                      onClick={handleStopStream}
                      className="text-xs font-bold px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white transition-colors"
                    >
                      Stop Stream
                    </button>
                  ) : (
                    <button
                      onClick={() => handleSelectWorker(activeWorker.workerId)}
                      className="text-xs font-bold px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-black transition-colors"
                    >
                      Resume Stream
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Viewport Body */}
            <div className="flex-1 bg-black flex items-center justify-center relative overflow-hidden min-h-[380px]">
              {currentFrame ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={currentFrame}
                  alt="Worker Live Screen"
                  className="w-full h-full object-contain select-none"
                />
              ) : (
                <div className="text-center p-8 max-w-md">
                  <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center mx-auto mb-4 text-slate-600">
                    <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <h4 className="text-base font-semibold text-slate-300">
                    {activeWorker ? "Awaiting Screen Stream..." : "No Active Screen Selected"}
                  </h4>
                  <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                    {activeWorker
                      ? "The stream signal has been dispatched to the worker's workstation. Frames will render instantaneously as transmitted."
                      : "Select a worker on the left or run CEOAdmin.exe on your desktop for dedicated multi-monitor viewing."}
                  </p>
                </div>
              )}
            </div>

            {/* CEO Guidance Console at bottom */}
            {activeWorker && (
              <div className="bg-[#0A0F1D] p-3.5 border-t border-slate-800 flex items-center gap-3">
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 whitespace-nowrap">
                  CEO Guidance:
                </span>
                <input
                  type="text"
                  value={guidanceText}
                  onChange={(e) => setGuidanceText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSendGuidance()}
                  placeholder={`Instruct ${activeWorker.name} (e.g., 'Switch to client invoice view')...`}
                  className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                />
                <button
                  onClick={handleSendGuidance}
                  className="text-xs font-bold px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-black transition-colors"
                >
                  Send
                </button>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
