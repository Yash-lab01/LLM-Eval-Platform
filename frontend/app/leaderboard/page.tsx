"use client";

import { useEffect, useState } from "react";
import {
  Award,
  BarChart3,
  Bot,
  CheckCircle2,
  Cpu,
  Database,
  DollarSign,
  Gauge,
  Layers,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  TrendingUp,
  Trophy,
  Zap,
} from "lucide-react";
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
import Header from "@/components/Header";
import { getLeaderboard, getModelRecommendation } from "@/lib/api";
import {
  LeaderboardEntry,
  ModelRecommendation,
  ScoringMetric,
  TaskType,
} from "@/types/api";

const TASK_CATEGORIES = [
  { value: "", label: "All Tasks Combined" },
  { value: TaskType.QUESTION_ANSWERING, label: "Question Answering" },
  { value: TaskType.SUMMARIZATION, label: "Summarization" },
  { value: TaskType.CODE_GENERATION, label: "Code Generation" },
  { value: TaskType.DATA_EXTRACTION, label: "Data Extraction" },
  { value: TaskType.CREATIVE_WRITING, label: "Creative Writing" },
  { value: TaskType.CLASSIFICATION, label: "Classification" },
  { value: TaskType.TRANSLATION, label: "Translation" },
];

const METRIC_OPTIONS = [
  { value: ScoringMetric.BERT_SCORE, label: "Semantic BERTScore (Quality)" },
  { value: ScoringMetric.LATENCY, label: "Lowest Latency (Speed)" },
  { value: ScoringMetric.ROUGE_L, label: "ROUGE-L Overlap" },
  { value: ScoringMetric.ESTIMATED_COST, label: "Lowest Cost ($)" },
];

