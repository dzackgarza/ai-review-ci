# Sage Mathematical Domain-Modeling Style Guide

> **Model the mathematics first; treat algorithms and representations as realizations of that model.**

Sage code is an extension of mathematical language. A useful computation belongs in a coherent mathematical landscape that survives the immediate spike. The terms **MUST**, **SHOULD**, and **MUST NOT** are normative.

## 1. Start with a mathematical transcript

Before a class diagram or algorithm, write the intended Sage session in mathematical statements:

```python
XS = M_gn(g, n, base=k)
assert XS in ModuliStacks(k)
assert XS in DeligneMumfordStacks(k)

pi = XS.coarse_moduli_morphism()
X = pi.codomain()
c = X.compactification(kind="stable-curves")
Xbar = c.codomain()
assert Xbar.is_proper()

Sigma = c.boundary().stratification()
P = Sigma.specialization_poset()
assert P.is_isomorphic(known_poset)
```

Nouns become objects or categories; verbs become morphisms or constructions; adjectives become axioms/properties; relations become native orders, actions, incidence relations, or Hom-sets. The public class diagram MUST be recoverable from ordinary mathematical prose.

Do not begin with implementation nouns such as `Model`, `Manager`, `Context`, `Descriptor`, `Record`, `Payload`, `Result`, `Factory`, or `BackendObject` and infer the mathematics later.

## 2. Establish the ambient mathematics before the target

The dependency direction is:

```text
category → general object → general construction → specialized instance → algorithmic realization
```

For stable-curve work, stacks over a base contain Deligne--Mumford stacks, which contain moduli stacks; compactifications contain an open immersion; a compactification has a boundary; an equipped stratification has a specialization poset. Stable-graph enumeration is one realization of one stratification, not the ambient ontology.

Generalize only along recognized mathematics: schemes, varieties, stacks, moduli problems, morphisms, compactifications, boundaries, stratifications, group actions, posets, simplicial complexes, stable graphs, curve families, and quotient objects. Do not generalize through software-shaped types such as `GeometricObjectModel`, `BoundaryComputationContext`, or `GraphEnumerationResult`.

A new general abstraction is justified only when it has a standard definition, clear objects and morphisms, at least one generic operation/theorem/invariant, a genuine target instance, a second exercising example, and public methods stated independently of a backend. Test a `Compactification` both on the target and, for example, \(\mathbf A^1\hookrightarrow\mathbf P^1\).

## 3. Use Sage Parent--Element--Category--Hom architecture

Sage categories own generic mathematical facts, algorithms, tests, and documentation. Parents model structured collections; elements belong to parents. This semantic hierarchy is distinct from ordinary Python inheritance.

| Mathematics | Sage architecture |
| --- | --- |
| category of objects | `Category` |
| structured collection | `Parent` |
| member | `Element` |
| morphism set | `Homset` / `Hom(X, Y)` |
| arrow | `Morphism` |
| structural adjective | category axiom/refinement |
| action | `Action` or permutation representation |
| finite order | `FinitePoset` |

Use plural parents and singular elements:

```python
G = StableGraphs(g, I)(data)
j = Compactifications(X)(open_immersion)
f = Hom(X, Y)(data)
assert f.domain() is X and f.codomain() is Y
```

Public morphisms MUST be elements of appropriate Hom-sets. A standalone object merely storing source/target dictionaries is not a Sage morphism. Custom parents SHOULD use `_element_constructor_`; do not override `Parent.__call__` except in exceptional Sage-supported circumstances.

## 4. Put methods on their mathematical owner

An operation belongs to the most general object for which it is intrinsically defined, not whichever class happens to carry enough data to compute it.

- `coarse_space()` belongs to a stack admitting a coarse moduli morphism.
- `boundary()` belongs to a compactification, not an arbitrary proper space.
- `specialization_poset()` belongs to a stratification or stratified space.
- `dual_graph()` belongs to a curve/fiber.
- `automorphism_group()` and `contract()` belong to the mathematical graph.
- `order_complex()` belongs to a native Sage poset.
- `fiber()` belongs to a family or morphism.

Operations requiring extra structure MUST live on equipped objects. A boundary needs an open immersion \(X\hookrightarrow\overline X\); write `Compactification(j).boundary()`. A stratification is not silently determined by an arbitrary space; write `Stratification(X, ...).specialization_poset()`.

Generic facts true throughout a category belong in `ParentMethods`, `ElementMethods`, or an axiom refinement: state a theorem once at the most general category where it is true.

## 5. Keep categories, axioms, objects, and constructions distinct

