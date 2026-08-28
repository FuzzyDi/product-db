import { createReadStream, existsSync, readFileSync } from 'node:fs';
import { stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import { dirname, extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const projectRoot = dirname(__dirname);
const distDir = join(__dirname, 'dist');
const indexFile = join(distDir, 'index.html');

const host = process.env.HOST || '0.0.0.0';
const port = Number(process.env.PORT || 3002);
const apiTarget = process.env.API_TARGET || 'http://127.0.0.1:8001';

function readDefaultApiKey() {
  if (process.env.API_PROXY_KEY) {
    return process.env.API_PROXY_KEY.trim();
  }

  try {
    const envText = readFileSync(join(projectRoot, '.env'), 'utf8');
    const line = envText
      .split(/\r?\n/)
      .find(item => item.startsWith('API_KEYS='));
    if (!line) return '';
    const value = line.slice('API_KEYS='.length).trim();
    return value.split(',')[0]?.trim() || '';
  } catch {
    return '';
  }
}

const defaultApiKey = readDefaultApiKey();

const CONTENT_TYPES = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

function sendJson(res, statusCode, body) {
  res.writeHead(statusCode, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(body));
}

function getContentType(pathname) {
  return CONTENT_TYPES[extname(pathname)] || 'application/octet-stream';
}

async function proxyApi(req, res) {
  const targetUrl = new URL(req.url, apiTarget);
  const headers = new Headers();
  for (const [key, value] of Object.entries(req.headers)) {
    if (Array.isArray(value)) {
      headers.set(key, value.join(', '));
    } else if (value) {
      headers.set(key, value);
    }
  }
  headers.set('host', targetUrl.host);
  if (defaultApiKey && !headers.has('x-api-key')) {
    headers.set('x-api-key', defaultApiKey);
  }

  try {
    const upstream = await fetch(targetUrl, {
      method: req.method,
      headers,
      body: req.method === 'GET' || req.method === 'HEAD' ? undefined : req,
      duplex: 'half',
    });

    const responseHeaders = {};
    upstream.headers.forEach((value, key) => {
      if (key.toLowerCase() !== 'transfer-encoding') {
        responseHeaders[key] = value;
      }
    });
    res.writeHead(upstream.status, responseHeaders);
    if (upstream.body) {
      for await (const chunk of upstream.body) {
        res.write(chunk);
      }
    }
    res.end();
  } catch (error) {
    sendJson(res, 502, {
      success: false,
      data: null,
      meta: {},
      error: `API proxy error: ${error instanceof Error ? error.message : String(error)}`,
    });
  }
}

async function serveFile(res, pathname) {
  const filePath = normalize(join(distDir, pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '')));
  const safePath = filePath.startsWith(distDir) ? filePath : indexFile;

  let finalPath = safePath;
  try {
    const fileStat = await stat(safePath);
    if (fileStat.isDirectory()) {
      finalPath = indexFile;
    }
  } catch {
    finalPath = pathname.startsWith('/assets/') ? safePath : indexFile;
  }

  if (!existsSync(finalPath)) {
    sendJson(res, 404, { success: false, data: null, meta: {}, error: 'Not found' });
    return;
  }

  res.writeHead(200, { 'Content-Type': getContentType(finalPath) });
  createReadStream(finalPath).pipe(res);
}

const server = createServer(async (req, res) => {
  if (!req.url) {
    sendJson(res, 400, { success: false, data: null, meta: {}, error: 'Missing URL' });
    return;
  }

  if (req.url.startsWith('/api/')) {
    await proxyApi(req, res);
    return;
  }

  await serveFile(res, req.url);
});

server.listen(port, host, () => {
  console.log(`Product DB frontend listening on http://${host}:${port}`);
});
