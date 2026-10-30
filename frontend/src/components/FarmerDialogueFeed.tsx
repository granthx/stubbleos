import React from "react";
import { MessageSquare, PhoneCall, Volume2 } from "lucide-react";
import { VernacularTurn } from "../types";

interface FeedProps {
  district?: string;
}

const DISTRICT_DIALOGUES: Record<string, VernacularTurn[]> = {
  sangrur: [
    {
      id: "san-1",
      sender: "+91 94170 11223 (Village Dhuri)",
      channel: "voice",
      language: "pa",
      text: "ਅਸੀਂ ਕੱਲ੍ਹ ਤੱਕ ਪਰਾਲੀ ਨਹੀਂ ਸਾੜਨਾ ਚਾਹੁੰਦੇ, ਮਸ਼ੀਨ ਭੇਜੋ ਜੀ। (Do not want to burn stubble, please dispatch machine)",
      intent: "urgent_request",
      timestamp: "10:39 AM",
      is_urgent: true,
    },
    {
      id: "san-2",
      sender: "+91 98140 88990 (Village Sunam)",
      channel: "whatsapp",
      language: "pa",
      text: "ਬੇਲਿੰਗ ਦੀ ਕੀ ਦਰ ਹੈ? ਛੋਟੇ ਕਿਸਾਨਾਂ ਲਈ ਕੀ ਛੋਟ ਹੈ? (What is baling rate & smallholder subsidy?)",
      intent: "query_price",
      timestamp: "10:31 AM",
    },
  ],
  patiala: [
    {
      id: "pat-1",
      sender: "+91 98722 44102 (Village Nabha)",
      channel: "whatsapp",
      language: "pa",
      text: "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ ਜੀ, ਸਾਡੇ 5 ਏਕੜ ਝੋਨੇ ਦੀ ਵਾਢੀ ਹੋ ਗਈ ਹੈ, ਸੁਪਰ ਸੀਡਰ ਕਦੋਂ ਮਿਲੇਗਾ? (Harvest done on 5 acres, when will Super Seeder arrive?)",
      intent: "book_machine",
      timestamp: "10:45 AM",
    },
    {
      id: "pat-2",
      sender: "+91 94633 11882 (Village Rajpura)",
      channel: "voice",
      language: "pa",
      text: "ਰਾਜਪੁਰਾ ਸੀ.ਬੀ.ਜੀ. ਪਲਾਂਟ ਵਾਲੇ ਟਰੱਕ ਕਦੋਂ ਭੇਜ ਰਹੇ ਨੇ ਗੱਠਾਂ ਚੁੱਕਣ ਲਈ? (When is Rajpura CBG plant sending trucks to collect bales?)",
      intent: "logistics_query",
      timestamp: "10:28 AM",
    },
  ],
  ludhiana: [
    {
      id: "lud-1",
      sender: "+91 98150 99441 (Village Raikot)",
      channel: "whatsapp",
      language: "pa",
      text: "ਰਾਏਕੋਟ ਬਲਾਕ ਵਿੱਚ ਹੈਪੀ ਸੀਡਰ ਬੁਕਿੰਗ ਦੀ ਪੁਸ਼ਟੀ ਹੋ ਗਈ ਹੈ? (Has Happy Seeder booking in Raikot block been confirmed?)",
      intent: "confirm_booking",
      timestamp: "10:48 AM",
    },
    {
      id: "lud-2",
      sender: "+91 98788 33119 (Village Jagraon)",
      channel: "voice",
      language: "pa",
      text: "ਸਾਡੀ ਕਣਕ ਬੀਜਣ ਦੀ ਆਖਰੀ ਤਾਰੀਖ ਨੇੜੇ ਹੈ, ਕਿਰਪਾ ਕਰਕੇ ਜਲਦੀ ਪ੍ਰਬੰਧ ਕਰੋ। (Wheat sowing deadline is near, please arrange urgently)",
      intent: "urgent_request",
      timestamp: "10:35 AM",
      is_urgent: true,
    },
  ],
  fatehgarh: [
    {
      id: "fgs-1",
      sender: "+91 94640 22331 (Village Sirhind)",
      channel: "whatsapp",
      language: "pa",
      text: "ਸਰਹਿੰਦ ਵਿੱਚ ਸਾਡੀ ਮਹਿਲਾ ਕਿਸਾਨ ਸਭਾ ਨੂੰ ਬੇਲਰ ਮਸ਼ੀਨ ਕਿਰਾਏ 'ਤੇ ਚਾਹੀਦੀ ਹੈ। (Our women farmer group in Sirhind needs baler machine on rent)",
      intent: "book_machine",
      timestamp: "10:41 AM",
    },
    {
      id: "fgs-2",
      sender: "+91 98761 55442 (Village Amloh)",
      channel: "voice",
      language: "pa",
      text: "ਅਮਲੋਹ ਵਿੱਚ ਕੰਬਾਈਨ ਲੇਟ ਹੋ ਗਈ, ਸੁਪਰ ਸੀਡਰ ਦੀ ਤਾਰੀਖ 2 ਦਿਨ ਅੱਗੇ ਕਰੋ। (Combine delayed in Amloh, please postpone Seeder by 2 days)",
      intent: "reschedule_booking",
      timestamp: "10:19 AM",
    },
  ],
  karnal: [
    {
      id: "kar-1",
      sender: "+91 94160 55112 (Village Nilokheri)",
      channel: "whatsapp",
      language: "hi",
      text: "राम राम जी, नीलोखेड़ी में सुपर सीडर की बुकिंग कब तक कंफर्म होगी? (Ram Ram, when will Super Seeder booking confirm in Nilokheri?)",
      intent: "book_machine",
      timestamp: "10:50 AM",
    },
    {
      id: "kar-2",
      sender: "+91 98120 77334 (Village Assandh)",
      channel: "voice",
      language: "hi",
      text: "हम पराली बिल्कुल नहीं जलाना चाहते। कस्टम हायरिंग सेंटर से बेलर ऑपरेटर का नंबर दे दो। (Do not want to burn straw. Please share baler operator contact)",
      intent: "urgent_request",
      timestamp: "10:44 AM",
      is_urgent: true,
    },
    {
      id: "kar-3",
      sender: "+91 94670 88221 (Village Gharaunda)",
      channel: "whatsapp",
      language: "hi",
      text: "पानीपत बायो-रिफाइनरी पराली का क्या रेट दे रही है? (What rate is Panipat Bio-Refinery offering for baled straw?)",
      intent: "query_price",
      timestamp: "10:32 AM",
    },
  ],
};

export const FarmerDialogueFeed: React.FC<FeedProps> = ({ district = "sangrur" }) => {
  const dKey = district.toLowerCase();
  const turns = DISTRICT_DIALOGUES[dKey] || DISTRICT_DIALOGUES.sangrur;
  const isHaryana = dKey === "karnal";

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden flex flex-col">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-emerald-400" />
          <h2 className="text-sm font-semibold text-white">Live Farmer Voice & WhatsApp Stream</h2>
        </div>
        <span className="text-xs text-slate-400 font-mono">
          {isHaryana ? "Hindi / Haryanvi" : "Punjabi (Gurmukhi)"}
        </span>
      </div>

      <div className="p-3 space-y-2.5 max-h-[300px] overflow-y-auto">
        {turns.map((turn) => (
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
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                Intent: {turn.intent.replace(/_/g, " ")}
              </span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                Lang: {turn.language}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
