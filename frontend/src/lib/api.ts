import { ApprovalItem, ContractItem, DistrictSummary, FieldInfo, MachineInfo, VernacularTurn } from "../types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const DISTRICT_GEO: Record<string, { lat: number; lon: number; code: string; operators: string[] }> = {
  sangrur: { lat: 30.245, lon: 75.842, code: "PB-SAN", operators: ["Harpreet Singh", "Gurjit Singh", "Balwinder Kumar", "Manpreet Dhillon"] },
  patiala: { lat: 30.330, lon: 76.390, code: "PB-PAT", operators: ["Kuldeep Walia", "Amrik Dhaliwal", "Paramjit Sandhu", "Jagjit Tiwana"] },
  ludhiana: { lat: 30.880, lon: 75.850, code: "PB-LUD", operators: ["Davinder Gill", "Avtar Toor", "Balraj Kahlon", "Surjit Mangat"] },
  fatehgarh: { lat: 30.640, lon: 76.390, code: "PB-FGS", operators: ["Ranjit Bajwa", "Hardev Virk", "Bhupinder Sahi", "Karamjit Sidhu"] },
  karnal: { lat: 29.690, lon: 76.980, code: "HR-KAR", operators: ["Virender Rathi", "Sunil Kamboj", "Ramesh Dahiya", "Sanjay Punia"] },
};

export async function fetchDistrictSummary(district: string = "sangrur"): Promise<DistrictSummary> {
  const dKey = district.toLowerCase();
  try {
    const res = await fetch(`${API_BASE}/district-summary/${dKey}`, { cache: "no-store" });
    if (res.ok) return await res.json();
  } catch (e) {
    // Fallback to synthetic preview
  }
  return {
    district,
    total_fields: 240,
    cleared_fields: 162,
    pending_residue_fields: 72,
    burn_incidents_detected: dKey === "sangrur" ? 4 : dKey === "ludhiana" ? 6 : dKey === "patiala" ? 3 : 2,
    burn_risk_index: 0.31,
    active_machines_count: 28,
    total_stubble_cleared_acres: 584.5,
    indicative_co2e_avoided_tonnes: 1052.1,
    pending_approvals_count: 2,
    open_biomass_orders_count: 6,
  };
}

export async function fetchFields(district: string = "sangrur"): Promise<FieldInfo[]> {
  const dKey = district.toLowerCase();
  try {
    const res = await fetch(`${API_BASE}/fields?district=${dKey}`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) return data;
    }
  } catch (e) {}

  const geo = DISTRICT_GEO[dKey] || DISTRICT_GEO.sangrur;
  return Array.from({ length: 12 }, (_, i) => {
    const isBurn = i === 4 || (i === 8 && (dKey === "ludhiana" || dKey === "patiala"));
    const isCleared = i < 5 && !isBurn;
    return {
      id: `field-${dKey}-${i + 1}`,
      farmer_id: `farmer-${dKey}-${(i % 5) + 1}`,
      district: dKey,
      village_code: `${geo.code}-00${i + 1}`,
      area_acres: 2.5 + (i % 4),
      state: isBurn ? "burn_detected" : isCleared ? "cleared" : "harvested_residue_present",
      state_confidence: 0.94,
      burn_risk_score: isBurn ? 0.96 : isCleared ? 0.05 : 0.78,
      center_lat: geo.lat + ((i % 4) * 0.02) - 0.03,
      center_lon: geo.lon + (Math.floor(i / 4) * 0.02) - 0.02,
    };
  });
}

export async function fetchMachines(district: string = "sangrur"): Promise<MachineInfo[]> {
  const dKey = district.toLowerCase();
  try {
    const res = await fetch(`${API_BASE}/machines?district=${dKey}`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) return data;
    }
  } catch (e) {}

  const geo = DISTRICT_GEO[dKey] || DISTRICT_GEO.sangrur;
  return [
    { id: `m-${dKey}-1`, machine_type: "super_seeder", district: dKey, status: "in_use", current_lat: geo.lat + 0.005, current_lon: geo.lon - 0.007, capacity_acres_per_day: 15, operator_name: geo.operators[0] },
    { id: `m-${dKey}-2`, machine_type: "baler", district: dKey, status: "in_use", current_lat: geo.lat + 0.018, current_lon: geo.lon + 0.005, capacity_acres_per_day: 25, operator_name: geo.operators[1] },
    { id: `m-${dKey}-3`, machine_type: "happy_seeder", district: dKey, status: "available", current_lat: geo.lat - 0.014, current_lon: geo.lon - 0.012, capacity_acres_per_day: 12, operator_name: geo.operators[2] },
    { id: `m-${dKey}-4`, machine_type: "baler", district: dKey, status: "available", current_lat: geo.lat + 0.027, current_lon: geo.lon + 0.021, capacity_acres_per_day: 25, operator_name: geo.operators[3] },
  ];
}

