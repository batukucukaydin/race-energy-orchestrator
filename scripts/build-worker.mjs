import { mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { dirname, extname, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dist = resolve(root, "dist");
const server = resolve(dist, "server");

const docs = resolve(root, "docs");
const contentTypes = { ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".csv": "text/csv; charset=utf-8" };

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map(entry => entry.isDirectory() ? walk(resolve(directory, entry.name)) : resolve(directory, entry.name)));
  return nested.flat();
}

await rm(dist, { recursive: true, force: true });
await mkdir(server, { recursive: true });

const entries = {};
for (const file of await walk(docs)) {
  const pathname = `/${relative(docs, file).split(sep).join("/")}`;
  entries[pathname] = { type: contentTypes[extname(file)] || "application/octet-stream", body: await readFile(file, "utf8") };
}
entries["/"] = entries["/index.html"];

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
