// Custom Next.js server — extend HTTP timeout untuk model lokal lambat
// (Gemma-12B / Qwen-32B via llama.cpp butuh 3-5 menit ingest 13K token)
// Default Next.js/Node.js timeout ~60s tidak cukup.
const { createServer } = require("http");
const { parse }        = require("url");
const next             = require("next");

const port = parseInt(process.env.PORT || "3002", 10);
const app  = next({ dev: false });
const handle = app.getRequestHandler();

app.prepare().then(() => {
  const server = createServer((req, res) => {
    handle(req, res, parse(req.url, true));
  });

  server.timeout          = 300_000;  // 5 menit — tunggu model ingest
  server.keepAliveTimeout = 305_000;
  server.headersTimeout   = 310_000;

  server.listen(port, "0.0.0.0", () => {
    console.log(`> Sultan Advisor ready on http://localhost:${port}`);
    console.log(`> HTTP timeout: ${server.timeout / 1000}s (model lokal mode)`);
  });
});
