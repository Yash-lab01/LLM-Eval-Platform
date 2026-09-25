"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  Code2,
  Copy,
  ExternalLink,
  FileText,
  Filter,
  Layers,
  PlayCircle,
  Search,
  Sparkles,
  Terminal,
} from "lucide-react";
import Header from "@/components/Header";
import { TaskType } from "@/types/api";

interface BenchmarkPrompt {
  id: string;
  title: string;
  taskType: TaskType;
  complexity: "Short" | "Medium" | "Long";
  prompt: string;
  referenceOutput?: string;
  tags: string[];
}

const BENCHMARK_PROMPTS: BenchmarkPrompt[] = [
  {
    id: "async-py-concurrency",
    title: "Asyncio Python Concurrency & Backoff",
    taskType: TaskType.CODE_GENERATION,
    complexity: "Medium",
    tags: ["python", "asyncio", "resilience"],
    prompt:
      "Write an asynchronous Python function `fetch_with_backoff(urls: list[str]) -> dict[str, str]` using `aiohttp` or `httpx` that fetches content from multiple endpoints in parallel using `asyncio.gather()`. Implement exponential backoff for HTTP 429 and 503 errors with a jitter factor and maximum of 3 retries.",
    referenceOutput:
      "A complete async Python implementation defining fetch_with_backoff utilizing asyncio.gather and exponential backoff retry loop with jitter.",
  },
  {
    id: "bertscore-vs-crossentropy",
    title: "BERTScore vs. Cross-Entropy Loss",
    taskType: TaskType.QUESTION_ANSWERING,
    complexity: "Short",
    tags: ["nlp", "evaluation", "metrics"],
    prompt:
      "Explain the fundamental theoretical and practical differences between traditional cross-entropy perplexity and modern embedding-based BERTScore for evaluating generated natural language summaries.",
    referenceOutput:
      "Cross-entropy measures token-level probability distribution alignment, penalizing vocabulary mismatches even when semantically identical. BERTScore utilizes pre-trained contextual embeddings to compute cosine similarity between tokens via greedy bipartite matching, effectively capturing semantic equivalence and paraphrasing.",
  },
  {
    id: "financial-earnings-json",
    title: "Financial Earnings Call Extraction",
    taskType: TaskType.DATA_EXTRACTION,
    complexity: "Medium",
    tags: ["json", "extraction", "finance"],
    prompt:
      "Extract the corporate financial metrics into a strict JSON schema containing `company_name`, `reporting_period`, `revenue_usd`, `arr_usd`, `yoy_growth_percent`, and `ebitda_margin_percent` from the following snippet: 'In Q3 2024, CloudScale AI posted record revenue of $128.4M, with annualized recurring revenue reaching $412.0M—representing a 34.2% YoY growth compared to Q3 2023. Adjusted EBITDA margin stood at 19.5%.' Output JSON only.",
    referenceOutput:
      '{"company_name": "CloudScale AI", "reporting_period": "Q3 2024", "revenue_usd": 128400000, "arr_usd": 412000000, "yoy_growth_percent": 34.2, "ebitda_margin_percent": 19.5}',
  },
  {
    id: "executive-board-summary",
    title: "Executive Architecture Summary",
    taskType: TaskType.SUMMARIZATION,
    complexity: "Long",
    tags: ["architecture", "exec-brief", "infrastructure"],
    prompt:
      "Synthesize an executive-level summary of an enterprise migration from legacy monolithic MySQL databases to a distributed multi-region CockroachDB cluster. Outline key business drivers, risk mitigations, latency impacts, and data consistency trade-offs in 3 concise bullet points followed by a final decision recommendation.",
  },
  {
    id: "rag-grounded-qa",
    title: "Grounded RAG Response Synthesis",
    taskType: TaskType.RAG_RESPONSE,
    complexity: "Medium",
    tags: ["rag", "citations", "groundedness"],
    prompt:
      "Given the context chunks:\n[Doc 1]: The Apollo 11 mission launched on July 16, 1969, carrying Neil Armstrong, Buzz Aldrin, and Michael Collins.\n[Doc 2]: Michael Collins remained in lunar orbit aboard the Command Module Columbia while the Lunar Module Eagle landed on the Moon on July 20, 1969.\n\nQuestion: Which astronaut remained in lunar orbit and what was the name of their spacecraft? Cite the source document ID.",
    referenceOutput:
      "Michael Collins remained in lunar orbit aboard the Command Module Columbia [Doc 2].",
  },
  {
    id: "bash-command-gen",
    title: "Linux Docker System Diagnostic",
    taskType: TaskType.COMMAND_GENERATION,
    complexity: "Short",
    tags: ["devops", "bash", "docker"],
    prompt:
      "Generate a single-line Linux bash pipeline that finds all stopped Docker containers older than 7 days, prints their container IDs and disk utilization, and formats the output into a tab-delimited table.",
  },
];

