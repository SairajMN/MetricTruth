"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

export default function EvaluationCenterPage() {
  const [suite, setSuite] = useState<any | null>(null);
  const [running, setRunning] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");
  const [error, setError] = useState<string | null>(null);

  async function loadResults() {
    try {
      const res = await apiFetch("/evaluations/results");
      if (res.latest) {
        setSuite(res.latest);
      }
    } catch (err: any) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadResults();
  }, []);

  async function handleRunSuite() {
    setRunning(true);
    setError(null);
    try {
      const res = await apiFetch("/evaluations/run", { method: "POST" });
      setSuite(res);
    } catch (err: any) {
      setError(err.message || "Evaluation run failed");
    } finally {
      setRunning(false);
    }
  }

  const cases: any[] = suite?.cases || [];
  const categories = [
    "ALL",
    ...Array.from(new Set(cases.map((c) => c.category))),
  ];
  const filteredCases =
    categoryFilter === "ALL"
      ? cases
      : cases.filter((c) => c.category === categoryFilter);

  const pct = (v: number | undefined) =>
    v !== undefined ? `${(Number(v) * 100).toFixed(1)}%` : "—";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Evaluation Center (55-Scenario Golden Benchmark)
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Automated grading across metric resolution, numerical accuracy,
            ambiguity abstention, stale-data warnings, SQL injection blocking,
            and claim grounding.
          </p>
        </div>

        <button
          type="button"
          onClick={handleRunSuite}
          disabled={running}
          className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 shadow-sm hover:bg-emerald-400 disabled:opacity-50"
        >
          {running
            ? "Running 55 Golden Scenarios..."
            : "Run 55-Case Golden Evaluation"}
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-950/30 p-4 text-xs text-rose-200">
          {error}
        </div>
      )}

      {suite && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/15 p-4">
              <div className="text-xs text-slate-400">Suite Pass Rate</div>
              <div className="mt-1 font-mono text-2xl font-bold text-emerald-400">
                {suite.passed_cases} / {suite.total_cases}
              </div>
              <div className="text-[11px] text-slate-400">
                Run ID: {suite.eval_run_id}
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs text-slate-400">
                Metric Selection Accuracy
              </div>
              <div className="mt-1 font-mono text-2xl font-bold text-white">
                {pct(suite.metric_selection_accuracy)}
              </div>
              <div className="text-[11px] text-emerald-400">Target: ≥ 95%</div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs text-slate-400">Numerical Accuracy</div>
              <div className="mt-1 font-mono text-2xl font-bold text-white">
                {pct(suite.numerical_accuracy)}
              </div>
              <div className="text-[11px] text-emerald-400">Target: 100%</div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs text-slate-400">Grounded Claim Rate</div>
              <div className="mt-1 font-mono text-2xl font-bold text-white">
                {pct(suite.grounded_claim_rate)}
              </div>
              <div className="text-[11px] text-emerald-400">Target: 100%</div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs text-slate-400">Security Pass Rate</div>
              <div className="mt-1 font-mono text-2xl font-bold text-emerald-400">
                {pct(suite.security_pass_rate)}
              </div>
              <div className="text-[11px] text-slate-400">
                Abstention: {pct(suite.abstention_accuracy)} | Avg{" "}
                {suite.avg_latency_ms} ms
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <h2
                id="eval-table-heading"
                className="text-sm font-semibold text-white"
              >
                Scenario-by-Scenario Grade Breakdown ({filteredCases.length})
              </h2>
              <div className="flex flex-wrap gap-1.5">
                {categories.map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setCategoryFilter(cat)}
                    className={`rounded px-2.5 py-1 text-[11px] font-medium ${
                      categoryFilter === cat
                        ? "bg-emerald-500 text-slate-950 font-semibold"
                        : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>

            <div
              className="table-wrapper rounded-lg border border-slate-800"
              tabIndex={0}
              role="region"
              aria-labelledby="eval-table-heading"
              style={
                {
                  "--label-2": "'Category'",
                  "--label-3": "'Question'",
                  "--label-4": "'Expected Status'",
                  "--label-5": "'Actual Result'",
                  "--label-6": "'Grade'",
                } as React.CSSProperties
              }
            >
              <table className="text-left text-xs">
                <thead className="bg-slate-950 text-slate-400">
                  <tr>
                    <th scope="col" className="px-3 py-2.5">
                      ID
                    </th>
                    <th scope="col" className="px-3 py-2.5">
                      Category
                    </th>
                    <th scope="col" className="px-3 py-2.5">
                      Question
                    </th>
                    <th scope="col" className="px-3 py-2.5">
                      Status (Exp / Act)
                    </th>
                    <th scope="col" className="px-3 py-2.5">
                      Result (Exp / Act)
                    </th>
                    <th scope="col" className="px-3 py-2.5">
                      Grade
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {filteredCases.map((c) => (
                    <tr key={c.test_id} className="hover:bg-slate-900/40">
                      <th
                        scope="row"
                        className="px-3 py-2.5 font-mono text-white"
                      >
                        {c.test_id}
                      </th>
                      <td data-col="2" className="px-3 py-2.5">
                        <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-cyan-300">
                          {c.category}
                        </span>
                      </td>
                      <td
                        data-col="3"
                        className="max-w-md px-3 py-2.5 text-slate-200"
                      >
                        {c.question}
                      </td>
                      <td data-col="4" className="px-3 py-2.5 font-mono">
                        {c.expected_status} / {c.actual_status}
                      </td>
                      <td data-col="5" className="px-3 py-2.5 font-mono">
                        {c.expected_result ?? "—"} / {c.actual_result ?? "—"}
                      </td>
                      <td data-col="6" className="px-3 py-2.5">
                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                            c.passed
                              ? "bg-emerald-500/15 text-emerald-300"
                              : "bg-rose-500/20 text-rose-300"
                          }`}
                        >
                          {c.passed ? "PASS" : "FAIL"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

