import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Compass,
  Crosshair,
  Eye,
  Flame,
  Layers,
  MapPin,
  Maximize2,
  Minimize2,
  Navigation,
  RefreshCw,
  SlidersHorizontal,
  Tractor,
  Volume2,
  Wheat,
  X,
  Zap,
} from "lucide-react";
import { FieldInfo, MachineInfo } from "../types";

interface MapProps {
  fields: FieldInfo[];
  machines: MachineInfo[];
  district?: string;
}

interface DistrictConfig {
  name: string;
  state: string;
  centerLat: number;
  centerLon: number;
  corridorName: string;
  canalName: string;
  chcHubName: string;
  villages: { name: string; dlat: number; dlon: number }[];
}

const DISTRICT_CONFIGS: Record<string, DistrictConfig> = {
  sangrur: {
    name: "Sangrur",
    state: "Punjab",
    centerLat: 30.245,
    centerLon: 75.842,
    corridorName: "NH-7 (Sangrur - Dhuri - Barnala Corridor)",
    canalName: "Bathinda Branch · Sirhind Canal Network",
    chcHubName: "CHC Sangrur Central Agri-Hub",
    villages: [
      { name: "Dhuri", dlat: 0.025, dlon: -0.015 },
      { name: "Sunam", dlat: -0.026, dlon: 0.018 },
      { name: "Bhawanigarh", dlat: 0.015, dlon: 0.028 },
      { name: "Longowal", dlat: -0.022, dlon: -0.025 },
    ],
  },
  patiala: {
    name: "Patiala",
    state: "Punjab",
    centerLat: 30.33,
    centerLon: 76.39,
    corridorName: "NH-64 (Patiala - Nabha - Sangrur Expressway)",
    canalName: "Bhakra Main Line (BML Feeder Canal)",
    chcHubName: "CHC Patiala East Depot",
    villages: [
      { name: "Nabha", dlat: 0.024, dlon: -0.022 },
      { name: "Samana", dlat: -0.028, dlon: 0.015 },
      { name: "Rajpura", dlat: 0.028, dlon: 0.025 },
      { name: "Sanaur", dlat: -0.018, dlon: -0.02 },
    ],
  },
  ludhiana: {
    name: "Ludhiana",
    state: "Punjab",
    centerLat: 30.88,
    centerLon: 75.85,
    corridorName: "NH-5 / NH-44 (Ludhiana - Khanna Agro-Belt)",
    canalName: "Sidhwan Canal & Sutlej River Basin Network",
    chcHubName: "CHC Ludhiana South CHC Cluster",
    villages: [
      { name: "Khanna", dlat: 0.026, dlon: 0.024 },
      { name: "Jagraon", dlat: -0.025, dlon: -0.026 },
      { name: "Samrala", dlat: 0.022, dlon: -0.018 },
      { name: "Doraha", dlat: -0.019, dlon: 0.022 },
    ],
  },
  fatehgarh: {
    name: "Fatehgarh Sahib",
    state: "Punjab",
    centerLat: 30.64,
    centerLon: 76.39,
    corridorName: "GT Road / Sirhind Bypass Agricultural Link",
    canalName: "Sirhind Feeder & Narwana Branch Canal",
    chcHubName: "CHC Sirhind Mandi Central Depot",
    villages: [
      { name: "Sirhind", dlat: -0.015, dlon: -0.015 },
      { name: "Mandi Gobindgarh", dlat: 0.028, dlon: 0.02 },
      { name: "Bassi Pathana", dlat: 0.022, dlon: -0.024 },
      { name: "Khamano", dlat: -0.024, dlon: 0.025 },
    ],
  },
  karnal: {
    name: "Karnal",
    state: "Haryana",
    centerLat: 29.69,
    centerLon: 76.98,
    corridorName: "NH-44 (Grand Trunk Road · Nilokheri - Gharaunda)",
    canalName: "Western Yamuna Canal (Augmentation Branch)",
    chcHubName: "CHC Karnal ICAR-CSSRI Farm Machinery Hub",
    villages: [
      { name: "Nilokheri", dlat: 0.028, dlon: -0.018 },
      { name: "Gharaunda", dlat: -0.026, dlon: 0.015 },
      { name: "Indri", dlat: 0.024, dlon: 0.026 },
      { name: "Assandh", dlat: -0.022, dlon: -0.024 },
    ],
  },
};

