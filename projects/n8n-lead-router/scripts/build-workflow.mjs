import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const code = async (name) => readFile(resolve(root, `src/nodes/${name}.js`), 'utf8');
const node = (name, type, position, parameters = {}, typeVersion = 2, id = name.toLowerCase().replaceAll(' ', '-')) => ({
  parameters, id, name, type, typeVersion, position,
});

const workflow = {
  name: 'Lead Router - Privacy-aware ICP qualification',
  nodes: [
    node('Lead Intake', 'n8n-nodes-base.webhook', [0, 300], {
      httpMethod: 'POST', path: 'lead-router', responseMode: 'responseNode', options: {},
    }, 2.1),
    node('Normalize + Validate', 'n8n-nodes-base.code', [220, 300], { jsCode: await code('normalize') }),
    node('Valid Payload?', 'n8n-nodes-base.if', [440, 300], {
      conditions: { options: { caseSensitive: true, leftValue: '', typeValidation: 'strict' },
        conditions: [{ leftValue: '={{ $json.accepted }}', rightValue: true, operator: { type: 'boolean', operation: 'true', singleValue: true } }],
        combinator: 'and' }, options: {},
    }),
    node('Score ICP Fit', 'n8n-nodes-base.code', [660, 220], { jsCode: await code('score') }),
    node('Sales Qualified?', 'n8n-nodes-base.if', [880, 220], {
      conditions: { options: { caseSensitive: true, leftValue: '', typeValidation: 'strict' },
        conditions: [{ leftValue: '={{ $json.qualification.route }}', rightValue: 'sales', operator: { type: 'string', operation: 'equals' } }], combinator: 'and' }, options: {},
    }),
    node('Nurture Qualified?', 'n8n-nodes-base.if', [1100, 340], {
      conditions: { options: { caseSensitive: true, leftValue: '', typeValidation: 'strict' },
        conditions: [{ leftValue: '={{ $json.qualification.route }}', rightValue: 'nurture', operator: { type: 'string', operation: 'equals' } }], combinator: 'and' }, options: {},
    }),
    node('Prepare Sales Handoff', 'n8n-nodes-base.code', [1100, 100], { jsCode: await code('response') }),
    node('Prepare Nurture Handoff', 'n8n-nodes-base.code', [1320, 280], { jsCode: await code('response') }),
    node('Prepare Rejection', 'n8n-nodes-base.code', [880, 500], { jsCode: await code('rejection') }),
    node('Sales Response', 'n8n-nodes-base.respondToWebhook', [1540, 100], { respondWith: 'json', responseBody: '={{ $json }}', options: { responseCode: 200 } }, 1.4),
    node('Nurture Response', 'n8n-nodes-base.respondToWebhook', [1540, 280], { respondWith: 'json', responseBody: '={{ $json }}', options: { responseCode: 202 } }, 1.4),
    node('Rejected Response', 'n8n-nodes-base.respondToWebhook', [1100, 500], { respondWith: 'json', responseBody: '={{ $json }}', options: { responseCode: 422 } }, 1.4),
  ],
  connections: {
    'Lead Intake': { main: [[{ node: 'Normalize + Validate', type: 'main', index: 0 }]] },
    'Normalize + Validate': { main: [[{ node: 'Valid Payload?', type: 'main', index: 0 }]] },
    'Valid Payload?': { main: [[{ node: 'Score ICP Fit', type: 'main', index: 0 }], [{ node: 'Prepare Rejection', type: 'main', index: 0 }]] },
    'Score ICP Fit': { main: [[{ node: 'Sales Qualified?', type: 'main', index: 0 }]] },
    'Sales Qualified?': { main: [[{ node: 'Prepare Sales Handoff', type: 'main', index: 0 }], [{ node: 'Nurture Qualified?', type: 'main', index: 0 }]] },
    'Nurture Qualified?': { main: [[{ node: 'Prepare Nurture Handoff', type: 'main', index: 0 }], [{ node: 'Prepare Rejection', type: 'main', index: 0 }]] },
    'Prepare Sales Handoff': { main: [[{ node: 'Sales Response', type: 'main', index: 0 }]] },
    'Prepare Nurture Handoff': { main: [[{ node: 'Nurture Response', type: 'main', index: 0 }]] },
    'Prepare Rejection': { main: [[{ node: 'Rejected Response', type: 'main', index: 0 }]] },
  },
  settings: { executionOrder: 'v1', saveManualExecutions: true },
  active: false,
  pinData: {},
  meta: { templateCredsSetupCompleted: true },
  tags: [],
};

const output = resolve(root, 'workflows/lead-router.json');
await mkdir(dirname(output), { recursive: true });
await writeFile(output, `${JSON.stringify(workflow, null, 2)}\n`);
console.log(`Built ${output}`);
