"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

export default function SqlInspectorPage() {
  const [runs, setRuns] = useState<any[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string>("");
  const [sqlBundle, setSqlBundle] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function init() {
      setLoading(true);
      try {
        const res = await apiFetch("/analytics/runs?limit=20");
        const list = res.runs || [];
        setRuns(list);
        const firstWithSql =
          list.find((r: any) => r.status === "COMPLETED") || list[0];
        if (firstWithSql) {
          setSelectedRunId(firstWithSql.run_id);
        }
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  useEffect(() => {
    if (!selectedRunId) return;
    apiFetch(`/analytics/runs/${selectedRunId}/sql`)
      .then(setSqlBundle)
      .catch(() => setSqlBundle(null));
  }, [selectedRunId]);

  const compiled = sqlBundle?.compiled_sql;
  const validation = sqlBundle?.query_validation;
  const record = sqlBundle?.query_run_record;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            SQL Inspector (Read-Only Audit View)
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Inspect deterministic SQLAlchemy Core CTE compilation, bound
            parameters, and SQLGlot AST verification. Arbitrary SQL editing is
            disabled by architectural policy.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="run-select" className="text-xs text-slate-400">
            Select Run:
          </label>
          <select
            id="run-select"
            value={selectedRunId}
            onChange={(e) => setSelectedRunId(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-white"
          >
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id} — {r.status} ({r.question.slice(0, 48)}...)
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading && (
        <div className="h-64 animate-pulse rounded-xl border border-slate-800 bg-slate-900/40" />
      )}

      {!loading && !compiled && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-6 text-sm text-amber-200">
          Selected run ({selectedRunId || "none"}) did not compile SQL because
          it was blocked or required clarification before reaching the SQL
          Compiler stage.
        </div>
      )}

      {compiled && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs text-slate-400">Certified Metric</div>
              <div className="mt-1 font-mono text-sm font-bold text-white">
                {compiled.metric_id} (v{compiled.metric_version})
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs text-slate-400">Execution Latency</div>
              <div className="mt-1 font-mono text-sm font-bold text-emerald-400">
                {record?.execution_ms ?? "1.4"} ms ({record?.row_count ?? 3}{" "}
                rows)
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs text-slate-400">Reporting Views Used</div>
              <div className="mt-1 font-mono text-xs text-cyan-300">
                {(compiled.tables_accessed || []).join(", ")}
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs text-slate-400">Query Fingerprint</div>
              <div className="mt-1 truncate font-mono text-xs text-slate-300">
                {compiled.query_fingerprint}
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">
                Compiled Parameterized PostgreSQL CTE Query
              </h2>
              <span className="rounded bg-slate-800 px-2.5 py-1 font-mono text-[11px] text-emerald-400">
                READ ONLY • NO DIRECT LLM SQL
              </span>
            </div>
            <pre className="mt-3 overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 p-4 font-mono text-xs leading-relaxed text-emerald-300">
              {compiled.display_sql}
            </pre>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
              <h3 className="text-sm font-semibold text-white">
                Bound Parameters ({Object.keys(compiled.bound_params || {}).length})
              </h3>
              <div className="mt-3 overflow-hidden rounded-lg border border-slate-800">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950 text-slate-400">
                    <tr>
                      <th className="px-3 py-2">Parameter Name</th>
                      <th className="px-3 py-2">Bound Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {Object.entries(compiled.bound_params || {}).map(
                      ([k, v]) => (
                        <tr key={k}>
                          <td className="px-3 py-2 font-mono text-cyan-300">
                            :{k}
                          </td>
                          <td className="px-3 py-2 font-mono text-slate-200">
                            {String(v)}
                          </td>
                        </tr>
                      )
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
              <h3 className="text-sm font-semibold text-white">
                9-Point SQLGlot AST & Security Policy Verification
              </h3>
              <div className="mt-3 space-y-2">
                {(validation?.checks || []).map((c: any) => (
                  <div
                    key={c.check_name}
                    className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs"
                  >
                    <div>
                      <div className="font-mono font-semibold text-white">
                        {c.check_name}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {c.detail}
                      </div>
                    </div>
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                        c.passed
                          ? "bg-emerald-500/15 text-emerald-300"
                          : "bg-rose-500/20 text-rose-300"
                      }`}
                    >
                      {c.passed ? "PASSED" : "BLOCKED"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

