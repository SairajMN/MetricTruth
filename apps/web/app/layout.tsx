import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: "MetricTruth — Certified Agentic Business Intelligence",
  description:
    "AI-powered business intelligence agent that answers business questions using certified metrics, deterministic SQL, and independently verified results.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}

