import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const root = new URL('../', import.meta.url);
const geometry = JSON.parse(await readFile(new URL('public/data/ontario-fsas.geojson', root)));
const index = JSON.parse(await readFile(new URL('public/data/fsa-index.json', root)));
const ids = geometry.features.map(f => f.properties.fsa);
assert.equal(new Set(ids).size, ids.length, 'FSA identifiers must be unique');
assert.deepEqual(ids, index.fsas.map(f => f.fsa), 'Map and search FSA identifiers must match');
assert.ok(ids.length > 500, 'Expected Ontario-wide census coverage');
const response = await fetch('http://127.0.0.1:8000/api/v1/predictions', {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ temperature_c: -40, day_type: 'weekend', hour: 23 }),
});
assert.equal(response.status, 200);
const result = await response.json();
assert.deepEqual(result.predictions.map(p => p.fsa), ids, 'API and map coverage must match');
assert.ok(result.predictions.every(p => Number.isFinite(p.value) && p.value >= 0));
console.log(`Verified ${ids.length} FSA joins and the live API for a midnight weekend scenario.`);
