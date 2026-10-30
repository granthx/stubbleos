import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "StubbleOS - District Operations Command Center",
  description: "Autonomous Crop Residue Management Coordination Layer for Punjab & Haryana",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 antialiased selection:bg-emerald-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}
