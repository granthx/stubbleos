"use client";

import React, { useEffect, useRef, useState } from "react";
import { Activity, Eye, Layers, Sparkles } from "lucide-react";

interface PixelWaveProps {
  district?: string;
  clearedRate?: number;
  burnAlerts?: number;
}

type WaveMode = "stubble_density" | "fleet_flow" | "thermal_anomaly";

export const PixelArtWave: React.FC<PixelWaveProps> = ({
  district = "sangrur",
  clearedRate = 99.3,
  burnAlerts = 0,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [mode, setMode] = useState<WaveMode>("stubble_density");
  const [isPaused, setIsPaused] = useState(false);
  const [waveSpeed, setWaveSpeed] = useState(1);
  const [stats, setStats] = useState({
    activeCells: 1764,
    scanVariance: "0.042",
    fluxRate: "1.24 kHz",
  });

  const mouseRef = useRef({ x: -1000, y: -1000, active: false });
  const animFrameRef = useRef<number | null>(null);
  const timeRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = (canvas.width = canvas.parentElement?.clientWidth || 960);
    let height = (canvas.height = 280);

    const handleResize = () => {
      if (!canvas || !canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = 280;
    };
    window.addEventListener("resize", handleResize);

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
        active: true,
      };
    };

    const handleMouseLeave = () => {
      mouseRef.current.active = false;
    };

    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("mouseleave", handleMouseLeave);

    const CELL_SIZE = 14; // Wild 14px grid scale!
    const GAP = 2;
    const cols = Math.ceil(width / (CELL_SIZE + GAP));
    const rows = Math.ceil(height / (CELL_SIZE + GAP));

    setStats((prev) => ({ ...prev, activeCells: cols * rows }));

    const render = () => {
      if (!isPaused) {
        timeRef.current += 0.035 * waveSpeed;
      }
      const t = timeRef.current;

      ctx.fillStyle = "#0A0A0A";
      ctx.fillRect(0, 0, width, height);

      // Fine Swiss coordinate grid background lines
      ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
      ctx.lineWidth = 1;
      for (let x = 0; x < width; x += CELL_SIZE * 4) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 0; y < height; y += CELL_SIZE * 4) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      const mouse = mouseRef.current;

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const px = c * (CELL_SIZE + GAP);
          const py = r * (CELL_SIZE + GAP);

          // Normalized spatial parameters
          const nx = c / cols;
          const ny = r / rows;

          // Multi-frequency generative wave harmonic
          const primaryWave = Math.sin(nx * 9 + t) * Math.cos(ny * 7 - t * 0.8);
          const secondaryWave = Math.sin(nx * 18 - t * 1.4) * 0.4;
          const microNoise = Math.sin((nx + ny) * 28 + t * 2) * 0.15;

          let waveVal = (primaryWave + secondaryWave + microNoise + 1.55) / 3.1; // 0 to 1

          // Interactive mouse perturbation
          if (mouse.active) {
            const dx = px - mouse.x;
            const dy = py - mouse.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < 140) {
              const ripple = Math.sin((dist / 140) * Math.PI * 4 - t * 6) * (1 - dist / 140);
              waveVal = Math.min(1, Math.max(0, waveVal + ripple * 0.5));
            }
          }

          // Dynamic Pixel coloring based on Mode & Wild Design Tokens
          let cellFill = "#1E2544";
          let borderFill = "transparent";

          if (mode === "stubble_density") {
            // Straw yellow (#f6d36d) to ink (#1e2544) to neon lime (#dcfc04)
            if (waveVal > 0.78) {
              cellFill = "#DCFC04"; // High biomass / cleared peak
            } else if (waveVal > 0.58) {
              cellFill = "#F6D36D"; // Straw dry biomass
            } else if (waveVal > 0.38) {
              cellFill = "#8B8B8B"; // Stubble residue field
            } else if (waveVal > 0.2) {
              cellFill = "#1E2544"; // Deep dark loam
            } else {
              cellFill = "#111420"; // Background void
            }
          } else if (mode === "fleet_flow") {
            // Neon Lime (#d8ff00) sweeps representing Super Seeders & Balers
            if (waveVal > 0.72) {
              cellFill = "#D8FF00";
              borderFill = "rgba(216, 255, 0, 0.4)";
            } else if (waveVal > 0.45) {
              cellFill = "#1E2544";
            } else {
              cellFill = "#121626";
            }
          } else if (mode === "thermal_anomaly") {
            // Thermal infrared: Alert red (#e0492a) for hot spots
            if (waveVal > 0.82) {
              cellFill = "#E0492A"; // Thermal hotspot alert
            } else if (waveVal > 0.6) {
              cellFill = "#7A2012";
            } else if (waveVal > 0.35) {
              cellFill = "#1E2544";
            } else {
              cellFill = "#0D101C";
            }
          }

          // Pixel size breathing dynamically with wave amplitude
          const scale = 0.65 + waveVal * 0.35;
          const drawSize = (CELL_SIZE - 1) * scale;
          const offset = (CELL_SIZE - drawSize) / 2;

          ctx.fillStyle = cellFill;
          // Clean 0px / 2px Swiss pixel rects
          ctx.fillRect(px + offset, py + offset, drawSize, drawSize);

          if (borderFill !== "transparent") {
            ctx.strokeStyle = borderFill;
            ctx.strokeRect(px + offset, py + offset, drawSize, drawSize);
          }
        }
      }

      animFrameRef.current = requestAnimationFrame(render);
    };

    animFrameRef.current = requestAnimationFrame(render);

    return () => {
      window.removeEventListener("resize", handleResize);
      canvas.removeEventListener("mousemove", handleMouseMove);
      canvas.removeEventListener("mouseleave", handleMouseLeave);
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [mode, isPaused, waveSpeed]);

  return (
    <div className="w-full bg-ink border border-ink/20 text-white rounded-none md:rounded-md overflow-hidden relative">
      {/* Top Header Bar of the Canvas */}
      <div className="border-b border-white/10 px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 bg-black/60 backdrop-blur">
        <div className="flex items-center gap-3">
          <span className="flex h-2 w-2 rounded-none bg-neon animate-pulse" />
          <div className="flex items-center gap-2">
            <span className="font-swiss-mono text-[10px] text-neon font-bold tracking-widest">
              GENERATIVE WAVEFORM // RESIDUE MATRIX
            </span>
            <span className="text-[10px] text-white/40 font-mono">
              [GRID 14px · {stats.activeCells} CELLS]
            </span>
          </div>
        </div>

        {/* Mode Selector */}
        <div className="flex items-center gap-1 bg-white/5 border border-white/10 p-0.5 rounded-none text-[10px] font-mono">
          <button
            onClick={() => setMode("stubble_density")}
            className={`px-2.5 py-1 uppercase transition-colors ${
              mode === "stubble_density"
                ? "bg-neon text-ink font-bold"
                : "text-white/70 hover:text-white"
            }`}
          >
            01 Residue Density
          </button>
          <button
            onClick={() => setMode("fleet_flow")}
            className={`px-2.5 py-1 uppercase transition-colors ${
              mode === "fleet_flow"
                ? "bg-neon text-ink font-bold"
                : "text-white/70 hover:text-white"
            }`}
          >
            02 Machinery Flow
          </button>
          <button
            onClick={() => setMode("thermal_anomaly")}
            className={`px-2.5 py-1 uppercase transition-colors ${
              mode === "thermal_anomaly"
                ? "bg-wild-red text-white font-bold"
                : "text-white/70 hover:text-white"
            }`}
          >
            03 Thermal VIIRS
          </button>
        </div>
      </div>

      {/* Main Pixel Canvas */}
      <div className="relative h-[240px] md:h-[280px] w-full cursor-crosshair">
        <canvas ref={canvasRef} className="w-full h-full block" />

        {/* Watermark Swiss Coordinate Overlay */}
        <div className="absolute bottom-3 left-4 pointer-events-none flex items-center gap-4 text-[10px] font-mono text-white/50">
          <div>
            SECTOR: <span className="text-white uppercase font-bold">{district}</span>
          </div>
          <div>
            CLEARANCE RATE: <span className="text-neon font-bold">{clearedRate}%</span>
          </div>
          <div>
            THERMAL ALERTS: <span className={burnAlerts > 0 ? "text-wild-red font-bold" : "text-white"}>{burnAlerts}</span>
          </div>
          <div className="hidden md:block">
            SATELLITE SYNC: <span className="text-white/80">SENTINEL-2 / MODIS</span>
          </div>
        </div>

        {/* Quick controls */}
        <div className="absolute bottom-3 right-4 flex items-center gap-2">
          <button
            onClick={() => setIsPaused(!isPaused)}
            className="px-2 py-0.5 bg-white/10 hover:bg-white/20 text-white font-mono text-[9px] uppercase tracking-wider border border-white/20"
          >
            {isPaused ? "RESUME" : "FREEZE"}
          </button>
          <button
            onClick={() => setWaveSpeed(waveSpeed === 1 ? 2 : waveSpeed === 2 ? 0.5 : 1)}
            className="px-2 py-0.5 bg-white/10 hover:bg-white/20 text-white font-mono text-[9px] uppercase tracking-wider border border-white/20"
          >
            SPEED: {waveSpeed}x
          </button>
        </div>
      </div>

      {/* Bottom Technical Strip */}
      <div className="border-t border-white/10 px-4 py-2 bg-black/80 flex flex-wrap items-center justify-between text-[10px] font-mono text-white/60">
        <div>
          AUTONOMOUS DISCRETE-EVENT SIMULATION & HARVEST DYNAMICS · 14-DAY COUNTDOWN TO RABI SEEDING
        </div>
        <div className="flex items-center gap-3">
          <span>LATENCY: 18.4ms</span>
          <span>·</span>
          <span>DISPATCH SOLVER: CP-SAT v9.8</span>
        </div>
      </div>
    </div>
  );
};

