"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BookOpen,
  Code2,
  FileBarChart2,
  LayoutDashboard,
  Search,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import { UserRole, getStoredRole, setStoredRole } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/", label: "1. Command Center", icon: LayoutDashboard },
  { href: "/ask", label: "2. Ask MetricTruth", icon: Search },
  { href: "/runs/latest", label: "3. Investigation Report", icon: FileBarChart2 },
  { href: "/sql", label: "4. SQL Inspector", icon: Code2 },
  { href: "/metrics", label: "5. Metric Registry", icon: BookOpen },
  { href: "/observatory", label: "6. Execution Observatory", icon: Activity },
  { href: "/evaluations", label: "7. Evaluation Center", icon: ShieldCheck },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [role, setRole] = useState<UserRole>("admin");

  useEffect(() => {
    setRole(getStoredRole());
  }, []);

  const handleRoleChange = (nextRole: UserRole) => {
    setRole(nextRole);
    setStoredRole(nextRole);
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-[#090d16] text-slate-100">
      <aside className="w-full lg:w-64 border-b lg:border-b-0 lg:border-r border-slate-800/80 bg-[#0d1322] flex flex-col justify-between shrink-0">
        <div>
          <div className="p-5 border-b border-slate-800/80 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="font-bold tracking-tight text-lg text-white">
                  METRICTRUTH
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                DirectMeds Certified BI Engine
              </p>
            </div>
          </div>

          <nav className="p-3 space-y-1" aria-label="Main navigation">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href.replace("/latest", ""));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    active
                      ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                  }`}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="p-4 border-t border-slate-800/80 bg-slate-900/40 space-y-2">
          <div className="flex items-center gap-2 text-xs text-slate-400 font-medium">
            <UserCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Active Access Role (RBAC)</span>
          </div>
          <select
            aria-label="Select active RBAC role"
            value={role}
            onChange={(e) => handleRoleChange(e.target.value as UserRole)}
            className="w-full rounded-md bg-slate-950 border border-slate-700 px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="viewer">Viewer (Employee)</option>
            <option value="analyst">Analyst (Data Team)</option>
            <option value="admin">Admin (Registry Owner)</option>
          </select>
          <p className="text-[11px] text-slate-500 leading-tight">
            DB Role: <code className="text-emerald-400">metrictruth_reader</code>{" "}
            (READ ONLY)
          </p>
        </div>
      </aside>

      <main className="flex-1 min-w-0 p-6 lg:p-8 overflow-y-auto">
        <div className="max-w-7xl mx-auto">{children}</div>
      </main>
    </div>
  );
}
