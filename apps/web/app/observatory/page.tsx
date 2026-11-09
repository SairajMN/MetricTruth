"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

export default function ExecutionObservatoryPage() {
  const [runs, setRuns] = useState<any[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string>("");
  const [runDetail, setRunDetail] = useState<any | null>(null);

  useEffect(() => {
    apiFetch("/analytics/runs?limit=25").then((res) => {
      const list = res.runs || [];
      setRuns(list);
      if (list.length > 0) {
        setSelectedRunId(list[0].run_id);
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedRunId) return;
    apiFetch(`/analytics/runs/${selectedRunId}`).then(setRunDetail);
  }, [selectedRunId]);

  const usage = runDetail?.usage;
  const events: any[] = runDetail?.events || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Execution Observatory
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Step-by-step agentic harness telemetry, token and cost ledger, cache
            hit tracking, and independent verification status.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="obs-run-select" className="text-xs text-slate-400">
            Inspect Run:
          </label>
          <select
            id="obs-run-select"
            value={selectedRunId}
            onChange={(e) => setSelectedRunId(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-white"
          >
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id} [{r.status}] — {r.question.slice(0, 45)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {runDetail && (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-6">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-[11px] text-slate-400">Input Tokens</div>
              <div className="mt-1 font-mono text-xl font-bold text-white">
                {usage?.input_tokens ?? 0}
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-[11px] text-slate-400">Output Tokens</div>
              <div className="mt-1 font-mono text-xl font-bold text-white">
                {usage?.output_tokens ?? 0}
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-[11px] text-slate-400">Cached Tokens</div>
              <div className="mt-1 font-mono text-xl font-bold text-cyan-300">
                {usage?.cached_tokens ?? 0}
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-[11px] text-slate-400">Model Calls</div>
              <div className="mt-1 font-mono text-xl font-bold text-white">
                {usage?.model_calls ?? 0} / {usage?.max_calls ?? 4}
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-[11px] text-slate-400">
                Execution Duration
              </div>
              <div className="mt-1 font-mono text-xl font-bold text-emerald-400">
                {runDetail.duration_ms} ms
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-[11px] text-slate-400">Actual API Cost</div>
              <div className="mt-1 font-mono text-xl font-bold text-emerald-300">
                ${Number(usage?.total_cost_usd ?? 0).toFixed(6)}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 rounded-xl border border-slate-800 bg-slate-900/60 p-5">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-white">
                  10-Component Pipeline Waterfall Trace
                </h2>
                <span className="font-mono text-xs text-slate-400">
                  {runDetail.run_id}
                </span>
              </div>

              <div className="mt-4 space-y-2.5">
                {events.map((ev) => (
                  <div
                    key={ev.sequence}
                    className="rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-800 font-mono text-[10px] text-slate-300">
                          {ev.sequence}
                        </span>
                        <span className="font-semibold text-white">
                          {ev.label}
                        </span>
                        <span className="font-mono text-[11px] text-slate-400">
                          {ev.component}
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
                    {ev.details && Object.keys(ev.details).length > 0 && (
                      <pre className="mt-2 overflow-x-auto rounded bg-slate-900/90 p-2 font-mono text-[11px] text-slate-300">
                        {JSON.stringify(ev.details, null, 2)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
                <h3 className="text-sm font-semibold text-white">
                  Component Model Invocations
                </h3>
                <div className="mt-3 space-y-2">
                  {(usage?.calls || []).map((c: any, i: number) => (
                    <div
                      key={i}
                      className="rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-emerald-300">
                          {c.component}
                        </span>
                        <span className="font-mono text-[11px] text-slate-400">
                          {c.duration_ms} ms
                        </span>
                      </div>
                      <div className="mt-1 font-mono text-[11px] text-slate-300">
                        Model: {c.model_name}
                      </div>
                      <div className="mt-1 flex justify-between text-[11px] text-slate-400">
                        <span>
                          In: {c.input_tokens} / Out: {c.output_tokens}
                        </span>
                        <span>${Number(c.cost_usd).toFixed(6)}</span>
                      </div>
                    </div>
                  ))}
                  {(!usage?.calls || usage.calls.length === 0) && (
                    <div className="text-xs text-slate-400">
                      0 model calls invoked (deterministic path or cache hit).
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
                <h3 className="text-sm font-semibold text-white">
                  Verification Summary
                </h3>
                <div className="mt-2 space-y-1.5 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Pipeline Status:</span>
                    <span className="font-mono font-bold text-white">
                      {runDetail.status}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Audit Bundle:</span>
                    <span className="font-mono text-emerald-300">
                      {runDetail.audit_bundle?.overall_status || "N/A"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Cache Hit:</span>
                    <span className="font-mono text-cyan-300">
                      {runDetail.cache_hit ? "TRUE" : "FALSE"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

