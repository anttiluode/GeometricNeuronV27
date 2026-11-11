// Regression for the infinite canvas growth at devicePixelRatio > 1.
// This tests the actual fit() helper from index.html, without a browser dependency.
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");

const html = fs.readFileSync(path.join(__dirname, "../index.html"), "utf8");
const found = html.match(/function fit\(c\)\{[\s\S]*?\n\}/);
assert.ok(found, "fit() present");

for (const [id, height] of [["ringC", 250], ["stripC", 64], ["distC", 150]]) {
  assert.ok(html.includes("#" + id + "{height:" + height + "px}"),
    id + " must have a fixed display height separate from the canvas backing store");
}

for (const dpr of [1, 1.25, 1.5, 2, 3]) {
  const fit = new Function("window", found[0] + "; return fit;")({devicePixelRatio:dpr});
  for (const height of [250, 64, 150]) {
    let assignments = 0;
    const canvas = {
      _w:300, _h:150,
      get width(){return this._w;},
      set width(v){this._w=v; assignments++;},
      get height(){return this._h;},
      set height(v){this._h=v; assignments++;},
      getBoundingClientRect(){return {width:700, height};},
      getContext(){return {setTransform(){}};}
    };
    for(let frame=0;frame<1000;frame++){
      const [,w,h]=fit(canvas);
      assert.equal(w,700);
      assert.equal(h,height);
      assert.equal(canvas.width,Math.round(700*dpr));
      assert.equal(canvas.height,Math.round(height*dpr));
    }
    assert.ok(assignments <= 2, "backing store must not reallocate on every frame");
  }
}
console.log("PASS: stable ring, strip, and distance canvases at DPR 1–3 (1000 frames each)");
