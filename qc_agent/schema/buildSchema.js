const fs = require('fs');
const path = require('path');

function buildSchema() {
  const schema = {
    title: 'QC Agent Configuration',
    type: 'object',
    properties: {
      lint: { type: 'boolean' },
      rules: {
        type: 'object',
        additionalProperties: { enum: ['off', 'warn', 'error'] },
      },
    },
    additionalProperties: false,
  };
  fs.writeFileSync(path.join(__dirname, 'qc_agent-config.schema.json'), JSON.stringify(schema, null, 2) + '\n');
}

if (require.main === module) buildSchema();

module.exports = buildSchema;
