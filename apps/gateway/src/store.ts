/**
 * Result cache. In-memory, keyed by jdId — sufficient for a PoC and avoids
 * spinning up Redis. The gateway owns this so re-fetching a shortlist after
 * the WebSocket completes doesn't re-run the pipeline.
 */
import type { PipelineResult } from "@polyhire/shared-types";

const store = new Map<string, PipelineResult>();

export function cacheResult(result: PipelineResult): void {
  store.set(result.jdId, result);
  // Keep the cache bounded — last 100 runs.
  if (store.size > 100) {
    const firstKey = store.keys().next().value;
    if (firstKey) store.delete(firstKey);
  }
}

export function getCached(jdId: string): PipelineResult | undefined {
  return store.get(jdId);
}

export function listCached(): string[] {
  return Array.from(store.keys());
}
