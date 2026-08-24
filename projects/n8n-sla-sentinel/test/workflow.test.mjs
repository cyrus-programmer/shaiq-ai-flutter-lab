import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const nodeCode = async (name) => readFile(join(root, 'src', 'nodes', `${name}.js`), 'utf8');
const execute = async (code, json, now = '2026-08-24T02:00:00.000Z') => {
  const FixedDate = class extends Date {
    constructor(value) { super(value === undefined ? now : value); }
    static now() { return new Date(now).getTime(); }
  };
  const context = vm.createContext({
    $input: { first: () => ({ json }) },
    Date: FixedDate,
    Number,
    RegExp
  });
  return new vm.Script(`(async () => { ${code}\n})()`).runInContext(context);
};

const validTicket = {
  body: {
    ticket_id: 'T-1042',
    subject: 'Customer needs help',
    message: 'The dashboard does not show the latest report.',
    customer_email: 'owner@example.com',
    customer_tier: 'standard',
    affected_users: 1
  }
};

test('normalizes a valid webhook body', async () => {
  const [item] = await execute(await nodeCode('normalize'), validTicket);
  assert.equal(item.json.valid, true);
  assert.equal(item.json.ticket.id, 'T-1042');
  assert.equal(item.json.ticket.customer_email, 'owner@example.com');
  assert.equal(item.json.received_at, '2026-08-24T02:00:00.000Z');
});

test('rejects missing and undersized required fields', async () => {
  const [item] = await execute(await nodeCode('normalize'), { body: { subject: 'x', message: 'short' } });
  assert.equal(item.json.valid, false);
  assert.equal(item.json.errors.length, 3);
});

test('rejects invalid tier, affected count, email, and timestamp', async () => {
  const payload = structuredClone(validTicket);
  Object.assign(payload.body, {
    customer_tier: 'vip', customer_email: 'bad', affected_users: 1.5, occurred_at: 'yesterdayish'
  });
  const [item] = await execute(await nodeCode('normalize'), payload);
  assert.equal(item.json.valid, false);
  assert.equal(item.json.errors.length, 4);
});

const triage = async (overrides = {}) => {
  const ticket = {
    id: 'T-1', subject: 'General question', message: 'Please explain the current report.',
    customer_tier: 'standard', affected_users: 1, occurred_at: null, ...overrides
  };
  const [item] = await execute(await nodeCode('triage'), {
    ticket, received_at: '2026-08-24T02:00:00.000Z'
  });
  return item.json;
};

test('routes a large enterprise payment outage as critical', async () => {
  const result = await triage({
    subject: 'Production checkout outage', message: 'Payments are failing for all users',
    customer_tier: 'enterprise', affected_users: 300
  });
  assert.equal(result.severity, 'critical');
  assert.equal(result.score, 100);
  assert.equal(result.route, 'on_call');
  assert.equal(result.sla_minutes, 15);
  assert.equal(result.acknowledge_by, '2026-08-24T02:15:00.000Z');
});

test('routes a security report as high', async () => {
  const result = await triage({ subject: 'Security issue', message: 'My account may be compromised.' });
  assert.equal(result.severity, 'high');
  assert.equal(result.is_urgent, true);
  assert.equal(result.sla_minutes, 60);
});

test('routes a payment question as medium', async () => {
  const result = await triage({ subject: 'Billing question', message: 'A payment is shown twice.' });
  assert.equal(result.severity, 'medium');
  assert.equal(result.route, 'support_priority');
});

test('routes a general question as low', async () => {
  const result = await triage();
  assert.equal(result.severity, 'low');
  assert.equal(result.route, 'support_standard');
  assert.deepEqual([...result.reasons], ['no elevated risk signals']);
});

test('redacts contact and card-like data from preview', async () => {
  const result = await triage({
    message: 'Email me@site.com or call +1 (415) 555-0123 about card 4111 1111 1111 1111.'
  });
  assert.equal(result.safe_preview.includes('site.com'), false);
  assert.equal(result.safe_preview.includes('555-0123'), false);
  assert.equal(result.safe_preview.includes('4111'), false);
  assert.match(result.safe_preview, /\[EMAIL_REDACTED\]/);
  assert.match(result.safe_preview, /\[PHONE_REDACTED\]/);
  assert.match(result.safe_preview, /\[CARD_REDACTED\]/);
});

test('uses occurred_at as the SLA clock when provided', async () => {
  const result = await triage({ occurred_at: '2026-08-24T01:00:00.000Z' });
  assert.equal(result.acknowledge_by, '2026-08-24T09:00:00.000Z');
});

test('response builders expose explicit actions', async () => {
  const urgent = await execute(await nodeCode('urgent-response'), { accepted: true });
  const standard = await execute(await nodeCode('standard-response'), { accepted: true });
  assert.equal(urgent[0].json.action, 'page_on_call');
  assert.equal(standard[0].json.action, 'queue_for_support');
});

test('rejection builder preserves validation details', async () => {
  const [item] = await execute(await nodeCode('rejection'), {
    errors: ['subject is required'], received_at: '2026-08-24T02:00:00.000Z'
  });
  assert.equal(item.json.accepted, false);
  assert.deepEqual([...item.json.details], ['subject is required']);
});

test('workflow graph has valid connections and safe defaults', async () => {
  const workflow = JSON.parse(await readFile(join(root, 'workflows', 'sla-sentinel.json'), 'utf8'));
  const names = new Set(workflow.nodes.map((node) => node.name));
  assert.equal(workflow.nodes.length, 11);
  assert.equal(workflow.active, false);
  assert.equal(workflow.nodes.filter((node) => node.type.endsWith('.respondToWebhook')).length, 3);
  assert.equal(workflow.nodes.some((node) => node.credentials), false);
  for (const output of Object.values(workflow.connections)) {
    for (const branch of output.main) {
      for (const edge of branch) assert(names.has(edge.node), `Unknown destination: ${edge.node}`);
    }
  }
  const serialized = JSON.stringify(workflow);
  assert.doesNotMatch(serialized, /api[_-]?key|bearer\s+[a-z0-9]/i);
});
