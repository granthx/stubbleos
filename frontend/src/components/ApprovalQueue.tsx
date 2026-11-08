"use client";

import React from "react";
import { CheckCircle2, ShieldAlert, XCircle } from "lucide-react";
import { ApprovalItem } from "../types";

interface ApprovalProps {
  approvals: ApprovalItem[];
  onResolve: (id: string, decision: "approved" | "rejected") => void;
}

export const ApprovalQueue: React.FC<ApprovalProps> = ({ approvals, onResolve }) => {
  const pending = approvals.filter((a) => a.status === "pending");

  return (
    <div className="border border-ink/15 bg-paper flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-ink/10 flex items-center justify-between bg-paper-subtle">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 bg-ink text-paper">
            <ShieldAlert className="h-4 w-4 text-wild-red" />
          </div>
          <div>
            <h2 className="text-xs font-mono font-bold text-ink uppercase tracking-wider">
              [03 // HITL POLICY GUARD QUEUE]
            </h2>
            <p className="text-[11px] text-wild-muted font-mono">
              AUTONOMOUS BOUNDARY ESCALATIONS
            </p>
          </div>
        </div>

        <span className={`text-[10px] font-mono px-2 py-0.5 font-bold uppercase border ${
          pending.length > 0
            ? "bg-wild-red text-white border-wild-red"
            : "bg-paper text-ink border-ink/20"
        }`}>
          {pending.length} Escalations
        </span>
      </div>

      {/* Body List */}
      <div className="p-4 space-y-3 flex-1 overflow-y-auto max-h-[320px]">
        {pending.length === 0 ? (
          <div className="text-center py-10 text-wild-muted font-mono text-xs space-y-2">
            <CheckCircle2 className="h-6 w-6 text-ink mx-auto" />
            <p className="font-bold text-ink">ALL SYSTEMS OPERATING WITHIN BOUNDS</p>
            <p className="text-[11px] text-wild-muted">
              Policy Guard active: No manual human interventions currently mandated.
            </p>
          </div>
        ) : (
          pending.map((item) => (
            <div
              key={item.id}
              className="border border-ink/15 bg-paper-subtle p-3.5 flex flex-col gap-2.5 hover:border-ink transition-colors"
            >
              <div className="flex items-center justify-between border-b border-ink/10 pb-1.5 text-[10px] font-mono">
                <span className="font-bold text-wild-red uppercase tracking-wider">
                  {item.kind.replace(/_/g, " ")}
                </span>
                <span className="text-wild-muted">
                  {new Date(item.created_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>

              <p className="text-xs font-sans text-ink leading-relaxed">
                {item.reason}
              </p>

              <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-[10px] font-mono">
                <span className="text-wild-blue-gray">
                  AGENT: <span className="text-ink font-bold">{item.requested_by}</span>
                </span>
                {item.confidence !== undefined && (
                  <span className="bg-ink/5 px-2 py-0.5 border border-ink/10 text-ink">
                    CONFIDENCE: {Math.round(item.confidence * 100)}%
                  </span>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 pt-2 border-t border-ink/10">
                <button
                  onClick={() => onResolve(item.id, "approved")}
                  className="flex-1 py-1.5 px-3 bg-ink hover:bg-neon hover:text-ink text-paper text-[10px] font-mono font-bold uppercase tracking-wider transition-colors border border-ink text-center"
                >
                  Authorize Action
                </button>
                <button
                  onClick={() => onResolve(item.id, "rejected")}
                  className="py-1.5 px-3 bg-paper hover:bg-wild-red hover:text-white text-ink text-[10px] font-mono font-bold uppercase tracking-wider transition-colors border border-ink/20 hover:border-wild-red"
                >
                  Reject
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="border-t border-ink/10 px-4 py-2 bg-paper-subtle flex items-center justify-between text-[10px] font-mono text-wild-muted">
        <div>POLICY LAYER: LANGGRAPH SUPERVISOR</div>
        <div>HASH LOGGED</div>
      </div>
    </div>
  );
};
