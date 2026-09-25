"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  Award,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  Cpu,
  Database,
  DollarSign,
  Gauge,
  Layers,
  Loader2,
  PlayCircle,
  RotateCcw,
  Sparkles,
  Trophy,
  Zap,
} from "lucide-react";
import Header from "@/components/Header";
import { getEvalRun } from "@/lib/api";
import { EvalRunResult, EvalScoreSchema, ModelResponseSchema } from "@/types/api";

export default function RunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params?.run_id as string;

  const [run, setRun] = useState<EvalRunResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState(false);
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [copiedOutputModel, setCopiedOutputModel] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    getEvalRun(runId)
      .then((data) => {
        if (isMounted) setRun(data);
      })
      .catch((err: unknown) => {
        if (isMounted) {
          const msg = err instanceof Error ? err.message : String(err);
          setError(msg);
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [runId]);

  const handleCopyId = () => {
    if (runId) {
      navigator.clipboard.writeText(runId);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    }
  };

  const handleCopyPrompt = () => {
    if (run?.prompt) {
      navigator.clipboard.writeText(run.prompt);
      setCopiedPrompt(true);
      setTimeout(() => setCopiedPrompt(false), 2000);
    }
  };

  const handleCopyOutput = (modelId: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedOutputModel(modelId);
    setTimeout(() => setCopiedOutputModel(null), 2000);
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
        <p className="text-sm text-slate-400">Loading evaluation run report...</p>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="space-y-6">
        <Header title="Run Not Found" description="The requested evaluation run could not be retrieved." />
        <div className="bg-rose-950/30 border border-rose-500/40 rounded-2xl p-6 text-center max-w-lg mx-auto space-y-4">
          <AlertCircle className="w-10 h-10 text-rose-400 mx-auto" />
          <h3 className="text-base font-semibold text-white">Failed to Load Run</h3>
          <p className="text-xs text-rose-300">{error || "Run not found or database unreachable."}</p>
          <div className="pt-2 flex items-center justify-center gap-3">
            <Link
              href="/history"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back to History
            </Link>
            <button
              onClick={() => router.refresh()}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" /> Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Map scores by model_id for fast lookup
  const scoresByModel: Record<string, EvalScoreSchema> = {};
  run.scores?.forEach((s) => {
    scoresByModel[s.model_id] = s;
  });

  return (
    <div className="space-y-8">
      {/* Top Navigation & Action Row */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link
            href="/history"
            className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-white">Evaluation Run</h1>
              <button
                onClick={handleCopyId}
                className="inline-flex items-center gap-1 font-mono text-xs text-slate-400 bg-slate-900/90 border border-slate-800 px-2 py-0.5 rounded hover:text-white transition-colors"
              >
                <span>{runId.slice(0, 8)}...</span>
                {copiedId ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              </button>
              <span
                className={`text-[11px] font-mono px-2 py-0.5 rounded-full border ${
                  run.status === "completed"
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                    : run.status === "running"
                    ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/30"
                    : "bg-rose-500/10 text-rose-400 border-rose-500/30"
                }`}
              >
                {run.status.toUpperCase()}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Task: <span className="font-semibold text-slate-200 capitalize">{run.task_type}</span> &bull;{" "}
              {new Date(run.created_at).toLocaleString()}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href={`/eval/new?prompt=${encodeURIComponent(run.prompt)}&task_type=${run.task_type}`}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20 transition-all hover:scale-105"
          >
            <PlayCircle className="w-3.5 h-3.5" /> Re-run Similar
          </Link>
        </div>
      </div>

      {/* Winner Banner if available */}
      {run.winner && (
        <div className="bg-gradient-to-r from-amber-500/20 via-purple-500/20 to-slate-900 border border-amber-500/40 rounded-2xl p-6 shadow-xl flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400 shadow-lg shadow-amber-500/20">
              <Trophy className="w-6 h-6" />
            </div>
            <div>
              <span className="text-xs uppercase font-mono tracking-wider text-amber-400 font-semibold">
                Evaluation Winner
              </span>
              <h2 className="text-xl font-bold text-white mt-0.5">{run.winner.replace(/^[^/]+\//, "")}</h2>
              <p className="text-xs text-slate-300">
                Selected as top overall performer based on composite quality scoring, latency, and token efficiency.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Prompt Card */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" /> Evaluated Prompt
          </span>
          <button
            onClick={handleCopyPrompt}
            className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1 transition-colors"
          >
            {copiedPrompt ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copiedPrompt ? "Copied" : "Copy"}</span>
          </button>
        </div>
        <div className="p-3.5 bg-slate-950 border border-slate-800/80 rounded-xl font-mono text-xs text-slate-200 whitespace-pre-wrap leading-relaxed">
          {run.prompt}
        </div>
      </div>

      {/* Model Outputs Comparison Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <Cpu className="w-4 h-4 text-indigo-400" /> Model Responses &amp; Metrics
          </h2>
          <span className="text-xs text-slate-400">{run.responses?.length || 0} Models Compared</span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {run.responses?.map((res) => {
            const score = scoresByModel[res.model_id];
            const isWinner = run.winner === res.model_id;

            return (
              <div
                key={res.model_id}
                className={`flex flex-col bg-slate-900/90 border rounded-2xl overflow-hidden shadow-xl transition-all ${
                  isWinner ? "border-amber-500/50 shadow-amber-500/10" : "border-slate-800"
                }`}
              >
                {/* Model Header */}
                <div className="px-5 py-3.5 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="font-semibold text-sm text-slate-100">
                      {res.model_id.replace(/^[^/]+\//, "")}
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                      {res.model_id.split("/")[0]}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {res.from_cache && (
                      <span className="text-[10px] font-mono bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 px-2 py-0.5 rounded-full flex items-center gap-1">
                        <Database className="w-2.5 h-2.5" /> Cache Hit
                      </span>
                    )}
                    {isWinner && (
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/30 flex items-center gap-1">
                        <Trophy className="w-3 h-3" /> Winner
                      </span>
                    )}
                  </div>
                </div>

                {/* Metrics Pill Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-3 bg-slate-950/40 border-b border-slate-800/80 text-center">
                  <div className="bg-slate-900/60 p-2 rounded-xl border border-slate-800">
                    <div className="text-[10px] uppercase text-slate-400 flex items-center justify-center gap-1">
                      <Gauge className="w-3 h-3 text-cyan-400" /> Latency
                    </div>
                    <div className="font-mono font-semibold text-xs text-white mt-0.5">
                      {res.latency_ms} ms
                    </div>
                  </div>
                  <div className="bg-slate-900/60 p-2 rounded-xl border border-slate-800">
                    <div className="text-[10px] uppercase text-slate-400 flex items-center justify-center gap-1">
                      <Zap className="w-3 h-3 text-amber-400" /> Tokens
                    </div>
                    <div className="font-mono font-semibold text-xs text-white mt-0.5">
                      {res.token_count}
                    </div>
                  </div>
                  <div className="bg-slate-900/60 p-2 rounded-xl border border-slate-800">
                    <div className="text-[10px] uppercase text-slate-400 flex items-center justify-center gap-1">
                      <Sparkles className="w-3 h-3 text-purple-400" /> BERTScore
                    </div>
                    <div className="font-mono font-semibold text-xs text-white mt-0.5">
                      {score?.bert_score_f1 !== null && score?.bert_score_f1 !== undefined
                        ? `${(score.bert_score_f1 * 100).toFixed(1)}%`
                        : "N/A"}
                    </div>
                  </div>
                  <div className="bg-slate-900/60 p-2 rounded-xl border border-slate-800">
                    <div className="text-[10px] uppercase text-slate-400 flex items-center justify-center gap-1">
                      <Layers className="w-3 h-3 text-emerald-400" /> ROUGE-L
                    </div>
                    <div className="font-mono font-semibold text-xs text-white mt-0.5">
                      {score?.rouge_l !== null && score?.rouge_l !== undefined
                        ? `${(score.rouge_l * 100).toFixed(1)}%`
                        : "N/A"}
                    </div>
                  </div>
                </div>

                {/* Model Text Output */}
                <div className="flex-1 p-5 bg-slate-950 font-mono text-xs text-slate-200 overflow-y-auto max-h-96 whitespace-pre-wrap leading-relaxed">
                  {res.output}
                </div>

                {/* Footer copy button */}
                <div className="px-4 py-2.5 bg-slate-950/90 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                  <span className="font-mono text-[11px]">
                    Cost: ${score?.estimated_cost_usd?.toFixed(6) || "0.000000"}
                  </span>
                  <button
                    onClick={() => handleCopyOutput(res.model_id, res.output)}
                    className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-white transition-colors"
                  >
                    {copiedOutputModel === res.model_id ? (
                      <Check className="w-3 h-3 text-emerald-400" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                    <span>{copiedOutputModel === res.model_id ? "Copied" : "Copy Output"}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