const DISTRICT_APPROVALS: Record<string, ApprovalItem[]> = {
  sangrur: [
    {
      id: "app-san-1",
      kind: "burn_threat_escalation",
      subject_id: "f-san-104",
      district: "sangrur",
      reason: "Farmer threatening fire due to combine harvest delay in Dhuri block",
      status: "pending",
      confidence: 0.98,
      requested_by: "farmer_voice_agent",
      created_at: new Date().toISOString(),
    },
    {
      id: "app-san-2",
      kind: "plan_confidence",
      subject_id: "plan-san-2026",
      district: "sangrur",
      reason: "Solver confidence (0.69 < 0.75) triggered by impending 12mm rain window",
      status: "pending",
      confidence: 0.69,
      requested_by: "orchestrator",
      created_at: new Date(Date.now() - 3600000).toISOString(),
    },
  ],
  patiala: [
    {
      id: "app-pat-1",
      kind: "smallholder_priority_dispute",
      subject_id: "f-pat-201",
      district: "patiala",
      reason: "Marginal farmer in Nabha block contesting machine queue skip by 18-acre estate",
      status: "pending",
      confidence: 0.88,
      requested_by: "policy_guard",
      created_at: new Date().toISOString(),
    },
    {
      id: "app-pat-2",
      kind: "moisture_anomaly",
      subject_id: "f-pat-205",
      district: "patiala",
      reason: "Straw moisture 19% exceeds Rajpura CBG intake limit (14%); requires sun-drying window extension",
      status: "pending",
      confidence: 0.92,
      requested_by: "field_monitor",
      created_at: new Date(Date.now() - 7200000).toISOString(),
    },
  ],
  ludhiana: [
    {
      id: "app-lud-1",
      kind: "machine_breakdown_reroute",
      subject_id: "m-lud-04",
      district: "ludhiana",
      reason: "Super Seeder breakdown near Raikot; 4 pending smallholder fields require urgent reallocation",
      status: "pending",
      confidence: 0.72,
      requested_by: "machine_scheduler",
      created_at: new Date().toISOString(),
    },
    {
      id: "app-lud-2",
      kind: "burn_threat_escalation",
      subject_id: "f-lud-308",
      district: "ludhiana",
      reason: "Active FIRMS thermal anomaly detected near Jagraon; immediate ground verification dispatched",
      status: "pending",
      confidence: 0.87,
      requested_by: "field_monitor",
      created_at: new Date(Date.now() - 1800000).toISOString(),
    },
  ],
  fatehgarh: [
    {
      id: "app-fgs-1",
      kind: "tariff_subsidy_override",
      subject_id: "f-fgs-102",
      district: "fatehgarh",
      reason: "Special cross-subsidy requested for women smallholder cooperative in Sirhind",
      status: "pending",
      confidence: 0.95,
      requested_by: "pricing_negotiation",
      created_at: new Date().toISOString(),
    },
  ],
  karnal: [
    {
      id: "app-kar-1",
      kind: "buyer_pricing_dispute",
      subject_id: "f-kar-401",
      district: "karnal",
      reason: "Biomass pellet mill in Nilokheri offered INR 1450/t (below INR 1600/t minimum tariff floor)",
      status: "pending",
      confidence: 0.91,
      requested_by: "buyer_demand_agent",
      created_at: new Date().toISOString(),
    },
  ],
};

export async function fetchApprovals(district: string = "sangrur"): Promise<ApprovalItem[]> {
  const dKey = district.toLowerCase();
  try {
    const res = await fetch(`${API_BASE}/approvals?district=${dKey}`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) return data;
    }
  } catch (e) {}

  return DISTRICT_APPROVALS[dKey] || DISTRICT_APPROVALS.sangrur;
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
