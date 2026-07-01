/**
 * Thin HTTP client to the Python ML service.
 *
 * Wraps every ML call so the gateway never reaches for axios directly in
 * route handlers. Centralizes timeout + error handling. The streaming
 * variant forwards Server-Sent Events from the ML service for per-stage
 * progress.
 */
import axios, { AxiosInstance } from "axios";
import type {
  PipelineInput,
  PipelineResult,
} from "@polyhire/shared-types";

import { config } from "./config.js";
import type { StageCallback } from "./types.js";

export interface MLCapabilities {
  voice_input: boolean;
  hindi_translation: boolean;
  bias_detection: boolean;
  skill_gap_reports: boolean;
  anomaly_detection: boolean;
  llm_explainability: boolean;
  embedding_model_loaded: boolean;
  reranker_model_loaded: boolean;
  fusion_ranker_trained: boolean;
}

export interface HealthResponse {
  status: string;
  index_ready: boolean;
  candidate_count: number;
  backend: string;
  capabilities: MLCapabilities;
  fallbacks_active: Record<string, boolean>;
}

export class MLClient {
  private http: AxiosInstance;

  constructor(baseUrl: string = config.mlServiceUrl) {
    this.http = axios.create({
      baseURL: baseUrl,
      timeout: 30_000,
      headers: { "Content-Type": "application/json" },
    });
  }

  async health(): Promise<HealthResponse> {
    const { data } = await this.http.get<HealthResponse>("/health");
    return data;
  }

  /** Generic GET for forwarding to the ML service (used by enterprise routes). */
  async getJSON<T = unknown>(path: string): Promise<T> {
    const { data } = await this.http.get<T>(path);
    return data;
  }

  /** Generic POST for forwarding to the ML service (used by enterprise routes). */
  async postJSON<T = unknown>(path: string, body: unknown): Promise<T> {
    const { data } = await this.http.post<T>(path, body);
    return data;
  }

  async runPipeline(
    input: PipelineInput,
    onProgress?: StageCallback,
  ): Promise<PipelineResult> {
    // Prefer the SSE stream so the gateway can fan progress out over WebSocket.
    if (onProgress) {
      return this.runPipelineStreamed(input, onProgress);
    }
    const { data } = await this.http.post<PipelineResult>("/pipeline/run", input);
    return data;
  }

  /**
   * Stream the ML service's /pipeline/run-stream SSE endpoint, invoking
   * onProgress for each stage event and resolving with the final result.
   */
  private async runPipelineStreamed(
    input: PipelineInput,
    onProgress: StageCallback,
  ): Promise<PipelineResult> {
    const url = `${config.mlServiceUrl}/pipeline/run-stream`;
    const body = JSON.stringify(input);

    // Node 22 ships fetch globally.
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body,
    });

    if (!resp.ok || !resp.body) {
      throw new Error(`ML stream failed: HTTP ${resp.status}`);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let result: PipelineResult | null = null;

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";
      for (const evt of events) {
        const line = evt.split("\n").find((l) => l.startsWith("data:"));
        if (!line) continue;
        const payload = JSON.parse(line.slice("data:".length).trim());
        if (payload.stage === "result" && payload.message) {
          result = JSON.parse(payload.message) as PipelineResult;
        } else if (payload.stage) {
          onProgress(payload.stage, payload.message ?? null, payload.progress ?? null);
        }
      }
    }

    if (!result) {
      // Stream ended without a result payload — fall back to blocking call.
      onProgress("complete", "Stream ended early; falling back to blocking call", null);
      const { data } = await this.http.post<PipelineResult>("/pipeline/run", input);
      return data;
    }
    return result;
  }
}

let singleton: MLClient | null = null;
export function getMLClient(): MLClient {
  if (!singleton) singleton = new MLClient();
  return singleton;
}
