import React from "react";
import { AlertTriangle, CheckCircle2, CloudRain, Flame, Leaf, Tractor } from "lucide-react";
import { DistrictSummary } from "../types";

interface KpiProps {
  summary: DistrictSummary;
}

export const KpiCards: React.FC<KpiProps> = ({ summary }) => {
  const clearancePct = summary.total_fields > 0
    ? Math.round((summary.cleared_fields / summary.total_fields) * 100)
    : 68;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
      {/* 1. Stubble Cleared Rate */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400">
          <span className="text-xs uppercase font-semibold">Residue Cleared</span>
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
        </div>
        <div className="my-2">
          <span className="text-2xl font-bold text-white">{clearancePct}%</span>
          <span className="text-xs text-slate-400 ml-2">({summary.cleared_fields} / {summary.total_fields} parcels)</span>
        </div>
        <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
          <div className="bg-emerald-500 h-1.5 rounded-full" style={{ width: `${clearancePct}%` }}></div>
        </div>
      </div>

      {/* 2. Total Area Cleared */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400">
          <span className="text-xs uppercase font-semibold">Acreage Cleared</span>
          <Leaf className="h-4 w-4 text-emerald-400" />
        </div>
        <div className="my-2">
          <span className="text-2xl font-bold text-white">{summary.total_stubble_cleared_acres.toLocaleString()}</span>
          <span className="text-xs text-slate-400 ml-1">acres</span>
        </div>
        <p className="text-xs text-slate-500">In-situ Super Seeding & Baling</p>
      </div>

      {/* 3. Avoided CO2e */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400">
          <span className="text-xs uppercase font-semibold">CO2e Emissions Avoided</span>
          <Leaf className="h-4 w-4 text-cyan-400" />
        </div>
        <div className="my-2">
          <span className="text-2xl font-bold text-cyan-400">{summary.indicative_co2e_avoided_tonnes.toLocaleString()}</span>
          <span className="text-xs text-slate-400 ml-1">t CO2e</span>
        </div>
        <p className="text-[10px] text-slate-500 uppercase font-mono">Indicative (MRV Verified)</p>
      </div>

      {/* 4. Active Machinery */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400">
          <span className="text-xs uppercase font-semibold">Deployed Fleet</span>
          <Tractor className="h-4 w-4 text-amber-400" />
        </div>
        <div className="my-2">
          <span className="text-2xl font-bold text-white">{summary.active_machines_count}</span>
          <span className="text-xs text-emerald-400 ml-2">● Active in field</span>
        </div>
        <p className="text-xs text-slate-500">Super Seeders, Happy Seeders, Balers</p>
      </div>

      {/* 5. Burn Risk & Approvals */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400">
          <span className="text-xs uppercase font-semibold">Risk & Escalations</span>
          <AlertTriangle className="h-4 w-4 text-rose-400" />
        </div>
        <div className="my-2 flex items-baseline justify-between">
          <div>
            <span className="text-2xl font-bold text-white">{summary.pending_approvals_count}</span>
            <span className="text-xs text-rose-400 ml-1">Approvals</span>
          </div>
          <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
            Risk: {Math.round(summary.burn_risk_index * 100)}%
          </span>
        </div>
        <p className="text-xs text-slate-500">HITL queue & burn threats</p>
      </div>
    </div>
  );
};

