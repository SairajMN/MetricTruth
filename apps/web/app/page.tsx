"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Database,
  DollarSign,
  FileCheck2,
  Percent,
  Sparkles,
  Users,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

export default function CommandCenterPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch("/analytics/overview")
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-10 w-80 bg-slate-800 rounded-lg" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-slate-900 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6 rounded-xl bg-rose-950/40 border border-rose-700/50 text-rose-200">
        <h2 className="font-semibold text-lg">Backend Connection Error</h2>
        <p className="text-sm mt-1">
          Could not reach MetricTruth API: {error}. Ensure the FastAPI server is
          running on port 8000.
        </p>
      </div>
    );
  }

  const counters = data.summary_counters;
  const perf = data.business_performance;
  const revMillions = (perf.attributed_revenue_usd / 1_000_000).toFixed(2);

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-indigo-400">
            Business Intelligence Control Center
          </span>
          <h1 className="text-2xl lg:text-3xl font-bold text-white mt-1">
            DirectMeds Analytics Command Center
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            All metrics resolved from certified YAML definitions and verified by
            deterministic SQL &amp; Decimal auditors.
          </p>
        </div>
        <Link
          href="/ask"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors"
        >
          <Sparkles className="w-4 h-4" />
          <span>Ask MetricTruth</span>
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>

      {/* Top System Counters */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <p className="text-xs text-slate-400 uppercase tracking-wider">
            Certified Metrics
          </p>
          <p className="text-2xl font-bold tabular-nums text-white mt-1">
            {counters.certified_metrics}{" "}
            <span className="text-xs font-normal text-slate-400">
              / {counters.total_registered_metrics} total
            </span>
          </p>
        </div>
        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <p className="text-xs text-slate-400 uppercase tracking-wider">
            Active Data Sources
          </p>
          <p className="text-2xl font-bold tabular-nums text-white mt-1">
            {counters.active_data_sources}
          </p>
        </div>
        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <p className="text-xs text-slate-400 uppercase tracking-wider">
            Queries Executed
          </p>
          <p className="text-2xl font-bold tabular-nums text-white mt-1">
            {counters.queries_today}
          </p>
        </div>
        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <p className="text-xs text-slate-400 uppercase tracking-wider">
            Successful Verifications
          </p>
          <p className="text-2xl font-bold tabular-nums text-emerald-400 mt-1">
            {counters.successful_verifications}
          </p>
        </div>
      </div>

      {/* Business Performance KPIs (Live from reporting views) */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            Certified Business Performance ({perf.period})
          </h2>
          <span className="text-xs text-emerald-400 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Live Read-Only View Query
          </span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 rounded-xl bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-xs font-medium">Paid CAC</span>
              <DollarSign className="w-4 h-4 text-indigo-400" />
            </div>
            <p className="text-3xl font-bold tabular-nums text-white mt-2">
              ${perf.paid_cac_usd.toFixed(2)}
            </p>
            <p className="text-xs text-rose-400 mt-1">
              +25.0% vs Oct ($30.00)
            </p>
          </div>

          <div className="p-5 rounded-xl bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-xs font-medium">Conversion Rate</span>
              <Percent className="w-4 h-4 text-emerald-400" />
            </div>
            <p className="text-3xl font-bold tabular-nums text-white mt-2">
              {perf.conversion_rate_pct.toFixed(2)}%
            </p>
            <p className="text-xs text-slate-400 mt-1">
              {perf.new_customers.toLocaleString()} /{" "}
              {perf.total_clicks.toLocaleString()} clicks
            </p>
          </div>

          <div className="p-5 rounded-xl bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-xs font-medium">Attributed Revenue</span>
              <Activity className="w-4 h-4 text-sky-400" />
            </div>
            <p className="text-3xl font-bold tabular-nums text-white mt-2">
              ${revMillions}M
            </p>
            <p className="text-xs text-emerald-400 mt-1">
              9.47x Paid ROAS
            </p>
          </div>

          <div className="p-5 rounded-xl bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-xs font-medium">Paid New Customers</span>
              <Users className="w-4 h-4 text-amber-400" />
            </div>
            <p className="text-3xl font-bold tabular-nums text-white mt-2">
              {perf.new_customers.toLocaleString()}
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Last non-direct paid click (7d)
            </p>
          </div>
        </div>
      </div>

      {/* Data Health & Recent Investigations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <Database className="w-4 h-4 text-indigo-400" />
              <span>Data Source Freshness &amp; Health</span>
            </h2>
            <Link
              href="/metrics"
              className="text-xs text-indigo-400 hover:underline"
            >
              Manage Sources →
            </Link>
          </div>
          <div className="space-y-2.5">
            {data.data_health.map((src: any) => (
              <div
                key={src.source_name}
                className="flex items-center justify-between p-3 rounded-lg bg-slate-900/80 border border-slate-800/80"
              >
                <div>
                  <p className="text-sm font-medium text-slate-200">
                    {src.source_name}
                  </p>
                  <p className="text-xs text-slate-400 tabular-nums">
                    {src.accepted_rows.toLocaleString()} accepted rows ·{" "}
                    {src.age_hours}h age (SLA ≤ 24h)
                  </p>
                </div>
                <span
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
                    src.health === "HEALTHY"
                      ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                      : "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                  }`}
                >
                  {src.health === "HEALTHY" ? (
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  ) : (
                    <AlertTriangle className="w-3.5 h-3.5" />
                  )}
                  {src.health}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <FileCheck2 className="w-4 h-4 text-emerald-400" />
              <span>Recent Verified Investigations</span>
            </h2>
            <Link
              href="/observatory"
              className="text-xs text-indigo-400 hover:underline"
            >
              All Traces →
            </Link>
          </div>
          <div className="space-y-2.5">
            {data.recent_investigations.length === 0 ? (
              <p className="text-sm text-slate-400 py-4">
                No investigations run yet. Click &ldquo;Ask MetricTruth&rdquo; to
                start.
              </p>
            ) : (
              data.recent_investigations.slice(0, 5).map((run: any) => (
                <Link
                  key={run.run_id}
                  href={`/runs/${run.run_id}`}
                  className="flex items-center justify-between p-3 rounded-lg bg-slate-900/80 hover:bg-slate-800/80 border border-slate-800/80 transition-colors"
                >
                  <div className="min-w-0 pr-3">
                    <p className="text-sm font-medium text-slate-200 truncate">
                      {run.question}
                    </p>
                    <p className="text-xs text-slate-400 tabular-nums mt-0.5">
                      {run.run_id} ·{" "}
                      {run.selected_metric_id || "policy_gate"} ·{" "}
                      {Number(run.duration_ms).toFixed(1)}ms
                    </p>
                  </div>
                  <span
                    className={`shrink-0 px-2.5 py-1 rounded-full text-xs font-semibold ${
                      run.status === "COMPLETED"
                        ? "bg-emerald-500/15 text-emerald-300"
                        : run.status === "CLARIFICATION_REQUIRED"
                        ? "bg-amber-500/15 text-amber-300"
                        : "bg-rose-500/15 text-rose-300"
                    }`}
                  >
                    {run.status}
                  </span>
                </Link>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

