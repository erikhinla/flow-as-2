/**
 * FAAS adapter for the official OpenClaw agent.
 * The selected model is supplied per job. No plain-chat fallback is allowed.
 */

import { createServer } from "node:http";
import { mkdir, unlink, writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";

const host = "0.0.0.0";
const port = Number(process.env.FLOW_RUNTIME_PORT || "18790");
// Paid models only. Never default to OpenRouter :free (free-models-per-day 429).
const model = process.env.OPENCLAW_AGENT_MODEL || "openai/gpt-5.6-terra";
const thinking = process.env.OPENCLAW_THINKING || "off";
const allowedModels = new Set([
  "openai/gpt-5.6-luna",
  "openai/gpt-5.6-terra",
  "openai/gpt-5.6-sol",
  "anthropic/claude-sonnet-5",
]);
const timeoutMs = Number(process.env.FLOW_RUNTIME_TIMEOUT_SECONDS || "900") * 1000;
const promptDir = "/home/node/.openclaw/flow-prompts";
const upstreamRepository = "https://github.com/openclaw/openclaw";
const upstreamCommit = process.env.OPENCLAW_UPSTREAM_COMMIT || "unknown";

await mkdir(promptDir, { recursive: true });

function execute(args, input = "") {
  return new Promise((resolve, reject) => {
    const child = spawn("node", ["/app/openclaw.mjs", ...args], {
      cwd: "/home/node/.openclaw/workspace",
      env: process.env,
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill("SIGTERM");
      reject(new Error("OpenClaw execution timed out"));
    }, timeoutMs);

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        const errText = (stderr.trim() || stdout.trim() || `OpenClaw exited ${code}`).trim();
        const lines = errText.split("\n").filter(Boolean);
        const last = [...lines]
          .reverse()
          .find((l) => /FailoverError|billing|422|rejected|overflow|error=/i.test(l));
        reject(new Error(last || lines.slice(-8).join("\n") || errText));
        return;
      }
      resolve({ stdout: stdout.trim(), stderr: stderr.trim() });
    });
    child.stdin.end(input);
  });
}

function parseEnvelope(stdout) {
  try {
    return JSON.parse(stdout);
  } catch {
    const start = stdout.lastIndexOf("{");
    const end = stdout.lastIndexOf("}");
    if (start >= 0 && end > start) {
      return JSON.parse(stdout.slice(start, end + 1));
    }
    throw new Error("OpenClaw returned non-JSON output");
  }
}

async function version() {
  const result = await execute(["--version"]);
  return result.stdout || result.stderr;
}

async function runAgent(prompt, jobId, selectedModel, selectedThinking) {
  if (!allowedModels.has(selectedModel)) {
    throw new Error(`model '${selectedModel}' is not approved for OpenClaw`);
  }
  const safeId = String(jobId || "anonymous").replace(/[^a-zA-Z0-9._-]/g, "_");
  const openClawModel = `openrouter/${selectedModel}`;
  const promptPath = `${promptDir}/${safeId}.md`;
  await writeFile(promptPath, prompt, { encoding: "utf8", mode: 0o600 });
  try {
    const args = [
      "agent",
      "--local",
      "--message-file",
      promptPath,
      "--model",
      openClawModel,
      "--session-id",
      `faas-${safeId}`,
      "--thinking",
      selectedThinking,
      "--json",
    ];
    const result = await execute(args);
    const envelope = parseEnvelope(result.stdout);
    if (envelope.aborted) {
      throw new Error("OpenClaw execution was aborted");
    }
    if (envelope.error?.kind === "context_overflow" || envelope.livenessState === "blocked") {
      throw new Error(
        envelope.error?.message || "OpenClaw agent blocked (context overflow or billing)",
      );
    }
    const final = String(
      envelope.finalAssistantVisibleText ||
        envelope.payloads?.map((payload) => payload?.text).filter(Boolean).join("\n\n") ||
        "",
    ).trim();
    if (!final) {
      throw new Error("OpenClaw returned an empty response");
    }
    return {
      final,
      model: envelope.meta?.agentMeta?.model || envelope.executionTrace?.winnerModel || selectedModel,
      provider: envelope.meta?.agentMeta?.provider || "openclaw",
      usage: envelope.meta?.agentMeta?.usage,
      mode: "openclaw_agent",
      envelope,
    };
  } finally {
    await unlink(promptPath).catch(() => {});
  }
}

function send(response, status, payload) {
  const body = JSON.stringify(payload);
  response.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(body),
  });
  response.end(body);
}

const server = createServer(async (request, response) => {
  if (request.method === "GET" && ["/health", "/healthz"].includes(request.url)) {
    try {
      send(response, 200, {
        ok: true,
        engine: "openclaw",
        version: await version(),
        model,
        thinking,
        allowed_models: [...allowedModels],
        official_agent_only: true,
        upstream_repository: upstreamRepository,
        upstream_commit: upstreamCommit,
      });
    } catch (error) {
      send(response, 503, { ok: false, engine: "openclaw", error: String(error.message || error) });
    }
    return;
  }

  if (request.method !== "POST" || request.url !== "/run") {
    send(response, 404, { ok: false, error: "not found" });
    return;
  }

  let body = "";
  request.on("data", (chunk) => {
    body += chunk.toString();
  });
  request.on("end", async () => {
    try {
      const payload = JSON.parse(body || "{}");
      const prompt = String(payload.prompt || "").trim();
      if (!prompt) {
        send(response, 400, { ok: false, error: "prompt is required" });
        return;
      }
      const selectedModel = String(payload.model || model).replace(/^openrouter\//, "");
      const selectedThinking = String(payload.thinking || thinking);
      const result = await runAgent(
        prompt,
        String(payload.job_id || "anonymous"),
        selectedModel,
        selectedThinking,
      );
      const reportedModel = String(result.model || "").replace(/^openrouter\//, "");
      if (reportedModel !== selectedModel) {
        throw new Error(
          `OpenClaw model mismatch: selected ${selectedModel}, reported ${reportedModel}`,
        );
      }
      send(response, 200, {
        ok: true,
        engine: "openclaw",
        final: result.final,
        usage: result.usage,
        model: result.model,
        provider: result.provider,
        execution_mode: result.mode,
        upstream_repository: upstreamRepository,
        upstream_commit: upstreamCommit,
      });
    } catch (error) {
      send(response, 500, { ok: false, engine: "openclaw", error: String(error.message || error) });
    }
  });
});

server.listen(port, host, () => {
  process.stdout.write(
    `OpenClaw adapter listening on ${host}:${port} default_model=${model} thinking=${thinking} official_agent_only=true (upstream ${upstreamCommit})\n`,
  );
});
