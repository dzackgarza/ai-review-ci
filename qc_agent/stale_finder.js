// Stale configuration pruning for the QC Stabilization Agent.
//
// Code-scanning tools can accumulate stale configurations that keep old issues
// open after the active configuration has fixed them. This utility removes
// duplicate and explicitly obsolete scan configurations before they enter the
// review context.

/**
 * Prune stale code scanning configurations.
 *
 * A configuration is considered stale if it has the same identifier as another
 * active configuration or if it is marked as `obsolete`. The returned array
 * contains only unique, non-obsolete configurations.
 *
 * @param {Array<{id: string, obsolete?: boolean}>} configs - Scan configurations.
 * @returns {Array<{id: string}>} The pruned configuration list.
 */
function pruneStaleConfigs(configs) {
  const seen = new Set();
  const result = [];
  for (const config of configs) {
    if (config.obsolete) continue;
    if (seen.has(config.id)) continue;
    seen.add(config.id);
    result.push({ id: config.id });
  }
  return result;
}

module.exports = pruneStaleConfigs;
