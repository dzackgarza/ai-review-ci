---
name: style-guide-sage
description: Load with the style guide before implementing or repairing SageMath. Requires mathematical domain modeling before algorithms, representations, or backends.
---
# SageMath Mathematical Domain Modeling

Read [[style-guide/sage/references/mathematical-domain-modeling|the Sage mathematical domain-modeling guide]] before designing Sage-facing public code.

Its governing rule is: **model the mathematics first; algorithms and representations realize that model.**

Use it with the relevant foundation card from the [[style-guide/references/style-guide-index|style-guide index]]. The foundation card owns the cross-language invariant; this guide owns Sage categories, parents, elements, Hom-sets, native structures, public mathematical vocabulary, backend boundaries, and mathematical proof.
