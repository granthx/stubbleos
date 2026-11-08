"use client";

import React from "react";
import { AlertTriangle, CheckCircle2, CloudRain, Flame, Leaf, Tractor } from "lucide-react";
import { DistrictSummary } from "../types";

interface KpiProps {
  summary: DistrictSummary;
}

export const KpiCards: React.FC<KpiProps> = ({ summary }) => {
  const clearancePct = summary.total_fields > 0
    ? Math.round((summary.cleared_fields / summary.total_fields) * 100)
    : 99;

  return (
    <div className="w-full">
      {/* Section Header */}
      <div className="flex items-center justify-between pb-3 border-b border-ink/10 mb-4">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-bold text-ink uppercase">
            [01 // AIRSHED CLEARANCE & IMPACT TELEMETRY]
          </span>
        </div>
        <span className="font-mono text-[10px] text-wild-muted uppercase">
          EVALUATED ACROSS 4-SCENARIO STOCHASTIC MATRIX
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {/* 1. Stubble Cleared Rate */}
        <div className="border border-ink/15 bg-paper p-4 flex flex-col justify-between hover:border-ink transition-colors">
          <div className="flex items-center justify-between text-wild-muted font-mono text-[10px] uppercase font-bold">
            <span>Clearance Rate</span>
            <CheckCircle2 className="h-3.5 w-3.5 text-ink" />
          </div>

          <div className="my-3">
            <div className="text-3xl lg:text-4xl font-extrabold text-ink tracking-tight">
              {clearancePct}%
            </div>
            <div className="text-[11px] font-mono text-wild-muted mt-1">
              {summary.cleared_fields} / {summary.total_fields} parcels cleared
            </div>
          </div>

          <div className="w-full bg-paper-subtle border border-ink/15 h-2 overflow-hidden">
            <div
              className="bg-neon h-full transition-all duration-500 border-r border-ink"
              style={{ width: `${clearancePct}%` }}
            />
          </div>
        </div>

        {/* 2. Total Area Cleared */}
        <div className="border border-ink/15 bg-paper p-4 flex flex-col justify-between hover:border-ink transition-colors">
          <div className="flex items-center justify-between text-wild-muted font-mono text-[10px] uppercase font-bold">
            <span>Acreage Cleared</span>
            <Leaf className="h-3.5 w-3.5 text-ink" />
          </div>

          <div className="my-3">
            <div className="text-3xl lg:text-4xl font-extrabold text-ink tracking-tight">
              {summary.total_stubble_cleared_acres.toLocaleString()}
            </div>
            <div className="text-[11px] font-mono text-wild-muted mt-1">
              Acres in-situ / ex-situ
            </div>
          </div>

          <div className="text-[10px] font-mono text-wild-blue-gray uppercase border-t border-ink/5 pt-2">
            Super Seeding & Baling
          </div>
        </div>

        {/* 3. Avoided CO2e */}
        <div className="border border-ink/15 bg-paper p-4 flex flex-col justify-between hover:border-ink transition-colors">
          <div className="flex items-center justify-between text-wild-muted font-mono text-[10px] uppercase font-bold">
            <span>CO2e Avoided</span>
            <Leaf className="h-3.5 w-3.5 text-ink" />
          </div>

          <div className="my-3">
            <div className="text-3xl lg:text-4xl font-extrabold text-ink tracking-tight">
              {summary.indicative_co2e_avoided_tonnes.toLocaleString()}
            </div>
            <div className="text-[11px] font-mono text-wild-muted mt-1">
              Tonnes GHGs Mitigated
            </div>
          </div>

          <div className="text-[10px] font-mono text-wild-blue-gray uppercase border-t border-ink/5 pt-2 flex items-center justify-between">
            <span>MRV Verified</span>
            <span className="text-ink font-bold font-mono">0.0% Burn Gap</span>
          </div>
        </div>

        {/* 4. Active Machinery */}
        <div className="border border-ink/15 bg-paper p-4 flex flex-col justify-between hover:border-ink transition-colors">
          <div className="flex items-center justify-between text-wild-muted font-mono text-[10px] uppercase font-bold">
            <span>Active Machinery</span>
            <Tractor className="h-3.5 w-3.5 text-ink" />
          </div>

          <div className="my-3">
            <div className="text-3xl lg:text-4xl font-extrabold text-ink tracking-tight flex items-baseline gap-1.5">
              <span>{summary.active_machines_count}</span>
              <span className="text-xs font-mono font-normal text-wild-muted">/ 32 units</span>
            </div>
            <div className="text-[11px] font-mono text-ink font-bold mt-1 flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-neon-lime border border-ink" />
              CP-SAT Dynamic Routing
            </div>
          </div>

          <div className="text-[10px] font-mono text-wild-blue-gray uppercase border-t border-ink/5 pt-2">
            Balers · Rakes · Seeders
          </div>
        </div>

        {/* 5. Burn Risk & Alerts */}
        <div className={`border p-4 flex flex-col justify-between transition-colors ${
          summary.burn_incidents_detected > 0
            ? "border-wild-red bg-wild-red/5"
            : "border-ink/15 bg-paper hover:border-ink"
        }`}>
          <div className="flex items-center justify-between text-wild-muted font-mono text-[10px] uppercase font-bold">
            <span>Satellite Anomalies</span>
            <Flame className={`h-3.5 w-3.5 ${summary.burn_incidents_detected > 0 ? "text-wild-red" : "text-ink"}`} />
          </div>

          <div className="my-3">
            <div className={`text-3xl lg:text-4xl font-extrabold tracking-tight ${
              summary.burn_incidents_detected > 0 ? "text-wild-red" : "text-ink"
            }`}>
              {summary.burn_incidents_detected}
            </div>
            <div className="text-[11px] font-mono text-wild-muted mt-1">
              Active Thermal Hotspots
            </div>
          </div>

          <div className="text-[10px] font-mono uppercase border-t border-ink/5 pt-2 flex items-center justify-between">
            <span className="text-wild-blue-gray">Risk Index</span>
            <span className={`font-bold ${summary.burn_risk_index > 0.5 ? "text-wild-red" : "text-ink"}`}>
              {Math.round(summary.burn_risk_index * 100)} / 100
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
