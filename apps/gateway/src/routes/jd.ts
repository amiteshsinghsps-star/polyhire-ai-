/**
 * JD submission route.
 *
 * Orchestrates the pipeline: forwards the JD to the ML service, fans per-stage
 * progress out to all connected Socket.IO clients, caches the result, and
 * responds to the HTTP caller. The Socket.IO server is injected so this route
 * stays decoupled from transport concerns.
 */
import { Router, type Request, type Response } from "express";
import { z } from "zod";
import type { Server as SocketIOServer } from "socket.io";
import type { PipelineInput, PipelineResult, PipelineStage } from "@polyhire/shared-types";

import { getMLClient } from "../mlClient.js";
import type { StageCallback } from "../types.js";
import { cacheResult } from "../store.js";

const submitSchema = z.object({
  text: z.string().optional(),
  audio_path: z.string().optional(),
  language: z.string().default("en"),
  dataset_path: z.string().optional(),
  top_k: z.number().int().positive().max(500).optional(),
}).refine((v) => v.text || v.audio_path, {
  message: "Either `text` or `audio_path` must be provided.",
});

export function jdRouter(io: SocketIOServer): Router {
  const router = Router();

  router.post("/submit", async (req: Request, res: Response) => {
    const parsed = submitSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: "Invalid request", details: parsed.error.flatten() });
      return;
    }

    const input: PipelineInput = parsed.data;
    const timestamp = Date.now();

    // Wire progress events to every connected client.
    const onProgress: StageCallback = (
      stage: PipelineStage,
      message: string | null,
      progress: number | null,
    ) => {
      io.emit("pipeline:progress", { stage, message, progress, timestamp: Date.now() });
    };

    io.emit("pipeline:started", { stage: "input_normalization", timestamp });
    console.log(`[jd] submit received: text=${(input.text ?? "").length}B lang=${input.language}`);

    try {
      const result: PipelineResult = await getMLClient().runPipeline(input, onProgress);
      cacheResult(result);
      io.emit("pipeline:complete", result);
      console.log(`[jd] pipeline complete: jdId=${result.jdId} rank0=${result.ranked_shortlist[0]?.candidate_id ?? "n/a"} latency=${result.metrics?.latency_ms ?? "?"}ms`);
      res.json(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      console.error("[jd] pipeline failed:", message);
      io.emit("pipeline:error", {
        stage: "complete",
        error: message,
        timestamp: Date.now(),
      });
      res.status(502).json({ error: "ML pipeline failed", details: message });
    }
  });

  return router;
}
