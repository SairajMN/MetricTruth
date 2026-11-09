"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import React, { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiFetch } from "../../../lib/api";

type TabKey = "report" | "sql" | "evidence" | "trace";

export default function InvestigationReportPage() {
  const params = useParams();
  const rawRunId = typeof params?.runId === "string" ? params.runId : "latest";

  const [run, setRun] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("report");

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        let targetId = rawRunId;
        if (targetId === "latest") {
          const listRes = await apiFetch("/analytics/runs?limit=10");
          const completedRun = (listRes.runs || []).find(
            (r: any) => r.status === "COMPLETED"
          );
          if (completedRun) {
            targetId = completedRun.run_id;
          } else {
            const seeded = await apiFetch("/analytics/ask", {
              method: "POST",
              body: JSON.stringify({
                question:
                  "Why did our paid customer acquisition cost increase this month compared with last month? Identify which campaigns are responsible.",
              }),
            });
            targetId = seeded.run_id;
          }
        }
        const detail = await apiFetch(`/analytics/runs/${targetId}`);
        if (active) setRun(detail);
      } catch (err: any) {
        if (active) setError(err.message || "Failed to load investigation run");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [rawRunId]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-24 animate-pulse rounded-xl border border-slate-800 bg-slate-900/50" />
        <div className="h-96 animate-pulse rounded-xl border border-slate-800 bg-slate-900/50" />
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="rounded-xl border border-rose-500/40 bg-rose-950/20 p-6 text-rose-200">
        <h2 className="text-base font-semibold">Investigation Not Available</h2>
        <p className="mt-1 text-sm text-rose-300">{error || "Run not found"}</p>
        <Link
          href="/ask"
          className="mt-4 inline-block rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
        >
          Ask a New Question
        </Link>
      </div>
    );
  }

  const report = run.report;
  const bundle = run.audit_bundle;
  const num = bundle?.numerical;
  const rows: any[] = num?.rows || [];
  const chartData = rows
    .filter((r) => r.current_value !== null)
    .map((r) => ({
      segment: r.dimension_key,
      Previous: r.previous_value !== null ? Number(r.previous_value) : 0,
      Current: Number(r.current_value),
      PrevCPC: r.previous_drivers?.cpc ? Number(r.previous_drivers.cpc) : 0,
      CurCPC: r.current_drivers?.cpc ? Number(r.current_drivers.cpc) : 0,
    }));

  const isCertified = report?.certification_status === "CERTIFIED";
  const isStale = report?.certification_status === "NOT_CERTIFIED_STALE_DATA";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <span>{run.run_id}</span>
            <span>•</span>
            <span>{run.duration_ms} ms</span>
            {run.cache_hit && (
              <span className="rounded bg-cyan-500/15 px-2 py-0.5 text-cyan-300">
                CACHE HIT
              </span>
            )}
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-white">
            {report?.title || "Analytical Investigation"}
          </h1>
          <p className="mt-1 text-sm text-slate-300">
            Question: <span className="text-white">“{run.question}”</span>
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {(
            [
              ["report", "Investigation Report"],
              ["sql", "View SQL"],
              ["evidence", "View Data Evidence"],
              ["trace", "View Execution Trace"],
            ] as [TabKey, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setActiveTab(key)}
              className={`rounded-lg px-3.5 py-2 text-xs font-semibold transition ${
                activeTab === key
                  ? "bg-emerald-500 text-slate-950 shadow-sm"
                  : "border border-slate-800 bg-slate-900 text-slate-300 hover:bg-slate-800"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {report && (
        <div
          className={`rounded-xl border p-4 ${
            isCertified
              ? "border-emerald-500/40 bg-emerald-950/20 text-emerald-200"
              : isStale
              ? "border-amber-500/50 bg-amber-950/30 text-amber-200"
              : "border-rose-500/50 bg-rose-950/30 text-rose-200"
          }`}
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span
                className={`rounded px-2 py-0.5 text-[11px] font-bold uppercase ${
                  isCertified
                    ? "bg-emerald-500 text-slate-950"
                    : isStale
                    ? "bg-amber-400 text-slate-950"
                    : "bg-rose-500 text-white"
                }`}
              >
                {report.certification_status}
              </span>
              <span className="text-xs font-medium">
                {report.certification_banner}
              </span>
            </div>
            <span className="font-mono text-xs">
              Grounded Claim Rate:{" "}
              {Math.round((report.grounded_claim_rate || 1) * 100)}%
            </span>
          </div>
        </div>
      )}

      {!report && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-950/20 p-5">
          <div className="text-xs font-bold uppercase text-amber-300">
            Run Status: {run.status}
          </div>
          <p className="mt-1 text-sm text-slate-200">
            {run.failure_reason ||
              run.clarification?.question ||
              "Run did not produce a report."}
          </p>
        </div>
      )}

      {activeTab === "report" && report && bundle && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs text-slate-400">
                Current Period ({bundle.current_period_label})
              </div>
              <div className="mt-1 text-2xl font-bold text-white">
                {num.aggregate_current_display}
              </div>
              <div className="mt-1 text-[11px] text-slate-400">
                Certified Metric v{bundle.metric_version}
              </div>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs text-slate-400">
                Comparison ({bundle.comparison_period_label || "None"})
              </div>
              <div className="mt-1 text-2xl font-bold text-slate-200">
                {num.aggregate_previous_display || "—"}
              </div>
              <div className="mt-1 text-[11px] text-slate-400">
                Delta:{" "}
                {num.aggregate_pct_change !== null
                  ? `${Number(num.aggregate_pct_change) >= 0 ? "+" : ""}${
                      num.aggregate_pct_change
                    }%`
                  : "N/A"}
              </div>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs text-slate-400">
                Total Audited Media Spend
              </div>
              <div className="mt-1 text-2xl font-bold text-white">
                ${Number(num.aggregate_cur_spend).toLocaleString()}
              </div>
              <div className="mt-1 text-[11px] text-emerald-400">
                Reconciliation: {bundle.reconciliation.status}
              </div>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs text-slate-400">
                Attributed New Customers
              </div>
              <div className="mt-1 text-2xl font-bold text-white">
                {Number(num.aggregate_cur_customers).toLocaleString()}
              </div>
              <div className="mt-1 text-[11px] text-slate-400">
                Clicks: {Number(num.aggregate_cur_clicks).toLocaleString()}
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-emerald-400">
              Overall Finding & Executive Summary
            </h2>
            <p className="mt-2 text-base font-medium text-white">
              {report.overall_finding}
            </p>
            <p className="mt-1 text-sm text-slate-300">
              {report.executive_summary}
            </p>
          </div>

          {chartData.length > 0 && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
                <h3 className="mb-3 text-sm font-semibold text-white">
                  {bundle.metric_name} by Segment (Previous vs Current)
                </h3>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="segment" stroke="#94a3b8" fontSize={12} />
                      <YAxis stroke="#94a3b8" fontSize={12} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#0f172a",
                          borderColor: "#334155",
                          color: "#f8fafc",
                        }}
                      />
                      <Legend />
                      <Bar
                        dataKey="Previous"
                        fill="#64748b"
                        radius={[4, 4, 0, 0]}
                      />
                      <Bar
                        dataKey="Current"
                        fill="#10b981"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
                <h3 className="mb-3 text-sm font-semibold text-white">
                  Driver Decomposition: Cost Per Click ($ USD)
                </h3>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="segment" stroke="#94a3b8" fontSize={12} />
                      <YAxis stroke="#94a3b8" fontSize={12} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#0f172a",
                          borderColor: "#334155",
                          color: "#f8fafc",
                        }}
                      />
                      <Legend />
                      <Bar
                        dataKey="PrevCPC"
                        name="Previous CPC ($)"
                        fill="#475569"
                        radius={[4, 4, 0, 0]}
                      />
                      <Bar
                        dataKey="CurCPC"
                        name="Current CPC ($)"
                        fill="#06b6d4"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <h2
              id="breakdown-table-title"
              className="mb-3 text-sm font-semibold text-white"
            >
              Independently Audited Segment Breakdown
            </h2>
            <div
              className="table-wrapper rounded-lg border border-slate-800"
              tabIndex={0}
              role="region"
              aria-labelledby="breakdown-table-title"
              style={
                {
                  "--label-2": "'Prev Value'",
                  "--label-3": "'Cur Value'",
                  "--label-4": "'Delta %'",
                  "--label-5": "'Spend (Cur)'",
                  "--label-6": "'Customers (Cur)'",
                } as React.CSSProperties
              }
            >
              <table className="text-left text-xs">
                <thead className="bg-slate-950 text-slate-400">
                  <tr>
                    <th scope="col" className="px-3.5 py-2.5">
                      Segment
                    </th>
                    <th scope="col" className="px-3.5 py-2.5">
                      Previous Period
                    </th>
                    <th scope="col" className="px-3.5 py-2.5">
                      Current Period
                    </th>
                    <th scope="col" className="px-3.5 py-2.5">
                      Change
                    </th>
                    <th scope="col" className="px-3.5 py-2.5">
                      Current Spend
                    </th>
                    <th scope="col" className="px-3.5 py-2.5">
                      Current Customers
                    </th>
                    <th scope="col" className="px-3.5 py-2.5">
                      Driver CPC / CVR
                    </th>
                    <th scope="col" className="px-3.5 py-2.5">
                      SQL vs Decimal Audit
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {rows.map((r) => (
                    <tr key={r.dimension_key} className="hover:bg-slate-900/40">
                      <th
                        scope="row"
                        className="px-3.5 py-2.5 font-semibold text-white"
                      >
                        {r.dimension_key}
                      </th>
                      <td data-col="2" className="px-3.5 py-2.5 text-slate-300">
                        {r.previous_display}
                      </td>
                      <td
                        data-col="3"
                        className="px-3.5 py-2.5 font-mono font-semibold text-emerald-300"
                      >
                        {r.current_display}
                      </td>
                      <td data-col="4" className="px-3.5 py-2.5 font-mono">
                        {r.pct_change !== null
                          ? `${Number(r.pct_change) >= 0 ? "+" : ""}${
                              r.pct_change
                            }%`
                          : "—"}
                      </td>
                      <td data-col="5" className="px-3.5 py-2.5 font-mono">
                        ${Number(r.cur_spend_usd).toLocaleString()}
                      </td>
                      <td data-col="6" className="px-3.5 py-2.5 font-mono">
                        {Number(r.cur_new_customers).toLocaleString()}
                      </td>
                      <td className="px-3.5 py-2.5 font-mono text-slate-300">
                        CPC: ${r.current_drivers?.cpc ?? "N/A"} | CVR:{" "}
                        {r.current_drivers?.cvr_pct ?? "N/A"}%
                      </td>
                      <td className="px-3.5 py-2.5">
                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                            r.sql_matched_audit
                              ? "bg-emerald-500/15 text-emerald-300"
                              : "bg-rose-500/20 text-rose-300"
                          }`}
                        >
                          {r.sql_matched_audit ? "EXACT MATCH" : "MISMATCH"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {report.sections.map((s: any, idx: number) => (
              <div
                key={idx}
                className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"
              >
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-white">
                    {s.heading}
                  </h3>
                  {s.highlight_metric && (
                    <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-xs text-emerald-300">
                      {s.highlight_metric}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-xs leading-relaxed text-slate-300">
                  {s.body}
                </p>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <h2 className="text-sm font-semibold text-white">
              Claim Validator Audit ({report.claims.length} Grounded Claims)
            </h2>
            <div className="mt-3 space-y-2">
              {report.claims.map((c: any) => (
                <div
                  key={c.claim_id}
                  className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-slate-800/80 bg-slate-950/60 p-3 text-xs"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[11px] text-slate-400">
                        {c.claim_id}
                      </span>
                      <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-semibold text-slate-300">
                        {c.claim_type}
                      </span>
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                          c.support_status === "SUPPORTED"
                            ? "bg-emerald-500/15 text-emerald-300"
                            : "bg-cyan-500/15 text-cyan-300"
                        }`}
                      >
                        {c.support_status}
                      </span>
                    </div>
                    <p className="text-slate-200">{c.statement}</p>
                    {c.qualification_note && (
                      <p className="text-[11px] italic text-cyan-300">
                        Note: {c.qualification_note}
                      </p>
                    )}
                  </div>
                  <span className="font-mono text-[11px] text-slate-400">
                    Source: {c.evidence_source}
                  </span>
                </div>
              ))}
            </div>

            {report.stripped_claims && report.stripped_claims.length > 0 && (
              <div className="mt-4 rounded-lg border border-rose-500/40 bg-rose-950/25 p-4">
                <div className="text-xs font-bold uppercase text-rose-300">
                  Stripped Unsupported / Hallucinated Claims (
                  {report.stripped_claims.length})
                </div>
                <div className="mt-2 space-y-2">
                  {report.stripped_claims.map((sc: any) => (
                    <div
                      key={sc.claim_id}
                      className="rounded border border-rose-500/30 bg-slate-950/70 p-2.5 text-xs"
                    >
                      <div className="font-mono text-rose-200 line-through">
                        “{sc.original_statement}”
                      </div>
                      <div className="mt-1 text-[11px] text-rose-300">
                        Reason: {sc.rejection_reason}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === "sql" && (
        <div className="space-y-4">
          {run.compiled_sql ? (
            <>
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h2 className="text-sm font-semibold text-white">
                      Deterministic SQLAlchemy Core CTE Query (Read-Only)
                    </h2>
                    <p className="text-xs text-slate-400">
                      Fingerprint:{" "}
                      <span className="font-mono text-emerald-400">
                        {run.compiled_sql.query_fingerprint}
                      </span>
                    </p>
                  </div>
                  <span className="rounded bg-emerald-500/15 px-2.5 py-1 text-xs font-semibold text-emerald-300">
                    SQLGlot AST Validated
                  </span>
                </div>
                <pre className="mt-4 overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 p-4 font-mono text-xs leading-relaxed text-emerald-300">
                  {run.compiled_sql.display_sql}
                </pre>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Bound Query Parameters
                  </h3>
                  <pre className="mt-2 overflow-x-auto rounded bg-slate-950 p-3 font-mono text-xs text-slate-200">
                    {JSON.stringify(run.compiled_sql.bound_params, null, 2)}
                  </pre>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    9-Point Query Policy & AST Checks
                  </h3>
                  <div className="mt-2 space-y-1.5">
                    {(run.query_validation?.checks || []).map((c: any) => (
                      <div
                        key={c.check_name}
                        className="flex items-center justify-between rounded bg-slate-950 px-2.5 py-1.5 text-xs"
                      >
                        <span className="font-mono text-slate-300">
                          {c.check_name}
                        </span>
                        <span
                          className={`font-semibold ${
                            c.passed ? "text-emerald-400" : "text-rose-400"
                          }`}
                        >
                          {c.passed ? "PASSED" : "FAILED"} — {c.detail}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-400">
              No SQL was compiled for this run because execution stopped at{" "}
              <span className="font-mono text-amber-300">
                {run.current_stage}
              </span>
              .
            </div>
          )}
        </div>
      )}

      {activeTab === "evidence" && (
        <div className="space-y-4">
          {bundle ? (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                <h3 className="text-xs font-semibold uppercase text-slate-400">
                  Metric Definition Used
                </h3>
                <div className="mt-2 space-y-1 text-xs">
                  <div>
                    ID:{" "}
                    <span className="font-mono text-white">
                      {bundle.metric_id}
                    </span>
                  </div>
                  <div>
                    Version:{" "}
                    <span className="font-mono text-emerald-300">
                      v{bundle.metric_version}
                    </span>
                  </div>
                  <div>
                    Current Window:{" "}
                    <span className="font-mono text-slate-200">
                      {bundle.current_period_label}
                    </span>
                  </div>
                  <div>
                    Comparison Window:{" "}
                    <span className="font-mono text-slate-200">
                      {bundle.comparison_period_label || "None"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                <h3 className="text-xs font-semibold uppercase text-slate-400">
                  Reconciliation Check
                </h3>
                <div className="mt-2 space-y-1 text-xs">
                  <div>
                    Status:{" "}
                    <span className="font-bold text-emerald-400">
                      {bundle.reconciliation.status}
                    </span>
                  </div>
                  <div>
                    Spend Diff:{" "}
                    <span className="font-mono">
                      ${bundle.reconciliation.spend_diff}
                    </span>
                  </div>
                  <div>
                    Customer Diff:{" "}
                    <span className="font-mono">
                      {bundle.reconciliation.customer_diff}
                    </span>
                  </div>
                  <div className="text-slate-400">
                    {bundle.reconciliation.detail}
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                <h3 className="text-xs font-semibold uppercase text-slate-400">
                  Freshness Watermark SLA
                </h3>
                <div className="mt-2 space-y-1 text-xs">
                  <div>
                    Status:{" "}
                    <span
                      className={`font-bold ${
                        bundle.freshness.certified_for_current_reporting
                          ? "text-emerald-400"
                          : "text-amber-400"
                      }`}
                    >
                      {bundle.freshness.status}
                    </span>
                  </div>
                  <div>
                    SLA Limit: {bundle.freshness.maximum_age_hours}h
                  </div>
                  {(bundle.freshness.sources || []).map((s: any) => (
                    <div key={s.source_name} className="font-mono text-[11px]">
                      {s.source_name}: {s.age_hours}h old (batch {s.batch_id})
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-400">
              No evidence bundle recorded for this run.
            </div>
          )}
        </div>
      )}

      {activeTab === "trace" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <h2 className="text-sm font-semibold text-white">
              Deterministic Orchestrator Step Waterfall
            </h2>
            <div className="mt-3 space-y-2">
              {(run.events || []).map((ev: any) => (
                <div
                  key={ev.sequence}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-slate-500">
                      #{ev.sequence}
                    </span>
                    <span className="font-semibold text-white">{ev.label}</span>
                    <span className="font-mono text-[11px] text-slate-400">
                      ({ev.component})
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-[11px] text-slate-400">
                      {ev.duration_ms} ms
                    </span>
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                        ev.status === "PASSED" || ev.status === "COMPLETED"
                          ? "bg-emerald-500/15 text-emerald-300"
                          : ev.status === "BLOCKED"
                          ? "bg-amber-500/20 text-amber-300"
                          : "bg-rose-500/20 text-rose-300"
                      }`}
                    >
                      {ev.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

