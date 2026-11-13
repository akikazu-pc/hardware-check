// Fetch OEM pages through Node's TLS stack and cache the bodies for the Python collectors.
//
// PowerShell, curl and Python all fail on several vendor sites from this host: Acer stalls on a
// TLS renegotiation, MSI and Gigabyte answer 403 to the schannel/OpenSSL fingerprints, and Dell
// blocks the same clients. Node's fetch passes all of them, so it is used only as the transport.
//
// Usage: node scripts/oem-http.mjs <url>... | --list <file> | --post <url> <json-body>
//        | --post-with-session <warm-url> <url> <json-body>
// Prints one JSON array entry per URL: {"url", "status", "file", "bytes"}.
//
// --post-with-session first GETs <warm-url> (Acer hands out the Akamai session cookies there) and
// replays the resulting cookies, Referer and Origin on the JSON POST. The warm body is not cached,
// so the URL cache still holds the response of the requested POST.
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const CACHE = join(ROOT, "artifacts", "oem-cache");
const TIMEOUT_MS = 45_000;
const PAUSE_MS = 400;
// Akamai hands out the session cookies on the page GET but rejects an immediate POST with 403;
// this short settle time lets the edge accept the replayed cookies.
const WARM_SETTLE_MS = 2500;
const HEADERS = {
  "user-agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
  "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  "accept-language": "en-US,en;q=0.9"
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function fetchOne(url, body) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const options = { signal: controller.signal, headers: HEADERS, redirect: "follow" };
  if (body !== undefined) {
    options.method = "POST";
    options.headers = { ...HEADERS, "content-type": "application/json", "x-requested-with": "XMLHttpRequest" };
    options.body = body;
  }
  try {
    const response = await fetch(url, options);
    const body = Buffer.from(await response.arrayBuffer());
    const file = join(CACHE, `${createHash("sha1").update(url).digest("hex")}.bin`);
    await writeFile(file, body);
    return { url, status: response.status, file, bytes: body.length };
  } catch (error) {
    return { url, status: 0, error: error.name, file: "", bytes: 0 };
  } finally {
    clearTimeout(timer);
  }
}

function sessionCookie(response) {
  const values = response.headers.getSetCookie ? response.headers.getSetCookie() : [];
  return values.map((value) => value.split(";")[0]).filter(Boolean).join("; ");
}

async function fetchWithSession(warmUrl, url, body) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    for (let attempt = 0; attempt < 2; attempt += 1) {
      const warm = await fetch(warmUrl, { signal: controller.signal, headers: HEADERS, redirect: "follow" });
      await warm.arrayBuffer();
      const cookies = sessionCookie(warm);
      const origin = new URL(warmUrl).origin;
      await sleep(WARM_SETTLE_MS * (attempt + 1));
      const response = await fetch(url, {
        signal: controller.signal,
        method: "POST",
        redirect: "follow",
        headers: {
          ...HEADERS,
          accept: "application/json, text/plain, */*",
          "content-type": "application/json",
          "x-requested-with": "XMLHttpRequest",
          cookie: cookies,
          referer: warmUrl,
          origin
        },
        body
      });
      const payload = Buffer.from(await response.arrayBuffer());
      if (response.status !== 403 || attempt === 1) {
        const file = join(CACHE, `${createHash("sha1").update(url).digest("hex")}.bin`);
        await writeFile(file, payload);
        return {
          url,
          status: response.status,
          file,
          bytes: payload.length,
          warmStatus: warm.status,
          cookies: cookies.length
        };
      }
    }
    throw new Error("unreachable");
  } catch (error) {
    return { url, status: 0, error: error.name, file: "", bytes: 0 };
  } finally {
    clearTimeout(timer);
  }
}

async function main() {
  const args = process.argv.slice(2);
  let urls = args;
  let body;
  let warmUrl;
  if (args[0] === "--list") {
    urls = (await readFile(args[1], "utf8")).split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  } else if (args[0] === "--post") {
    urls = [args[1]];
    body = args[2];
  } else if (args[0] === "--post-with-session") {
    warmUrl = args[1];
    urls = [args[2]];
    body = args[3];
  }
  await mkdir(CACHE, { recursive: true });
  const results = [];
  for (const url of urls) {
    results.push(warmUrl ? await fetchWithSession(warmUrl, url, body) : await fetchOne(url, body));
    await sleep(PAUSE_MS);
  }
  console.log(JSON.stringify(results, null, 1));
}

await main();
