"use client";

import React from "react";
import { ArrowUpRight, DollarSign, Factory, ShoppingBag } from "lucide-react";

interface MarketplaceProps {
  district?: string;
}

const DISTRICT_BUYERS: Record<string, Array<{ id: string; buyer: string; tonnes: number; bidPrice: number; delivery: string; status: string }>> = {
  sangrur: [
    { id: "san-b1", buyer: "Sangrur CBG Bio-Energy Hub", tonnes: 450, bidPrice: 2100, delivery: "CIF Plant", status: "Active Contract" },
    { id: "san-b2", buyer: "Dhuri Agro Pellets Corp", tonnes: 300, bidPrice: 1750, delivery: "Ex-Field", status: "Negotiated" },
    { id: "san-b3", buyer: "Sunam Biomass Power Station", tonnes: 200, bidPrice: 1680, delivery: "Ex-Field", status: "Pending Match" },
  ],
  patiala: [
    { id: "pat-b1", buyer: "Nabha Bio-Power Ltd", tonnes: 500, bidPrice: 1750, delivery: "Ex-Field", status: "Negotiated" },
    { id: "pat-b2", buyer: "Rajpura Thermal Bio-Gen Co.", tonnes: 350, bidPrice: 2150, delivery: "CIF Plant", status: "Active Contract" },
    { id: "pat-b3", buyer: "Samana Green Fuel Plant", tonnes: 250, bidPrice: 1700, delivery: "Ex-Field", status: "Pending Dispatch" },
  ],
  ludhiana: [
    { id: "lud-b1", buyer: "Khanna Biomass Co-Gen Plant", tonnes: 600, bidPrice: 2200, delivery: "CIF Plant", status: "Active Contract" },
    { id: "lud-b2", buyer: "Raikot Paperboard Mills", tonnes: 350, bidPrice: 1800, delivery: "Ex-Field", status: "Negotiated" },
    { id: "lud-b3", buyer: "Jagraon Bio-Coal Briquettes", tonnes: 220, bidPrice: 1650, delivery: "Ex-Field", status: "Pending Match" },
  ],
  fatehgarh: [
    { id: "fgs-b1", buyer: "Amloh Green Steel & Power", tonnes: 400, bidPrice: 2050, delivery: "CIF Plant", status: "Active Contract" },
    { id: "fgs-b2", buyer: "Sirhind Biomass Briquettes", tonnes: 280, bidPrice: 1720, delivery: "Ex-Field", status: "Negotiated" },
  ],
  karnal: [
    { id: "kar-b1", buyer: "Panipat 2G Ethanol Refinery (IOCL)", tonnes: 800, bidPrice: 2250, delivery: "CIF Plant", status: "Active Contract" },
    { id: "kar-b2", buyer: "Karnal CBG Biofuel Corp", tonnes: 420, bidPrice: 1950, delivery: "CIF Plant", status: "Negotiated" },
    { id: "kar-b3", buyer: "Nilokheri Agro Pellets Ltd", tonnes: 250, bidPrice: 1650, delivery: "Ex-Field", status: "Pending Acceptance" },
  ],
};

export const BiomassMarketplace: React.FC<MarketplaceProps> = ({ district = "sangrur" }) => {
  const dKey = district.toLowerCase();
  const buyerOrders = DISTRICT_BUYERS[dKey] || DISTRICT_BUYERS.sangrur;

  return (
    <div className="border border-ink/15 bg-paper flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-ink/10 flex items-center justify-between bg-paper-subtle">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 bg-ink text-paper">
            <Factory className="h-4 w-4 text-neon" />
          </div>
          <div>
            <h2 className="text-xs font-mono font-bold text-ink uppercase tracking-wider">
              [04 // BIOMASS CONTRACT-NET AUCTION]
            </h2>
            <p className="text-[11px] text-wild-muted font-mono">
              INDUSTRIAL OFF-TAKE & 2G REFINERY BIDS
            </p>
          </div>
        </div>

        <span className="text-[10px] font-mono px-2 py-0.5 bg-neon text-ink border border-ink font-bold uppercase">
          Auction Active
        </span>
      </div>

      {/* List */}
      <div className="divide-y divide-ink/10 text-xs">
        {buyerOrders.map((bo) => (
          <div
            key={bo.id}
            className="p-4 hover:bg-paper-subtle transition-colors flex flex-col justify-between gap-3"
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <h3 className="font-bold text-ink text-sm font-sans">{bo.buyer}</h3>
                <div className="flex items-center gap-2 mt-1 text-[11px] font-mono text-wild-blue-gray">
                  <span>ORDER #{bo.id.toUpperCase()}</span>
                  <span>·</span>
                  <span className="font-bold text-ink">{bo.tonnes} Tonnes</span>
                </div>
              </div>

              <div className="text-right">
                <div className="text-base font-extrabold text-ink font-mono">
                  ₹{bo.bidPrice.toLocaleString()}
                  <span className="text-[10px] font-normal text-wild-muted ml-0.5">/t</span>
                </div>
                <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 bg-ink/5 border border-ink/10 text-wild-blue-gray">
                  {bo.delivery}
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-1 border-t border-ink/5 text-[10px] font-mono">
              <span
                className={`px-2 py-0.5 uppercase font-bold border ${
                  bo.status === "Active Contract"
                    ? "bg-neon text-ink border-ink"
                    : bo.status === "Negotiated"
                    ? "bg-straw text-ink border-ink"
                    : "bg-paper text-wild-muted border-ink/20"
                }`}
              >
                {bo.status}
              </span>

              <span className="text-wild-muted flex items-center gap-1">
                ESCROW LOCKED
                <ArrowUpRight className="h-3 w-3" />
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="border-t border-ink/10 px-4 py-2 bg-paper-subtle flex items-center justify-between text-[10px] font-mono text-wild-muted mt-auto">
        <div>PROTOCOL: CONTRACT-NET EXTENDED</div>
        <div>STABLE PRICE FLOOR: ₹1,650/t</div>
      </div>
    </div>
  );
};
