// Fetch one Dell driver-list response with a browser cookie and save the raw body.
// Usage: node scripts/dell-api-fetch.mjs <url> <cookieFile> <outputFile> [referer]
import fs from "node:fs";

const [url, cookieFile, outputFile, referer = "https://www.dell.com/support/home/ja-jp"] = process.argv.slice(2);
const cookie = fs.readFileSync(cookieFile, "utf8").trim();
const response = await fetch(url, {
  headers: {
    accept: "application/json, text/javascript, */*; q=0.01",
    cookie,
    origin: "https://www.dell.com",
    referer,
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36 Edg/157.0.0.0",
    "x-requested-with": "XMLHttpRequest"
  }
});
const text = await response.text();
fs.writeFileSync(outputFile, text);
console.log(response.status, text.length);
