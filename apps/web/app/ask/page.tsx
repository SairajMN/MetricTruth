"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Circle,
  HelpCircle,
  Loader2,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

const SUGGESTED_QUESTIONS = [
  {
    label: "Compare campaign CAC (Nov vs Oct) + Driver Analysis",
    question:
      "Why did our customer acquisition cost increase this month compared with last month? Identify which campaigns are responsible.",
  },
  {
    label: "Ambiguity Check (Unqualified CAC)",
    question: "Why did our CAC increase?",
  },
  {
    label: "Identify conversion-rate changes",
    question:
      "What caused our conversion rate to decline in November 2026 compared with last month?",
  },
  {
    label: "Highest-value acquisition channel (ROAS)",
    question:
      "Which acquisition channel generates the highest-value return on ad spend in November 2026?",
  },
  {
    label: "Zero-Customer Campaign (Sept Display)",
    question: "What was our paid CAC by campaign in September 2026?",
  },
  {
    label: "Unapproved Metric Gate (Block Test)",
    question: "Analyze imaginary_customer_quality_score by campaign.",
  },
];

const PIPELINE_STEPS = [
  "Understanding business question",
  "Resolving certified metrics",
  "Mapping approved data relationships",
  "Building analytical plan",
  "Compiling deterministic SQL",
  "Validating query & permissions",
  "Executing read-only SQL",
  "Auditing numerical results",
  "Generating explanation",
  "Verifying analytical claims",
];

const METRIC_OPTION_MAP: Record<string, string> = {
  "Paid CAC": "paid_customer_acquisition_cost",
  "Blended CAC": "blended_customer_acquisition_cost",
  "Fully Loaded CAC": "fully_loaded_customer_acquisition_cost",
};

