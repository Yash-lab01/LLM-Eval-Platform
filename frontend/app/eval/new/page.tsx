"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  Bot,
  Check,
  CheckCircle2,
  ChevronDown,
  Cpu,
  ExternalLink,
  Flame,
  Gauge,
  Layers,
  Loader2,
  PlayCircle,
  RefreshCw,
  Sparkles,
  Trophy,
  Zap,
} from "lucide-react";
import Header from "@/components/Header";
import { triggerEvalRun } from "@/lib/api";
import { useEvalStore } from "@/lib/store";
import { connectEvalWebSocket } from "@/lib/websocket";
import { ModelID, ScoringMetric, TaskType } from "@/types/api";

const AVAILABLE_MODELS = [
  {
    id: ModelID.GEMINI_3_5_FLASH,
    name: "Gemini 3.5 Flash",
    provider: "Google",
    badge: "Cloud Free",
    badgeColor: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
    desc: "Ultra-fast multimodal reasoning with expansive context.",
  },
  {
    id: ModelID.GEMINI_3_8_FLASH,
    name: "Gemini 3.8 Flash",
    provider: "Google",
    badge: "Cloud Free",
    badgeColor: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
    desc: "Next-gen experimental Flash model with high accuracy.",
  },
  {
    id: ModelID.GROQ_GPT_OSS_120B,
    name: "GPT-OSS 120B",
    provider: "Groq",
    badge: "LPU Inference",
    badgeColor: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    desc: "Massive open weights model accelerated on Groq LPUs.",
  },
  {
    id: ModelID.GROQ_GPT_OSS_20B,
    name: "GPT-OSS 20B",
    provider: "Groq",
    badge: "Ultra Fast",
    badgeColor: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    desc: "High throughput, ultra-low latency LPU execution.",
  },
  {
    id: ModelID.GROQ_QWEN_27B,
    name: "Qwen 3.8 27B",
    provider: "Groq",
    badge: "Coding / Math",
    badgeColor: "bg-purple-500/10 text-purple-400 border-purple-500/30",
    desc: "Top-tier open reasoning, code generation, and math model.",
  },
  {
    id: ModelID.GROQ_QWEN_32B,
    name: "Qwen 3 32B",
    provider: "Groq",
    badge: "Reasoning",
    badgeColor: "bg-purple-500/10 text-purple-400 border-purple-500/30",
    desc: "Balanced instruction-following and structured synthesis.",
  },
  {
    id: ModelID.OLLAMA_LLAMA_3_2,
    name: "Llama 3.2",
    provider: "Ollama",
    badge: "Local Offline",
    badgeColor: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    desc: "Locally served model via Ollama with zero API egress.",
  },
  {
    id: ModelID.OLLAMA_MISTRAL,
    name: "Mistral 7B",
    provider: "Ollama",
    badge: "Local Offline",
    badgeColor: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    desc: "Efficient 7B parameter local baseline model.",
  },
];

const TASK_CATEGORIES = [
  { value: TaskType.QUESTION_ANSWERING, label: "Question Answering" },
  { value: TaskType.SUMMARIZATION, label: "Summarization" },
  { value: TaskType.CODE_GENERATION, label: "Code Generation" },
  { value: TaskType.DATA_EXTRACTION, label: "Data Extraction" },
  { value: TaskType.CREATIVE_WRITING, label: "Creative Writing" },
  { value: TaskType.CLASSIFICATION, label: "Classification" },
  { value: TaskType.TRANSLATION, label: "Translation" },
  { value: TaskType.RAG_RESPONSE, label: "RAG Synthesis" },
  { value: TaskType.COMMAND_GENERATION, label: "Command Generation" },
];

