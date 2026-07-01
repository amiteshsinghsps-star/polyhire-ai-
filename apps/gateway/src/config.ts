/**
 * Gateway runtime configuration. Single place env vars are read.
 */
import "dotenv/config";

function required(key: string, fallback = ""): string {
  const v = process.env[key] ?? fallback;
  return v;
}

function int(key: string, fallback: number): number {
  const raw = process.env[key];
  if (!raw) return fallback;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) ? n : fallback;
}

export const config = {
  port: int("GATEWAY_PORT", 4000),
  mlServiceUrl: required("ML_SERVICE_URL", "http://localhost:8000"),
  corsOrigin: required("CORS_ORIGIN", "*"),
  nodeEnv: required("NODE_ENV", "development"),
} as const;