export const DistrictMap: React.FC<MapProps> = ({ fields, machines, district = "sangrur" }) => {
  const dKey = district.toLowerCase();
  const config = DISTRICT_CONFIGS[dKey] || DISTRICT_CONFIGS.sangrur;

  // Selected state
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  const [selectedMachineId, setSelectedMachineId] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<"all" | "burn" | "residue" | "fleet" | "cleared">("all");
  const [fastDispatchedIds, setFastDispatchedIds] = useState<Record<string, boolean>>({});

  // Layer visibility toggles
  const [showRoads, setShowRoads] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);
  const [showThermal, setShowThermal] = useState(true);
  const [showGrid, setShowGrid] = useState(true);

  // Zoom and Pan
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const panStartRef = useRef({ x: 0, y: 0 });

  // Reset selections when district changes
  useEffect(() => {
    setSelectedFieldId(null);
    setSelectedMachineId(null);
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setFastDispatchedIds({});
  }, [district]);

  // Canvas coordinate space
  const CANVAS_W = 960;
  const CANVAS_H = 540;
  const PADDING = 60;

  // Compute realistic spatial bounds around the district center
  const { minLon, maxLon, minLat, maxLat } = useMemo(() => {
    const lats = fields.map((f) => f.center_lat).concat(machines.map((m) => m.current_lat));
    const lons = fields.map((f) => f.center_lon).concat(machines.map((m) => m.current_lon));

    const centerLat = config.centerLat;
    const centerLon = config.centerLon;

    const baseMinLat = lats.length > 0 ? Math.min(...lats) : centerLat - 0.04;
    const baseMaxLat = lats.length > 0 ? Math.max(...lats) : centerLat + 0.04;
    const baseMinLon = lons.length > 0 ? Math.min(...lons) : centerLon - 0.04;
    const baseMaxLon = lons.length > 0 ? Math.max(...lons) : centerLon + 0.04;

    const latSpan = Math.max(0.07, baseMaxLat - baseMinLat);
    const lonSpan = Math.max(0.08, baseMaxLon - baseMinLon);

    const midLat = (baseMinLat + baseMaxLat) / 2;
    const midLon = (baseMinLon + baseMaxLon) / 2;

    const padLat = latSpan * 0.42;
    const padLon = lonSpan * 0.42;

    return {
      minLat: midLat - padLat,
      maxLat: midLat + padLat,
      minLon: midLon - padLon,
      maxLon: midLon + padLon,
    };
  }, [fields, machines, config]);

  // Coordinate projection mapping lat/lon to fixed SVG space (960 x 540)
  const projectX = (lon: number) => {
    const ratio = (lon - minLon) / Math.max(0.0001, maxLon - minLon);
    return PADDING + ratio * (CANVAS_W - 2 * PADDING);
  };

  const projectY = (lat: number) => {
    // Invert Y so North is up
    const ratio = (lat - minLat) / Math.max(0.0001, maxLat - minLat);
    return CANVAS_H - PADDING - ratio * (CANVAS_H - 2 * PADDING);
  };

  // Generate realistic cadastral parcel polygon shapes scaled to area_acres
  const getParcelPolygon = (field: FieldInfo, idx: number) => {
    const cx = projectX(field.center_lon);
    const cy = projectY(field.center_lat);
    const scale = Math.sqrt(Math.max(2, field.area_acres)) * 8.5;

    // Agricultural field orientations (aligned with rural survey boundaries)
    const anglePresets = [18, -12, 8, -20, 15, -8, 25, -15, 10, -5];
    const angleRad = (anglePresets[idx % anglePresets.length] * Math.PI) / 180;
    const cosA = Math.cos(angleRad);
    const sinA = Math.sin(angleRad);

    const w = scale * 1.8;
    const h = scale * 1.15;

    // Trapezoidal boundary points relative to center
    const corners = [
      { dx: -w / 2 - 3, dy: -h / 2 + 2 },
      { dx: w / 2 + 2, dy: -h / 2 - 2 },
      { dx: w / 2 - 2, dy: h / 2 + 3 },
      { dx: -w / 2 + 1, dy: h / 2 - 1 },
    ];

    const rotatedPoints = corners.map((pt) => {
      const rx = pt.dx * cosA - pt.dy * sinA;
      const ry = pt.dx * sinA + pt.dy * cosA;
      return `${(cx + rx).toFixed(1)},${(cy + ry).toFixed(1)}`;
    });

    return {
      points: rotatedPoints.join(" "),
      cx,
      cy,
    };
  };

  // Map machines to assigned target fields for realistic dispatch corridors
  const machineAssignments = useMemo(() => {
    return machines.map((m, idx) => {
      // Pair each machine deterministically with a field needing attention or in-progress
      const targetField =
        fields.find((f) => f.state === "burn_detected") ||
        fields.find((f) => f.state === "harvested_residue_present") ||
        (fields.length > 0 ? fields[idx % fields.length] : null);

      const typeCode = m.machine_type
        .split("_")
        .map((w) => w[0].toUpperCase())
        .join("");
      const distCode = (m.district || "SEC").substring(0, 3).toUpperCase();
      const numCode = m.id.replace(/[^0-9]/g, "").slice(-2) || String(idx + 1).padStart(2, "0");
      const callsign = `${typeCode}-${distCode}-${numCode}`;

      return {
        machine: m,
        callsign,
        targetField,
        isInUse: m.status === "in_use",
        etaMinutes: 8 + (idx * 4) % 15,
        distanceKm: (1.8 + ((idx * 7) % 25) / 10).toFixed(1),
      };
    });
  }, [machines, fields]);

  // Selected objects
  const selectedField = useMemo(
    () => fields.find((f) => f.id === selectedFieldId) || null,
    [fields, selectedFieldId]
  );

  const selectedMachine = useMemo(
    () => machineAssignments.find((a) => a.machine.id === selectedMachineId) || null,
    [machineAssignments, selectedMachineId]
  );

  // Incoming machine assigned to selected field
  const incomingMachineForSelectedField = useMemo(() => {
    if (!selectedField) return null;
    return machineAssignments.find(
      (a) => a.targetField?.id === selectedField.id && a.isInUse
    );
  }, [selectedField, machineAssignments]);

  // Filtered fields based on active pill
  const filteredFields = useMemo(() => {
    return fields.filter((f) => {
      if (activeFilter === "burn") return f.state === "burn_detected";
      if (activeFilter === "residue") return f.state === "harvested_residue_present";
      if (activeFilter === "cleared") return f.state === "cleared";
      return true;
    });
  }, [fields, activeFilter]);

  // Filter counts
  const burnCount = fields.filter((f) => f.state === "burn_detected").length;
  const residueCount = fields.filter((f) => f.state === "harvested_residue_present").length;
  const clearedCount = fields.filter((f) => f.state === "cleared").length;
  const activeFleetCount = machineAssignments.filter((a) => a.isInUse).length;

  // Zoom & Pan handlers
  const handleZoomIn = () => setZoom((z) => Math.min(2.5, Number((z + 0.25).toFixed(2))));
  const handleZoomOut = () => setZoom((z) => Math.max(1, Number((z - 0.25).toFixed(2))));
  const handleResetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (zoom <= 1) return;
    setIsPanning(true);
    panStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isPanning) return;
    setPan({
      x: e.clientX - panStartRef.current.x,
      y: e.clientY - panStartRef.current.y,
    });
  };

  const handleMouseUp = () => setIsPanning(false);

  // Colors & styles by field status
  const getFieldStyle = (state: string, isSelected: boolean) => {
    switch (state) {
      case "burn_detected":
        return {
          fill: "fill-red-600/35",
          stroke: isSelected ? "stroke-red-300" : "stroke-red-500",
          strokeWidth: isSelected ? 3 : 2,
          glow: "drop-shadow(0 0 10px rgba(239, 68, 68, 0.7))",
          labelBg: "bg-red-950/90 text-red-300 border-red-700",
        };
      case "harvested_residue_present":
        return {
          fill: "fill-amber-500/25",
          stroke: isSelected ? "stroke-amber-200" : "stroke-amber-400",
          strokeWidth: isSelected ? 3 : 1.6,
          glow: isSelected ? "drop-shadow(0 0 8px rgba(245, 158, 11, 0.6))" : undefined,
          labelBg: "bg-amber-950/90 text-amber-300 border-amber-800",
        };
      case "cleared":
        return {
          fill: "fill-emerald-500/20",
          stroke: isSelected ? "stroke-emerald-200" : "stroke-emerald-400",
          strokeWidth: isSelected ? 3 : 1.4,
          glow: isSelected ? "drop-shadow(0 0 8px rgba(16, 185, 129, 0.6))" : undefined,
          labelBg: "bg-emerald-950/90 text-emerald-300 border-emerald-800",
        };
      default:
        return {
          fill: "fill-slate-700/20",
          stroke: isSelected ? "stroke-slate-300" : "stroke-slate-500",
          strokeWidth: isSelected ? 2.5 : 1.2,
          glow: undefined,
          labelBg: "bg-slate-900/90 text-slate-400 border-slate-700",
        };
    }
  };

  // Highway corridor anchor points
  const highwayPoints = useMemo(() => {
    const p1x = projectX(config.centerLon - 0.05);
    const p1y = projectY(config.centerLat + 0.035);
    const p2x = projectX(config.centerLon);
    const p2y = projectY(config.centerLat);
    const p3x = projectX(config.centerLon + 0.055);
    const p3y = projectY(config.centerLat - 0.038);
    return `M ${p1x} ${p1y} Q ${p2x} ${p2y - 15} ${p3x} ${p3y}`;
  }, [config, minLon, maxLon, minLat, maxLat]);

  // Canal network path
  const canalPoints = useMemo(() => {
    const c1x = projectX(config.centerLon - 0.045);
    const c1y = projectY(config.centerLat - 0.032);
    const c2x = projectX(config.centerLon + 0.005);
    const c2y = projectY(config.centerLat + 0.005);
    const c3x = projectX(config.centerLon + 0.048);
    const c3y = projectY(config.centerLat + 0.038);
    return `M ${c1x} ${c1y} C ${c2x - 30} ${c2y - 20}, ${c2x + 20} ${c2y + 15}, ${c3x} ${c3y}`;
  }, [config, minLon, maxLon, minLat, maxLat]);

  // CHC Depot position
  const chcPos = useMemo(() => {
    return {
      x: projectX(config.centerLon + 0.002),
      y: projectY(config.centerLat - 0.004),
    };
  }, [config, minLon, maxLon, minLat, maxLat]);

  return (
    <div className="border border-ink/15 bg-paper rounded-none md:rounded-md overflow-hidden flex flex-col h-[560px] shadow-sm relative select-none">
      {/* Top Header Bar */}
      <div className="px-4 py-2.5 border-b border-ink/10 bg-paper flex flex-wrap items-center justify-between gap-3 z-20">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 bg-ink text-paper">
            <Layers className="h-4 w-4 text-neon" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xs font-mono font-bold text-ink uppercase tracking-wider">
                [06 // {config.name} GIS CADASTRE & DISPATCH RADAR]
              </h2>
              <span className="text-[10px] font-mono px-1.5 py-0.2 bg-paper-subtle text-ink border border-ink/20">
                {config.state}
              </span>
              {burnCount > 0 ? (
                <span className="text-[10px] px-2.5 py-0.5 bg-wild-red text-white font-mono font-bold uppercase flex items-center gap-1 animate-pulse">
                  <Flame className="h-3 w-3 text-white" />
                  {burnCount} FIRMS Thermal {burnCount === 1 ? "Hotspot" : "Hotspots"}
                </span>
              ) : (
                <span className="text-[10px] px-2.5 py-0.5 bg-paper-subtle text-ink border border-ink/20 font-mono font-semibold uppercase flex items-center gap-1">
                  <Zap className="h-3 w-3 text-ink" />
                  Zero Active Fires
                </span>
              )}
            </div>
            <p className="text-[10px] text-wild-muted font-mono uppercase">
              Sentinel-2 L2A Multispectral Cadastre (10m) · CP-SAT Dynamic Fleet Router
            </p>
          </div>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1 text-[10px] font-mono">
          <button
            onClick={() => setActiveFilter("all")}
            className={`px-2.5 py-1 uppercase border transition-colors ${
              activeFilter === "all"
                ? "bg-ink text-paper border-ink font-bold"
                : "bg-paper text-wild-muted border-ink/15 hover:border-ink"
            }`}
          >
            All ({fields.length})
          </button>
          <button
            onClick={() => setActiveFilter("burn")}
            className={`px-2.5 py-1 uppercase border transition-colors flex items-center gap-1 ${
              activeFilter === "burn"
                ? "bg-wild-red text-white border-wild-red font-bold"
                : "bg-paper text-wild-red border-ink/15 hover:border-wild-red"
            }`}
          >
            <Flame className="h-3 w-3" /> Fires ({burnCount})
          </button>
          <button
            onClick={() => setActiveFilter("residue")}
            className={`px-2.5 py-1 uppercase border transition-colors flex items-center gap-1 ${
              activeFilter === "residue"
                ? "bg-straw text-ink border-ink font-bold"
                : "bg-paper text-ink border-ink/15 hover:border-ink"
            }`}
          >
            <Wheat className="h-3 w-3" /> Residue ({residueCount})
          </button>
          <button
            onClick={() => setActiveFilter("cleared")}
            className={`px-2.5 py-1 uppercase border transition-colors flex items-center gap-1 ${
              activeFilter === "cleared"
                ? "bg-neon text-ink border-ink font-bold"
                : "bg-paper text-ink border-ink/15 hover:border-ink"
            }`}
          >
            Cleared ({clearedCount})
          </button>
        </div>

        {/* Layer Visibility Toggles */}
        <div className="flex items-center gap-1.5 text-[10px] font-mono">
          <button
            onClick={() => setShowRoads((v) => !v)}
            title="Toggle Rural Road Network"
            className={`px-2 py-1 uppercase border transition flex items-center gap-1 ${
              showRoads
                ? "bg-ink text-paper border-ink font-bold"
                : "bg-paper text-wild-muted border-ink/15 hover:border-ink"
            }`}
          >
            <span>🛣️ Roads</span>
          </button>
          <button
            onClick={() => setShowRoutes((v) => !v)}
            title="Toggle Fleet Dispatch Corridors"
            className={`px-2 py-1 uppercase border transition flex items-center gap-1 ${
              showRoutes
                ? "bg-ink text-paper border-ink font-bold"
                : "bg-paper text-wild-muted border-ink/15 hover:border-ink"
            }`}
          >
            <span>🚜 Routes ({activeFleetCount})</span>
          </button>
          <button
            onClick={() => setShowThermal((v) => !v)}
            title="Toggle Thermal Anomaly Overlay"
            className={`px-2 py-1 uppercase border transition flex items-center gap-1 ${
              showThermal
                ? "bg-wild-red text-white border-wild-red font-bold"
                : "bg-paper text-wild-muted border-ink/15 hover:border-ink"
            }`}
          >
            <span>🔥 Thermal</span>
          </button>
          <button
            onClick={() => setShowGrid((v) => !v)}
            title="Toggle Coordinate Grid"
            className={`px-2 py-1 uppercase border transition flex items-center gap-1 ${
              showGrid
                ? "bg-ink/10 text-ink border-ink/30 font-bold"
                : "bg-paper text-wild-muted border-ink/15 hover:border-ink"
            }`}
          >
            <span>🛰️ Grid</span>
          </button>
        </div>
      </div>

      {/* Main Map Viewport */}
      <div
        className="relative flex-1 bg-slate-950 overflow-hidden cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
      >
        <svg
          className="w-full h-full"
          viewBox={`0 0 ${CANVAS_W} ${CANVAS_H}`}
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            {/* Dark GIS Satellite Grid Pattern */}
            <pattern id="gisGrid" width="48" height="48" patternUnits="userSpaceOnUse">
              <path d="M 48 0 L 0 0 0 48" fill="none" stroke="#1e293b" strokeWidth="0.75" />
              <circle cx="24" cy="24" r="0.8" fill="#334155" />
            </pattern>

            {/* Farm Residue Stubble Hatch Pattern */}
            <pattern id="stubblePattern" width="10" height="10" patternUnits="userSpaceOnUse">
              <line x1="0" y1="10" x2="10" y2="0" stroke="#f59e0b" strokeWidth="0.8" opacity="0.3" />
            </pattern>

            {/* Cleared / Wheat Seeding Furrow Pattern */}
            <pattern id="clearedPattern" width="8" height="8" patternUnits="userSpaceOnUse">
              <line x1="0" y1="4" x2="8" y2="4" stroke="#10b981" strokeWidth="0.7" opacity="0.25" />
            </pattern>

            {/* Thermal Hazard Glow Filter */}
            <filter id="fireGlow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>

            {/* Route Outer Corridor Glow */}
            <filter id="routeGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3.5" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Transform group for Zoom & Pan */}
          <g
            transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}
            transform-origin={`${CANVAS_W / 2} ${CANVAS_H / 2}`}
          >
            {/* Background Satellite Canvas Base */}
            <rect width={CANVAS_W} height={CANVAS_H} fill="#030712" />
            {showGrid && <rect width={CANVAS_W} height={CANVAS_H} fill="url(#gisGrid)" opacity="0.9" />}

            {/* Rural Geographic Coordinate Axis Markings */}
            {showGrid && (
              <g className="text-[10px] font-mono fill-slate-500 select-none pointer-events-none">
                {/* Latitudes on Left */}
                <text x="16" y={projectY(config.centerLat + 0.025)}>
                  {(config.centerLat + 0.025).toFixed(3)}°N
                </text>
                <line
                  x1="12"
                  y1={projectY(config.centerLat + 0.025)}
                  x2={CANVAS_W - 12}
                  y2={projectY(config.centerLat + 0.025)}
                  stroke="#1e293b"
                  strokeDasharray="2 4"
                />

                <text x="16" y={projectY(config.centerLat)}>
                  {config.centerLat.toFixed(3)}°N [District Center]
                </text>
                <line
                  x1="12"
                  y1={projectY(config.centerLat)}
                  x2={CANVAS_W - 12}
                  y2={projectY(config.centerLat)}
                  stroke="#334155"
                  strokeDasharray="3 3"
                />

                <text x="16" y={projectY(config.centerLat - 0.025)}>
                  {(config.centerLat - 0.025).toFixed(3)}°N
                </text>
                <line
                  x1="12"
                  y1={projectY(config.centerLat - 0.025)}
                  x2={CANVAS_W - 12}
                  y2={projectY(config.centerLat - 0.025)}
                  stroke="#1e293b"
                  strokeDasharray="2 4"
                />

                {/* Longitudes on Bottom */}
                <text x={projectX(config.centerLon - 0.03)} y={CANVAS_H - 18} textAnchor="middle">
                  {(config.centerLon - 0.03).toFixed(3)}°E
                </text>
                <text x={projectX(config.centerLon)} y={CANVAS_H - 18} textAnchor="middle">
                  {config.centerLon.toFixed(3)}°E
                </text>
                <text x={projectX(config.centerLon + 0.03)} y={CANVAS_H - 18} textAnchor="middle">
                  {(config.centerLon + 0.03).toFixed(3)}°E
                </text>
              </g>
            )}

            {/* Canal Network Layer */}
            {showRoads && (
              <g className="select-none">
                {/* Canal Water Glow & Core */}
                <path
                  d={canalPoints}
                  fill="none"
                  stroke="#0284c7"
                  strokeWidth="8"
                  opacity="0.18"
                  strokeLinecap="round"
                />
                <path
                  d={canalPoints}
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="2.4"
                  opacity="0.75"
                  strokeDasharray="12 4"
                />
                {/* Canal Label */}
                <text
                  x={projectX(config.centerLon + 0.015)}
                  y={projectY(config.centerLat + 0.012)}
                  fontSize="9.5"
                  fontFamily="monospace"
                  fill="#7dd3fc"
                  opacity="0.85"
                >
                  💧 {config.canalName}
                </text>
              </g>
            )}

            {/* Rural Arterial Highway Corridor */}
            {showRoads && (
              <g className="select-none">
                {/* Highway Bed */}
                <path
                  d={highwayPoints}
                  fill="none"
                  stroke="#334155"
                  strokeWidth="7"
                  strokeLinecap="round"
                />
                {/* Highway Centerline */}
                <path
                  d={highwayPoints}
                  fill="none"
                  stroke="#fbbf24"
                  strokeWidth="1.2"
                  strokeDasharray="6 6"
                  opacity="0.8"
                />
                {/* Highway Label */}
                <text
                  x={projectX(config.centerLon - 0.032)}
                  y={projectY(config.centerLat + 0.02)}
                  fontSize="9.5"
                  fontFamily="monospace"
                  fill="#cbd5e1"
                  opacity="0.9"
                  className="font-medium"
                >
                  🛣️ {config.corridorName}
                </text>

                {/* Rural Connector Roads joining village clusters */}
                {config.villages.map((v, i) => {
                  const vx = projectX(config.centerLon + v.dlon);
                  const vy = projectY(config.centerLat + v.dlat);
                  const hwX = projectX(config.centerLon);
                  const hwY = projectY(config.centerLat);

                  return (
                    <g key={`road-${v.name}`}>
                      <path
                        d={`M ${chcPos.x} ${chcPos.y} Q ${(chcPos.x + vx) / 2} ${(chcPos.y + vy) / 2 - 10} ${vx} ${vy}`}
                        fill="none"
                        stroke="#1e293b"
                        strokeWidth="2.5"
                        strokeDasharray="4 3"
                        opacity="0.8"
                      />
                      {/* Village settlement label */}
                      <circle cx={vx} cy={vy} r="3" fill="#64748b" />
                      <text
                        x={vx + 6}
                        y={vy - 4}
                        fontSize="9"
                        fontFamily="sans-serif"
                        fill="#94a3b8"
                        className="font-semibold"
                      >
                        📍 {v.name}
                      </text>
                    </g>
                  );
                })}
              </g>
            )}

            {/* Custom Hiring Center (CHC Central Machinery Depot) */}
            <g
              transform={`translate(${chcPos.x}, ${chcPos.y})`}
              className="cursor-pointer"
              onClick={() => setSelectedMachineId(machines[0]?.id || null)}
            >
              <rect
                x="-46"
                y="-14"
                width="92"
                height="28"
                rx="6"
                fill="#0f172a"
                stroke="#0284c7"
                strokeWidth="1.5"
                opacity="0.95"
              />
              <circle cx="-32" cy="0" r="4.5" fill="#38bdf8" />
              <text
                x="4"
                y="3.5"
                textAnchor="middle"
                fontSize="8.5"
                fontFamily="sans-serif"
                fill="#e2e8f0"
                className="font-bold select-none"
              >
                🏢 CHC DEPOT
              </text>
            </g>

            {/* Machine Dispatch Route Corridors */}
            {showRoutes &&
              machineAssignments.map((a, idx) => {
                const mx = projectX(a.machine.current_lon);
                const my = projectY(a.machine.current_lat);

                if (!a.targetField) return null;
                const fx = projectX(a.targetField.center_lon);
                const fy = projectY(a.targetField.center_lat);

                const isSelected =
                  selectedMachineId === a.machine.id || selectedFieldId === a.targetField.id;
                const isDimmed =
                  (selectedMachineId || selectedFieldId) && !isSelected;

                if (!a.isInUse && !isSelected) return null;

                // Waypoint corridor via nearest rural link route
                const midX = (mx + fx) / 2 + ((idx % 2 === 0 ? 1 : -1) * 22);
                const midY = (my + fy) / 2 - 16;
                const routePath = `M ${mx} ${my} Q ${midX} ${midY} ${fx} ${fy}`;

                return (
                  <g
                    key={`route-${a.machine.id}`}
                    opacity={isDimmed ? 0.25 : 1}
                    className="transition-opacity duration-300"
                  >
                    {/* Outer Ambient Glow */}
                    <path
                      d={routePath}
                      fill="none"
                      stroke="#06b6d4"
                      strokeWidth={isSelected ? "8" : "5"}
                      opacity={isSelected ? "0.45" : "0.2"}
                      strokeLinecap="round"
                      filter="url(#routeGlow)"
                    />

                    {/* Base Route Track */}
                    <path
                      d={routePath}
                      fill="none"
                      stroke="#0891b2"
                      strokeWidth={isSelected ? "2.6" : "1.8"}
                      strokeDasharray="4 3"
                      opacity="0.8"
                    />

                    {/* Directional Flow Animation Track */}
                    <path
                      d={routePath}
                      fill="none"
                      stroke={isSelected ? "#ffffff" : "#22d3ee"}
                      strokeWidth={isSelected ? "2.4" : "1.8"}
                      strokeDasharray="7 5"
                      className="animate-route-flow"
                    />

                    {/* Destination Entry Waypoint Pin */}
                    <circle cx={fx} cy={fy} r="5" fill="#06b6d4" opacity="0.4" />
                    <circle cx={fx} cy={fy} r="2.5" fill="#22d3ee" />

                    {/* Interactive Telemetry Route Badge along midpoint */}
                    <g
                      transform={`translate(${midX}, ${midY})`}
                      className="cursor-pointer"
                      onClick={() => {
                        setSelectedMachineId(a.machine.id);
                        setSelectedFieldId(a.targetField!.id);
                      }}
                    >
                      <rect
                        x="-48"
                        y="-10"
                        width="96"
                        height="20"
                        rx="10"
                        fill="#082f49"
                        stroke="#38bdf8"
                        strokeWidth="1.2"
                      />
                      <text
                        x="0"
                        y="3.5"
                        textAnchor="middle"
                        fontSize="8.5"
                        fontFamily="monospace"
                        fontWeight="bold"
                        fill="#e0f2fe"
                        className="select-none pointer-events-none"
                      >
                        {a.distanceKm} km · {a.etaMinutes}m ETA
                      </text>
                    </g>
                  </g>
                );
              })}

            {/* Field Parcels (Authentic Cadastre Boundary Geometry) */}
            {filteredFields.map((field, idx) => {
              const { points, cx, cy } = getParcelPolygon(field, idx);
              const isSelected = selectedFieldId === field.id;
              const isFire = field.state === "burn_detected";
              const isResidue = field.state === "harvested_residue_present";
              const isCleared = field.state === "cleared";
              const isFastDispatched = Boolean(fastDispatchedIds[field.id]);
              const style = getFieldStyle(field.state, isSelected);

              return (
                <g
                  key={field.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedFieldId(field.id);
                    // Also highlight assigned machine if present
                    const assigned = machineAssignments.find(
                      (m) => m.targetField?.id === field.id
                    );
                    if (assigned) setSelectedMachineId(assigned.machine.id);
                  }}
                  className="cursor-pointer transition-all duration-200"
                >
                  {/* Active Thermal Wave Beacon (FIRMS Anomaly Alert) */}
                  {showThermal && isFire && (
                    <g>
                      <circle
                        cx={cx}
                        cy={cy}
                        r="30"
                        fill="none"
                        stroke="#ef4444"
                        strokeWidth="1.5"
                        className="animate-radar-ring"
                      />
                      <circle
                        cx={cx}
                        cy={cy}
                        r="20"
                        fill="none"
                        stroke="#f97316"
                        strokeWidth="1.8"
                        className="animate-radar-ring"
                        style={{ animationDelay: "0.6s" }}
                      />
                      <circle
                        cx={cx}
                        cy={cy}
                        r="14"
                        fill="#ef4444"
                        opacity="0.35"
                        filter="url(#fireGlow)"
                      />
                    </g>
                  )}

                  {/* Parcel Cadastre Boundary Polygon */}
                  <polygon
                    points={points}
                    className={`${style.fill} ${style.stroke} transition-all`}
                    strokeWidth={style.strokeWidth}
                    style={{ filter: style.glow }}
                  />

                  {/* Internal Crop Residue / Cleared Pattern Overlay */}
                  {isResidue && (
                    <polygon
                      points={points}
                      fill="url(#stubblePattern)"
                      className="pointer-events-none"
                    />
                  )}
                  {isCleared && (
                    <polygon
                      points={points}
                      fill="url(#clearedPattern)"
                      className="pointer-events-none"
                    />
                  )}

                  {/* Selected Highlight Outline */}
                  {isSelected && (
                    <polygon
                      points={points}
                      fill="none"
                      stroke="#38bdf8"
                      strokeWidth="2.5"
                      strokeDasharray="4 2"
                      className="pointer-events-none"
                    />
                  )}

                  {/* Parcel Callsign Badge */}
                  <g transform={`translate(${cx}, ${cy})`} className="pointer-events-none">
                    <rect
                      x="-25"
                      y="-8"
                      width="50"
                      height="16"
                      rx="4"
                      className={`${style.labelBg} border transition-colors`}
                    />
                    <text
                      y="3.5"
                      textAnchor="middle"
                      fontSize="8"
                      fontFamily="monospace"
                      fontWeight="bold"
                      fill="#ffffff"
                      className="select-none"
                    >
                      {field.village_code.split("-").slice(-2).join("-")}
                    </text>
                  </g>

                  {/* Acreage Pill Tag */}
                  <g transform={`translate(${cx}, ${cy + 13})`} className="pointer-events-none">
                    <text
                      y="0"
                      textAnchor="middle"
                      fontSize="7.5"
                      fontFamily="sans-serif"
                      fill="#94a3b8"
                      className="font-medium select-none"
                    >
                      {field.area_acres} ac {isFire ? "🔥" : isFastDispatched ? "⚡" : ""}
                    </text>
                  </g>
                </g>
              );
            })}

            {/* Machinery Fleet Markers */}
            {machineAssignments.map((a) => {
              const mx = projectX(a.machine.current_lon);
              const my = projectY(a.machine.current_lat);
              const isSelected = selectedMachineId === a.machine.id;
              const isInUse = a.isInUse;

              return (
                <g
                  key={`marker-${a.machine.id}`}
                  transform={`translate(${mx}, ${my})`}
                  className="cursor-pointer"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedMachineId(a.machine.id);
                    if (a.targetField) setSelectedFieldId(a.targetField.id);
                  }}
                >
                  {/* Active Radar Pulse Ring for In-Use Machines */}
                  {isInUse && (
                    <circle
                      r="18"
                      fill="none"
                      stroke="#06b6d4"
                      strokeWidth="1.5"
                      className="animate-radar-ring"
                    />
                  )}

                  {/* Outer Contrast Rim */}
                  <circle
                    r={isSelected ? 14 : 11}
                    fill="#020617"
                    stroke={isSelected ? "#38bdf8" : isInUse ? "#0891b2" : "#059669"}
                    strokeWidth={isSelected ? 2.5 : 1.8}
                  />

                  {/* Core Status Indicator */}
                  <circle
                    r={isSelected ? 9 : 7}
                    fill={isInUse ? "#06b6d4" : "#10b981"}
                  />

                  {/* Tractor Icon Silhouette Center */}
                  <text
                    y="2.5"
                    textAnchor="middle"
                    fontSize={isSelected ? "9" : "7.5"}
                    fill="#ffffff"
                    fontWeight="bold"
                    className="select-none pointer-events-none"
                  >
                    🚜
                  </text>

                  {/* Machine Callsign Tag */}
                  <g transform="translate(0, -17)" className="pointer-events-none">
                    <rect
                      x="-26"
                      y="-7"
                      width="52"
                      height="14"
                      rx="3"
                      fill="#0f172a"
                      stroke={isSelected ? "#38bdf8" : "#334155"}
                      strokeWidth="1"
                    />
                    <text
                      y="3.5"
                      textAnchor="middle"
                      fontSize="7.5"
                      fontFamily="monospace"
                      fontWeight="bold"
                      fill={isInUse ? "#67e8f9" : "#a7f3d0"}
                      className="select-none"
                    >
                      {a.callsign}
                    </text>
                  </g>
                </g>
              );
            })}
          </g>
        </svg>

        {/* Floating Zoom & GIS Controls */}
        <div className="absolute top-4 right-4 flex flex-col gap-1.5 bg-paper border border-ink/20 p-1 shadow-md z-20 font-mono">
          <button
            onClick={handleZoomIn}
            title="Zoom In"
            className="w-7 h-7 bg-paper-subtle hover:bg-ink hover:text-paper text-ink border border-ink/10 flex items-center justify-center font-bold text-sm transition"
          >
            +
          </button>
          <button
            onClick={handleZoomOut}
            title="Zoom Out"
            className="w-7 h-7 bg-paper-subtle hover:bg-ink hover:text-paper text-ink border border-ink/10 flex items-center justify-center font-bold text-sm transition"
          >
            −
          </button>
          <button
            onClick={handleResetView}
            title="Reset View"
            className="w-7 h-7 bg-paper-subtle hover:bg-ink hover:text-paper text-ink border border-ink/10 flex items-center justify-center text-xs transition"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
          <div className="border-t border-ink/10 pt-1 mt-0.5 text-center font-mono text-[9px] text-wild-muted">
            {Math.round(zoom * 100)}%
          </div>
        </div>

        {/* Legend Overlay at Bottom Right */}
        <div className="absolute bottom-3 right-4 bg-paper border border-ink/20 px-3 py-2 text-[10px] font-mono shadow-sm flex items-center gap-4 text-ink z-10">
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 bg-neon border border-ink inline-block" />
            <span>Cleared (In-Situ)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 bg-straw border border-ink inline-block" />
            <span>Residue Present</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 bg-wild-red border border-ink inline-block animate-pulse" />
            <span className="text-wild-red font-bold">FIRMS Fire Alert</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 bg-ink text-neon border border-neon inline-block" />
            <span>Active Machine</span>
          </div>
        </div>

        {/* Interactive Parcel Inspector HUD Drawer (Bottom Left) */}
        {selectedField && (
          <div className="absolute bottom-3 left-4 bg-paper border border-ink p-4 w-80 text-xs shadow-2xl z-30 font-mono text-ink">
            <div className="flex items-center justify-between pb-2 border-b border-ink/10">
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4 text-ink" />
                <span className="font-bold text-ink text-sm uppercase">PARCEL {selectedField.village_code}</span>
              </div>
              <button
                onClick={() => setSelectedFieldId(null)}
                className="text-wild-muted hover:text-ink p-1 hover:bg-ink/5 transition"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-3 space-y-2 text-ink">
              <div className="grid grid-cols-2 gap-2 bg-paper-subtle p-2 border border-ink/10 text-xs">
                <div>
                  <span className="text-[9px] text-wild-muted block uppercase font-bold">Cadastre Acreage</span>
                  <span className="font-bold text-ink">{selectedField.area_acres} acres</span>
                </div>
                <div>
                  <span className="text-[9px] text-wild-muted block uppercase font-bold">Estimated Straw</span>
                  <span className="font-bold text-ink">
                    {(selectedField.area_acres * 2.4).toFixed(1)} t dry stubble
                  </span>
                </div>
              </div>

              <div className="flex justify-between items-center py-1 border-b border-ink/10 text-[11px]">
                <span className="text-wild-muted uppercase">Harvest Status:</span>
                <span
                  className={`font-bold px-2 py-0.5 text-[10px] uppercase border ${
                    selectedField.state === "cleared"
                      ? "bg-neon text-ink border-ink"
                      : selectedField.state === "burn_detected"
                      ? "bg-wild-red text-white border-wild-red animate-pulse"
                      : "bg-straw text-ink border-ink"
                  }`}
                >
                  {selectedField.state.replace(/_/g, " ")}
                </span>
              </div>

              <div className="flex justify-between items-center py-1 border-b border-ink/10 text-[11px]">
                <span className="text-wild-muted uppercase">Burn Risk Index:</span>
                <div className="flex items-center gap-2">
                  <div className="w-16 h-2 bg-paper-subtle border border-ink/20 overflow-hidden">
                    <div
                      className={`h-full ${
                        selectedField.burn_risk_score > 0.7
                          ? "bg-wild-red"
                          : selectedField.burn_risk_score > 0.3
                          ? "bg-straw"
                          : "bg-neon"
                      }`}
                      style={{ width: `${Math.round(selectedField.burn_risk_score * 100)}%` }}
                    />
                  </div>
                  <span className="font-mono font-bold text-ink">
                    {Math.round(selectedField.burn_risk_score * 100)}%
                  </span>
                </div>
              </div>

              <div className="flex justify-between items-center py-1 border-b border-ink/10 text-[11px]">
                <span className="text-wild-muted uppercase">Satellite Sensor:</span>
                <span className="font-mono font-bold text-ink">
                  Sentinel-2 L2A ({Math.round(selectedField.state_confidence * 100)}%)
                </span>
              </div>

              <div className="flex justify-between items-center py-1 border-b border-ink/10 text-[11px]">
                <span className="text-wild-muted uppercase">Farmgate GPS:</span>
                <span className="font-mono text-wild-blue-gray">
                  {selectedField.center_lat.toFixed(4)}°N, {selectedField.center_lon.toFixed(4)}°E
                </span>
              </div>

              {/* Machinery Dispatch Status or 1-Click Fast Dispatch */}
              <div className="pt-2">
                {incomingMachineForSelectedField ? (
                  <div className="bg-paper-subtle border border-ink p-2 space-y-1">
                    <div className="flex items-center justify-between text-ink font-bold text-[10px] uppercase">
                      <span className="flex items-center gap-1">
                        <Tractor className="h-3.5 w-3.5 text-neon-lime" />
                        Dispatched: {incomingMachineForSelectedField.callsign}
                      </span>
                      <span className="text-wild-red font-mono">
                        {incomingMachineForSelectedField.etaMinutes}m ETA
                      </span>
                    </div>
                    <div className="text-[10px] text-wild-muted flex justify-between">
                      <span>Operator: {incomingMachineForSelectedField.machine.operator_name}</span>
                      <span>{incomingMachineForSelectedField.distanceKm} km route</span>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => {
                      setFastDispatchedIds((prev) => ({ ...prev, [selectedField.id]: true }));
                    }}
                    className={`w-full py-2 border font-bold text-xs uppercase flex items-center justify-center gap-1.5 transition ${
                      fastDispatchedIds[selectedField.id]
                        ? "bg-neon text-ink border-ink"
                        : "bg-ink hover:bg-neon hover:text-ink text-paper border-ink"
                    }`}
                  >
                    <Zap className="h-3.5 w-3.5" />
                    {fastDispatchedIds[selectedField.id]
                      ? "DISPATCHED: SEEDER EN ROUTE"
                      : "FAST DISPATCH NEAREST BALER"}
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Selected Machine Telemetry HUD Overlay (Top Left) */}
        {selectedMachine && !selectedField && (
          <div className="absolute top-4 left-4 bg-paper border border-ink p-3.5 w-76 text-xs shadow-2xl z-30 font-mono text-ink">
            <div className="flex items-center justify-between pb-2 border-b border-ink/10">
              <div className="flex items-center gap-2">
                <Tractor className="h-4 w-4 text-neon-lime" />
                <span className="font-bold text-ink uppercase">{selectedMachine.callsign}</span>
              </div>
              <button
                onClick={() => setSelectedMachineId(null)}
                className="text-wild-muted hover:text-ink p-1 hover:bg-ink/5"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-2.5 space-y-1.5 text-ink">
              <div className="flex justify-between">
                <span className="text-wild-muted uppercase text-[10px]">Machine Type:</span>
                <span className="font-bold text-ink capitalize">
                  {selectedMachine.machine.machine_type.replace(/_/g, " ")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-wild-muted uppercase text-[10px]">Operator:</span>
                <span className="font-bold text-ink">
                  {selectedMachine.machine.operator_name || "Unassigned"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-wild-muted uppercase text-[10px]">Daily Cap:</span>
                <span className="font-mono font-bold text-ink">
                  {selectedMachine.machine.capacity_acres_per_day} ac/day
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-wild-muted uppercase text-[10px]">Status:</span>
                <span
                  className={`font-bold uppercase text-[10px] px-2 py-0.5 border ${
                    selectedMachine.isInUse
                      ? "bg-neon text-ink border-ink"
                      : "bg-paper-subtle text-ink border-ink/20"
                  }`}
                >
                  {selectedMachine.machine.status.replace(/_/g, " ")}
                </span>
              </div>
              {selectedMachine.targetField && (
                <div className="mt-2 pt-2 border-t border-ink/10 bg-paper-subtle p-2 text-[11px]">
                  <span className="text-wild-muted block text-[9px] uppercase font-bold">
                    Assigned Destination:
                  </span>
                  <div className="flex justify-between items-center text-ink font-bold">
                    <span>Parcel {selectedMachine.targetField.village_code}</span>
                    <span className="text-wild-red font-mono text-[10px]">
                      {selectedMachine.etaMinutes}m ETA
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
