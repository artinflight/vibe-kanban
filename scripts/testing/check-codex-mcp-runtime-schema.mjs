// Read-only offline protocol verification; this generates schemas, not a session.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
const [command, output] = process.argv.slice(2);
if (!command || !output)
  throw new Error(
    'Usage: node check-codex-mcp-runtime-schema.mjs <configured-launcher> <mounted-output-directory>'
  );
function run(args) {
  const result = spawnSync(command, args, { encoding: 'utf8' });
  if (result.status !== 0)
    throw new Error(`Schema command failed (${result.status})`);
  return result.stdout.trim();
}
const version = run(['--version']);
run(['app-server', 'generate-json-schema', '--out', output]);
function schema(name) {
  const raw = readFileSync(resolve(output, `${name}.json`));
  return {
    value: JSON.parse(raw),
    sha256: createHash('sha256').update(raw).digest('hex'),
  };
}
const request = schema('McpServerElicitationRequestParams');
const response = schema('McpServerElicitationRequestResponse');
assert.equal(request.value.type, 'object');
for (const name of ['threadId', 'serverName'])
  assert.equal(request.value.properties[name].type, 'string');
assert.ok(request.value.properties.turnId.type.includes('null'));
const form = request.value.oneOf.find((shape) =>
  shape.properties.mode.enum.includes('form')
);
assert.ok('_meta' in form.properties);
assert.equal(
  form.properties.requestedSchema.$ref,
  '#/definitions/McpElicitationSchema'
);
assert.equal(response.value.type, 'object');
assert.deepEqual(response.value.required, ['action']);
assert.deepEqual(response.value.definitions.McpServerElicitationAction.enum, [
  'accept',
  'decline',
  'cancel',
]);
for (const field of ['content', '_meta'])
  assert.ok(field in response.value.properties);
console.log(
  JSON.stringify(
    {
      version,
      requestSha256: request.sha256,
      responseSha256: response.sha256,
      verified:
        'form envelope, nullable turn, empty object result, accept/decline/cancel and optional metadata',
      limitation:
        'openai/form, openaiForm, URL and nonempty input schemas remain unsupported and cancel',
    },
    null,
    2
  )
);
