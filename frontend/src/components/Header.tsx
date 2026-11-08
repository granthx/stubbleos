"use client";

import React from "react";
import { Flame, Radio, ShieldCheck, Tractor } from "lucide-react";

interface HeaderProps {
  district: string;
  onDistrictChange: (d: string) => void;
  burnAlerts: number;
  onOpenAudit?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  district,
  onDistrictChange,
  burnAlerts,
  onOpenAudit,
}) => {
  return (
    <header className="border-b border-ink/10 bg-paper sticky top-0 z-50">
      <div className="max-w-[1440px] mx-auto px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
        {/* Brand / Logo */}
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 bg-ink flex items-center justify-center text-paper font-bold text-sm tracking-tighter">
            <Tractor className="h-5 w-5 text-neon" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-black tracking-tight text-ink uppercase">
                Stubble<span className="text-wild-blue-gray">OS</span>
              </h1>
              <span className="text-[10px] px-2 py-0.5 bg-ink text-neon font-mono uppercase font-semibold">
                Live v1.0
              </span>
            </div>
            <p className="text-[11px] text-wild-muted font-mono uppercase tracking-wider">
              Autonomous Crop Residue Layer · Punjab & Haryana
            </p>
          </div>
        </div>

        {/* Controls & Badges */}
        <div className="flex flex-wrap items-center gap-3">
          {/* District Selector */}
          <div className="flex items-center bg-paper-subtle border border-ink/20 px-3 py-1.5 text-xs text-ink font-mono">
            <span className="text-[10px] text-wild-muted uppercase font-bold mr-2">
              SECTOR:
            </span>
            <select
              value={district}
              onChange={(e) => onDistrictChange(e.target.value)}
              className="bg-transparent font-bold text-ink uppercase focus:outline-none cursor-pointer"
            >
              <option value="sangrur">Sangrur (Punjab)</option>
              <option value="ludhiana">Ludhiana (Punjab)</option>
              <option value="patiala">Patiala (Punjab)</option>
              <option value="fatehgarh">Fatehgarh Sahib (Punjab)</option>
              <option value="karnal">Karnal (Haryana)</option>
            </select>
          </div>

          {/* Live Status Beacon */}
          <div className="flex items-center gap-2 border border-ink/10 px-3 py-1.5 text-xs font-mono bg-paper">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-neon opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-neon-lime border border-ink" />
            </span>
            <span className="text-[11px] font-bold tracking-wider text-ink">
              TELEMETRY LIVE
            </span>
          </div>

          {/* Thermal Fire Warning Badge */}
          {burnAlerts > 0 ? (
            <div className="flex items-center gap-1.5 bg-wild-red text-white px-3 py-1.5 text-xs font-mono font-bold uppercase animate-pulse">
              <Flame className="h-3.5 w-3.5 text-white" />
              <span>{burnAlerts} Active Fire Alerts</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 border border-ink/10 bg-paper-subtle text-ink px-3 py-1.5 text-xs font-mono font-semibold uppercase">
              <ShieldCheck className="h-3.5 w-3.5 text-ink" />
              <span>0 Fires · Sector Clear</span>
            </div>
          )}

          {/* MRV Audit Link */}
          {onOpenAudit && (
            <button
              onClick={onOpenAudit}
              className="border border-ink bg-ink text-paper hover:bg-neon hover:text-ink px-3 py-1.5 text-xs font-mono font-bold uppercase transition-colors"
            >
              MRV Ledger
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
