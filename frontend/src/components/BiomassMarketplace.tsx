import React from "react";
import { DollarSign, Factory, FileCheck, ShoppingBag } from "lucide-react";

interface MarketplaceProps {
  district?: string;
}

const DISTRICT_BUYERS: Record<string, Array<{ id: string; buyer: string; tonnes: number; bidPrice: number; delivery: string; status: string }>> = {
  sangrur: [
    { id: "san-b1", buyer: "Sangrur CBG Bio-Energy", tonnes: 450, bidPrice: 2100, delivery: "CIF Plant", status: "Active Contract" },
    { id: "san-b2", buyer: "Dhuri Agro Pellets", tonnes: 300, bidPrice: 1750, delivery: "Ex-Field", status: "Negotiated" },
    { id: "san-b3", buyer: "Sunam Biomass Power", tonnes: 200, bidPrice: 1680, delivery: "Ex-Field", status: "Pending Acceptance" },
  ],
  patiala: [
    { id: "pat-b1", buyer: "Nabha Bio-Power Ltd", tonnes: 500, bidPrice: 1750, delivery: "Ex-Field", status: "Negotiated" },
    { id: "pat-b2", buyer: "Rajpura Thermal Bio-Gen", tonnes: 350, bidPrice: 2150, delivery: "CIF Plant", status: "Active Contract" },
    { id: "pat-b3", buyer: "Samana Green Fuel Plant", tonnes: 250, bidPrice: 1700, delivery: "Ex-Field", status: "Pending Delivery" },
  ],
  ludhiana: [
    { id: "lud-b1", buyer: "Khanna Biomass Co-Gen", tonnes: 600, bidPrice: 2200, delivery: "CIF Plant", status: "Active Contract" },
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
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden flex flex-col">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Factory className="h-4 w-4 text-emerald-400" />
          <h2 className="text-sm font-semibold text-white">Biomass Off-take & Buyer Marketplace</h2>
        </div>
        <span className="text-xs text-emerald-400 font-mono">Contract-Net Active</span>
      </div>

      <div className="divide-y divide-slate-800 text-xs">
        {buyerOrders.map((bo) => (
          <div key={bo.id} className="p-3 hover:bg-slate-800/30 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white">{bo.buyer}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                  {bo.delivery}
                </span>
              </div>
              <p className="text-slate-400 mt-0.5">
                Volume: <span className="text-slate-200 font-medium">{bo.tonnes} tonnes</span> @{" "}
                <span className="text-emerald-400 font-semibold">₹{bo.bidPrice} / tonne</span>
              </p>
            </div>

            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-800">
                {bo.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
