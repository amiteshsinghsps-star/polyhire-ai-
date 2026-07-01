/** Shared gateway-local types. */
import type { PipelineStage } from "@polyhire/shared-types";

export type StageCallback = (
  stage: PipelineStage,
  message: string | null,
  progress: number | null,
) => void;

export interface SocketServer {
  emit: (event: string, ...args: unknown[]) => void;
}
