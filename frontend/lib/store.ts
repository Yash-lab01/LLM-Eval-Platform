/**
 * Zustand global state store for active evaluation runs and real-time streaming tokens.
 */

import { create } from "zustand";
import { EvalScoreSchema } from "@/types/api";

export interface ModelStreamState {
  output: string;
  tokens: number;
  latency: number;
  isFinal: boolean;
}

interface EvalStore {
  activeRunId: string | null;
  status: "idle" | "running" | "completed" | "error";
  error: string | null;
  modelStreams: Record<string, ModelStreamState>;
  scores: EvalScoreSchema[];
  winner: string | null;

  initRun: (runId: string, models: string[]) => void;
  appendStreamToken: (modelId: string, token: string) => void;
  finalizeModelStream: (
    modelId: string,
    output: string,
    latency: number,
    tokens: number
  ) => void;
  setEvaluationComplete: (scores: EvalScoreSchema[], winner?: string | null) => void;
  setError: (err: string) => void;
  reset: () => void;
}

export const useEvalStore = create<EvalStore>((set) => ({
  activeRunId: null,
  status: "idle",
  error: null,
  modelStreams: {},
  scores: [],
  winner: null,

  initRun: (runId, models) => {
    const initialStreams: Record<string, ModelStreamState> = {};
    models.forEach((m) => {
      initialStreams[m] = { output: "", tokens: 0, latency: 0, isFinal: false };
    });
    set({
      activeRunId: runId,
      status: "running",
      error: null,
      modelStreams: initialStreams,
      scores: [],
      winner: null,
    });
  },

  appendStreamToken: (modelId, token) =>
    set((state) => {
      const current = state.modelStreams[modelId] || {
        output: "",
        tokens: 0,
        latency: 0,
        isFinal: false,
      };
      return {
        modelStreams: {
          ...state.modelStreams,
          [modelId]: {
            ...current,
            output: current.output + token,
            tokens: current.tokens + 1,
          },
        },
      };
    }),

  finalizeModelStream: (modelId, output, latency, tokens) =>
    set((state) => ({
      modelStreams: {
        ...state.modelStreams,
        [modelId]: {
          output,
          latency,
          tokens,
          isFinal: true,
        },
      },
    })),

  setEvaluationComplete: (scores, winner) =>
    set({
      status: "completed",
      scores,
      winner: winner || null,
    }),

  setError: (err) =>
    set({
      status: "error",
      error: err,
    }),

  reset: () =>
    set({
      activeRunId: null,
      status: "idle",
      error: null,
      modelStreams: {},
      scores: [],
      winner: null,
    }),
}));
