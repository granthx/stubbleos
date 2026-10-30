"use client";

import React, { useEffect, useState } from "react";
import { Header } from "../components/Header";
import { KpiCards } from "../components/KpiCards";
import { DistrictMap } from "../components/DistrictMap";
import { MachineDispatchTable } from "../components/MachineDispatchTable";
import { ApprovalQueue } from "../components/ApprovalQueue";
import { BiomassMarketplace } from "../components/BiomassMarketplace";
import { FarmerDialogueFeed } from "../components/FarmerDialogueFeed";
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
  const [loading, setLoading] = useState(true);

  const loadData = async (targetDistrict: string) => {
    setLoading(true);
    try {
      const [sumData, fldData, machData, appData] = await Promise.all([
        fetchDistrictSummary(targetDistrict),
        fetchFields(targetDistrict),
        fetchMachines(targetDistrict),
        fetchApprovals(targetDistrict),
      ]);
      setSummary(sumData);
      setFields(fldData);
      setMachines(machData);
      setApprovals(appData);
    } catch (e) {
      console.error("Failed to load dashboard data", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(district);
    const interval = setInterval(() => loadData(district), 15000);
    return () => clearInterval(interval);
  }, [district]);

  const handleResolveApproval = async (id: string, decision: "approved" | "rejected") => {
    await resolveApproval(id, decision);
    setApprovals((prev) =>
      prev.map((a) => (a.id === id ? { ...a, status: decision === "approved" ? "approved" : "rejected" } : a))
    );
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      <Header
        district={district}
        onDistrictChange={(d) => setDistrict(d)}
        burnAlerts={summary?.burn_incidents_detected || 0}
      />

      <main className="flex-1 p-6 space-y-6 max-w-[1600px] mx-auto w-full">
        {/* KPI Stat Cards */}
        {summary && <KpiCards summary={summary} />}

        {/* Central Map & Fleet Section */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <DistrictMap fields={fields} machines={machines} district={district} />
          </div>
          <div className="flex flex-col gap-6">
            <ApprovalQueue approvals={approvals} onResolve={handleResolveApproval} />
            <FarmerDialogueFeed />
          </div>
        </div>

        {/* Bottom Section: Fleet Table & Biomass Marketplace */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <MachineDispatchTable machines={machines} />
          </div>
          <div>
            <BiomassMarketplace />
          </div>
        </div>
      </main>

      <footer className="border-t border-slate-900 bg-slate-950/80 px-6 py-4 text-center text-xs text-slate-500">
        StubbleOS Phase 7 · Multi-Agent Autonomous Coordination Layer · Indicative impact records (not registry-verified)
      </footer>
    </div>
  );
}

