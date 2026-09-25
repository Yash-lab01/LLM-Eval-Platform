"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  Calendar,
  Check,
  CheckCircle2,
  Clock,
  ExternalLink,
  GitCompare,
  History,
  Layers,
  Loader2,
  PlayCircle,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import Header from "@/components/Header";
import { compareEvalRuns, getEvalHistory } from "@/lib/api";
import { EvalRunSummary, RunComparison, TaskType } from "@/types/api";

const TASK_CATEGORIES = [
  { value: "", label: "All Task Categories" },
  { value: TaskType.QUESTION_ANSWERING, label: "Question Answering" },
  { value: TaskType.SUMMARIZATION, label: "Summarization" },
  { value: TaskType.CODE_GENERATION, label: "Code Generation" },
  { value: TaskType.DATA_EXTRACTION, label: "Data Extraction" },
  { value: TaskType.CREATIVE_WRITING, label: "Creative Writing" },
  { value: TaskType.CLASSIFICATION, label: "Classification" },
  { value: TaskType.TRANSLATION, label: "Translation" },
];

export default function HistoryPage() {
  const [runs, setRuns] = useState<EvalRunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [taskFilter, setTaskFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [comparison, setComparison] = useState<RunComparison | null>(null);
  const [comparing, setComparing] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const taskParam = taskFilter ? (taskFilter as TaskType) : undefined;
      const data = await getEvalHistory(taskParam, 50);
      setRuns(data);
    } catch (err) {
      console.error("Failed to load history:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [taskFilter]);

  const toggleSelectRun = (runId: string) => {
    if (selectedRunIds.includes(runId)) {
      setSelectedRunIds(selectedRunIds.filter((id) => id !== runId));
    } else {
      if (selectedRunIds.length >= 2) {
        // Keep the latest 2
        setSelectedRunIds([selectedRunIds[1], runId]);
      } else {
        setSelectedRunIds([...selectedRunIds, runId]);
      }
    }
  };

  const handleCompare = async () => {
    if (selectedRunIds.length !== 2) return;
    setComparing(true);
    setCompareError(null);
    try {
      const result = await compareEvalRuns(selectedRunIds[0], selectedRunIds[1]);
      setComparison(result);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setCompareError(msg);
    } finally {
      setComparing(false);
    }
  };

  const filteredRuns = runs.filter((r) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      r.run_id.toLowerCase().includes(q) ||
      r.task_type.toLowerCase().includes(q) ||
      r.models.some((m) => m.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-8">
      <Header
        title="Evaluation History &amp; Diff"
        description="Browse all completed benchmarking runs, review archived models, and compare multi-model metric deltas."
      />

      {/* Filter and Comparison Action Bar */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 flex flex-col md:flex-row items-center justify-between gap-4 shadow-sm">
        <div className="flex flex-col sm:flex-row items-center gap-3 w-full md:w-auto">
          {/* Search Box */}
          <div className="relative w-full sm:w-64">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              id="input-search-history"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by ID or model..."
              className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
            />
          </div>

          {/* Task Filter */}
          <select
            id="select-history-task"
            value={taskFilter}
            onChange={(e) => setTaskFilter(e.target.value)}
            className="w-full sm:w-auto bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
          >
            {TASK_CATEGORIES.map((cat) => (
              <option key={cat.value} value={cat.value}>
                {cat.label}
              </option>
            ))}
          </select>
        </div>

        {/* Comparison Trigger Button */}
        <div className="flex items-center gap-3 w-full md:w-auto justify-end">
          <div className="text-xs text-slate-400 font-mono">
            Selected: <span className="text-cyan-400 font-bold">{selectedRunIds.length}/2</span>
          </div>

          <button
            id="btn-compare-runs"
            onClick={handleCompare}
            disabled={selectedRunIds.length !== 2 || comparing}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white shadow-md shadow-indigo-600/20 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            {comparing ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <GitCompare className="w-3.5 h-3.5" />
            )}
            <span>Compare 2 Runs</span>
          </button>

          <button
            onClick={fetchHistory}
            disabled={loading}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Run Comparison Modal / Card */}
      {comparison && (
        <div className="bg-slate-900 border border-indigo-500/40 rounded-2xl p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-200">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <GitCompare className="w-5 h-5 text-indigo-400" />
              <h2 className="text-base font-semibold text-white">Score Delta Analysis</h2>
            </div>
            <button
              onClick={() => setComparison(null)}
              className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4 text-xs">
            <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
              <span className="text-slate-500 uppercase font-mono text-[10px]">Baseline (Run A)</span>
              <div className="font-mono text-cyan-400 font-semibold mt-0.5 truncate">
                {comparison.run_id_a}
              </div>
            </div>
            <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
              <span className="text-slate-500 uppercase font-mono text-[10px]">Comparison (Run B)</span>
              <div className="font-mono text-purple-400 font-semibold mt-0.5 truncate">
                {comparison.run_id_b}
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/70 border-b border-slate-800 text-slate-400 font-mono text-[11px] uppercase">
                <tr>
                  <th className="py-2.5 px-3">Model</th>
                  <th className="py-2.5 px-3 text-center">&Delta; BERTScore F1</th>
                  <th className="py-2.5 px-3 text-center">&Delta; ROUGE-L</th>
                  <th className="py-2.5 px-3 text-center">&Delta; Latency (ms)</th>
                  <th className="py-2.5 px-3 text-right">&Delta; Cost ($)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {Object.entries(comparison.score_deltas).map(([model, deltas]) => (
                  <tr key={model} className="hover:bg-slate-800/20">
                    <td className="py-2.5 px-3 font-semibold text-slate-200">
                      {model.replace(/^[^/]+\//, "")}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      {deltas.bert_score_f1 !== null && deltas.bert_score_f1 !== undefined ? (
                        <span
                          className={
                            deltas.bert_score_f1 > 0
                              ? "text-emerald-400"
                              : deltas.bert_score_f1 < 0
                              ? "text-rose-400"
                              : "text-slate-400"
                          }
                        >
                          {deltas.bert_score_f1 > 0 ? "+" : ""}
                          {(deltas.bert_score_f1 * 100).toFixed(2)}%
                        </span>
                      ) : (
                        "--"
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      {deltas.rouge_l !== null && deltas.rouge_l !== undefined ? (
                        <span
                          className={
                            deltas.rouge_l > 0
                              ? "text-emerald-400"
                              : deltas.rouge_l < 0
                              ? "text-rose-400"
                              : "text-slate-400"
                          }
                        >
                          {deltas.rouge_l > 0 ? "+" : ""}
                          {(deltas.rouge_l * 100).toFixed(2)}%
                        </span>
                      ) : (
                        "--"
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      {deltas.latency_ms !== null && deltas.latency_ms !== undefined ? (
                        <span
                          className={
                            deltas.latency_ms < 0
                              ? "text-emerald-400" // Lower latency is better
                              : deltas.latency_ms > 0
                              ? "text-rose-400"
                              : "text-slate-400"
                          }
                        >
                          {deltas.latency_ms > 0 ? "+" : ""}
                          {deltas.latency_ms} ms
                        </span>
                      ) : (
                        "--"
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      {deltas.estimated_cost_usd !== null && deltas.estimated_cost_usd !== undefined ? (
                        <span
                          className={
                            deltas.estimated_cost_usd < 0
                              ? "text-emerald-400"
                              : deltas.estimated_cost_usd > 0
                              ? "text-rose-400"
                              : "text-slate-400"
                          }
                        >
                          {deltas.estimated_cost_usd > 0 ? "+" : ""}
                          ${deltas.estimated_cost_usd.toFixed(6)}
                        </span>
                      ) : (
                        "--"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {compareError && (
        <div className="bg-rose-950/40 border border-rose-500/40 rounded-xl p-3 text-xs text-rose-300 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{compareError}</span>
        </div>
      )}

      {/* History Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-indigo-400" />
            <h2 className="text-base font-semibold text-white">Archived Runs</h2>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            {filteredRuns.length} Runs Recorded
          </span>
        </div>

        {loading ? (
          <div className="py-16 text-center text-slate-400 flex flex-col items-center justify-center space-y-3">
            <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
            <span className="text-xs">Loading evaluation runs...</span>
          </div>
        ) : filteredRuns.length === 0 ? (
          <div className="py-16 text-center text-slate-500 text-xs">
            No evaluation runs found matching your search.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/70 border-b border-slate-800 text-slate-400 font-mono text-[11px] uppercase">
                <tr>
                  <th className="py-3 px-4 w-12 text-center">Compare</th>
                  <th className="py-3 px-4">Run ID</th>
                  <th className="py-3 px-4">Task Category</th>
                  <th className="py-3 px-4">Models Evaluated</th>
                  <th className="py-3 px-4 text-center">Status</th>
                  <th className="py-3 px-4">Created At</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {filteredRuns.map((r) => {
                  const isChecked = selectedRunIds.includes(r.run_id);
                  return (
                    <tr
                      key={r.run_id}
                      className={`hover:bg-slate-800/30 transition-colors ${
                        isChecked ? "bg-indigo-950/20" : ""
                      }`}
                    >
                      <td className="py-3 px-4 text-center">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleSelectRun(r.run_id)}
                          className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-0 cursor-pointer"
                        />
                      </td>
                      <td className="py-3 px-4 font-mono font-medium text-slate-200">
                        <Link
                          href={`/eval/${r.run_id}`}
                          className="text-cyan-400 hover:text-cyan-300 hover:underline flex items-center gap-1.5"
                        >
                          <span>{r.run_id.slice(0, 8)}...</span>
                          <ExternalLink className="w-3 h-3 text-slate-500" />
                        </Link>
                      </td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-slate-800 text-slate-300 border border-slate-700">
                          {r.task_type}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex flex-wrap gap-1 max-w-xs">
                          {r.models?.map((m) => (
                            <span
                              key={m}
                              className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-950 text-slate-400 border border-slate-800"
                            >
                              {m.replace(/^[^/]+\//, "")}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span
                          className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
                            r.status === "completed"
                              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                              : r.status === "running"
                              ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/30"
                              : "bg-rose-500/10 text-rose-400 border-rose-500/30"
                          }`}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-400 font-mono text-[11px]">
                        {new Date(r.created_at).toLocaleDateString()}{" "}
                        {new Date(r.created_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Link
                          href={`/eval/${r.run_id}`}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors"
                        >
                          <span>View</span>
                          <ArrowRight className="w-3 h-3" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
