"use client";

import React, { useEffect, useRef, useState } from "react";
import { apiFetch } from "../../lib/api";

export default function MetricRegistryPage() {
  const [metrics, setMetrics] = useState<any[]>([]);
  const [sources, setSources] = useState<any[]>([]);
  const [selectedMetric, setSelectedMetric] = useState<any | null>(null);
  const [statusMessage, setStatusMessage] = useState<{
    type: "ok" | "err";
    text: string;
  } | null>(null);

  const metricDialogRef = useRef<HTMLDialogElement>(null);
  const uploadDialogRef = useRef<HTMLDialogElement>(null);
  const [uploadSource, setUploadSource] = useState("daily_campaign_performance");
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  async function loadAll() {
    const [mRes, sRes] = await Promise.all([
      apiFetch("/metrics"),
      apiFetch("/data/sources"),
    ]);
    setMetrics(mRes.metrics || []);
    setSources(sRes.sources || []);
  }

  useEffect(() => {
    loadAll();
  }, []);

  function openMetricModal(m: any) {
    setSelectedMetric(m);
    metricDialogRef.current?.showModal();
  }

  async function handleApproveMetric(metricId: string) {
    setStatusMessage(null);
    try {
      await apiFetch(`/metrics/${metricId}/approve`, { method: "POST" });
      setStatusMessage({
        type: "ok",
        text: `Metric '${metricId}' promoted to APPROVED and version incremented.`,
      });
      await loadAll();
    } catch (err: any) {
      setStatusMessage({
        type: "err",
        text: `Approval blocked: ${err.message}`,
      });
    }
  }

  async function handleSimulateFreshness(ageHours: number) {
    setStatusMessage(null);
    try {
      await apiFetch("/data/simulate-freshness", {
        method: "POST",
        body: JSON.stringify({
          source_name: "daily_campaign_performance",
          age_hours: ageHours,
        }),
      });
      setStatusMessage({
        type: "ok",
        text:
          ageHours > 24
            ? `Simulated stale watermark (${ageHours}h old) on daily_campaign_performance. Subsequent reports will be marked NOT CERTIFIED.`
            : "Restored fresh watermark (0h old) on daily_campaign_performance.",
      });
      await loadAll();
    } catch (err: any) {
      setStatusMessage({
        type: "err",
        text: `Watermark update blocked: ${err.message}`,
      });
    }
  }

  async function handleCsvUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!uploadFile) return;
    setStatusMessage(null);
    try {
      const fd = new FormData();
      fd.append("source_name", uploadSource);
      fd.append("file", uploadFile);
      const res = await apiFetch("/data/upload", {
        method: "POST",
        body: fd,
      });
      uploadDialogRef.current?.close();
      setStatusMessage({
        type: "ok",
        text: `Ingested ${res.file_name}: ${res.accepted_rows} accepted, ${res.duplicate_rows} duplicates, ${res.rejected_rows} rejected.`,
      });
      await loadAll();
    } catch (err: any) {
      setStatusMessage({
        type: "err",
        text: `CSV Upload failed: ${err.message}`,
      });
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Certified Metric Registry & Data Governance
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Authoritative semantic layer definitions, role-gated approval
            workflows, and freshness SLA watermarks.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => handleSimulateFreshness(48)}
            className="rounded-lg border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs font-semibold text-amber-300 hover:bg-amber-900/40"
          >
            Simulate 48h Stale Watermark
          </button>
          <button
            type="button"
            onClick={() => handleSimulateFreshness(0)}
            className="rounded-lg border border-emerald-500/40 bg-emerald-950/30 px-3 py-2 text-xs font-semibold text-emerald-300 hover:bg-emerald-900/40"
          >
            Restore Fresh Watermark (0h)
          </button>
          <button
            type="button"
            onClick={() => uploadDialogRef.current?.showModal()}
            className="rounded-lg bg-emerald-500 px-3.5 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400"
          >
            Upload CSV Batch
          </button>
        </div>
      </div>

      {statusMessage && (
        <div
          className={`rounded-xl border p-4 text-xs font-medium ${
            statusMessage.type === "ok"
              ? "border-emerald-500/40 bg-emerald-950/25 text-emerald-200"
              : "border-rose-500/40 bg-rose-950/25 text-rose-200"
          }`}
        >
          {statusMessage.text}
        </div>
      )}

      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <h2
          id="registry-table-heading"
          className="mb-3 text-sm font-semibold text-white"
        >
          Registered Business Metrics ({metrics.length})
        </h2>
        <div
          className="table-wrapper rounded-lg border border-slate-800"
          tabIndex={0}
          role="region"
          aria-labelledby="registry-table-heading"
          style={
            {
              "--label-2": "'Formula'",
              "--label-3": "'Dimensions'",
              "--label-4": "'SLA'",
              "--label-5": "'Status'",
              "--label-6": "'Actions'",
            } as React.CSSProperties
          }
        >
          <table className="text-left text-xs">
            <thead className="bg-slate-950 text-slate-400">
              <tr>
                <th scope="col" className="px-3.5 py-2.5">
                  Metric Name & ID
                </th>
                <th scope="col" className="px-3.5 py-2.5">
                  Certified Formula
                </th>
                <th scope="col" className="px-3.5 py-2.5">
                  Dimensions
                </th>
                <th scope="col" className="px-3.5 py-2.5">
                  Freshness SLA
                </th>
                <th scope="col" className="px-3.5 py-2.5">
                  Status / Version
                </th>
                <th scope="col" className="px-3.5 py-2.5">
                  Governance Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {metrics.map((m) => (
                <tr key={m.metric_id} className="hover:bg-slate-900/40">
                  <th scope="row" className="px-3.5 py-3 font-medium text-white">
                    <div>{m.name}</div>
                    <div className="font-mono text-[11px] text-slate-400">
                      {m.metric_id}
                    </div>
                  </th>
                  <td data-col="2" className="px-3.5 py-3 font-mono text-cyan-300">
                    {m.formula.numerator} / {m.formula.denominator}
                  </td>
                  <td data-col="3" className="px-3.5 py-3 text-slate-300">
                    {(m.dimensions || []).join(", ")}
                  </td>
                  <td data-col="4" className="px-3.5 py-3 font-mono">
                    ≤ {m.freshness.maximum_age_hours}h ({m.owner})
                  </td>
                  <td data-col="5" className="px-3.5 py-3">
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase ${
                        m.status === "approved"
                          ? "bg-emerald-500/15 text-emerald-300"
                          : "bg-amber-500/20 text-amber-300"
                      }`}
                    >
                      {m.status} • v{m.version}
                    </span>
                  </td>
                  <td data-col="6" className="px-3.5 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => openMetricModal(m)}
                        className="rounded border border-slate-700 bg-slate-800 px-2.5 py-1 text-[11px] text-slate-200 hover:bg-slate-700"
                      >
                        Inspect Spec
                      </button>
                      {m.status !== "approved" && (
                        <button
                          type="button"
                          onClick={() => handleApproveMetric(m.metric_id)}
                          className="rounded bg-emerald-500 px-2.5 py-1 text-[11px] font-semibold text-slate-950 hover:bg-emerald-400"
                        >
                          Approve (Admin)
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <h2 className="mb-3 text-sm font-semibold text-white">
          Data Source Ingestion Audit & Watermarks
        </h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {sources.slice(0, 6).map((s) => (
            <div
              key={s.batch_id}
              className="rounded-lg border border-slate-800 bg-slate-950 p-3.5 text-xs"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono font-semibold text-white">
                  {s.source_name}
                </span>
                <span className="font-mono text-[11px] text-emerald-400">
                  {s.batch_id}
                </span>
              </div>
              <div className="mt-1.5 flex flex-wrap gap-3 text-[11px] text-slate-400">
                <span>Accepted: {s.accepted_rows}</span>
                <span>Duplicates: {s.duplicate_rows}</span>
                <span>Rejected: {s.rejected_rows}</span>
                <span>Watermark: {s.freshness_watermark}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Native <dialog> modal per modern-web-guidance: no role="dialog" or aria-modal */}
      <dialog
        ref={metricDialogRef}
        aria-labelledby="metric-modal-title"
        onClick={(e) => {
          if (e.target === e.currentTarget) e.currentTarget.close();
        }}
        className="w-full max-w-2xl rounded-xl border border-slate-700 bg-slate-900 p-6 text-slate-100 shadow-2xl"
      >
        {selectedMetric && (
          <div className="space-y-4">
            <div className="flex items-start justify-between gap-4 border-b border-slate-800 pb-3">
              <div>
                <h2 id="metric-modal-title" className="text-lg font-bold text-white">
                  {selectedMetric.name} (v{selectedMetric.version})
                </h2>
                <p className="font-mono text-xs text-emerald-400">
                  {selectedMetric.metric_id}
                </p>
              </div>
              <form method="dialog">
                <button
                  type="submit"
                  className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1 text-xs text-slate-300 hover:bg-slate-700"
                >
                  Close
                </button>
              </form>
            </div>

            <p className="text-xs leading-relaxed text-slate-300">
              {selectedMetric.description}
            </p>

            <pre className="max-h-80 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-3 font-mono text-xs text-cyan-300">
              {JSON.stringify(selectedMetric, null, 2)}
            </pre>
          </div>
        )}
      </dialog>

      <dialog
        ref={uploadDialogRef}
        aria-labelledby="upload-modal-title"
        onClick={(e) => {
          if (e.target === e.currentTarget) e.currentTarget.close();
        }}
        className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-900 p-6 text-slate-100 shadow-2xl"
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 id="upload-modal-title" className="text-base font-bold text-white">
              Upload & Validate Synthetic CSV Batch
            </h2>
            <form method="dialog">
              <button
                type="submit"
                className="rounded border border-slate-700 px-2.5 py-1 text-xs text-slate-300"
              >
                Cancel
              </button>
            </form>
          </div>

          <form onSubmit={handleCsvUpload} className="space-y-4 text-xs">
            <div>
              <label className="block text-slate-400">Target Dataset</label>
              <select
                value={uploadSource}
                onChange={(e) => setUploadSource(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
              >
                <option value="campaigns">campaigns</option>
                <option value="daily_campaign_performance">
                  daily_campaign_performance
                </option>
                <option value="customer_acquisitions">
                  customer_acquisitions
                </option>
                <option value="expenses">expenses</option>
              </select>
            </div>
            <div>
              <label className="block text-slate-400">CSV File</label>
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-slate-300"
              />
            </div>
            <button
              type="submit"
              disabled={!uploadFile}
              className="w-full rounded-lg bg-emerald-500 py-2 font-semibold text-slate-950 disabled:opacity-40"
            >
              Validate & Ingest CSV
            </button>
          </form>
        </div>
      </dialog>
    </div>
  );
}

