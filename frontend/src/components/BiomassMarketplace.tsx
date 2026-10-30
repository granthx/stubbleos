import React from "react";
import { DollarSign, Factory, FileCheck, ShoppingBag } from "lucide-react";

export const BiomassMarketplace: React.FC = () => {
  const buyerOrders = [
    { id: "bo-1", buyer: "Nabha Bio-Power Ltd", tonnes: 500, bidPrice: 1750, delivery: "Ex-Field", status: "Negotiated" },
    { id: "bo-2", buyer: "Sangrur CBG Plant", tonnes: 300, bidPrice: 2100, delivery: "CIF Plant", status: "Active Contract" },
    { id: "bo-3", buyer: "Shree Paper Mills", tonnes: 200, bidPrice: 1650, delivery: "Ex-Field", status: "Pending Acceptance" },
  ];

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
