-- Computational transport, with no mathematical catalogue or semantic registration.
namespace RuntimeTransport
-- # ruleid: lean-shim-suffix-decl
inductive ComputationData where
  | inline (packet : String)
end RuntimeTransport
