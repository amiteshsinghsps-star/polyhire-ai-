/**
 * PolyHire AI — API Gateway entrypoint.
 *
 * Node.js + Express + Socket.IO. Owns session state, fans pipeline progress
 * out to the 3D frontend over WebSocket, and proxies the heavy lifting to the
 * Python ML service. Stays fast and non-blocking — no ML inference runs here.
 */
import cors from "cors";
import express from "express";
import morgan from "morgan";
import { createServer } from "node:http";
import { Server as SocketIOServer } from "socket.io";

import { config } from "./config.js";
import { healthRouter } from "./routes/health.js";
import { jdRouter } from "./routes/jd.js";
import { shortlistRouter } from "./routes/shortlist.js";
import { enterpriseRouter } from "./routes/enterprise.js";
import { bharatRouter } from "./routes/bharat.js";
import { intentRouter } from "./routes/intent.js";
import { skillDecayRouter } from "./routes/skillDecay.js";
import { hirePredictRouter } from "./routes/hirePredict.js";
import { registerSocketHandlers } from "./socket.js";

const app = express();
app.use(cors({ origin: config.corsOrigin }));
app.use(express.json({ limit: "10mb" }));
if (config.nodeEnv !== "test") {
  app.use(morgan("tiny"));
}

const httpServer = createServer(app);
const io = new SocketIOServer(httpServer, {
  cors: { origin: config.corsOrigin, methods: ["GET", "POST"] },
});

// Routes
app.get("/", (_req, res) => {
  res.json({
    service: "PolyHire AI — Gateway",
    version: "2.0.0",
    endpoints: {
      submit_jd: "POST /api/jd/submit",
      shortlist: "GET /api/shortlist/:jdId",
      candidate: "GET /api/shortlist/:jdId/candidate/:candidateId",
      skill_gap: "GET /api/shortlist/:jdId/candidate/:candidateId/skill-gap",
      galaxy: "GET /api/shortlist/:jdId/galaxy",
      enterprise: "/api/enterprise/*",
      bharat: "/api/bharat/*",
      intent: "/api/intent/*",
      skill_decay: "/api/skill-decay/*",
      hire_predict: "/api/hire-predict/*",
      health: "GET /api/health",
    },
  });
});

app.use("/api/health", healthRouter());
app.use("/api/jd", jdRouter(io));
app.use("/api/shortlist", shortlistRouter());
app.use("/api/enterprise", enterpriseRouter());
app.use("/api/bharat", bharatRouter());
// v2.0 Feature Expansion
app.use("/api/intent", intentRouter());
app.use("/api/skill-decay", skillDecayRouter());
app.use("/api/hire-predict", hirePredictRouter());

// Socket wiring
registerSocketHandlers(io);

httpServer.listen(config.port, () => {
  console.log(`\n  PolyHire AI Gateway`);
  console.log(`  ─────────────────────────────────────────`);
  console.log(`  HTTP:     http://localhost:${config.port}`);
  console.log(`  WebSocket: ws://localhost:${config.port}`);
  console.log(`  ML service: ${config.mlServiceUrl}`);
  console.log(`  Env: ${config.nodeEnv}\n`);
});

export { app, httpServer, io };
