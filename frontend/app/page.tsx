"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Activity,
  ArrowRight,
  Award,
  CheckCircle2,
  Clock,
  Layers,
  PlayCircle,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import Header from "@/components/Header";
import { getEvalHistory, getLeaderboard } from "@/lib/api";
import { EvalRunSummary, LeaderboardEntry } from "@/types/api";

export default function DashboardPage() {
  const [history, setHistory] = useState<EvalRunSummary[]>([]);
  const [topModels, setTopModels] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadDashboardData() {
      try {
        const [historyData, leaderboardData] = await Promise.all([
          getEvalHistory(undefined, 8).catch(() => []),
          getLeaderboard(undefined).catch(() => ({ entries: [], from_cache: false })),
        ]);
        setHistory(historyData);
        setTopModels(leaderboardData.entries.slice(0, 3));
      } finally {
        setLoading(false);
      }
    }
    loadDashboardData();
  }, []);

  const totalRuns = history.length;
  const topWinner = topModels[0]?.model_id || "Gemini 3.5 Flash";
  const avgLatency = topModels.length
    ? Math.round(topModels.reduce((acc, m) => acc + m.avg_latency_ms, 0) / topModels.length)
    : 240;

  return (
    <div className="space-y-8">
      <Header
        title="Benchmarking Dashboard"
        description="Real-time multi-model evaluation metrics, latency telemetry, and historical win-rates."
      />

      {/* Hero Action Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-900/60 via-purple-900/40 to-slate-900 border border-indigo-500/30 p-8 shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none" />
        <div className="relative z-10 max-w-2xl space-y-3">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Automated Scoring &amp; Non-blocking Inference</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-white">
            Benchmark Gemini, Groq, and Ollama Side-by-Side
          </h2>
          <p className="text-sm text-slate-300">
            Send prompts across free-tier open models simultaneously. Watch tokens stream
            in real time, evaluate BERTScore and ROUGE-L similarity, and track empirical win rates.
          </p>
          <div className="pt-2">
            <Link
              href="/eval/new"
              id="btn-hero-start-eval"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white shadow-lg shadow-cyan-500/20 transition-all hover:scale-105 active:scale-95"
            >
              <PlayCircle className="w-4 h-4" />
              <span>Launch Evaluation</span>
              <ArrowRight className="w-4 h-4 ml-1" />
            </Link>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Total Runs</span>
            <Layers className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-white">
            {loading ? "..." : totalRuns}
          </div>
          <p className="text-xs text-slate-500 mt-1">Recorded in database</p>
        </div>

        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Top Leader</span>
            <Award className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-lg font-bold text-cyan-300 truncate">
            {loading ? "..." : topWinner.replace("gemini/", "").replace("groq/openai/", "")}
          </div>
          <p className="text-xs text-slate-500 mt-1">Leading composite score</p>
        </div>

        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Avg Latency</span>
            <Clock className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-300">
            {loading ? "..." : `${avgLatency} ms`}
          </div>
          <p className="text-xs text-slate-500 mt-1">Across benchmark models</p>
        </div>

        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Telemetry</span>
            <Activity className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-bold text-purple-300">Langfuse</div>
          <p className="text-xs text-slate-500 mt-1">Live trace callbacks</p>
        </div>
      </div>

      {/* Main Grid: Recent Runs & Leaderboard Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Runs Table */}
        <div className="lg:col-span-2 bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-white flex items-center gap-2">
              <Clock className="w-4 h-4 text-indigo-400" />
              Recent Evaluation Runs
            </h3>
            <Link
              href="/history"
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
            >
              View All <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {loading ? (
            <div className="py-12 text-center text-slate-500 text-sm">
              Loading historical benchmarks...
            </div>
          ) : history.length === 0 ? (
            <div className="py-12 text-center space-y-3">
              <p className="text-sm text-slate-400">No evaluation runs recorded yet.</p>
              <Link
                href="/eval/new"
                className="inline-flex items-center gap-1.5 text-xs text-cyan-400 hover:underline"
              >
                Run your first benchmark &rarr;
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-xs uppercase font-medium">
                    <th className="py-2.5 px-3">Run ID</th>
                    <th className="py-2.5 px-3">Task Category</th>
                    <th className="py-2.5 px-3">Models</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                  {history.map((run) => (
                    <tr key={run.run_id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-3 text-slate-300 font-mono">
                        {run.run_id.slice(0, 8)}...
                      </td>
                      <td className="py-3 px-3 text-slate-400 capitalize">
                        {run.task_type.replace("_", " ")}
                      </td>
                      <td className="py-3 px-3 text-slate-400">
                        {run.models.length} model{run.models.length > 1 ? "s" : ""}
                      </td>
                      <td className="py-3 px-3">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          <CheckCircle2 className="w-3 h-3" />
                          {run.status}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <Link
                          href={`/eval/${run.run_id}`}
                          id={`btn-view-run-${run.run_id.slice(0, 8)}`}
                          className="text-indigo-400 hover:text-indigo-300 font-sans font-medium text-xs hover:underline"
                        >
                          View Details &rarr;
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Top Models Leaderboard Preview */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-white flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-cyan-400" />
              Leaderboard Preview
            </h3>
            <Link
              href="/leaderboard"
              className="text-xs text-cyan-400 hover:text-cyan-300 font-medium flex items-center gap-1"
            >
              Full Board <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="space-y-3">
            {topModels.length === 0 ? (
              <div className="py-8 text-center text-slate-500 text-xs">
                No leaderboard entries yet. Run evaluations to populate rankings.
              </div>
            ) : (
              topModels.map((entry, idx) => (
                <div
                  key={entry.model_id}
                  className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 flex items-center justify-between"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`w-6 h-6 rounded-lg text-xs font-bold flex items-center justify-center ${
                        idx === 0
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                          : idx === 1
                          ? "bg-slate-500/20 text-slate-300 border border-slate-500/40"
                          : "bg-orange-500/20 text-orange-300 border border-orange-500/40"
                      }`}
                    >
                      {idx + 1}
                    </span>
                    <div>
                      <p className="text-xs font-semibold text-white truncate max-w-[150px]">
                        {entry.model_id.replace("gemini/", "").replace("groq/openai/", "")}
                      </p>
                      <p className="text-[11px] text-slate-500">
                        {entry.total_runs} benchmark runs
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-xs font-bold text-cyan-400">
                      {entry.win_rate}%
                    </span>
                    <p className="text-[10px] text-slate-500">win rate</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