Categories classify (`Schemes(S)`, `Varieties(k)`, `Stacks(S)`, `DeligneMumfordStacks(S)`). Axioms refine semantic structure (`Proper`, `Smooth`, `Projective`, `Nodal`) rather than becoming constructor booleans. Objects are instances. Constructions have mathematically defined input and output categories:

```python
X.product(Y)
X.quotient(G, action)
X.compactification()
X.normalization()
C.dual_graph()
```

Properties of morphisms—proper, smooth, etale, finite—belong first to morphisms; an object over a base inherits the statement through its structure morphism.

## 6. Use public mathematical vocabulary

Every public type MUST be definable by a research mathematician without referring to code. Prefer `Variety`, `Stack`, `ModuliProblem`, `StablePointedCurve`, `Compactification`, `Boundary`, `Stratification`, `StableGraph`, `GroupAction`, and `ClutchingMorphism`.

Names such as `Descriptor`, `Signature`, `Datum`, `Info`, `Result`, `Context`, `Manager`, `Factory`, `Payload`, `Adapter`, and `Backend` are usually private implementation vocabulary. Expose one public name per concept; do not retain spike-history aliases such as `StableGraphRecord`, `StableGraphType`, and `StableCurveType` unless they are genuinely distinct mathematical objects.

Use standard verbs: `normalization`, `compactification`, `dual_graph`, `contract`, `stratum`, `restrict`, and `orbit`, rather than `build_model`, `compute_signature`, or `resolve_context`.

## 7. State equality and isomorphism explicitly

Every public parent MUST document whether `==` means equality of labeled objects, equality of canonical representatives in a skeleton, or equality of isomorphism classes. Do not mix representative-dependent and isomorphism-invariant methods. Provide explicit `is_isomorphic`, `canonical_representative`, and Hom-set isomorphism operations where appropriate. Canonical labels, keys, and serialization orderings are private unless canonical form is part of the mathematics.

## 8. Choose inheritance, composition, and wrapping semantically

Use Python inheritance only for genuine substitutability: a clutching morphism is a stack morphism; a stable-graph isomorphism is a stable-graph morphism. Do not subclass merely to acquire methods.

Use composition for equipped objects:

```python
Compactification(open_immersion=j)
StratifiedSpace(space=X, stratification=Sigma)
QuotientStack(space=X, group=G, action=rho)
PointedCurve(curve=C, markings=sections)
```

Wrap only at real semantic boundaries: external implementations, lossless realizations, or Sage facade structures. Do not create wrappers merely to forward a native API. Return an actual `FinitePoset`, with `Sigma.specialization_poset()` recording the domain convention.

## 9. Reuse native Sage primitives where semantics match

Return native `FinitePoset`, graphs/Hasse diagrams, `SimplicialComplex`, `PermutationGroup`, `Action`, `Homset`, `Morphism`, schemes, and enumerated sets when their mathematical meaning agrees with the domain object.

Do not force reuse when it destroys semantics. A stable half-edge graph may require a semantic `StableGraph` parent because a generic graph can lose legs, flags, vertex genus, or loop branches. Expose faithful views such as `G.sage_graph()` or `G.incidence_graph()`; do not falsely subclass `Graph`.

## 10. Actions and relations remain native relations

A group acting on vertices, flags, and edges gives separate induced actions with clear acted-on parents. Compute orbits, kernels, and images from those actions; do not export an aggregate `AutomorphismAction` holding parallel permutation records.

If the mathematics gives a poset, graph, simplicial complex, category, group action, or equivalence relation, construct and return that native object. An incidence poset, a category of strata, and a boundary complex are distinct objects even when derived from related data.

## 11. Keep backends and engineering types private

Canonical keys, JSON schemas, serialization records, external-process payloads, enumeration state, backend selection, temporary labels, CAS adapters, file formats, and profiling state live in private modules. Public modules are organized by mathematical subject.

Changing a backend (`sage`, `admcycles`, GAP, Singular, Julia, Macaulay2) MUST NOT change public return types, equality, category membership, method names, ordering conventions, or interpretation. Convert external objects once at a private adapter boundary into public Sage domain objects.

## 12. Preserve mathematical parameters and avoid flag ontology

Do not use flags such as `compact=True`, `coarse=True`, `stacky=True`, `reduced=True`, or `canonical=True` to conflate different mathematical objects. Prefer separate constructors or an honest construction relation.

Bases and label sets are mathematical data. Use `Varieties(k)`, `Stacks(S)`, `M_gI(g, I)`, and `StableGraphs(g, I)` when labels matter; cardinality-only forms are convenience specializations. Public vertices, half-edges, edges, components, and strata have identifiable parents; raw integer indexes remain internal.

