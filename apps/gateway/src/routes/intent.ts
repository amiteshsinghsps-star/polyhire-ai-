/**
 * CandidateIntent™ Proxy Routes (v2.0 — F1)
 *
 * Forwards to the ML service /intent/* endpoints.
 */
import { Router } from "express";
import { getMLClient } from "../mlClient.js";

function forward<T>(
  fn: () => Promise<T>,
  res: { json: (body: unknown) => void; status: (code: number) => { json: (body: unknown) => void } },
): void {
  fn()
    .then((data) => res.json(data))
    .catch((err: unknown) => {
      const message = err instanceof Error ? err.message : "ML service error";
      res.status(502).json({ error: message });
    });
}

export function intentRouter(): Router {
  const router = Router();

  /** Score a single candidate's intent / mobility readiness. */
  router.post("/score", (req, res) => {
    const client = getMLClient();
    forward(() => client.postJSON("/intent/score", req.body), res);
  });

  /** Enrich a full shortlist with intent scores and re-sort. */
  router.post("/score-batch", (req, res) => {
    const client = getMLClient();
    forward(() => client.postJSON("/intent/score-batch", req.body), res);
  });

  /** Build the 2×2 Fit × Intent priority matrix. */
  router.post("/priority-matrix", (req, res) => {
    const client = getMLClient();
    forward(() => client.postJSON("/intent/priority-matrix", req.body), res);
  });

  return router;
}
