/**
 * Bharat Intelligence Layer — Gateway proxy routes.
 * Forwards /api/bharat/* to the ML service /bharat/* endpoints.
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

export function bharatRouter(): Router {
  const router = Router();

  router.post("/tier-normalize", (req, res) => {
    const client = getMLClient();
    forward(() => client.postJSON("/bharat/tier-normalize", req.body), res);
  });

  router.get("/classify-city", (req, res) => {
    const client = getMLClient();
    const city = String(req.query.city ?? "");
    forward(() => client.getJSON(`/bharat/classify-city?city=${encodeURIComponent(city)}`), res);
  });

  router.post("/institution-score", (req, res) => {
    const client = getMLClient();
    forward(() => client.postJSON("/bharat/institution-score", req.body), res);
  });

  router.get("/nirf-lookup", (req, res) => {
    const client = getMLClient();
    const name = String(req.query.name ?? "");
    forward(() => client.getJSON(`/bharat/nirf-lookup?name=${encodeURIComponent(name)}`), res);
  });

  router.post("/code-switch-parse", (req, res) => {
    const client = getMLClient();
    forward(() => client.postJSON("/bharat/code-switch-parse", req.body), res);
  });

  router.post("/informal-sector-translate", (req, res) => {
    const client = getMLClient();
    forward(() => client.postJSON("/bharat/informal-sector-translate", req.body), res);
  });

  return router;
}
