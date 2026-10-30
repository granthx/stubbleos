# StubbleOS Operations Dashboard (Phase 7)

Interactive District Command Center built with **Next.js 14**, **TypeScript**, and **Tailwind CSS**.

## Features

1. **District Overview & KPIs**: Real-time stubble clearance %, avoided carbon emissions (t CO2e), deployed machinery fleet, and thermal fire risk indices.
2. **Interactive Map View**: Visualizes agricultural field parcels color-coded by Sentinel-2 & FIRMS detection status (Cleared, Residue Present, Thermal Alert) alongside active machine GPS tracks.
3. **Active Machine Fleet Table**: Live tracking of Super Seeders, Happy Seeders, and Balers with assigned operators and daily throughput capacities.
4. **Human-in-the-Loop (HITL) Queue**: District supervisor decision console for reviewing low-confidence solver plans, weather shift replans, and urgent residue burning threats.
5. **Biomass Off-take Marketplace**: Contract-Net industrial buyer order book and agreed contract register.
6. **Bilingual Farmer Dialogue Stream**: Live feed of vernacular WhatsApp messages and IVR voice call transcripts (Punjabi Gurmukhi and Hindi Devanagari).

## Development

```bash
cd frontend
npm install
npm run dev
```

The dashboard runs on `http://localhost:3000` and automatically connects to the FastAPI backend on `http://localhost:8000/api/v1` (or uses built-in live mock fallback if backend is offline).
