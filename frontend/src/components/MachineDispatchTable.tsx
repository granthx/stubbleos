"use client";

import React, { useState } from "react";
import { Check, Clock, Settings2, Tractor, Wrench, Zap } from "lucide-react";
import { MachineInfo } from "../types";

interface TableProps {
  machines: MachineInfo[];
}

export const MachineDispatchTable: React.FC<TableProps> = ({ machines }) => {
  const [filterType, setFilterType] = useState<string>("all");

  const filteredMachines = machines.filter((m) => {
    if (filterType === "all") return true;
    return m.machine_type === filterType;
  });

  return (
    <div className="border border-ink/15 bg-paper flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-ink/10 flex flex-wrap items-center justify-between gap-3 bg-paper-subtle">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 bg-ink text-paper">
            <Tractor className="h-4 w-4 text-neon" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xs font-mono font-bold text-ink uppercase tracking-wider">
                [02 // MACHINERY FLEET & VRP ROUTE DISPATCH]
              </h2>
            </div>
            <p className="text-[11px] text-wild-muted font-mono">
              CP-SAT SOLVER OPTIMIZED · ZERO-BURN IN-SITU & BALING FLEET
            </p>
          </div>
        </div>

        {/* Machine Type Filter */}
        <div className="flex items-center gap-1 font-mono text-[10px]">
          {["all", "super_seeder", "happy_seeder", "baler"].map((t) => (
            <button
              key={t}
              onClick={() => setFilterType(t)}
              className={`px-2.5 py-1 uppercase border transition-colors ${
                filterType === t
                  ? "bg-ink text-paper border-ink font-bold"
                  : "bg-paper text-wild-muted border-ink/10 hover:border-ink"
              }`}
            >
              {t.replace(/_/g, " ")}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto flex-1">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-paper-subtle text-wild-muted border-b border-ink/10 uppercase text-[10px] tracking-wider">
            <tr>
              <th className="py-2.5 px-4 font-bold">Machine ID</th>
              <th className="py-2.5 px-4 font-bold">Equipment Type</th>
              <th className="py-2.5 px-4 font-bold">Assigned Operator</th>
              <th className="py-2.5 px-4 font-bold">Daily Capacity</th>
              <th className="py-2.5 px-4 font-bold">Status</th>
              <th className="py-2.5 px-4 font-bold text-right">Telemetry</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink/5 text-ink">
            {filteredMachines.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-wild-muted text-xs">
                  No machinery currently matching criteria.
                </td>
              </tr>
            ) : (
              filteredMachines.map((m) => {
                const typeCode = m.machine_type
                  .split("_")
                  .map((w) => w[0].toUpperCase())
                  .join("");
                const distCode = (m.district || "SEC").substring(0, 3).toUpperCase();
                const numCode = m.id.replace(/[^0-9]/g, "").slice(-2) || "01";
                const badgeId = `${typeCode}-${distCode}-${numCode}`;

                return (
                  <tr key={m.id} className="hover:bg-paper-subtle transition-colors">
                    <td className="py-3 px-4 font-bold text-ink">
                      <span className="bg-ink/5 px-2 py-0.5 border border-ink/10 text-ink">
                        {badgeId}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-sans font-medium capitalize">
                      {m.machine_type.replace(/_/g, " ")}
                    </td>
                    <td className="py-3 px-4 font-sans text-wild-blue-gray">
                      {m.operator_name || "Unassigned Contractor"}
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-bold text-ink">{m.capacity_acres_per_day}</span>
                      <span className="text-wild-muted text-[11px] ml-1">acres/day</span>
                    </td>
                    <td className="py-3 px-4">
                      {m.status === "in_use" ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-neon text-ink border border-ink text-[10px] font-bold uppercase">
                          <Zap className="h-2.5 w-2.5 fill-current" />
                          IN FIELD
                        </span>
                      ) : m.status === "available" ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-paper-subtle text-ink border border-ink/20 text-[10px] font-bold uppercase">
                          <Check className="h-2.5 w-2.5" />
                          DISPATCH READY
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-wild-red/10 text-wild-red border border-wild-red/30 text-[10px] font-bold uppercase">
                          <Wrench className="h-2.5 w-2.5" />
                          DEPOT MAINT
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right text-wild-muted text-[11px]">
                      {m.current_lat.toFixed(3)}°N, {m.current_lon.toFixed(3)}°E
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Footer bar */}
      <div className="border-t border-ink/10 px-4 py-2 bg-paper-subtle flex items-center justify-between text-[10px] font-mono text-wild-muted">
        <div>TOTAL UNITS: {filteredMachines.length}</div>
        <div>ALGORITHM: CP-SAT TIME WINDOW DISPATCH</div>
      </div>
    </div>
  );
};
