/**
 * HirePredict™ Proxy Routes (v2.0 — F3)
 *
 * Forwards to the ML service /hire-predict/* endpoints.
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

export function hirePredictRouter(): Router {
  const router = Router();

  /** Submit a hire/no-hire outcome to train the feedback model. */
  router.post("/feedback", (req, res) => {
    const client = getMLClient();
    forward(() => client.postJSON("/hire-predict/feedback", req.body), res);
  });

  /** Get hire probability predictions for a shortlist. */
  router.post("/predict", (req, res) => {
    const client = getMLClient();
    forward(() => client.postJSON("/hire-predict/predict", req.body), res);
  });

  /** Force model retraining after bulk feedback. */
  router.post("/train", (_req, res) => {
    const client = getMLClient();
    forward(() => client.postJSON("/hire-predict/train", {}), res);
  });

  /** Model accuracy report + outcome collection progress. */
  router.get("/accuracy", (_req, res) => {
    const client = getMLClient();
    forward(() => client.getJSON("/hire-predict/accuracy"), res);
  });

  /** All outcomes recorded for a specific JD. */
  router.get("/outcomes/:jdId", (req, res) => {
    const client = getMLClient();
    forward(() => client.getJSON(`/hire-predict/outcomes/${req.params.jdId}`), res);
  });

  return router;
}