export default function AskMetricTruthPage() {
  const router = useRouter();
  const [question, setQuestion] = useState(SUGGESTED_QUESTIONS[0].question);
  const [injectHallucination, setInjectHallucination] = useState(false);
  const [running, setRunning] = useState(false);
  const [activeStepIdx, setActiveStepIdx] = useState(-1);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const executeInvestigation = async (
    qText: string,
    metricOverride?: string
  ) => {
    setRunning(true);
    setError(null);
    setResult(null);
    setActiveStepIdx(0);

    const stepTimer = setInterval(() => {
      setActiveStepIdx((prev) =>
        prev < PIPELINE_STEPS.length - 1 ? prev + 1 : prev
      );
    }, 90);

    try {
      const payload: Record<string, any> = {
        question: qText,
        use_cache: !injectHallucination,
      };
      if (metricOverride) {
        payload.metric_override = metricOverride;
      }
      if (injectHallucination) {
        payload.injected_unverified_claim =
          "Search CAC increased because competitors raised their bidding budgets.";
      }

      const res = await apiFetch("/analytics/ask", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      clearInterval(stepTimer);
      setActiveStepIdx(PIPELINE_STEPS.length);
      setResult(res);
    } catch (err: any) {
      clearInterval(stepTimer);
      setError(err.message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <div>
        <span className="text-xs font-semibold uppercase tracking-wider text-indigo-400">
          Natural Language Analytics
        </span>
        <h1 className="text-2xl lg:text-3xl font-bold text-white mt-1">
          Ask MetricTruth
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Ask a business question in plain English. MetricTruth resolves
          certified definitions, compiles safe SQL, and audits every calculation
          independently.
        </p>
      </div>

      {/* Question Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          executeInvestigation(question);
        }}
        className="p-6 rounded-xl bg-[#0f172a] border border-slate-800 space-y-4"
      >
        <label
          htmlFor="nl-question-input"
          className="block text-xs font-semibold uppercase tracking-wider text-slate-300"
        >
          Business Question
        </label>
        <textarea
          id="nl-question-input"
          rows={3}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a business question... e.g. Why did our CAC increase this month?"
          className="w-full rounded-lg bg-slate-950 border border-slate-700 p-3.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
        />

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-1">
          <label className="inline-flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={injectHallucination}
              onChange={(e) => setInjectHallucination(e.target.checked)}
              className="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500"
            />
            <span>
              Demo Mode: Inject unverified causal claim (&ldquo;Competitors
              increased bids&rdquo;) to test Claim Validator
            </span>
          </label>

          <button
            type="submit"
            disabled={running || !question.trim()}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold transition-colors"
          >
            {running ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Investigating...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Run Certified Investigation</span>
              </>
            )}
          </button>
        </div>
      </form>

      {/* Suggested Questions */}
      <div className="space-y-2.5">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Suggested Investigations &amp; Guardrail Scenarios
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
          {SUGGESTED_QUESTIONS.map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => {
                setQuestion(item.question);
                executeInvestigation(item.question);
              }}
              className="text-left p-3 rounded-lg bg-slate-900/80 hover:bg-slate-800/80 border border-slate-800 transition-colors"
            >
              <p className="text-xs font-semibold text-indigo-300">
                {item.label}
              </p>
              <p className="text-xs text-slate-300 mt-1 line-clamp-2">
                &ldquo;{item.question}&rdquo;
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Live Execution Progress Stepper */}
      {(running || result) && (
        <div className="p-6 rounded-xl bg-[#0f172a] border border-slate-800 space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
              Deterministic Orchestrator Execution Progress
            </h2>
            {result && (
              <span className="text-xs font-mono text-slate-400">
                Run ID: {result.run_id} ({result.duration_ms}ms)
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {PIPELINE_STEPS.map((label, idx) => {
              const matchedEvent = result?.events?.find(
                (e: any) => e.label === label
              );
              const isCompleted = matchedEvent
                ? matchedEvent.status === "COMPLETED" ||
                  matchedEvent.status === "PASSED"
                : !running && idx < activeStepIdx;
              const isFailed =
                matchedEvent &&
                (matchedEvent.status === "BLOCKED" ||
                  matchedEvent.status === "FAILED");
              const isCurrent = running && idx === activeStepIdx;

              return (
                <div
                  key={label}
                  className={`flex items-center justify-between p-2.5 rounded-lg border text-xs ${
                    isFailed
                      ? "bg-rose-950/30 border-rose-700/50 text-rose-200"
                      : isCompleted
                      ? "bg-emerald-950/20 border-emerald-800/40 text-emerald-200"
                      : isCurrent
                      ? "bg-indigo-950/30 border-indigo-600/50 text-indigo-200"
                      : "bg-slate-900/40 border-slate-800/60 text-slate-500"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    {isFailed ? (
                      <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
                    ) : isCompleted ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    ) : isCurrent ? (
                      <Loader2 className="w-4 h-4 text-indigo-400 animate-spin shrink-0" />
                    ) : (
                      <Circle className="w-4 h-4 text-slate-600 shrink-0" />
                    )}
                    <span>{label}</span>
                  </div>
                  {matchedEvent && (
                    <span className="font-mono text-[11px] opacity-80">
                      {matchedEvent.status}
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Outcome Branch: Clarification Required */}
          {result?.status === "CLARIFICATION_REQUIRED" &&
            result.clarification && (
              <div className="p-5 rounded-xl bg-amber-950/30 border border-amber-600/50 space-y-3">
                <div className="flex items-center gap-2 text-amber-300 font-semibold text-sm">
                  <HelpCircle className="w-4 h-4" />
                  <span>Clarification Required — Ambiguity Detected</span>
                </div>
                <p className="text-sm text-slate-200">
                  {result.clarification.question}
                </p>
                <div className="flex flex-wrap gap-2 pt-1">
                  {result.clarification.options.map((opt: string) => (
                    <button
                      key={opt}
                      type="button"
                      onClick={() => {
                        const mappedId = METRIC_OPTION_MAP[opt];
                        if (mappedId) {
                          executeInvestigation(
                            `${question} (${opt})`,
                            mappedId
                          );
                        } else {
                          executeInvestigation(`${question} for ${opt}`);
                        }
                      }}
                      className="px-3.5 py-2 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-200 text-xs font-semibold transition-colors"
                    >
                      Select: {opt}
                    </button>
                  ))}
                </div>
              </div>
            )}

          {/* Outcome Branch: Blocked or Failed */}
          {(result?.status === "BLOCKED" || result?.status === "FAILED") && (
            <div className="p-5 rounded-xl bg-rose-950/40 border border-rose-700/60 space-y-2">
              <div className="flex items-center gap-2 text-rose-300 font-semibold text-sm">
                <AlertCircle className="w-4 h-4" />
                <span>
                  EXECUTION {result.status} — No Unverified Numbers Generated
                </span>
              </div>
              <p className="text-sm text-slate-200 font-mono">
                {result.failure_reason}
              </p>
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => router.push(`/runs/${result.run_id}`)}
                  className="text-xs text-rose-300 underline hover:text-white"
                >
                  Inspect Full Security &amp; Execution Trace →
                </button>
              </div>
            </div>
          )}

          {/* Outcome Branch: Completed */}
          {result?.status === "COMPLETED" && (
            <div className="p-5 rounded-xl bg-emerald-950/30 border border-emerald-700/50 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
                  Verification Status: {result.audit_bundle?.overall_status}
                </p>
                <p className="text-base font-bold text-white mt-0.5">
                  {result.report?.overall_finding}
                </p>
                {result.report?.stripped_claims?.length > 0 && (
                  <p className="text-xs text-amber-300 mt-1">
                    Claim Validator stripped{" "}
                    {result.report.stripped_claims.length} unsupported causal
                    claim(s) from the final report.
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => router.push(`/runs/${result.run_id}`)}
                className="shrink-0 inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-colors"
              >
                <span>Open Full Investigation Report</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-700 text-rose-200 text-sm">
          {error}
        </div>
      )}
    </div>
  );
}

