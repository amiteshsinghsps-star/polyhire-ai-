import { useEffect, useRef } from "react";
import { io, type Socket } from "socket.io-client";
import type { PipelineProgressEvent, PipelineResult, GalaxyUpdateEvent } from "@polyhire/shared-types";
import { useAppDispatch } from "../store/hooks";
import {
  pipelineProgress,
  pipelineComplete,
  pipelineError,
} from "../store/slices/pipelineSlice";
import { setShortlist, setNearMissSkillGaps } from "../store/slices/shortlistSlice";
import { setNodes, setWeights } from "../store/slices/galaxySlice";
import { setBharatSummary, setCandidateAdjustments } from "../store/slices/bharatSlice";

const GATEWAY_URL =
  typeof import.meta !== "undefined" && import.meta.env?.VITE_GATEWAY_URL
    ? String(import.meta.env.VITE_GATEWAY_URL)
    : "http://localhost:4000";

/**
 * Portable handle returned by useSocket. Exposes only `emit` so the
 * non-portable socket.io internal Emitter type never crosses the module
 * boundary (which would break declaration emit / typecheck portability).
 */
export interface SocketHandle {
  emit: (event: string, ...args: unknown[]) => void;
}

/**
 * Establishes the Socket.IO connection and wires server events into Redux.
 * Returns a handle exposing `emit` for outbound commands (e.g. galaxy reweight).
 */
export function useSocket(): React.MutableRefObject<SocketHandle | null> {
  const dispatch = useAppDispatch();
  const socketRef = useRef<Socket | null>(null);
  const handleRef = useRef<SocketHandle | null>(null);

  useEffect(() => {
    const socket = io(GATEWAY_URL, { transports: ["websocket", "polling"] });
    socketRef.current = socket;
    handleRef.current = {
      emit: (event: string, ...args: unknown[]) => socket.emit(event, ...args),
    };

    socket.on("connect", () => {
      console.log("[socket] connected:", socket.id);
    });

    socket.on("pipeline:progress", (evt: PipelineProgressEvent) => {
      dispatch(
        pipelineProgress({
          stage: evt.stage,
          message: evt.message ?? null,
          progress: evt.progress ?? null,
        }),
      );
    });

    socket.on("pipeline:complete", (result: PipelineResult) => {
      dispatch(
        pipelineComplete({
          jdId: result.jdId,
          latencyMs: result.metrics?.latency_ms ?? null,
          structuredJd: result.structured_jd as unknown as Record<string, unknown>,
          biasFlags: result.bias_flags,
        }),
      );
      dispatch(setShortlist(result.ranked_shortlist));
      dispatch(setNearMissSkillGaps(result.near_miss_skill_gaps));
      if (result.galaxy) {
        dispatch(setNodes(result.galaxy.nodes));
        dispatch(setWeights(result.galaxy.weights));
      }
      if (result.bharat_context) {
        dispatch(setBharatSummary(result.bharat_context));
      }
      if (result.bharat_adjustments) {
        dispatch(setCandidateAdjustments(result.bharat_adjustments));
      }
    });

    socket.on("pipeline:error", (evt: { error: string }) => {
      dispatch(pipelineError(evt.error));
    });

    socket.on("galaxy:update", (evt: GalaxyUpdateEvent) => {
      dispatch(setNodes(evt.coordinates));
      dispatch(setWeights(evt.weights));
    });

    return () => {
      socket.disconnect();
    };
  }, [dispatch]);

  // Stable handle whose emit forwards to the live socket — avoids null on
  // first render and prevents WeightSliders from throwing on early emit.
  if (handleRef.current === null) {
    handleRef.current = {
      emit: (event: string, ...args: unknown[]) => {
        socketRef.current?.emit(event, ...args);
      },
    };
  }
  return handleRef;
}
