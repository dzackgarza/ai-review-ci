// Reliability module for the QC Stabilization Agent.
//
// This module provides a minimal implementation of reliability features
// for AI review orchestration. It includes a risk-tier classifier and a
// simple circuit breaker that can downgrade to fallback models when a
// primary model is unavailable.

/**
 * Classify the risk tier of a diff based on the number of changed lines and
 * files. Trivial changes require fewer AI reviewers, while large or security-
 * sensitive changes warrant a full set of specialists.
 *
 * @param {Object} stats - Diff statistics.
 * @param {number} stats.linesChanged - Total added plus removed lines.
 * @param {number} stats.filesChanged - Number of changed files.
 * @param {boolean} stats.securitySensitive - Whether security-sensitive paths changed.
 * @returns {"trivial"|"lite"|"full"} The selected risk tier.
 */
function classifyRisk(stats) {
  const { linesChanged, filesChanged, securitySensitive } = stats;
  if (filesChanged > 50 || securitySensitive) return "full";
  if (linesChanged <= 10 && filesChanged <= 20) return "trivial";
  if (linesChanged <= 100 && filesChanged <= 20) return "lite";
  return "full";
}

/**
 * A simple circuit breaker for model calls. When a model reports a retryable
 * error, the breaker returns the configured fallback model. Non-retryable
 * errors do not trigger failback.
 */
class CircuitBreaker {
  /**
   * @param {Object} options - Configuration options.
   * @param {Record<string, string|null>} options.failbackChain - Model fallback map.
   */
  constructor({ failbackChain } = {}) {
    this.failbackChain = failbackChain || {};
    this.state = {};
  }

  /**
   * Determine whether to fail back based on an error.
   *
   * @param {Error & {retryable?: boolean}} err - The model call error.
   * @param {string} model - The current model name.
   * @returns {string|null} The fallback model, or null.
   */
  getFallback(err, model) {
    if (!err || !err.retryable) return null;
    return this.failbackChain[model] || null;
  }
}

module.exports = { classifyRisk, CircuitBreaker };
