/** Health + capabilities route — proxies the ML service's /health so the
 * frontend can adapt its UI to whichever bonus models loaded in this build. */
import { Router, type Request, type Response } from "express";
import { getMLClient } from "../mlClient.js";

export function healthRouter(): Router {
  const router = Router();

  router.get("/", async (_req: Request, res: Response) => {
    try {
      const health = await getMLClient().health();
      res.json({
        status: "ok",
        gateway: { version: "1.0.0" },
        ml: health,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      res.status(503).json({
        status: "degraded",
        error: `ML service unreachable: ${message}`,
      });
    }
  });

  return router;
}
