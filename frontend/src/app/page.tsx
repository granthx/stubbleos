"use client";

import React, { useEffect, useState } from "react";
import { Header } from "../components/Header";
import { HeroMarquee } from "../components/HeroMarquee";
import { PixelArtWave } from "../components/PixelArtWave";
import { KpiCards } from "../components/KpiCards";
import { DistrictMap } from "../components/DistrictMap";
import { MachineDispatchTable } from "../components/MachineDispatchTable";
import { ApprovalQueue } from "../components/ApprovalQueue";
import { BiomassMarketplace } from "../components/BiomassMarketplace";
import { FarmerDialogueFeed } from "../components/FarmerDialogueFeed";
import { AuditModal } from "../components/AuditModal";
import {
  fetchApprovals,
  fetchDistrictSummary,
  fetchFields,
  fetchMachines,
  resolveApproval,
} from "../lib/api";
import { ApprovalItem, DistrictSummary, FieldInfo, MachineInfo } from "../types";

export default function DashboardPage() {
  const [district, setDistrict] = useState("sangrur");
  const [summary, setSummary] = useState<DistrictSummary | null>(null);
  const [fields, setFields] = useState<FieldInfo[]>([]);
  const [machines, setMachines] = useState<MachineInfo[]>([]);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [isAuditOpen, setIsAuditOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isCancelled = false;

    const run = async () => {
      try {
        const [sumData, fldData, machData, appData] = await Promise.all([
          fetchDistrictSummary(district),
          fetchFields(district),
          fetchMachines(district),
          fetchApprovals(district),
        ]);
        if (!isCancelled) {
          setSummary(sumData);
          setFields(fldData);
          setMachines(machData);
          setApprovals(appData);
          setLoading(false);
        }
      } catch (e) {
        console.error("Failed to load dashboard data", e);
      }
    };

    run();
    const interval = setInterval(run, 15000);
    return () => {
      isCancelled = true;
      clearInterval(interval);
    };
  }, [district]);

  const handleResolveApproval = async (id: string, decision: "approved" | "rejected") => {
    await resolveApproval(id, decision);
    setApprovals((prev) =>
      prev.map((a) =>
        a.id === id ? { ...a, status: decision === "approved" ? "approved" : "rejected" } : a
      )
    );
  };

  return (
    <div className="min-h-screen bg-paper text-ink flex flex-col font-sans selection:bg-neon selection:text-ink">
      {/* 1. Swiss Header */}
      <Header
        district={district}
        onDistrictChange={(d) => setDistrict(d)}
        burnAlerts={summary?.burn_incidents_detected || 0}
        onOpenAudit={() => setIsAuditOpen(true)}
      />

      {/* 2. Marquee Hero (Wild Macrostructure) */}
      <HeroMarquee
        district={district}
        summary={summary}
        onDistrictSelect={(d) => setDistrict(d)}
        onOpenAuditLog={() => setIsAuditOpen(true)}
      />

      {/* 3. Main Command Dashboard Grid */}
      <main className="flex-1 px-4 sm:px-6 py-8 max-w-[1440px] mx-auto w-full space-y-8">
        {/* Generative Pixel-Art Wave Canvas */}
        <section className="space-y-2">
          <div className="flex items-center justify-between text-[10px] font-mono uppercase text-wild-muted px-1">
            <span>[GENERATIVE MULTISPECTRAL WAVEFORM]</span>
            <span>AUTONOMOUS FIELD CANOPY TELEMETRY · 14px SATELLITE RESOLUTION</span>
          </div>
          <PixelArtWave
            district={district}
            clearedRate={summary?.total_fields ? Math.round((summary.cleared_fields / summary.total_fields) * 100) : 99.3}
            burnAlerts={summary?.burn_incidents_detected || 0}
          />
        </section>

        {/* KPI Metric Blocks */}
        {summary && <KpiCards summary={summary} />}

        {/* Tactical Cadastre Map & Command Feed */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <div className="lg:col-span-8">
            <DistrictMap fields={fields} machines={machines} district={district} />
          </div>

          <div className="lg:col-span-4 flex flex-col gap-6">
            <ApprovalQueue approvals={approvals} onResolve={handleResolveApproval} />
            <FarmerDialogueFeed district={district} />
          </div>
        </div>

        {/* Lower Fleet Dispatch & Biomass Marketplace */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <div className="lg:col-span-8">
            <MachineDispatchTable machines={machines} />
          </div>

          <div className="lg:col-span-4">
            <BiomassMarketplace district={district} />
          </div>
        </div>
      </main>

      {/* 4. Swiss Technical Footer */}
      <footer className="border-t border-ink/10 bg-paper-subtle py-8 px-6 mt-12 text-ink">
        <div className="max-w-[1440px] mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-6 font-mono text-xs">
          <div className="space-y-1">
            <div className="flex items-center gap-2 font-bold uppercase tracking-wider">
              <span>STUBBLEOS</span>
              <span>//</span>
              <span>PRODUCTION RELEASE</span>
            </div>
            <p className="text-wild-muted text-[11px]">
              Autonomous Crop Residue Coordination Layer for Punjab & Haryana · Indicative impact records (not registry-verified)
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-[11px] text-wild-blue-gray">
            <button
              onClick={() => setIsAuditOpen(true)}
              className="hover:text-ink underline underline-offset-4"
            >
              [INSPECT MRV MERKLE CHAIN]
            </button>
            <span>·</span>
            <span>SIMULATION MULTI-SEED RUNS</span>
            <span>·</span>
            <span>CP-SAT VRP SOLVER</span>
            <span>·</span>
            <span className="text-ink font-bold">ZERO OPEN-BURNING TARGET</span>
          </div>
        </div>
      </footer>

      {/* 5. Cryptographic MRV Audit Inspector Modal */}
      <AuditModal
        isOpen={isAuditOpen}
        onClose={() => setIsAuditOpen(false)}
        district={district}
      />
    </div>
  );
}