export default function LeaderboardPage() {
  const [selectedTask, setSelectedTask] = useState<string>("");
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [fromCache, setFromCache] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Recommendation state
  const [recTask, setRecTask] = useState<TaskType>(TaskType.QUESTION_ANSWERING);
  const [recMetric, setRecMetric] = useState<ScoringMetric>(ScoringMetric.BERT_SCORE);
  const [recommendation, setRecommendation] = useState<ModelRecommendation | null>(null);
  const [recLoading, setRecLoading] = useState(false);

  const fetchLeaderboardData = async (force: boolean = false) => {
    if (force) setRefreshing(true);
    else setLoading(true);

    try {
      const taskParam = selectedTask ? (selectedTask as TaskType) : undefined;
      const res = await getLeaderboard(taskParam, force);
      setEntries(res.entries || []);
      setFromCache(res.from_cache || false);
    } catch (err) {
      console.error("Failed to load leaderboard:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchLeaderboardData(false);
  }, [selectedTask]);

  const handleGetRecommendation = async () => {
    setRecLoading(true);
    try {
      const res = await getModelRecommendation(recTask, recMetric);
      setRecommendation(res);
    } catch (err) {
      console.error("Failed to fetch recommendation:", err);
    } finally {
      setRecLoading(false);
    }
  };

  // Prepare chart data
  const chartData = entries.map((entry) => ({
    name: entry.model_id.replace(/^[^/]+\//, ""),
    winRate: Number((entry.win_rate * 100).toFixed(1)),
    latency: entry.avg_latency_ms,
    bertScore: entry.avg_bert_score ? Number((entry.avg_bert_score * 100).toFixed(1)) : 0,
  }));

  return (
    <div className="space-y-8">
      <Header
        title="Model Leaderboard"
        description="Empirical win rates, latency benchmarks, and SQL aggregation across multi-model evaluations."
      />

      {/* Control Bar: Filters & Cache Status */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-sm">
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <label htmlFor="select-leaderboard-task" className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Task Filter:
          </label>
          <select
            id="select-leaderboard-task"
            value={selectedTask}
            onChange={(e) => setSelectedTask(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
          >
            {TASK_CATEGORIES.map((cat) => (
              <option key={cat.value} value={cat.value}>
                {cat.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
          <span
            className={`inline-flex items-center gap-1.5 font-mono text-[11px] px-2.5 py-1 rounded-full border ${
              fromCache
                ? "bg-indigo-500/10 text-indigo-400 border-indigo-500/30"
                : "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
            }`}
          >
            <Database className="w-3 h-3" />
            <span>{fromCache ? "Redis Cached (300s TTL)" : "PostgreSQL Live"}</span>
          </span>

          <button
            id="btn-refresh-leaderboard"
            onClick={() => fetchLeaderboardData(true)}
            disabled={refreshing || loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/60 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Visual Chart Card */}
      {chartData.length > 0 && (
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-xl">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-cyan-400" />
                <span>Win Rate (%) Comparison</span>
              </h2>
              <p className="text-xs text-slate-400">Head-to-head empirical win frequency across all benchmarked runs</p>
            </div>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 25 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  dataKey="name"
                  stroke="#64748b"
                  tick={{ fontSize: 11, fill: "#94a3b8" }}
                  angle={-15}
                  textAnchor="end"
                />
                <YAxis
                  stroke="#64748b"
                  tick={{ fontSize: 11, fill: "#94a3b8" }}
                  domain={[0, 100]}
                  unit="%"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#090d16",
                    borderColor: "#334155",
                    borderRadius: "0.75rem",
                    color: "#f8fafc",
                    fontSize: "12px",
                  }}
                />
                <Legend wrapperStyle={{ fontSize: "12px", paddingTop: "10px" }} />
                <Bar dataKey="winRate" name="Win Rate (%)" fill="#6366f1" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Ranked Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Trophy className="w-5 h-5 text-amber-400" />
            <h2 className="text-base font-semibold text-white">Ranked Model Performance</h2>
          </div>
          <span className="text-xs text-slate-400 font-mono">{entries.length} Models Benchmarked</span>
        </div>

        {loading ? (
          <div className="py-16 text-center text-slate-400 flex flex-col items-center justify-center space-y-3">
            <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
            <span className="text-xs">Computing leaderboard rankings...</span>
          </div>
        ) : entries.length === 0 ? (
          <div className="py-16 text-center text-slate-500 text-xs">
            No evaluation data found for this task category. Run your first benchmark to populate the leaderboard.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/70 border-b border-slate-800 text-slate-400 font-mono text-[11px] uppercase">
                <tr>
                  <th className="py-3 px-4">Rank</th>
                  <th className="py-3 px-4">Model</th>
                  <th className="py-3 px-4 text-center">Total Runs</th>
                  <th className="py-3 px-4">Win Rate</th>
                  <th className="py-3 px-4 text-center">Avg BERTScore</th>
                  <th className="py-3 px-4 text-center">Avg ROUGE-L</th>
                  <th className="py-3 px-4 text-center">Avg Latency</th>
                  <th className="py-3 px-4 text-center">Avg Tokens</th>
                  <th className="py-3 px-4 text-right">Est. Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {entries.map((entry, idx) => {
                  const winRatePct = (entry.win_rate * 100).toFixed(1);
                  return (
                    <tr key={entry.model_id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3.5 px-4 font-mono font-bold">
                        {idx === 0 ? (
                          <span className="text-amber-400 flex items-center gap-1">
                            <Trophy className="w-4 h-4" /> #1
                          </span>
                        ) : idx === 1 ? (
                          <span className="text-slate-300">#2</span>
                        ) : idx === 2 ? (
                          <span className="text-amber-600">#3</span>
                        ) : (
                          <span className="text-slate-500">#{idx + 1}</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-slate-100">
                          {entry.model_id.replace(/^[^/]+\//, "")}
                        </div>
                        <div className="text-[11px] font-mono text-slate-500">
                          {entry.model_id}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-center font-mono text-slate-300">
                        {entry.total_runs}
                      </td>
                      <td className="py-3.5 px-4 min-w-[140px]">
                        <div className="flex items-center justify-between text-xs font-mono font-semibold text-slate-200 mb-1">
                          <span>{winRatePct}%</span>
                        </div>
                        <div className="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-gradient-to-r from-cyan-500 to-indigo-500 h-full rounded-full"
                            style={{ width: `${winRatePct}%` }}
                          />
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-center font-mono text-slate-300">
                        {entry.avg_bert_score !== null && entry.avg_bert_score !== undefined
                          ? `${(entry.avg_bert_score * 100).toFixed(1)}%`
                          : "--"}
                      </td>
                      <td className="py-3.5 px-4 text-center font-mono text-slate-300">
                        {entry.avg_rouge_l !== null && entry.avg_rouge_l !== undefined
                          ? `${(entry.avg_rouge_l * 100).toFixed(1)}%`
                          : "--"}
                      </td>
                      <td className="py-3.5 px-4 text-center font-mono text-cyan-400">
                        {entry.avg_latency_ms} ms
                      </td>
                      <td className="py-3.5 px-4 text-center font-mono text-slate-300">
                        {entry.avg_token_count}
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono text-slate-400">
                        ${entry.total_estimated_cost_usd?.toFixed(5) || "0.00000"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Model Recommendation Engine Widget */}
      <div className="bg-gradient-to-br from-indigo-950/60 via-slate-900 to-slate-950 border border-indigo-500/30 rounded-2xl p-6 shadow-xl space-y-5">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <span>Smart Model Recommender</span>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                  Automated Oracle
                </span>
              </h3>
              <p className="text-xs text-slate-300">
                Find the empirically superior LLM for your workload based on past historical evaluations.
              </p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Task Type
            </label>
            <select
              id="select-rec-task"
              value={recTask}
              onChange={(e) => setRecTask(e.target.value as TaskType)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            >
              {TASK_CATEGORIES.filter((c) => c.value).map((cat) => (
                <option key={cat.value} value={cat.value}>
                  {cat.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Optimize For
            </label>
            <select
              id="select-rec-metric"
              value={recMetric}
              onChange={(e) => setRecMetric(e.target.value as ScoringMetric)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            >
              {METRIC_OPTIONS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end">
            <button
              id="btn-get-recommendation"
              onClick={handleGetRecommendation}
              disabled={recLoading}
              className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded-xl text-xs font-semibold bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white shadow-md shadow-cyan-500/20 disabled:opacity-50 transition-all hover:scale-105"
            >
              {recLoading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Querying Oracle...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Find Best Model</span>
                </>
              )}
            </button>
          </div>
        </div>

        {recommendation && (
          <div className="mt-4 p-4 rounded-xl bg-slate-950/80 border border-cyan-500/30 flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-cyan-400 uppercase tracking-wider">
                  Recommended Model:
                </span>
                <span className="font-bold text-sm text-white">
                  {recommendation.recommended_model}
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                {recommendation.reason}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
