"use client";

import React from "react";
import { CheckCircle2, Copy, FileText, Lock, ShieldCheck, X } from "lucide-react";

interface AuditModalProps {
  isOpen: boolean;
  onClose: () => void;
  district: string;
}

export const AuditModal: React.FC<AuditModalProps> = ({ isOpen, onClose, district }) => {
  if (!isOpen) return null;

  const records = [
    {
      blockHeight: 1482,
      timestamp: "2026-11-07 15:04:12 UTC",
      eventType: "TELEMETRY_INGESTION_SENTINEL2",
      prevHash: "7b4c81a29f8c61e05d09b2e811c7fa154bb3920199e4d5885c4a1612e3f89021",
      leafHash: "8f2a99c0d18e3881efb98020a583921908e2f819a274c4e19812541a7b8e1920",
      signer: "ed25519:node-sangrur-01",
      details: "Multi-spectral NDVI residue scan verified (Band 4/8/12). 0.08 fire anomaly score.",
      status: "VERIFIED",
    },
    {
      blockHeight: 1481,
      timestamp: "2026-11-07 14:58:30 UTC",
      eventType: "CP_SAT_SOLVER_DISPATCH",
      prevHash: "4a1612e3f890217b4c81a29f8c61e05d09b2e811c7fa154bb3920199e4d5885c",
      leafHash: "7b4c81a29f8c61e05d09b2e811c7fa154bb3920199e4d5885c4a1612e3f89021",
      signer: "ed25519:solver-cpsat-core",
      details: "Optimization objective: Maximize clearance before rainfall window (Fairness gap: -0.47%).",
      status: "VERIFIED",
    },
    {
      blockHeight: 1480,
      timestamp: "2026-11-07 14:51:19 UTC",
      eventType: "CONSENT_LEDGER_ENFORCEMENT",
      prevHash: "1e05d09b2e811c7fa154bb3920199e4d5885c4a1612e3f890217b4c81a29f8c6",
      leafHash: "4a1612e3f890217b4c81a29f8c61e05d09b2e811c7fa154bb3920199e4d5885c",
      signer: "ed25519:privacy-guard-pii",
      details: "Smallholder pseudonymization enforced: farmer PII redacted under DPDP Act 2023.",
      status: "VERIFIED",
    },
    {
      blockHeight: 1479,
      timestamp: "2026-11-07 14:40:05 UTC",
      eventType: "BIOMASS_CONTRACT_ESCROW_MATCH",
      prevHash: "885c4a1612e3f890217b4c81a29f8c61e05d09b2e811c7fa154bb3920199e4d5",
      leafHash: "1e05d09b2e811c7fa154bb3920199e4d5885c4a1612e3f890217b4c81a29f8c6",
      signer: "ed25519:contract-net-arbiter",
      details: "Contract-Net match locked: ₹2,100/t CIF with Sangrur CBG Bio-Energy (450t).",
      status: "VERIFIED",
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/70 backdrop-blur-sm p-4">
      <div className="border border-ink bg-paper text-ink max-w-4xl w-full max-h-[85vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="border-b border-ink/10 px-6 py-4 flex items-center justify-between bg-paper-subtle">
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-ink text-paper">
              <Lock className="h-4 w-4 text-neon" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-mono text-sm font-bold uppercase text-ink">
                  HASH-CHAINED AUDIT LOG & MRV EVIDENCE REGISTRY
                </h3>
                <span className="text-[10px] font-mono px-2 py-0.5 bg-neon text-ink border border-ink font-bold">
                  SHA-256 LEDGER
                </span>
              </div>
              <p className="text-[11px] font-mono text-wild-muted uppercase">
                Immutable Merkle Tree · Indicative Impact & Verification Bundles
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1 hover:bg-ink hover:text-paper border border-transparent hover:border-ink transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Top Summary Banner */}
        <div className="bg-ink text-paper px-6 py-3 flex flex-wrap items-center justify-between gap-4 font-mono text-xs">
          <div>
            SECTOR: <span className="text-neon font-bold uppercase">{district}</span>
          </div>
          <div>
            CHAIN ROOT: <span className="text-white/80">0x8f2a...c4e1</span>
          </div>
          <div className="flex items-center gap-2 text-neon">
            <ShieldCheck className="h-4 w-4" />
            <span>INTEGRITY VERIFIED: 100% UNBROKEN CHAIN</span>
          </div>
        </div>

        {/* Body Records */}
        <div className="p-6 space-y-4 overflow-y-auto flex-1 font-mono text-xs">
          {records.map((r) => (
            <div
              key={r.blockHeight}
              className="border border-ink/15 bg-paper-subtle p-4 hover:border-ink transition-colors space-y-2.5"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ink/10 pb-2">
                <div className="flex items-center gap-2 font-bold">
                  <span className="bg-ink text-paper px-2 py-0.5 text-[10px]">
                    BLOCK #{r.blockHeight}
                  </span>
                  <span className="text-ink">{r.eventType}</span>
                </div>
                <div className="flex items-center gap-2 text-wild-muted text-[11px]">
                  <span>{r.timestamp}</span>
                  <span className="text-ink font-bold px-1.5 py-0.2 border border-ink/20 bg-neon">
                    {r.status}
                  </span>
                </div>
              </div>

              <p className="font-sans text-xs text-wild-blue-gray">
                {r.details}
              </p>

              <div className="space-y-1 text-[10px] text-wild-muted pt-1">
                <div className="flex items-center gap-2">
                  <span className="w-16 uppercase text-wild-muted">Leaf Hash:</span>
                  <span className="text-ink font-bold break-all bg-paper px-1 border border-ink/10">
                    {r.leafHash}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-16 uppercase text-wild-muted">Prev Hash:</span>
                  <span className="text-wild-blue-gray break-all bg-paper px-1 border border-ink/10">
                    {r.prevHash}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-16 uppercase text-wild-muted">Signer:</span>
                  <span className="text-wild-blue-gray">{r.signer}</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="border-t border-ink/10 px-6 py-3.5 bg-paper-subtle flex items-center justify-between font-mono text-xs text-wild-muted">
          <div>COMPLIANCE: DPDP ACT 2023 · ISO 14064 MRV STANDARDS</div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-ink text-paper hover:bg-neon hover:text-ink font-bold uppercase transition-colors"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
};

