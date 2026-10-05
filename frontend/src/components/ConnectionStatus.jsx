import { useEffect, useState } from "react";
import * as api from "../lib/api.js";

/**
 * Green/amber/red dot showing whether the backend (GET /health) is reachable.
 * Probes on mount and every 10s. Purely additive — informational only.
 */
export default function ConnectionStatus() {
  const [state, setState] = useState("checking"); // checking | ok | down

  useEffect(() => {
    let alive = true;
    const probe = async () => {
      try {
        await api.health();
        if (alive) setState("ok");
      } catch {
        if (alive) setState("down");
      }
    };
    probe();
    const t = setInterval(probe, 10000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const meta = {
    checking: { dot: "bg-aurora-400 animate-pulse", label: "Connecting to backend…" },
    ok: { dot: "bg-mint-400", label: "Backend online" },
    down: { dot: "bg-coral-500", label: "Backend offline — is `uvicorn app.main:app` running on port 8000?" },
  }[state];

  return (
    <span title={meta.label} className="flex items-center gap-1.5 text-xs text-slate-400 shrink-0">
      <span className={`w-2 h-2 rounded-full ${meta.dot}`} />
      {state === "down" && <span className="text-coral-500">Offline</span>}
    </span>
  );
}