export default function PromptsPage() {
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const filteredPrompts = BENCHMARK_PROMPTS.filter((p) => {
    const matchesCategory = !selectedCategory || p.taskType === selectedCategory;
    const matchesSearch =
      !searchQuery.trim() ||
      p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.prompt.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.tags.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="space-y-8">
      <Header
        title="Prompt Benchmark Library"
        description="Curated standardized prompts across core NLP tasks for consistent model comparison and evaluation."
      />

      {/* Filter and Search Bar */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 flex flex-col md:flex-row items-center justify-between gap-4 shadow-sm">
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            id="input-search-prompts"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search prompts by keyword or tag..."
            className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
          />
        </div>

        {/* Task Category Filter Chips */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto pb-1 md:pb-0">
          <button
            onClick={() => setSelectedCategory("")}
            className={`text-xs px-3 py-1.5 rounded-xl font-medium transition-colors shrink-0 ${
              selectedCategory === ""
                ? "bg-indigo-600 text-white shadow-sm"
                : "bg-slate-950 text-slate-400 border border-slate-800 hover:text-slate-200"
            }`}
          >
            All Categories
          </button>
          {[
            TaskType.CODE_GENERATION,
            TaskType.QUESTION_ANSWERING,
            TaskType.DATA_EXTRACTION,
            TaskType.SUMMARIZATION,
            TaskType.RAG_RESPONSE,
            TaskType.COMMAND_GENERATION,
          ].map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`text-xs px-3 py-1.5 rounded-xl font-medium transition-colors shrink-0 capitalize ${
                selectedCategory === cat
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-slate-950 text-slate-400 border border-slate-800 hover:text-slate-200"
              }`}
            >
              {cat.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      {/* Prompts Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredPrompts.map((bp) => {
          const evalUrl = `/eval/new?prompt=${encodeURIComponent(bp.prompt)}&task_type=${bp.taskType}`;

          return (
            <div
              key={bp.id}
              className="flex flex-col justify-between bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl hover:border-slate-700/80 transition-all hover:translate-y-[-2px] group"
            >
              <div>
                {/* Header tags */}
                <div className="flex items-center justify-between gap-2 mb-3">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 uppercase tracking-wider">
                    {bp.taskType.replace("_", " ")}
                  </span>
                  <span className="text-[10px] font-mono text-slate-500">
                    {bp.complexity} Prompt
                  </span>
                </div>

                <h3 className="font-semibold text-sm text-slate-100 group-hover:text-cyan-300 transition-colors">
                  {bp.title}
                </h3>

                {/* Prompt Preview */}
                <div className="mt-3 p-3 bg-slate-950 border border-slate-800/80 rounded-xl text-xs text-slate-300 font-mono line-clamp-4 leading-relaxed">
                  {bp.prompt}
                </div>

                {/* Reference Output Notice */}
                {bp.referenceOutput && (
                  <div className="mt-2.5 flex items-center gap-1.5 text-[11px] text-emerald-400">
                    <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                    <span>Includes reference ground truth for BERTScore</span>
                  </div>
                )}

                {/* Tags */}
                <div className="mt-3 flex flex-wrap gap-1">
                  {bp.tags.map((tag) => (
                    <span
                      key={tag}
                      className="text-[10px] font-mono text-slate-500 bg-slate-950 px-1.5 py-0.5 rounded border border-slate-800/60"
                    >
                      #{tag}
                    </span>
                  ))}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="mt-5 pt-4 border-t border-slate-800 flex items-center justify-between gap-2">
                <button
                  type="button"
                  id={`btn-copy-prompt-${bp.id}`}
                  onClick={() => handleCopy(bp.id, bp.prompt)}
                  className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 transition-colors"
                >
                  {copiedId === bp.id ? (
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                  <span>{copiedId === bp.id ? "Copied" : "Copy"}</span>
                </button>

                <Link
                  href={evalUrl}
                  id={`btn-run-prompt-${bp.id}`}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white shadow-md shadow-cyan-500/20 transition-all hover:scale-105"
                >
                  <PlayCircle className="w-3.5 h-3.5" />
                  <span>Run in Eval</span>
                  <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
