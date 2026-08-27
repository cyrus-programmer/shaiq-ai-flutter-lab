import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const root = new URL('../', import.meta.url);
const runCode = async (name, json, env = {}) => {
  const source = await readFile(new URL(`src/nodes/${name}.js`, root), 'utf8');
  const script = new vm.Script(`(async () => { ${source} })()`);
  return script.runInNewContext({ $json: json, $env: env });
};

const validLead = {
  body: {
    email: 'buyer@acme.health', company: 'Acme Health', website: 'https://acme.health/',
    employeeCount: 180, annualBudget: 30000, submittedAt: '2026-08-27T03:00:00Z',
    source: 'ProductHunt', painPoint: 'We need a reliable way to route and qualify inbound enterprise leads across our sales team.',
    consent: true, country: 'US', industry: 'healthcare',
  },
};

test('normalizes a valid lead and derives policy signals', async () => {
  const [result] = await runCode('normalize', validLead, { SALES_OWNERS: 'alex@example.com,sam@example.com' });
  assert.equal(result.json.accepted, true);
  assert.equal(result.json.lead.website, 'https://acme.health');
  assert.equal(result.json.signals.businessEmail, true);
  assert.equal(result.json.signals.targetIndustry, true);
  assert.equal(result.json.signals.targetCountry, true);
});

test('rejects malformed input with all useful errors', async () => {
  const [result] = await runCode('normalize', { body: { email: 'bad', company: '', employeeCount: 0, annualBudget: -1, painPoint: 'short' } });
  assert.equal(result.json.accepted, false);
  assert.equal(result.json.errors.length, 6);
});

test('free email does not earn the business-email signal', async () => {
  const lead = structuredClone(validLead);
  lead.body.email = 'person@gmail.com';
  const [result] = await runCode('normalize', lead);
  assert.equal(result.json.signals.businessEmail, false);
});

test('high-fit lead routes to sales with a stable owner', async () => {
  const [normalized] = await runCode('normalize', validLead, { SALES_OWNERS: 'alex@example.com,sam@example.com' });
  const [first] = await runCode('score', normalized.json);
  const [second] = await runCode('score', normalized.json);
  assert.equal(first.json.qualification.route, 'sales');
  assert.equal(first.json.qualification.score, 100);
  assert.equal(first.json.qualification.owner, second.json.qualification.owner);
});

test('mid-fit lead routes to nurture', async () => {
  const [normalized] = await runCode('normalize', validLead);
  normalized.json.lead.annualBudget = 1000;
  normalized.json.signals.targetIndustry = false;
  const [result] = await runCode('score', normalized.json);
  assert.equal(result.json.qualification.route, 'nurture');
  assert.equal(result.json.qualification.owner, null);
});

test('missing consent always overrides a high score', async () => {
  const [normalized] = await runCode('normalize', validLead);
  normalized.json.lead.consent = false;
  const [result] = await runCode('score', normalized.json);
  assert.equal(result.json.qualification.route, 'rejected');
});

test('response masks email and preserves routing evidence', async () => {
  const [normalized] = await runCode('normalize', validLead);
  const [scored] = await runCode('score', normalized.json);
  const [response] = await runCode('response', scored.json);
  assert.equal(response.json.lead.email, 'bu***@acme.health');
  assert.equal(response.json.route, 'sales');
  assert.ok(response.json.reasons.length >= 5);
});

test('generated workflow embeds source code exactly', async () => {
  const workflow = JSON.parse(await readFile(new URL('workflows/lead-router.json', root), 'utf8'));
  assert.equal(workflow.nodes.length, 12);
  assert.equal(workflow.active, false);
  for (const [nodeName, fileName] of [['Normalize + Validate', 'normalize'], ['Score ICP Fit', 'score'], ['Prepare Sales Handoff', 'response'], ['Prepare Rejection', 'rejection']]) {
    const embedded = workflow.nodes.find((node) => node.name === nodeName).parameters.jsCode;
    assert.equal(embedded, await readFile(new URL(`src/nodes/${fileName}.js`, root), 'utf8'));
  }
});

test('every connection points to an existing node', async () => {
  const workflow = JSON.parse(await readFile(new URL('workflows/lead-router.json', root), 'utf8'));
  const names = new Set(workflow.nodes.map((node) => node.name));
  for (const [source, outputs] of Object.entries(workflow.connections)) {
    assert.ok(names.has(source));
    for (const branch of outputs.main) for (const edge of branch) assert.ok(names.has(edge.node));
  }
});