function EvalRunnerContent() {
  const searchParams = useSearchParams();
  const initialPrompt = searchParams.get("prompt") || "";
  const initialTaskType = (searchParams.get("task_type") as TaskType) || TaskType.QUESTION_ANSWERING;

  const [prompt, setPrompt] = useState(initialPrompt);
  const [referenceOutput, setReferenceOutput] = useState("");
  const [showReference, setShowReference] = useState(false);
  const [taskType, setTaskType] = useState<TaskType>(initialTaskType);
  const [selectedModels, setSelectedModels] = useState<ModelID[]>([
    ModelID.GEMINI_3_5_FLASH,
    ModelID.GROQ_GPT_OSS_120B,
  ]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    activeRunId,
    status,
    error,
    modelStreams,
    scores,
    winner,
    initRun,
    reset,
  } = useEvalStore();

  const wsCleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => {
      if (wsCleanupRef.current) {
        wsCleanupRef.current();
      }
    };
  }, []);

  const toggleModel = (modelId: ModelID) => {
    if (selectedModels.includes(modelId)) {
      if (selectedModels.length === 1) return; // Must have at least 1
      setSelectedModels(selectedModels.filter((id) => id !== modelId));
    } else {
      setSelectedModels([...selectedModels, modelId]);
    }
  };

  const handleLaunchEval = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || selectedModels.length === 0) return;

    setIsSubmitting(true);
    reset();

    try {
      // 1. Trigger run on backend
      const response = await triggerEvalRun({
        prompt: prompt.trim(),
        task_type: taskType,
        models: selectedModels,
        reference_output: referenceOutput.trim() || undefined,
        scoring_metrics: [
          ScoringMetric.BERT_SCORE,
          ScoringMetric.ROUGE_L,
          ScoringMetric.LATENCY,
          ScoringMetric.TOKEN_COUNT,
          ScoringMetric.ESTIMATED_COST,
        ],
      });

      const runId = response.run_id;

      // 2. Initialize Zustand store
      initRun(runId, selectedModels);

      // 3. Connect real-time WebSocket stream
      if (wsCleanupRef.current) {
        wsCleanupRef.current();
      }
      wsCleanupRef.current = connectEvalWebSocket(runId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      useEvalStore.getState().setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const isRunning = status === "running";
  const isCompleted = status === "completed";

  return (
    <div className="space-y-8">
      <Header
        title="Evaluation Runner"
        description="Configure multi-model prompts, stream inference in parallel, and compare quality metrics live."
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Configuration Form */}
        <div className="lg:col-span-5 space-y-6">
          <form
            onSubmit={handleLaunchEval}
            className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5"
          >
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-cyan-400" />
                <span>Evaluation Settings</span>
              </h2>
              <span className="text-xs text-slate-400 font-mono">
                {selectedModels.length} Models Selected
              </span>
            </div>

            {/* Task Category */}
            <div>
              <label
                htmlFor="select-task-type"
                className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2"
              >
                Task Category
              </label>
              <select
                id="select-task-type"
                value={taskType}
                onChange={(e) => setTaskType(e.target.value as TaskType)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
              >
                {TASK_CATEGORIES.map((cat) => (
                  <option key={cat.value} value={cat.value}>
                    {cat.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Model Selection */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Select Models to Compare
              </label>
              <div className="grid grid-cols-1 gap-2 max-h-56 overflow-y-auto pr-1">
                {AVAILABLE_MODELS.map((model) => {
                  const isChecked = selectedModels.includes(model.id);
                  return (
                    <div
                      key={model.id}
                      onClick={() => toggleModel(model.id)}
                      className={`cursor-pointer flex items-center justify-between p-3 rounded-xl border text-xs transition-all ${
                        isChecked
                          ? "bg-indigo-950/40 border-indigo-500/50 text-white shadow-sm shadow-indigo-500/10"
                          : "bg-slate-950/40 border-slate-800/80 text-slate-400 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                            isChecked
                              ? "bg-indigo-600 border-indigo-500 text-white"
                              : "border-slate-700 bg-slate-900"
                          }`}
                        >
                          {isChecked && <Check className="w-3 h-3 stroke-[3]" />}
                        </div>
                        <div>
                          <div className="font-semibold text-slate-200">{model.name}</div>
                          <div className="text-[11px] text-slate-500">{model.desc}</div>
                        </div>
                      </div>
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${model.badgeColor}`}
                      >
                        {model.badge}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Prompt Input */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label
                  htmlFor="input-prompt"
                  className="text-xs font-semibold uppercase tracking-wider text-slate-400"
                >
                  Prompt
                </label>
                <span className="text-[11px] text-slate-500 font-mono">
                  {prompt.length} chars
                </span>
              </div>
              <textarea
                id="input-prompt"
                rows={4}
                required
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Enter prompt to evaluate across selected models simultaneously..."
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 resize-y"
              />
            </div>

            {/* Reference Output Toggle & Input */}
            <div>
              <button
                type="button"
                id="btn-toggle-reference"
                onClick={() => setShowReference(!showReference)}
                className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1.5 font-medium transition-colors"
              >
                <span>{showReference ? "Hide" : "+ Add"} Reference Output (for Ground Truth BERTScore)</span>
                <ChevronDown
                  className={`w-3.5 h-3.5 transition-transform ${showReference ? "rotate-180" : ""}`}
                />
              </button>

              {showReference && (
                <div className="mt-2.5">
                  <textarea
                    id="input-reference"
                    rows={3}
                    value={referenceOutput}
                    onChange={(e) => setReferenceOutput(e.target.value)}
                    placeholder="Provide optimal reference text to compute automated ROUGE-L and semantic BERTScore..."
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
                  />
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="pt-2">
              <button
                type="submit"
                id="btn-run-eval"
                disabled={isSubmitting || isRunning || !prompt.trim()}
                className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-medium text-sm text-white bg-gradient-to-r from-cyan-500 via-indigo-600 to-purple-600 hover:from-cyan-400 hover:to-purple-500 shadow-lg shadow-cyan-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all hover:scale-[1.01] active:scale-[0.99]"
              >
                {isSubmitting || isRunning ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>{isRunning ? "Streaming Inference..." : "Initializing Run..."}</span>
                  </>
                ) : (
                  <>
                    <PlayCircle className="w-4 h-4" />
                    <span>Run Parallel Evaluation</span>
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Quick preset chips */}
          <div className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-4">
            <div className="text-xs font-medium text-slate-400 mb-2 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
              <span>Try Benchmark Presets:</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                id="btn-preset-code"
                onClick={() => {
                  setTaskType(TaskType.CODE_GENERATION);
                  setPrompt(
                    "Write an async Python function using asyncio that fetches data from three URLs concurrently with exponential backoff on HTTP 429."
                  );
                }}
                className="text-xs px-2.5 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-800 text-slate-300 border border-slate-700/60 transition-colors"
              >
                Async Python Backoff
              </button>
              <button
                type="button"
                id="btn-preset-qa"
                onClick={() => {
                  setTaskType(TaskType.QUESTION_ANSWERING);
                  setPrompt(
                    "Explain the difference between cross-entropy loss and BERTScore for evaluating generated natural language summaries."
                  );
                }}
                className="text-xs px-2.5 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-800 text-slate-300 border border-slate-700/60 transition-colors"
              >
                BERTScore vs Cross-Entropy
              </button>
              <button
                type="button"
                id="btn-preset-extract"
                onClick={() => {
                  setTaskType(TaskType.DATA_EXTRACTION);
                  setPrompt(
                    "Extract all named entities, ISO dates, and numerical values from: 'In Q3 2024, Acme Corp reported $42.5M in ARR, up 18% YoY from Sept 2023.'"
                  );
                }}
                className="text-xs px-2.5 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-800 text-slate-300 border border-slate-700/60 transition-colors"
              >
                Entity JSON Extraction
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Real-time Live Stream & Output Telemetry */}
        <div className="lg:col-span-7 space-y-6">
          {/* Winner Celebration Banner */}
          {isCompleted && (
            <div className="bg-gradient-to-r from-amber-500/20 via-indigo-500/20 to-cyan-500/20 border border-amber-500/40 rounded-2xl p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-300">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 shadow-lg shadow-amber-500/20">
                    <Trophy className="w-6 h-6" />
                  </div>
                  <div>
                    <span className="text-xs uppercase font-mono tracking-wider text-amber-400 font-semibold">
                      Evaluation Complete &bull; Winner Decided
                    </span>
                    <h3 className="text-xl font-bold text-white mt-0.5">
                      {winner ? winner.replace(/^[^/]+\//, "") : "Benchmark Completed"}
                    </h3>
                  </div>
                </div>
                {activeRunId && (
                  <Link
                    href={`/eval/${activeRunId}`}
                    id="btn-view-run-details"
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-white/10 hover:bg-white/20 text-white border border-white/20 transition-all hover:scale-105"
                  >
                    <span>Full Report</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </Link>
                )}
              </div>

              {/* Scored Metrics Breakdown */}
              {scores.length > 0 && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-4 border-t border-white/10">
                  {scores.map((sc) => (
                    <div
                      key={sc.model_id}
                      className={`p-2.5 rounded-xl border text-xs ${
                        sc.model_id === winner
                          ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
                          : "bg-slate-950/40 border-slate-800 text-slate-300"
                      }`}
                    >
                      <div className="font-semibold truncate mb-1">
                        {sc.model_id.replace(/^[^/]+\//, "")}
                      </div>
                      <div className="space-y-0.5 text-[11px] text-slate-400">
                        {sc.bert_score_f1 !== null && sc.bert_score_f1 !== undefined && (
                          <div>BERT: {(sc.bert_score_f1 * 100).toFixed(1)}%</div>
                        )}
                        <div>Latency: {sc.latency_ms}ms</div>
                        <div>Tokens: {sc.token_count}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="bg-rose-950/40 border border-rose-500/40 rounded-2xl p-4 flex items-center gap-3 text-rose-300 text-xs">
              <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Live Streaming Terminals Grid */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Cpu className="w-4 h-4 text-indigo-400" />
                <span>Model Outputs &amp; Streaming Telemetry</span>
              </h3>
              {activeRunId && (
                <span className="text-[11px] font-mono text-slate-400 bg-slate-900 px-2.5 py-1 rounded-lg border border-slate-800">
                  Run ID: {activeRunId.slice(0, 8)}...
                </span>
              )}
            </div>

            {selectedModels.length === 0 ? (
              <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-12 text-center text-slate-500 text-sm">
                Select one or more models on the left to view output streams.
              </div>
            ) : (
              <div
                className={`grid grid-cols-1 ${
                  selectedModels.length > 1 ? "md:grid-cols-2" : ""
                } gap-4`}
              >
                {selectedModels.map((modelId) => {
                  const stream = modelStreams[modelId] || {
                    output: "",
                    tokens: 0,
                    latency: 0,
                    isFinal: false,
                  };
                  const isWinningModel = winner === modelId;
                  const isModelStreaming = isRunning && !stream.isFinal;

                  return (
                    <div
                      key={modelId}
                      className={`flex flex-col bg-slate-900/90 border rounded-2xl overflow-hidden shadow-lg transition-all ${
                        isWinningModel
                          ? "border-amber-500/50 shadow-amber-500/10"
                          : isModelStreaming
                          ? "border-cyan-500/40 shadow-cyan-500/10"
                          : "border-slate-800"
                      }`}
                    >
                      {/* Terminal Header */}
                      <div className="px-4 py-3 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span
                            className={`w-2 h-2 rounded-full ${
                              isModelStreaming
                                ? "bg-cyan-400 animate-ping"
                                : stream.isFinal
                                ? "bg-emerald-400"
                                : "bg-slate-600"
                            }`}
                          />
                          <span className="text-xs font-semibold text-slate-200">
                            {modelId.replace(/^[^/]+\//, "")}
                          </span>
                        </div>
                        {isWinningModel && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/30">
                            <Trophy className="w-3 h-3" /> Winner
                          </span>
                        )}
                      </div>

                      {/* Stream Terminal Window */}
                      <div className="p-4 bg-slate-950 font-mono text-xs text-slate-200 h-64 overflow-y-auto whitespace-pre-wrap selection:bg-cyan-900">
                        {stream.output ? (
                          <>
                            {stream.output}
                            {isModelStreaming && (
                              <span className="inline-block w-2 h-3.5 bg-cyan-400 ml-0.5 animate-pulse" />
                            )}
                          </>
                        ) : isRunning ? (
                          <div className="h-full flex items-center justify-center text-slate-500 text-xs">
                            <Loader2 className="w-4 h-4 animate-spin mr-2 text-cyan-400" />
                            Awaiting first token chunk...
                          </div>
                        ) : (
                          <span className="text-slate-600 italic">
                            Output will stream live once evaluation begins.
                          </span>
                        )}
                      </div>

                      {/* Terminal Footer Telemetry */}
                      <div className="px-4 py-2.5 bg-slate-950/90 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
                        <div className="flex items-center gap-3">
                          <span className="flex items-center gap-1">
                            <Gauge className="w-3 h-3 text-cyan-400" />
                            {stream.latency > 0 ? `${stream.latency}ms` : "--"}
                          </span>
                          <span className="flex items-center gap-1">
                            <Zap className="w-3 h-3 text-amber-400" />
                            {stream.tokens > 0 ? `${stream.tokens} tok` : "--"}
                          </span>
                        </div>
                        <div>
                          {stream.isFinal ? (
                            <span className="text-emerald-400 flex items-center gap-1">
                              <CheckCircle2 className="w-3 h-3" /> Done
                            </span>
                          ) : isModelStreaming ? (
                            <span className="text-cyan-400">Streaming</span>
                          ) : (
                            <span className="text-slate-500">Idle</span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function EvalRunnerPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-[60vh] text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin text-cyan-400 mr-2" />
          <span>Loading Evaluation Runner...</span>
        </div>
      }
    >
      <EvalRunnerContent />
    </Suspense>
  );
}
