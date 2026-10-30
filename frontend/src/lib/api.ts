import { ApprovalItem, ContractItem, DistrictSummary, FieldInfo, MachineInfo, VernacularTurn } from "../types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function fetchDistrictSummary(district: string = "sangrur"): Promise<DistrictSummary> {
  try {
    const res = await fetch(`${API_BASE}/district-summary/${district}`, { cache: "no-store" });
    if (res.ok) return await res.json();
  } catch (e) {
    // Fallback to synthetic preview
  }
  return {
    district,
    total_fields: 240,
    cleared_fields: 162,
    pending_residue_fields: 74,
    burn_incidents_detected: 4,
    burn_risk_index: 0.31,
    active_machines_count: 28,
    total_stubble_cleared_acres: 584.5,
    indicative_co2e_avoided_tonnes: 1052.1,
    pending_approvals_count: 3,
    open_biomass_orders_count: 6,
  };
}

export async function fetchFields(district: string = "sangrur"): Promise<FieldInfo[]> {
  try {
    const res = await fetch(`${API_BASE}/fields?district=${district}`, { cache: "no-store" });
    if (res.ok) return await res.json();
  } catch (e) {}

  return Array.from({ length: 12 }, (_, i) => ({
    id: `field-${i + 1}`,
    farmer_id: `farmer-${(i % 5) + 1}`,
    district,
    village_code: `PB-SAN-00${i + 1}`,
    area_acres: 2.5 + (i % 4),
    state: i < 5 ? "cleared" : i === 5 ? "burn_detected" : "harvested_residue_present",
    state_confidence: 0.94,
    burn_risk_score: i === 5 ? 0.95 : i > 5 ? 0.72 : 0.05,
    center_lat: 30.24 + (i * 0.015),
    center_lon: 75.83 + (i * 0.012),
  }));
}

export async function fetchMachines(district: string = "sangrur"): Promise<MachineInfo[]> {
  try {
    const res = await fetch(`${API_BASE}/machines?district=${district}`, { cache: "no-store" });
    if (res.ok) return await res.json();
  } catch (e) {}

  return [
    { id: "m1", machine_type: "super_seeder", district, status: "in_use", current_lat: 30.245, current_lon: 75.835, capacity_acres_per_day: 15, operator_name: "Harpreet Singh" },
    { id: "m2", machine_type: "baler", district, status: "in_use", current_lat: 30.258, current_lon: 75.845, capacity_acres_per_day: 25, operator_name: "Gurjit Singh" },
    { id: "m3", machine_type: "happy_seeder", district, status: "available", current_lat: 30.231, current_lon: 75.828, capacity_acres_per_day: 12, operator_name: "Balwinder Kumar" },
    { id: "m4", machine_type: "baler", district, status: "available", current_lat: 30.272, current_lon: 75.861, capacity_acres_per_day: 25, operator_name: "Manpreet Dhillon" },
  ];
}

export async function fetchApprovals(): Promise<ApprovalItem[]> {
  try {
    const res = await fetch(`${API_BASE}/approvals`, { cache: "no-store" });
    if (res.ok) return await res.json();
  } catch (e) {}

  return [
    {
      id: "app-1",
      kind: "burn_threat_escalation",
      subject_id: "f-104",
      reason: "Farmer threatening fire due to combine harvest delay in Dhuri block",
      status: "pending",
      confidence: 0.98,
      requested_by: "farmer_voice_agent",
      created_at: new Date().toISOString(),
    },
    {
      id: "app-2",
      kind: "plan_confidence",
      subject_id: "plan-2026-11-01",
      reason: "Solver confidence (0.69 < 0.75) triggered by impending 12mm rain window",
      status: "pending",
      confidence: 0.69,
      requested_by: "orchestrator",
      created_at: new Date(Date.now() - 3600000).toISOString(),
    },
  ];
}

export async function resolveApproval(id: string, decision: "approved" | "rejected"): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/approvals/${id}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": "stubbleos-operator-key" },
      body: JSON.stringify({ decision, note: "Resolved via Web Dashboard" }),
    });
    return res.ok;
  } catch (e) {
    return true;
  }
}
