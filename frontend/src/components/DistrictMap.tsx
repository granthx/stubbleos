import React, { useState } from "react";
import { Flame, Layers, MapPin, Navigation, Tractor } from "lucide-react";
import { FieldInfo, MachineInfo } from "../types";

interface MapProps {
  fields: FieldInfo[];
  machines: MachineInfo[];
  district?: string;
}

export const DistrictMap: React.FC<MapProps> = ({ fields, machines, district = "sangrur" }) => {
  const [selectedField, setSelectedField] = useState<FieldInfo | null>(null);

  // Dynamically compute bounds from all fields and machines in the selected district
  const allLats = [...fields.map((f) => f.center_lat), ...machines.map((m) => m.current_lat)];
  const allLons = [...fields.map((f) => f.center_lon), ...machines.map((m) => m.current_lon)];

  let minLat = 30.22, maxLat = 30.38;
  let minLon = 75.80, maxLon = 75.98;

  if (allLats.length > 0 && allLons.length > 0) {
    const rawMinLat = Math.min(...allLats);
    const rawMaxLat = Math.max(...allLats);
    const rawMinLon = Math.min(...allLons);
    const rawMaxLon = Math.max(...allLons);
    const padLat = Math.max(0.015, (rawMaxLat - rawMinLat) * 0.2);
    const padLon = Math.max(0.015, (rawMaxLon - rawMinLon) * 0.2);
    minLat = rawMinLat - padLat;
    maxLat = rawMaxLat + padLat;
    minLon = rawMinLon - padLon;
    maxLon = rawMaxLon + padLon;
  }

  const toX = (lon: number) => Math.max(5, Math.min(95, ((lon - minLon) / Math.max(0.001, maxLon - minLon)) * 90 + 5));
  const toY = (lat: number) => Math.max(5, Math.min(95, (1 - (lat - minLat) / Math.max(0.001, maxLat - minLat)) * 90 + 5));

  const stateColors: Record<string, { bg: string; border: string; label: string }> = {
    cleared: { bg: "fill-emerald-500/30", border: "stroke-emerald-400", label: "Cleared (No Fire Risk)" },
    harvested_residue_present: { bg: "fill-amber-500/30", border: "stroke-amber-400", label: "Harvested (Residue Present)" },
    burn_detected: { bg: "fill-red-500/50", border: "stroke-red-400", label: "Active Fire Alert (FIRMS)" },
    not_harvested: { bg: "fill-slate-600/20", border: "stroke-slate-500", label: "Standing Crop" },
  };

  const burnCount = fields.filter((f) => f.state === "burn_detected").length;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden flex flex-col h-[520px]">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between bg-slate-900/80">
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4 text-emerald-400" />
          <h2 className="text-sm font-semibold text-white capitalize">{district} Geospatial Field Monitoring & Route Map</h2>
          {burnCount > 0 && (
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-red-950/80 text-red-400 border border-red-800 font-mono font-medium animate-pulse">
              {burnCount} Anomalies
            </span>
          )}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5 text-slate-300">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 inline-block"></span>
            <span>Cleared</span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-300">
            <span className="h-2.5 w-2.5 rounded-full bg-amber-400 inline-block"></span>
            <span>Residue Present</span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-300">
            <span className="h-2.5 w-2.5 rounded-full bg-red-500 inline-block animate-ping"></span>
            <span className="text-red-400 font-medium">Burn Detected</span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-300">
            <Tractor className="h-3.5 w-3.5 text-cyan-400 inline" />
            <span>Active Machine</span>
          </div>
        </div>
      </div>

      <div className="relative flex-1 bg-slate-950 p-4 overflow-hidden">
        {/* Synthetic Vector / SVG Map Canvas */}
        <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
          {/* Subtle grid lines */}
          <defs>
            <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
              <path d="M 10 0 L 0 0 0 10" fill="none" stroke="#1e293b" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100" height="100" fill="url(#grid)" />

          {/* Machine dispatch route traces */}
          {machines.map((m, idx) => {
            const x = toX(m.current_lon);
            const y = toY(m.current_lat);
            return (
              <path
                key={`route-${m.id}`}
                d={`M ${x - 10} ${y + 8} Q ${x - 4} ${y - 6} ${x} ${y}`}
                fill="none"
                stroke="#06b6d4"
                strokeWidth="0.6"
                strokeDasharray="1.5,1"
                opacity="0.6"
              />
            );
          })}

          {/* Field Parcels */}
          {fields.map((f, i) => {
            const cx = toX(f.center_lon);
            const cy = toY(f.center_lat);
            const style = stateColors[f.state] || stateColors.not_harvested;
            const isFire = f.state === "burn_detected";

            return (
              <g
                key={f.id}
                onClick={() => setSelectedField(f)}
                className="cursor-pointer transition-transform hover:scale-110"
              >
                <polygon
                  points={`${cx - 3},${cy - 2} ${cx + 3},${cy - 2.5} ${cx + 3.5},${cy + 2.5} ${cx - 2.5},${cy + 3}`}
                  className={`${style.bg} ${style.border}`}
                  strokeWidth={isFire ? "1" : "0.5"}
                />
                {isFire && (
                  <circle cx={cx} cy={cy} r="3" fill="#ef4444" opacity="0.3" className="animate-ping" />
                )}
              </g>
            );
          })}

          {/* Machinery Markers */}
          {machines.map((m) => {
            const mx = toX(m.current_lon);
            const my = toY(m.current_lat);
            return (
              <g key={m.id} transform={`translate(${mx}, ${my})`}>
                <circle r="1.8" fill="#06b6d4" stroke="#ffffff" strokeWidth="0.5" />
              </g>
            );
          })}
        </svg>

        {/* Selected Field Modal / Overlay */}
        {selectedField && (
          <div className="absolute bottom-4 left-4 bg-slate-900/95 border border-slate-700 rounded-lg p-3 w-72 text-xs shadow-xl backdrop-blur">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <span className="font-semibold text-white">Parcel {selectedField.village_code}</span>
              <button
                onClick={() => setSelectedField(null)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <div className="mt-2 space-y-1.5 text-slate-300">
              <div className="flex justify-between">
                <span className="text-slate-500">Acreage:</span>
                <span className="font-medium text-white">{selectedField.area_acres} acres</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Status:</span>
                <span className={`font-medium ${selectedField.state === "cleared" ? "text-emerald-400" : selectedField.state === "burn_detected" ? "text-red-400 font-bold" : "text-amber-400"}`}>
                  {selectedField.state.replace(/_/g, " ").toUpperCase()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Burn Risk Score:</span>
                <span className="font-mono">{Math.round(selectedField.burn_risk_score * 100)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Satellite Confidence:</span>
                <span className="font-mono text-emerald-400">{Math.round(selectedField.state_confidence * 100)}%</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

