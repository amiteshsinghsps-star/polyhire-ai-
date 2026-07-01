/**
 * SkillDecay™ Proxy Routes (v2.0 — F2)
 *
 * Forwards to the ML service /skill-decay/* endpoints.
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

export function skillDecayRouter(): Router {
  const router = Router();

  /** Compute time-decayed skill relevance for a single candidate. */
  router.post("/analyze", (req, res) => {
    const client = getMLClient();
    forward(() => client.postJSON("/skill-decay/analyze", req.body), res);
  });

  /** Enrich a full shortlist — replaces static skill_overlap_ratio. */
  router.post("/enrich-batch", (req, res) => {
    const client = getMLClient();
    forward(() => client.postJSON("/skill-decay/enrich-batch", req.body), res);
  });

  return router;
}
