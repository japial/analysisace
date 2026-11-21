// Builds the favicon and app icons from the analysisACE logo system.
//
//   node scripts/build-brand-assets.mjs
//
// Writes apps/web/src/app/icon.svg, apple-icon.png and favicon.ico, plus public/icon-512.png.
// The geometry matches the owner's brand artifact (docs/DECISIONS.md, D14); the in-page logo
// lives in apps/web/src/components/brand/logo.tsx. Change both if the logo changes.
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const NAVY = "#0B1F3A";
const TEAL_DEEP = "#0F766E";
const here = path.dirname(fileURLToPath(import.meta.url));
const app = path.join(here, "../apps/web/src/app");
const pub = path.join(here, "../apps/web/public");
mkdirSync(pub, { recursive: true });

const D = '<path d="M32 6L60 58H4Z" fill="#FFFFFF"/>';
// Standard bars, for large sizes: two short side bars and a taller teal centre bar.
const BARS = `<rect x="17" y="42" width="7" height="10" rx="1.5" fill="${NAVY}"/>
<rect x="40" y="42" width="7" height="10" rx="1.5" fill="${NAVY}"/>
<rect x="28.5" y="30" width="7" height="22" rx="1.5" fill="${TEAL_DEEP}"/>`;
// Thicker bars, for 16 to 48 px where the standard ones blur.
const BARS_SMALL = `<rect x="16" y="41" width="8" height="11" rx="1.5" fill="${NAVY}"/>
<rect x="40" y="41" width="8" height="11" rx="1.5" fill="${NAVY}"/>
<rect x="28" y="29" width="8" height="23" rx="1.5" fill="${TEAL_DEEP}"/>`;

/** Mark centred on a navy square. `radius` rounds the square; `scale` sizes the mark. */
function icon({ radius, scale, bars }) {
  const offset = (64 - 64 * scale) / 2;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="${radius}" fill="${NAVY}"/>
<g transform="translate(${offset} ${offset}) scale(${scale})">${D}${bars}</g>
</svg>`;
}

const svgIcon = icon({ radius: 14, scale: 0.7, bars: BARS_SMALL });
// iOS rounds the corners itself, so the square is full-bleed.
const appleSvg = icon({ radius: 0, scale: 0.625, bars: BARS });

writeFileSync(path.join(app, "icon.svg"), `${svgIcon}\n`);

const browser = await chromium.launch();
const page = await browser.newPage();

async function png(svg, size) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(
    `<style>html,body{margin:0;background:transparent}svg{display:block;width:${size}px;height:${size}px}</style>${svg}`,
  );
  return page.screenshot({ omitBackground: true, clip: { x: 0, y: 0, width: size, height: size } });
}

writeFileSync(path.join(app, "apple-icon.png"), await png(appleSvg, 180));
writeFileSync(path.join(pub, "icon-512.png"), await png(icon({ radius: 14, scale: 0.625, bars: BARS }), 512));

// favicon.ico holding 16, 32 and 48 px PNG images.
const sizes = [16, 32, 48];
const images = [];
for (const size of sizes) images.push(await png(svgIcon, size));
await browser.close();

const header = Buffer.alloc(6);
header.writeUInt16LE(1, 2); // type: icon
header.writeUInt16LE(sizes.length, 4);
const entries = Buffer.alloc(16 * sizes.length);
let offset = header.length + entries.length;
sizes.forEach((size, i) => {
  const at = i * 16;
  entries.writeUInt8(size, at);
  entries.writeUInt8(size, at + 1);
  entries.writeUInt16LE(1, at + 4); // colour planes
  entries.writeUInt16LE(32, at + 6); // bits per pixel
  entries.writeUInt32LE(images[i].length, at + 8);
  entries.writeUInt32LE(offset, at + 12);
  offset += images[i].length;
});
writeFileSync(path.join(app, "favicon.ico"), Buffer.concat([header, entries, ...images]));
console.log("Brand assets written.");
