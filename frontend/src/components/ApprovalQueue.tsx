import React from "react";
import { AlertCircle, CheckCircle2, ShieldAlert, XCircle } from "lucide-react";
import { ApprovalItem } from "../types";

interface ApprovalProps {
  approvals: ApprovalItem[];
  onResolve: (id: string, decision: "approved" | "rejected") => void;
}

export const ApprovalQueue: React.FC<ApprovalProps> = ({ approvals, onResolve }) => {
  const pending = approvals.filter((a) => a.status === "pending");

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden flex flex-col">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-rose-400" />
          <h2 className="text-sm font-semibold text-white">Human-in-the-Loop (HITL) Queue</h2>
        </div>
        <span className="text-xs px-2 py-0.5 rounded-full bg-rose-950 text-rose-400 border border-rose-800 font-medium">
          {pending.length} Pending Actions
        </span>
      </div>

      <div className="p-4 space-y-3 flex-1 overflow-y-auto max-h-[300px]">
        {pending.length === 0 ? (
          <div className="text-center py-6 text-slate-500 text-xs">
            <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto mb-2 opacity-60" />
            No pending escalation items. All systems operating within autonomous confidence boundaries.
          </div>
        ) : (
          pending.map((item) => (
            <div
              key={item.id}
              className="bg-slate-950/70 border border-slate-800 rounded-lg p-3 flex flex-col justify-between gap-2.5 text-xs"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-rose-300 uppercase tracking-wide font-mono text-[11px]">
                    {item.kind.replace(/_/g, " ")}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
                <p className="text-slate-300 mt-1">{item.reason}</p>
                {item.confidence !== undefined && (
                  <span className="text-[10px] text-amber-400 font-mono">
                    Solver Confidence: {Math.round(item.confidence * 100)}%
                  </span>
                )}
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800/80">
                <button
                  onClick={() => onResolve(item.id, "rejected")}
                  className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center gap-1 transition"
                >
                  <XCircle className="h-3.5 w-3.5 text-red-400" />
                  Reject
                </button>
                <button
                  onClick={() => onResolve(item.id, "approved")}
                  className="px-2.5 py-1 rounded bg-emerald-700 hover:bg-emerald-600 text-white font-medium flex items-center gap-1 transition"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Approve Override
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
