"use client";

import React, { useState } from "react";
import { MessageSquare, PhoneCall, Volume2, ShieldAlert } from "lucide-react";
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
      text: "ਅਸੀਂ ਕੱਲ੍ਹ ਤੱਕ ਪਰਾਲੀ ਨਹੀਂ ਸਾੜਨਾ ਚਾਹੁੰਦੇ, ਮਸ਼ੀਨ ਭੇਜੋ ਜੀ। (Do not want to burn stubble, please dispatch machine urgently)",
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
    {
      id: "san-3",
      sender: "+91 98725 33411 (Village Bhawanigarh)",
      channel: "whatsapp",
      language: "pa",
      text: "ਸੁਪਰ ਸੀਡਰ ਦਾ ਡਰਾਈਵਰ ਕਦੋਂ ਪਹੁੰਚੇਗਾ? 2 ਏਕੜ ਖੇਤ ਤਿਆਰ ਹੈ। (When will Super Seeder driver arrive? 2 acres prepped)",
      intent: "schedule_status",
      timestamp: "10:14 AM",
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
      sender: "+91 98141 22334 (Village Khanna)",
      channel: "whatsapp",
      language: "pa",
      text: "ਪਰਾਲੀ ਦੀਆਂ ਗੰਢਾਂ ਬਣ ਗਈਆਂ ਨੇ। ਖੰਨਾ ਪਲਾਂਟ ਵਿੱਚ ਭੇਜਣ ਦਾ ਸਮਾਂ ਦੱਸੋ। (Bales created. Advise delivery schedule to Khanna plant)",
      intent: "delivery_ready",
      timestamp: "10:50 AM",
    },
    {
      id: "lud-2",
      sender: "+91 94172 99881 (Village Jagraon)",
      channel: "voice",
      language: "pa",
      text: "ਕੱਲ੍ਹ ਮੀਂਹ ਪੈਣ ਦੀ ਸੰਭਾਵਨਾ ਹੈ, ਅੱਜ ਹੀ ਸੁਪਰ ਸੀਡਰ ਭੇਜੋ ਜੀ। (Rain expected tomorrow, please send Super Seeder today)",
      intent: "urgent_request",
      timestamp: "10:15 AM",
      is_urgent: true,
    },
  ],
  fatehgarh: [
    {
      id: "fgs-1",
      sender: "+91 98760 12345 (Village Sirhind)",
      channel: "whatsapp",
      language: "pa",
      text: "ਸਾਡੇ 3 ਏਕੜ ਰਕਬੇ ਲਈ ਸੁਪਰ ਸੀਡਰ ਦੀ ਬੁਕਿੰਗ ਦੀ ਪੁਸ਼ਟੀ ਕਰੋ ਜੀ। (Please confirm Super Seeder booking for 3 acres)",
      intent: "booking_confirmation",
      timestamp: "10:35 AM",
    },
  ],
  karnal: [
    {
      id: "kar-1",
      sender: "+91 94160 55667 (Village Nilokheri)",
      channel: "whatsapp",
      language: "hi",
      text: "सुपर सीडर की बुकिंग कब तक कन्फर्म होगी? गेहूं की बिजाई का समय निकला जा रहा है। (When will booking confirm? Sowing window closing)",
      intent: "urgent_request",
      timestamp: "10:48 AM",
      is_urgent: true,
    },
    {
      id: "kar-2",
      sender: "+91 98961 77889 (Village Gharaunda)",
      channel: "voice",
      language: "hi",
      text: "पानीपत एथेनॉल रिफाइनरी वाले पराली की क्या कीमत दे रहे हैं? (What rate is Panipat Ethanol Refinery offering for straw?)",
      intent: "price_query",
      timestamp: "10:20 AM",
    },
  ],
};

export const FarmerDialogueFeed: React.FC<FeedProps> = ({ district = "sangrur" }) => {
  const dKey = district.toLowerCase();
  const dialogues = DISTRICT_DIALOGUES[dKey] || DISTRICT_DIALOGUES.sangrur;
  const [filterChannel, setFilterChannel] = useState<string>("all");

  const filtered = dialogues.filter((d) => {
    if (filterChannel === "all") return true;
    return d.channel === filterChannel;
  });

  return (
    <div className="border border-ink/15 bg-paper flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-ink/10 flex items-center justify-between bg-paper-subtle">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 bg-ink text-paper">
            <MessageSquare className="h-4 w-4 text-neon" />
          </div>
          <div>
            <h2 className="text-xs font-mono font-bold text-ink uppercase tracking-wider">
              [05 // VERNACULAR FARMER TELEPHONY FEED]
            </h2>
            <p className="text-[11px] text-wild-muted font-mono">
              IVR VOICE & WHATSAPP INTERACTION STREAM
            </p>
          </div>
        </div>

        {/* Filter buttons */}
        <div className="flex items-center gap-1 font-mono text-[10px]">
          {["all", "whatsapp", "voice"].map((ch) => (
            <button
              key={ch}
              onClick={() => setFilterChannel(ch)}
              className={`px-2 py-0.5 uppercase border transition-colors ${
                filterChannel === ch
                  ? "bg-ink text-paper border-ink font-bold"
                  : "bg-paper text-wild-muted border-ink/10 hover:border-ink"
              }`}
            >
              {ch}
            </button>
          ))}
        </div>
      </div>

      {/* Feed list */}
      <div className="p-4 space-y-3 flex-1 overflow-y-auto max-h-[340px]">
        {filtered.map((d) => (
          <div
            key={d.id}
            className={`border p-3.5 transition-colors ${
              d.is_urgent
                ? "border-wild-red bg-wild-red/5"
                : "border-ink/15 bg-paper-subtle hover:border-ink"
            }`}
          >
            <div className="flex items-center justify-between border-b border-ink/10 pb-2 text-[10px] font-mono">
              <div className="flex items-center gap-2">
                {d.channel === "voice" ? (
                  <span className="flex items-center gap-1 px-1.5 py-0.5 bg-ink text-paper font-bold uppercase">
                    <PhoneCall className="h-2.5 w-2.5 text-neon" />
                    IVR Voice
                  </span>
                ) : (
                  <span className="flex items-center gap-1 px-1.5 py-0.5 bg-paper-subtle border border-ink/20 text-ink font-bold uppercase">
                    <MessageSquare className="h-2.5 w-2.5" />
                    WhatsApp
                  </span>
                )}
                <span className="font-bold text-ink">{d.sender}</span>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-[9px] px-1.5 py-0.2 border border-ink/10 text-wild-blue-gray uppercase">
                  {d.language.toUpperCase()}
                </span>
                <span className="text-wild-muted">{d.timestamp}</span>
              </div>
            </div>

            <p className="text-xs font-sans text-ink leading-relaxed mt-2.5">
              {d.text}
            </p>

            <div className="flex items-center justify-between pt-2 mt-2 border-t border-ink/10 text-[10px] font-mono">
              <span className="text-wild-blue-gray uppercase">
                INTENT: <span className="font-bold text-ink">{d.intent.replace(/_/g, " ")}</span>
              </span>

              {d.is_urgent && (
                <span className="flex items-center gap-1 text-wild-red font-bold uppercase">
                  <ShieldAlert className="h-3 w-3" />
                  Burn Threat Priority
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="border-t border-ink/10 px-4 py-2 bg-paper-subtle flex items-center justify-between text-[10px] font-mono text-wild-muted">
        <div>CHANNELS: PUNJABI (GURMUKHI) · HINDI · ENGLISH</div>
        <div>QUIET HOURS ENFORCED</div>
      </div>
    </div>
  );
};
