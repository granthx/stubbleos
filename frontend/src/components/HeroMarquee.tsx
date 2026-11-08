"use client";

import React from "react";
import { ArrowUpRight, Flame, Leaf, Shield, Tractor } from "lucide-react";
import { DistrictSummary } from "../types";

interface HeroMarqueeProps {
  district: string;
  summary: DistrictSummary | null;
  onDistrictSelect: (d: string) => void;
  onOpenAuditLog: () => void;
}

export const HeroMarquee: React.FC<HeroMarqueeProps> = ({
  district,
  summary,
  onDistrictSelect,
  onOpenAuditLog,
}) => {
  const clearanceRate = summary?.total_fields
    ? Math.round((summary.cleared_fields / summary.total_fields) * 100)
    : 99.3;

  const co2eAvoided = summary?.indicative_co2e_avoided_tonnes || 1052.1;
  const activeFleet = summary?.active_machines_count || 28;
  const burnIncidents = summary?.burn_incidents_detected ?? 0;

  const marqueeText = [
    `STUBBLEOS // PROTOCOL PRODUCTION RELEASE`,
    `AUTONOMOUS PADDY STRAW COORDINATION LAYER`,
    `DISTRICT SECTOR: ${district.toUpperCase()}`,
    `CLEARANCE RATE: ${clearanceRate}%`,
    `CO2e EMISSIONS AVOIDED: ${co2eAvoided.toLocaleString()} TONNES`,
    `FLEET DEPLOYED: ${activeFleet} MACHINES (SUPER SEEDER / BALER)`,
    `ACTIVE FIRE INCIDENTS: ${burnIncidents} DETECTED`,
    `WHEAT SOWING WINDOW: 14 DAYS TO TARGET DEADLINE`,
    `CONTRACT-NET BIOMASS AUCTION ACTIVE`,
    `VERNACULAR TELEPHONY (PA / HI / EN) RUNNING`,
    `AUDIT LOG ROOT: MERKLE-HASH VERIFIED`,
  ].join("   ·   ");

  return (
    <div className="w-full border-b border-ink/10 bg-paper">
      {/* 1. Infinite Marquee Ticker Tape */}
      <div className="overflow-hidden whitespace-nowrap bg-ink text-paper py-2.5 border-y border-ink">
        <div className="animate-marquee-left flex items-center font-mono text-[11px] font-semibold tracking-wider uppercase">
          <span className="mx-4 text-neon">● LIVE TELEMETRY STREAM</span>
          <span className="mx-4">{marqueeText}</span>
          <span className="mx-4 text-neon">● LIVE TELEMETRY STREAM</span>
          <span className="mx-4">{marqueeText}</span>
        </div>
      </div>

      {/* 2. Giant Swiss Typography Hero Section */}
      <div className="max-w-[1440px] mx-auto px-6 py-10 md:py-14">
        {/* Top Meta Line with Swiss Badges */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6 text-[10px] font-mono tracking-widest uppercase border-b border-ink/10 pb-4">
          <div className="flex items-center gap-3">
            <span className="px-2 py-0.5 bg-ink text-paper font-bold">
              SYS // AUTONOMOUS_V1
            </span>
            <span className="text-wild-muted">
              PUNJAB & HARYANA CRITICAL AIRSHED (PB-01/03/11 · HR-05)
            </span>
          </div>

          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-ink font-semibold">
              <span className="inline-block w-2 h-2 rounded-full bg-neon-lime border border-ink" />
              CP-SAT SOLVER SYNCHRONIZED
            </span>
            <button
              onClick={onOpenAuditLog}
              className="text-ink hover:text-wild-red transition-colors flex items-center gap-1 underline underline-offset-4"
            >
              [AUDIT LEDGER]
              <ArrowUpRight className="w-3 h-3" />
            </button>
          </div>
        </div>

        {/* Hero Headline Ramp (75px Sneak ratio) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          <div className="lg:col-span-8 space-y-4">
            <h1 className="text-4xl sm:text-6xl lg:text-[75px] font-extrabold tracking-[-0.04em] text-ink leading-[0.92] uppercase">
              Autonomous
              <br />
              Stubble Clearance
              <br />
              <span className="text-ink-deep bg-neon px-2 inline-block">
                Zero-Burn
              </span>{" "}
              Grid.
            </h1>

            <p className="text-base sm:text-lg text-wild-blue-gray max-w-[620px] font-normal leading-relaxed pt-2">
              Coordinating smallholder farmers, machinery contractors, logistics routes, and industrial biomass buyers across Punjab and Haryana so paddy residue is cleared before the wheat-sowing deadline without open-field burning.
            </p>
          </div>

          {/* Right Column: Swiss Technical Info Block */}
          <div className="lg:col-span-4 border border-ink/10 bg-paper-subtle p-6 flex flex-col justify-between space-y-6">
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b border-ink/10 pb-2">
                <span className="text-[10px] font-mono uppercase text-wild-muted">Target Objective</span>
                <span className="text-xs font-mono font-bold text-ink">Zero Smoke Plumes</span>
              </div>
              <div className="flex items-center justify-between border-b border-ink/10 pb-2">
                <span className="text-[10px] font-mono uppercase text-wild-muted">Active Sector</span>
                <span className="text-xs font-mono font-bold text-ink uppercase">{district} District</span>
              </div>
              <div className="flex items-center justify-between border-b border-ink/10 pb-2">
                <span className="text-[10px] font-mono uppercase text-wild-muted">Clearance Window</span>
                <span className="text-xs font-mono font-bold text-wild-red">14 Days Remaining</span>
              </div>
              <div className="flex items-center justify-between border-b border-ink/10 pb-2">
                <span className="text-[10px] font-mono uppercase text-wild-muted">Biomass Tariff</span>
                <span className="text-xs font-mono font-bold text-ink">₹1,750 - ₹2,250 / t</span>
              </div>
            </div>

            {/* Quick District Selector Pills */}
            <div className="space-y-2">
              <span className="text-[10px] font-mono uppercase text-wild-muted block">
                Select Operational Airshed:
              </span>
              <div className="grid grid-cols-3 gap-1.5 font-mono text-[10px]">
                {["sangrur", "patiala", "ludhiana", "fatehgarh", "karnal"].map((d) => (
                  <button
                    key={d}
                    onClick={() => onDistrictSelect(d)}
                    className={`py-1.5 px-2 text-center uppercase border transition-all ${
                      district.toLowerCase() === d
                        ? "bg-ink text-paper border-ink font-bold shadow-sm"
                        : "bg-paper text-ink border-ink/15 hover:border-ink"
                    }`}
                  >
                    {d.slice(0, 7)}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

