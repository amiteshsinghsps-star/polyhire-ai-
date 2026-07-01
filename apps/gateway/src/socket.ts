/**
 * Socket.IO connection wiring.
 *
 * Handles the galaxy reweight command (recruiter drags weight sliders → the
 * gateway re-scores via the ML service and broadcasts new coordinates to all
 * viewers). Other events are emitted from the JD route, not here.
 */
import type { Server as SocketIOServer } from "socket.io";
import type {
  GalaxyNode,
  GalaxyReweightCommand,
  GalaxyUpdateEvent,
  PipelineResult,
} from "@polyhire/shared-types";

import { getCached } from "./store.js";

export function registerSocketHandlers(io: SocketIOServer): void {
  io.on("connection", (socket) => {
    console.log(`[socket] client connected: ${socket.id}`);

    socket.on("galaxy:reweight", (cmd: GalaxyReweightCommand) => {
      const { jdId, weights } = cmd ?? {};
      if (!jdId || !weights) {
        socket.emit("galaxy:error", { error: "jdId and weights are required" });
        return;
      }
      const cached = getCached(jdId);
      if (!cached) {
        socket.emit("galaxy:error", { error: `No cached run for jdId ${jdId}` });
        return;
      }

      // Re-score the shortlist locally using the simple weighted-sum model
      // derived from the fusion feature_contributions. The galaxy geometry
      // updates instantly; the authoritative score lives in the ML service.
      const updated = reweightLocally(cached, weights);
      const event: GalaxyUpdateEvent = {
        jdId,
        coordinates: updated,
        weights,
      };
      io.emit("galaxy:update", event); // broadcast to all viewers of this run
    });

    socket.on("disconnect", (reason) => {
      console.log(`[socket] client disconnected: ${socket.id} (${reason})`);
    });
  });
}

/**
 * Lightweight client-side reweight using each candidate's feature_contributions.
 * The fusion score under new weights ≈ sum(contrib * newW / oldW) for features
 * whose contribution we already have. This avoids a round-trip to the ML
 * service on every slider tick.
 *
 * Returns GalaxyNode[] (the same schema the frontend expects), preserving each
 * node's existing spatial coordinates + cluster and only updating rank/score.
 */
function reweightLocally(
  result: PipelineResult,
  weights: Record<string, number>,
): GalaxyNode[] {
  const galaxyNodeById = new Map(
    (result.galaxy?.nodes ?? []).map((n) => [n.candidateId, n]),
  );

  // First compute the new proxy scores, then rank, then assign coordinates.
  const scored = result.ranked_shortlist.map((c) => {
    const contribs = c.feature_contributions ?? {};
    let score = 0;
    for (const [key, rawValue] of Object.entries(contribs)) {
      if (key === "base_value") continue;
      const value = typeof rawValue === "number" ? rawValue : Number(rawValue) || 0;
      score += (weights[key] ?? 1) * Math.sign(value) * Math.abs(value);
    }
    // Normalize to [0,1]-ish via tanh for stable visualization.
    return {
      candidateId: c.candidate_id,
      proxyScore: Math.tanh(Math.max(0, score)),
    };
  });

  // Sort by proxy score desc so the rank assignment reflects new weights.
  scored.sort((a, b) => b.proxyScore - a.proxyScore);

  return scored.map((s, idx) => {
    const node = galaxyNodeById.get(s.candidateId);
    return {
      candidateId: s.candidateId,
      rank: idx + 1,
      score: s.proxyScore,
      // Preserve original spatial position + cluster; the frontend re-lays-out
      // smoothly from these coordinates under the new score weighting.
      x: node?.x ?? 0,
      y: node?.y ?? 0,
      z: node?.z ?? 0,
      cluster: node?.cluster ?? "general",
      isNearMiss: idx >= 20,
    } satisfies GalaxyNode;
  });
}
