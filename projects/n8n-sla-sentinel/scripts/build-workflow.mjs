import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const readNode = (name) => readFile(join(root, 'src', 'nodes', `${name}.js`), 'utf8');
const [normalize, triage, rejection, urgent, standard] = await Promise.all(
  ['normalize', 'triage', 'rejection', 'urgent-response', 'standard-response'].map(readNode)
);

const codeNode = (id, name, code, position) => ({
  parameters: { jsCode: code }, id, name, type: 'n8n-nodes-base.code', typeVersion: 2, position
});
const ifNode = (id, name, leftValue, position) => ({
  parameters: {
    conditions: {
      options: { caseSensitive: true, leftValue: '', typeValidation: 'strict', version: 2 },
      conditions: [{
        id: `${id}-condition`, leftValue, rightValue: '',
        operator: { type: 'boolean', operation: 'true', singleValue: true }
      }],
      combinator: 'and'
    },
    options: {}
  },
  id, name, type: 'n8n-nodes-base.if', typeVersion: 2.2, position
});
const respondNode = (id, name, responseCode, position) => ({
  parameters: {
    respondWith: 'json', responseBody: '={{ $json }}', options: { responseCode }
  },
  id, name, type: 'n8n-nodes-base.respondToWebhook', typeVersion: 1.4, position
});
const edge = (node, index = 0) => ({ node, type: 'main', index });

const workflow = {
  name: 'SLA Sentinel - Support Intake and Triage',
  nodes: [
    {
      parameters: {
        httpMethod: 'POST', path: 'support-intake', responseMode: 'responseNode', options: {}
      },
      id: '0cce338a-5b22-4df2-847a-e82695d72ed2',
      name: 'Support Intake Webhook',
      type: 'n8n-nodes-base.webhook',
      typeVersion: 2.1,
      position: [-900, 0],
      webhookId: 'a07a16b8-0f28-446b-9dfa-cf3d93c938ae'
    },
    codeNode('c431a86d-5b75-45c7-8ae2-dd69f31f55b5', 'Normalize and Validate', normalize, [-680, 0]),
    ifNode('1b025173-8536-4795-9ee4-ce8c7943e117', 'Valid Ticket?', '={{ $json.valid }}', [-460, 0]),
    codeNode('1c68d719-41e8-42ec-b710-d572289a2313', 'Compute Severity and SLA', triage, [-240, -120]),
    ifNode('5982efb8-6d1b-4527-81c2-751a2cad9f91', 'Urgent?', '={{ $json.is_urgent }}', [0, -120]),
    codeNode('d0658986-731a-48c6-83ea-bc9a8787ccbb', 'Prepare Urgent Response', urgent, [240, -220]),
    respondNode('a87d87a5-5be3-4ddf-adb4-bb20a3d15ffc', 'Respond Urgent', 202, [500, -220]),
    codeNode('97550fb5-d91e-4a73-b3dd-7463068e0394', 'Prepare Standard Response', standard, [240, -20]),
    respondNode('92bc33dc-96d0-4839-a038-df3c35e28da7', 'Respond Standard', 202, [500, -20]),
    codeNode('3ec7bc52-e65e-4b78-985e-50e4b3797dad', 'Prepare Rejection', rejection, [-220, 180]),
    respondNode('84e30f19-1e0e-443d-b4eb-1fc51dc23813', 'Respond Invalid', 400, [40, 180])
  ],
  connections: {
    'Support Intake Webhook': { main: [[edge('Normalize and Validate')]] },
    'Normalize and Validate': { main: [[edge('Valid Ticket?')]] },
    'Valid Ticket?': { main: [[edge('Compute Severity and SLA')], [edge('Prepare Rejection')]] },
    'Compute Severity and SLA': { main: [[edge('Urgent?')]] },
    'Urgent?': { main: [[edge('Prepare Urgent Response')], [edge('Prepare Standard Response')]] },
    'Prepare Urgent Response': { main: [[edge('Respond Urgent')]] },
    'Prepare Standard Response': { main: [[edge('Respond Standard')]] },
    'Prepare Rejection': { main: [[edge('Respond Invalid')]] }
  },
  pinData: {},
  settings: { executionOrder: 'v1', saveManualExecutions: true, callerPolicy: 'workflowsFromSameOwner' },
  active: false,
  versionId: '436a3cb8-05af-4fb4-8b0f-1ba2110e615e',
  meta: { templateCredsSetupCompleted: true },
  tags: []
};

const names = new Set(workflow.nodes.map((node) => node.name));
assert.equal(names.size, workflow.nodes.length, 'node names must be unique');
assert.equal(new Set(workflow.nodes.map((node) => node.id)).size, workflow.nodes.length, 'node IDs must be unique');
for (const outputs of Object.values(workflow.connections)) {
  for (const branch of outputs.main) {
    for (const connection of branch) assert(names.has(connection.node), `unknown node: ${connection.node}`);
  }
}
assert(!workflow.nodes.some((node) => node.credentials), 'workflow must not embed credentials');

const output = `${JSON.stringify(workflow, null, 2)}\n`;
const target = join(root, 'workflows', 'sla-sentinel.json');
if (process.argv.includes('--check')) {
  const existing = await readFile(target, 'utf8');
  assert.equal(existing, output, 'workflow JSON is stale; run npm run build');
  console.log(`Validated generated workflow: ${workflow.nodes.length} nodes`);
} else {
  await writeFile(target, output);
  console.log(`Generated ${target}`);
}
