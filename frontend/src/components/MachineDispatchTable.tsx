import React from "react";
import { Check, Clock, Settings2, Tractor, Wrench } from "lucide-react";
import { MachineInfo } from "../types";

interface TableProps {
  machines: MachineInfo[];
}

export const MachineDispatchTable: React.FC<TableProps> = ({ machines }) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden flex flex-col">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Tractor className="h-4 w-4 text-emerald-400" />
          <h2 className="text-sm font-semibold text-white">Active Machinery & Fleet Dispatch</h2>
        </div>
        <span className="text-xs text-slate-500 font-mono">CP-SAT / VRP Routes Active</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-950/50 text-slate-400 border-b border-slate-800 uppercase font-semibold">
            <tr>
              <th className="py-2.5 px-4">Machine ID</th>
              <th className="py-2.5 px-4">Type</th>
              <th className="py-2.5 px-4">Operator</th>
              <th className="py-2.5 px-4">Daily Cap</th>
              <th className="py-2.5 px-4">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-slate-300">
            {machines.map((m) => (
              <tr key={m.id} className="hover:bg-slate-800/40">
                <td className="py-2.5 px-4 font-mono font-medium text-white">{m.id.substring(0, 8)}</td>
                <td className="py-2.5 px-4">
                  <span className="capitalize">{m.machine_type.replace(/_/g, " ")}</span>
                </td>
                <td className="py-2.5 px-4">{m.operator_name || "Unassigned"}</td>
                <td className="py-2.5 px-4 font-mono">{m.capacity_acres_per_day} ac/day</td>
                <td className="py-2.5 px-4">
                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                      m.status === "in_use"
                        ? "bg-amber-950 text-amber-300 border border-amber-800"
                        : m.status === "available"
                        ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                        : "bg-red-950 text-red-300 border border-red-800"
                    }`}
                  >
                    <span className="h-1.5 w-1.5 rounded-full bg-current"></span>
                    {m.status.toUpperCase()}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
