// Optional frontend checks: node --test tests/test_chart_scale.js
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/call-chart.js'), 'utf8'), sandbox);

test('packet axes cover zero, small, large and anomalous negative counts with integral ticks', () => {
  for (const values of [[], [0], [1], [4], [44], [123456], [-3, 4]]) {
    const scale = sandbox.chartScale(values, 'packets');
    assert.ok(scale.high > scale.low);
    assert.ok(scale.ticks.every(Number.isInteger));
    assert.ok(new Set(scale.ticks).size === scale.ticks.length);
    assert.ok(scale.ticks.length <= 7);
    for (const value of values) assert.ok(value >= scale.low && value <= scale.high);
  }
});

test('percentages and continuous measurements preserve fractional scales', () => {
  for (const unit of ['%', 'ms', 'raw']) {
    const scale = sandbox.chartScale([0.004, 0.04], unit);
    assert.ok(scale.ticks.some(v => v > 0 && v < 1));
    assert.ok(scale.high >= 0.04);
  }
});

test('normal MOS uses the full meaningful 1–5 scale; anomalies stay visible', () => {
  const scale = sandbox.chartScale([4.1, 4.4], 'MOS');
  assert.equal(scale.low, 1);
  assert.equal(scale.high, 5);
  const anomalous = sandbox.chartScale([-2, 8], 'MOS');
  assert.ok(anomalous.low <= -2 && anomalous.high >= 8);
});
