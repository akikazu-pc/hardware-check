// Warm the Acer support page then POST the driver search, printing the JSON reply.
// Usage: node scripts/acer-api-fetch.mjs <warmUrl> <apiUrl> <jsonBody>
import fs from "node:fs";

const [warmUrl, apiUrl, body] = process.argv.slice(2);
const jar = new Map();
function absorb(response) {
  const cookies = response.headers.getSetCookie?.() || [];
  for (const cookie of cookies) {
    const pair = cookie.split(";")[0];
    const at = pair.indexOf("=");
    if (at > 0) jar.set(pair.slice(0, at), pair.slice(at + 1));
  }
}
const headers = {
  "accept": "*/*",
  "accept-language": "en-US,en;q=0.9",
  "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36 Edg/157.0.0.0"
};
absorb(await fetch(warmUrl, { headers }));
const cookie = [...jar].map(([key, value]) => `${key}=${value}`).join("; ");
for (let attempt = 0; attempt < 3; attempt += 1) {
  const response = await fetch(apiUrl, {
    method: "POST",
    headers: { ...headers, "content-type": "application/json", cookie, referer: warmUrl, origin: "https://www.acer.com" },
    body
  });
  absorb(response);
  const text = await response.text();
  if (text.includes('"hits":[')) {
    process.stdout.write(text);
    process.exit(0);
  }
  await new Promise((resolve) => setTimeout(resolve, 2500));
}
process.stdout.write('{"hits":null}');
