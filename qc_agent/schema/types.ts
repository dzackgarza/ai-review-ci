export interface QCAgentConfig {
  /** Enable lint rules. */
  lint?: boolean;
  /** Rule severities keyed by rule id. */
  rules?: Record<string, 'off' | 'warn' | 'error'>;
}
