export type FieldState = "not_harvested" | "harvested_residue_present" | "cleared" | "burn_detected";
export type MachineType = "super_seeder" | "happy_seeder" | "baler" | "rake";
export type MachineStatus = "available" | "in_use" | "broken" | "maintenance";
export type ApprovalStatus = "pending" | "approved" | "rejected" | "expired";
export type ContractStatus = "draft" | "offered" | "accepted" | "rejected" | "executed" | "cancelled";

export interface FieldInfo {
  id: string;
  farmer_id: string;
  district: string;
  village_code: string;
  area_acres: number;
  state: FieldState;
  state_confidence: number;
  burn_risk_score: number;
  center_lat: number;
  center_lon: number;
}

export interface MachineInfo {
  id: string;
  machine_type: MachineType;
  district: string;
  status: MachineStatus;
  current_lat: number;
  current_lon: number;
  capacity_acres_per_day: number;
  operator_name?: string;
}

export interface ApprovalItem {
  id: string;
  kind: string;
  subject_id: string;
  reason: string;
  status: ApprovalStatus;
  confidence?: number;
  requested_by: string;
  created_at: string;
}

export interface ContractItem {
  id: string;
  farmer_id: string;
  field_id: string;
  buyer_id?: string;
  price_inr_per_tonne: number;
  tonnes_agreed: number;
  status: ContractStatus;
  contract_sha256: string;
  created_at: string;
}

export interface DistrictSummary {
  district: string;
  total_fields: number;
  cleared_fields: number;
  pending_residue_fields: number;
  burn_incidents_detected: number;
  burn_risk_index: number;
  active_machines_count: number;
  total_stubble_cleared_acres: number;
  indicative_co2e_avoided_tonnes: number;
  pending_approvals_count: number;
  open_biomass_orders_count: number;
}

export interface VernacularTurn {
  id: string;
  sender: string;
  channel: "whatsapp" | "voice";
  language: "pa" | "hi" | "en";
  text: string;
  intent: string;
  timestamp: string;
  is_urgent?: boolean;
}
