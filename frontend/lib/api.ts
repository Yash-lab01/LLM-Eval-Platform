/**
 * Backend REST API client for the LLM Evaluation Platform.
 * Connects to FastAPI backend running on port 8000.
 */

import {
  EvalRunResult,
  EvalRunSummary,
  LeaderboardResponse,
  ModelRecommendation,
  PromptRunRequest,
  RunComparison,
  ScoringMetric,
  TaskType,
} from "@/types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });

  if (!res.ok) {
    let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
    try {
      const errorJson = await res.json();
      if (errorJson.detail) {
        errorDetail = typeof errorJson.detail === "string"
          ? errorJson.detail
          : JSON.stringify(errorJson.detail);
      }
    } catch {
      // Use fallback errorDetail
    }
    throw new Error(errorDetail);
  }

  return res.json() as Promise<T>;
}

export async function checkSystemHealth(): Promise<{
  status: string;
  environment: string;
  components: { database: string; redis: string };
}> {
  return fetchJson("/health");
}

export async function triggerEvalRun(request: PromptRunRequest): Promise<{
  run_id: string;
  status: string;
  task_type: string;
  models: string[];
  stream_url: string;
}> {
  return fetchJson("/api/v1/eval/run", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function getEvalRun(runId: string): Promise<EvalRunResult> {
  return fetchJson(`/api/v1/eval/${runId}`);
}

export async function getEvalHistory(
  taskType?: TaskType,
  limit: number = 20
): Promise<EvalRunSummary[]> {
  const query = new URLSearchParams();
  if (taskType) query.set("task_type", taskType);
  query.set("limit", limit.toString());
  return fetchJson(`/api/v1/eval/history/list?${query.toString()}`);
}

export async function compareEvalRuns(
  runIdA: string,
  runIdB: string
): Promise<RunComparison> {
  return fetchJson(`/api/v1/eval/compare?run_id_a=${runIdA}&run_id_b=${runIdB}`);
}

export async function getLeaderboard(
  taskType?: TaskType,
  forceRefresh: boolean = false
): Promise<LeaderboardResponse> {
  const query = new URLSearchParams();
  if (taskType) query.set("task_type", taskType);
  if (forceRefresh) query.set("force_refresh", "true");
  return fetchJson(`/api/v1/leaderboard?${query.toString()}`);
}

export async function getModelRecommendation(
  taskType: TaskType = TaskType.QUESTION_ANSWERING,
  metric: ScoringMetric = ScoringMetric.BERT_SCORE
): Promise<ModelRecommendation> {
  return fetchJson(`/api/v1/models/recommend?task_type=${taskType}&metric=${metric}`);
}
