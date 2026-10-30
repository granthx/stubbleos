import React from "react";
import { MessageSquare, PhoneCall, Volume2 } from "lucide-react";
import { VernacularTurn } from "../types";

export const FarmerDialogueFeed: React.FC = () => {
  const sampleTurns: VernacularTurn[] = [
    {
      id: "vt-1",
      sender: "+91 98765 43210 (Village Nabha)",
      channel: "whatsapp",
      language: "pa",
      text: "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ ਜੀ, ਮੈਨੂੰ 4 ਏਕੜ ਲਈ ਸੁਪਰ ਸੀਡਰ ਚਾਹੀਦਾ ਹੈ। (I need super seeder for 4 acres)",
      intent: "book_machine",
      timestamp: "10:42 AM",
    },
    {
      id: "vt-2",
      sender: "+91 94170 11223 (Village Dhuri)",
      channel: "voice",
      language: "pa",
      text: "ਅਸੀਂ ਕੱਲ੍ਹ ਤੱਕ ਪਰਾਲੀ ਨਹੀਂ ਸਾੜਨਾ ਚਾਹੁੰਦੇ, ਮਸ਼ੀਨ ਭੇਜੋ ਜੀ। (Do not want to burn stubble, please dispatch machine)",
      intent: "urgent_request",
      timestamp: "10:39 AM",
      is_urgent: true,
    },
    {
      id: "vt-3",
      sender: "+91 98140 88990 (Village Sunam)",
      channel: "whatsapp",
      language: "hi",
      text: "बेलिंग की क्या दर है? छोटे किसानों के लिए क्या छूट है? (What is baling rate & smallholder subsidy?)",
      intent: "query_price",
      timestamp: "10:31 AM",
    },
  ];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden flex flex-col">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-emerald-400" />
          <h2 className="text-sm font-semibold text-white">Live Farmer Voice & WhatsApp Stream</h2>
        </div>
        <span className="text-xs text-slate-500 font-mono">Bilingual (Punjabi / Hindi)</span>
      </div>

      <div className="p-3 space-y-2.5 max-h-[300px] overflow-y-auto">
        {sampleTurns.map((turn) => (
          <div
            key={turn.id}
            className={`p-3 rounded-lg border text-xs ${
              turn.is_urgent
                ? "bg-rose-950/40 border-rose-800/80 text-rose-200"
                : "bg-slate-950/60 border-slate-800 text-slate-300"
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-1.5 font-medium text-white">
                {turn.channel === "voice" ? (
                  <PhoneCall className="h-3 w-3 text-cyan-400" />
                ) : (
                  <MessageSquare className="h-3 w-3 text-emerald-400" />
                )}
                <span>{turn.sender}</span>
              </div>
              <span className="text-[10px] text-slate-500 font-mono">{turn.timestamp}</span>
            </div>

            <p className="mt-1 leading-relaxed">{turn.text}</p>

            <div className="mt-2 flex items-center gap-2">
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                Intent: {turn.intent.replace(/_/g, " ")}
              </span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                Lang: {turn.language}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
