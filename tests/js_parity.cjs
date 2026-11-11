// v27.js must give the same beat ticks as gn27.py (tests/fixture.json).
const fs = require("fs"), path = require("path");
require(path.join(__dirname, "..", "taps.js"));
const { Net } = require(path.join(__dirname, "..", "v27.js"));
const fx = JSON.parse(fs.readFileSync(path.join(__dirname, "fixture.json"), "utf8"));
let bad = 0;
for (const [name, c] of Object.entries(fx.cases)) {
  const net = new Net(c.const, c.edges, c.lam).settle(1500);
  const n = net.n, prev = new Array(n).fill(true), ev = Array.from({ length: n }, () => []);
  for (let k = 0; k < 4000; k++) {
    const sp = new Float64Array(n);
    if (k < fx.bits.length) sp[0] = -10 * fx.bits[k];
    const own = net.step(null, sp);
    for (let i = 0; i < n; i++) { const loud = own[i] > 3; if (loud && !prev[i]) ev[i].push(k); prev[i] = loud; }
  }
  const same = JSON.stringify(ev) === JSON.stringify(c.beats);
  console.log((same ? "ok   " : "FAIL ") + name + "  beats per unit " + ev.map(e => e.length).join(","));
  if (!same) bad++;
}
if (bad) { console.error(bad + " case(s) differ from gn27.py"); process.exit(1); }
console.log("v27.js matches gn27.py on every case");
