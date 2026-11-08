import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "StubbleOS — Autonomous Residue Coordination Layer",
  description: "Swiss-Engineered Autonomous Crop Residue Clearance & Zero-Burn Command Protocol for Punjab & Haryana",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-paper text-ink antialiased selection:bg-neon selection:text-ink min-h-screen">
        {children}
      </body>
    </html>
  );
}
