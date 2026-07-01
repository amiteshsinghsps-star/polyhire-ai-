/**
 * Shortlist + candidate + galaxy REST routes.
 *
 * These read from the in-memory result store populated by /api/jd/submit.
 * The ML service is the source of truth for ranking; the gateway only
 * re-serves cached results here to avoid re-running the pipeline.
 */
import { Router, type Request, type Response } from "express";
import type { RankedCandidate } from "@polyhire/shared-types";

import { getCached, listCached } from "../store.js";

export function shortlistRouter(): Router {
  const router = Router();

  // List all cached run ids.
  router.get("/", (_req: Request, res: Response) => {
    res.json({ runs: listCached() });
  });

  // Fetch a previously computed ranked shortlist.
  router.get("/:jdId", (req: Request, res: Response) => {
    const result = getCached(req.params.jdId);
    if (!result) {
      res.status(404).json({ error: `No cached run for jdId ${req.params.jdId}` });
      return;
    }
    res.json({
      jdId: result.jdId,
      structured_jd: result.structured_jd,
      ranked_shortlist: result.ranked_shortlist,
      metrics: result.metrics,
    });
  });

  // Fetch a single ranked candidate by id within a run.
  router.get("/:jdId/candidate/:candidateId", (req: Request, res: Response) => {
    const result = getCached(req.params.jdId);
    if (!result) {
      res.status(404).json({ error: `No cached run for jdId ${req.params.jdId}` });
      return;
    }
    const candidate: RankedCandidate | undefined = result.ranked_shortlist.find(
      (c) => c.candidate_id === req.params.candidateId,
    );
    if (!candidate) {
      res.status(404).json({ error: `Candidate ${req.params.candidateId} not in run ${req.params.jdId}` });
      return;
    }
    res.json(candidate);
  });

  // Skill-gap report for a near-miss candidate.
  router.get("/:jdId/candidate/:candidateId/skill-gap", (req: Request, res: Response) => {
    const result = getCached(req.params.jdId);
    if (!result) {
      res.status(404).json({ error: `No cached run for jdId ${req.params.jdId}` });
      return;
    }
    const report = result.near_miss_skill_gaps.find(
      (g) => g.candidate_id === req.params.candidateId,
    );
    if (!report) {
      res.status(404).json({
        error: `No skill-gap report for ${req.params.candidateId}. (Only near-miss candidates have one.)`,
      });
      return;
    }
    res.json(report);
  });

  // Galaxy 3D coordinates for a run.
  router.get("/:jdId/galaxy", (req: Request, res: Response) => {
    const result = getCached(req.params.jdId);
    if (!result) {
      res.status(404).json({ error: `No cached run for jdId ${req.params.jdId}` });
      return;
    }
    if (!result.galaxy) {
      res.status(404).json({ error: "Galaxy projection unavailable for this run." });
      return;
    }
    res.json(result.galaxy);
  });

  return router;
}
