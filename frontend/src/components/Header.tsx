import React from "react";
import { Flame, Radio, ShieldCheck, Tractor } from "lucide-react";

interface HeaderProps {
  district: string;
  onDistrictChange: (d: string) => void;
  burnAlerts: number;
}

export const Header: React.FC<HeaderProps> = ({ district, onDistrictChange, burnAlerts }) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-50 px-6 py-4 flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold">
          <Tractor className="h-6 w-6 text-emerald-400" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-white">StubbleOS</h1>
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800 font-medium">
              Phase 7 Live
            </span>
          </div>
          <p className="text-xs text-slate-400">Autonomous Crop Residue Coordination Command Center</p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* District Selector */}
        <div className="flex items-center gap-2 bg-slate-800/80 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-slate-200">
          <span className="text-xs text-slate-400 uppercase font-semibold">District:</span>
          <select
            value={district}
            onChange={(e) => onDistrictChange(e.target.value)}
            className="bg-transparent font-medium text-white focus:outline-none cursor-pointer"
          >
            <option value="sangrur" className="bg-slate-900">Sangrur (Punjab)</option>
            <option value="patiala" className="bg-slate-900">Patiala (Punjab)</option>
            <option value="fatehgarh" className="bg-slate-900">Fatehgarh Sahib (Punjab)</option>
            <option value="karnal" className="bg-slate-900">Karnal (Haryana)</option>
          </select>
        </div>

        {/* Live Status Beacon */}
        <div className="flex items-center gap-2 bg-slate-800/50 border border-slate-700/60 rounded-lg px-3 py-1.5 text-xs text-slate-300">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
          </span>
          <span className="font-mono text-emerald-400 font-medium">LIVE TELEMETRY</span>
        </div>

        {/* Thermal Fire Warning Badge */}
        {burnAlerts > 0 && (
          <div className="flex items-center gap-1.5 bg-red-950/60 border border-red-800/80 rounded-lg px-3 py-1.5 text-xs text-red-300 font-semibold animate-pulse">
            <Flame className="h-4 w-4 text-red-400" />
            <span>{burnAlerts} Active Fire Alerts</span>
          </div>
        )}
      </div>
    </header>
  );
};

