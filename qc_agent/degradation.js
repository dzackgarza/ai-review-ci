function createReport(baselineAvailable, diagnostics) {
  return {
    baselineDegraded: !baselineAvailable,
    diagnostics: diagnostics || [],
  };
}

module.exports = createReport;
