import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dist = resolve(root, "dist");
const server = resolve(dist, "server");

const files = {
  "/": { file: "index.html", type: "text/html; charset=utf-8" },
  "/index.html": { file: "index.html", type: "text/html; charset=utf-8" },
  "/metrics.csv": { file: "metrics.csv", type: "text/csv; charset=utf-8" },
  "/strategy_trace.csv": { file: "strategy_trace.csv", type: "text/csv; charset=utf-8" },
};

await rm(dist, { recursive: true, force: true });
await mkdir(server, { recursive: true });

const entries = {};
for (const [route, meta] of Object.entries(files)) {
  entries[route] = {
    type: meta.type,
    body: await readFile(resolve(root, "docs", meta.file), "utf8"),
  };
}

const worker = `const files = ${JSON.stringify(entries)};

function securityHeaders(contentType) {
  return {
    "content-type": contentType,
    "cache-control": "public, max-age=300",
    "x-content-type-options": "nosniff"
  };
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const route = files[url.pathname] || files[url.pathname.replace(/\\/$/, "")];

    if (!route) {
      return new Response("Not found", {
        status: 404,
        headers: securityHeaders("text/plain; charset=utf-8")
      });
    }

    return new Response(route.body, {
      headers: securityHeaders(route.type)
    });
  }
};
`;

await writeFile(resolve(server, "index.js"), worker);
