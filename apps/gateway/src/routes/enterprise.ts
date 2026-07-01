/**
 * Enterprise Feature Routes (§23).
 *
 * Gateway-side proxy for the ML service's /enterprise/* endpoints.
 * Mirrors the structure of the other routers but stays thin —
 * just forwards to the ML service with light validation.
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

export function enterpriseRouter(): Router {
  const router = Router();

  // §23.1 — Uncertainty bands
  router.post("/candidate/:id/uncertainty", async (req, res) => {
    const client = getMLClient();
    forward(
      () => client.postJSON(`/enterprise/uncertainty`, { candidate_id: req.params.id, ...req.body }),
      res,
    );
  });

  // §23.2 — Counterfactual
  router.post("/candidate/:id/counterfactual", async (req, res) => {
    const client = getMLClient();
    forward(
      () => client.postJSON(`/enterprise/counterfactual/${req.params.id}`, req.body),
      res,
    );
  });

  // §23.3 — Portfolio optimization
  router.post("/portfolio/optimize", async (req, res) => {
    const client = getMLClient();
    forward(() => client.postJSON(`/enterprise/portfolio/optimize`, req.body), res);
  });

  // §23.4 — Audit trail
  router.get("/audit/:jdId", async (req, res) => {
    const client = getMLClient();
    forward(() => client.getJSON(`/enterprise/audit/${req.params.jdId}`), res);
  });

  router.get("/audit/:jdId/verify", async (req, res) => {
    const client = getMLClient();
    forward(() => client.getJSON(`/enterprise/audit/${req.params.jdId}/verify`), res);
  });

  router.post("/audit/disparate-impact", async (req, res) => {
    const client = getMLClient();
    forward(() => client.postJSON(`/enterprise/audit/disparate-impact`, req.body), res);
  });

  // §23.5 — Diversity re-ranking
  router.post("/shortlist/diversify", async (req, res) => {
    const client = getMLClient();
    forward(() => client.postJSON(`/enterprise/diversify`, req.body), res);
  });

  // §23.6 — Passive talent matches
  router.get("/talent-pool/passive-matches", async (req, res) => {
    const client = getMLClient();
    const threshold = req.query.threshold ?? "0.85";
    forward(() => client.getJSON(`/enterprise/talent-pool/passive-matches?threshold=${threshold}`), res);
  });

  // §23.7 — Interview questions
  router.post("/interview-questions", async (req, res) => {
    const client = getMLClient();
    forward(() => client.postJSON(`/enterprise/interview-questions`, req.body), res);
  });

  // §23.8 — Drift status
  router.get("/drift-status", async (_req, res) => {
    const client = getMLClient();
    forward(() => client.getJSON(`/enterprise/drift-status`), res);
  });

  return router;
}