## 13. Separate semantic objects from realizations

A theorem-defined object can exist before every algorithm is implemented. Distinguish:

```text
semantic object:       Mbar_gn(g, n)
available realization: stable-dual-graph stratification
computational backend: Sage / admcycles / GAP
```

Document available operations honestly, but do not rename a mathematical object as a “model” merely because only one realization is implemented.

## 14. Spikes leave reusable mathematics

A successful spike leaves honest categories, typed objects, Hom-set morphisms, generic constructions, a mathematician-facing transcript, native Sage outputs, private backends, independent oracles, and a specialized target that instantiates the framework. It does not leave only service objects, dataclass forests, result wrappers, and bespoke graph/poset/action proxies.

Every new general abstraction SHOULD have a non-target example: `\mathbf A^1\hookrightarrow\mathbf P^1` for compactification, a simple orbit stratification, a finite group quotient, `(\mathbf P^1;0,1,\infty)` for pointed curves, or a standard permutation action.

## 15. Implementation workflow

1. Write an executable mathematical use case.
2. Extract categories, parents, elements, morphisms, properties, actions, relations, and constructions.
3. Draw the category/construction diagram and determine ownership.
4. Audit Sage and external primitives; reuse only semantically matching structures.
5. Implement one generic vertical slice: category → parent → element → morphism → construction → native invariant.
6. Exercise an unrelated example.
7. Implement the specialized target as an instance, not a bypass.
8. Add computational realizations only after public interfaces are fixed.
9. Add literature oracles.
10. Audit every exported name for mathematical meaning.

## 16. Testing requirements

Tests must include category membership, parent--element ownership, identity/associativity laws for morphisms, construction laws, action laws, functoriality, native-output types, backend opacity, and an unrelated generality example.

The primary external evidence is a literature oracle: full poset isomorphism, complete incidence relation, published action, quotient description, clutching source, dimension/homology theorem, or complete classification. Counts and rank vectors are diagnostics, not sufficient proof.

## 17. Documentation and API layering

Document every public category, parent, element, and morphism in this order:

1. mathematical definition and hypotheses;
2. Sage semantics: category, parent/Hom-set, equality, base, source/target;
3. representation, algorithms, conversions, backends, and limitations.

A non-specialist algebraic geometer should encounter general geometry first, then moduli interpretation, specialized stratification, combinatorics, and only finally backend realizations. Cite definitions and nontrivial facts supporting category membership, dimensions, smoothness/properness, moduli interpretations, classifications, and oracle structures.

## 18. Review checklist

Before accepting a Sage contribution, establish:

- public categories, objects, morphisms, parents, elements, equality, actions, relations, and constructions;
- proper ownership, category axioms, and Hom-set membership;
- standard public vocabulary without implementation-history aliases;
- correct Parent/Element/Homset/Morphism use and native Sage outputs;
- private backend and canonicalization boundaries;
- a genuine general construction exercised outside the target;
- category, morphism, action, construction, functoriality, backend, native-output, and literature-oracle proof.

## Condensed doctrine

1. Write the mathematical transcript first.
2. Introduce honest ambient categories before specialized instances.
3. Use Sage categories for semantic ownership and generic facts.
4. Use parents, elements, Hom-sets, and morphisms according to their mathematics.
5. Use standard mathematical public vocabulary.
6. Compose equipped objects; inherit only under true substitutability; wrap only at semantic boundaries.
7. Return native Sage structures when their semantics match.
8. Keep adapters, records, canonical keys, and computational state private.
9. Demonstrate generality away from the motivating target.
10. Validate against independent mathematics from the literature.

## Primary Sage references

- [Elements, parents, and categories](https://doc.sagemath.org/html/en/reference/categories/sage/categories/primer.html)
- [Homsets](https://doc.sagemath.org/html/en/reference/categories/sage/categories/homset.html)
- [Implementing algebraic structures](https://doc.sagemath.org/html/en/thematic_tutorials/coercion_and_categories.html)
- [Category axioms](https://doc.sagemath.org/html/en/reference/categories/sage/categories/category_with_axiom.html)
- [Schemes](https://doc.sagemath.org/html/en/reference/categories/sage/categories/schemes.html)
- [Finite posets](https://doc.sagemath.org/html/en/reference/combinat/sage/combinat/posets/posets.html)
- [Actions](https://doc.sagemath.org/html/en/reference/categories/sage/categories/action.html)
