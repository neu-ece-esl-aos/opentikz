# Figure-Authoring Backend Contract — Phase 1 (FROZEN SEAM)

**Contract version:** `1.2.0` · **Status:** frozen (Phase-1 exit deliverable, ADR-0004 R3.1)
**Backend #1:** TikZ / circuitikz (this skill). **Consumers:** Phase 2 (opentikz-TikZ),
Phase 3 (draw.io/diagrams.net).

> **`1.2.0` (additive, cp-4873).** The **6-primitive generic placement-semantics core** —
> a backend-agnostic shared vocabulary (`direction-axis · containment · alignment-symmetry ·
> relative-placement · typed-routing · pinned-axis`) — is named as frozen contract content in
> **§3a**, and every per-family placement rule is now **tagged with the primitive(s) it
> instantiates** (hybrid model, cp-4870). Naming the primitive core in the contract (not only
> the skill body) is what stops Phase-2/3 backends re-deriving divergent layout rules (R3.5).
> The placement grammar is now **survey-grounded** (cp-4870 prior-art survey) — the blanket
> "PROVISIONAL" framing is relaxed to "settled-default, extensible"; only the *general*
> netlist→schematic layout core stays roadmap-level (cp-4849; see §3 status note). Per-family
> extensions applied (circuit substructure/symmetry/orientation/rails/signal-flow;
> architecture ports+hierarchy; flow layer-assignment+crossing-minimization; timeline pinned-
> axis). All additive — no existing role/token meaning changed. See Change control below.

> **`1.1.0` (additive, cp-4868).** Per-family **placement grammar** named first-class
> settled-decisions content a backend MUST honor (§3); timeline/sequence components added to
> the flow vocabulary (§1b); a neutral hex added per style token for non-TeX backends (§2).
> All additive — no existing role/token meaning changed.

> **What this document is.** The **renderer-independent seam** of the figure-authoring
> capability. Everything here lives *above* any particular rendering backend. A new
> backend (opentikz, draw.io, SVG, …) is anything that consumes this contract and emits
> a figure — it MUST be implementable from this document **alone**, without reading the
> TikZ internals in `figstyle.tex` / `tikzsemantics.tex`. If you find yourself needing to
> read the `.tex` macros to build a backend, that is a contract gap — record it, do not
> silently couple to TikZ.
>
> The four contract elements (R3.1): **{ semantic component/macro vocabulary · style/color
> tokens · settled-decisions schema · intent-record format }**. Each has its own section. The
> settled-decisions schema (§3) carries the **6-primitive generic placement-semantics core**
> (§3a) — the backend-agnostic layout vocabulary every family grammar instantiates and every
> backend realizes natively. Freezing this contract is the milestone that unblocks Phases 2 and 3.

---

## 0. Contract principle: reason on the semantic model, render downstream

The author manipulates **components and their relationships** — *Core / Cache / DMA /
Accelerator / NoC / crossbar-cell / KCL-node / ADC / task / stage* — never `(x,y)`,
`anchor=`, or `shift={…}`. The backend's one job is to turn semantic components + style
tokens + layout intent into a rendered figure. This contract is the vocabulary of that
semantic model. (ADR-0004 R2.1.)

---

## 1. Semantic component / macro vocabulary

A backend must provide a component for each entry. The TikZ backend realizes each as the
named macro/style in the cited asset; another backend realizes it as a shape, a template,
or a draw.io shape-library cell. **Names and roles are the contract; the realization is not.**

### 1a. Circuit / schematic family (realized in `figstyle.tex`)

| Component (contract name) | Role in the figure | TikZ realization |
|---|---|---|
| `crossbar-cell` | one weight/conductance cell in a VMM array | `\crossbarcell{name}{placement-opts}{label}` / `cell` style |
| `crossbar-array` | a full nrows×ncols VMM cell array, placed by row/col index | `\crossbararray{prefix}{nrows}{ncols}` |
| `kcl-node` | summation node (KCL) collecting column current; **always tagged "KCL"** | `\kclsum{name}{placement-opts}` / `kclnode` style |
| `adc` | analog→digital converter, drawn as a small apex-right triangle | `\adctri{name}{placement-opts}` / `adc` shape style |
| `v-source` | input voltage / activation source | `vsource` style |
| `domain-band` | shaded background band for a signal domain; **label sits inside it** | `\domainband{name}{color}{fitspec}{label}{anchor}` |
| `domain-boundary` | dashed divider between two domains | `\domainboundary{from}{to}` |
| `analog-wire` | edge carrying analog current | `awire` style |
| `digital-wire` | edge carrying a digital word | `dwire` style |
| `voltage-wire` | edge carrying an input voltage/activation | `vwire` style |
| `current-label` / `voltage-label` / `digital-label` / `sidenote` | typed edge/role annotations | `currentlbl` / `voltagelbl` / `digitallbl` / `sidenote` styles |

### 1b. Architecture / flow family (realized in `tikzsemantics.tex`)

| Component (contract name) | Role in the figure | TikZ realization |
|---|---|---|
| `cpu-core` | a CPU / general processing core | `\cpucore{name}{label}{opts}` / `core` style |
| `acc-core` | an accelerator core | `\acccore{name}{label}{opts}` |
| `pe` | a small processing element inside a tile | `\pe{name}{label}{opts}` / `pecore` style |
| `mem-block` | a cache / shared-memory block | `\memblock{name}{label}{opts}` |
| `tile` | a tile / cluster container that holds PEs | `\tile{name}{corner-label}{opts}` |
| `intra-bus` | intra-tile interconnect edge | `intrabus` style |
| `inter-bus` | inter-tile interconnect edge | `interbus` style |
| `task-node` | a task/DAG vertex (task-graph family) | `\tasknode{name}{label}{opts}` / `node` style |
| `proc-stage` | a pipeline/flow transform stage | `\procstage{name}{label}{opts}` / `process` style |
| `param-node` | a parameter/artifact box (chamfered) | `\paramnode{name}{label}{opts}` / `parameters` style |
| `flow-edge` | directed flow/dependency edge, optional weight label | `\flowedge{from}{to}{label}` |
| `time-axis` | the one shared time axis a timeline/sequence registers against | `\timeaxis{name}{from}{to}{label}` |
| `lifeline` | an actor/object's time extent (head + dashed lifeline) — sequence family | `\lifeline{name}{opts}{label}{drop}` |
| `sync-marker` | an event/sync point on a lifeline (temporal analog of a task-node) | `\syncmarker{lifeline}{depth}{label}` |
| `life-message` | a message/sync edge between two lifelines at a shared time depth | `\lifemsg{from}{to}{depth}{label}` |
| `group-box` | a `fit`-style grouping/legend container with a caption | `\groupbox{fitspec}{caption}` |

**Extensibility rule.** New components are added to the vocabulary *here first*, then
realized per backend. A backend never invents a semantic component the contract does not name.

---

## 2. Style / color tokens

Colors are named by **signal/interconnect domain**, never by raw hue. A backend maps each
token to its medium (a TikZ `\colorlet`, a draw.io style string, an SVG class). These are
the settled analog-family + tsarilp-family assignments; a host document MAY override the hue
but MUST keep the token→role mapping. The **Default hue** is the TikZ/xcolor name (some are
dvipsnames); the **Neutral hex** is a backend-agnostic sRGB fallback for backends without an
xcolor name table (draw.io, SVG). The hex is a starting default, not part of the mapping —
override it freely; the token→role binding is what is frozen.

| Token | Role / meaning | Default hue | Neutral hex |
|---|---|---|---|
| `inputdomain` | inputs / activations | blue | `#2B6CB0` |
| `weightdomain` | analog weight cells | green | `#2F8F4E` |
| `digitaldomain` | digital words / logic | gray | `#7A7A7A` |
| `analogdomain` | analog current / accumulation | orange | `#E08A1E` |
| `intra-bus` | intra-tile interconnect | Orange | `#E8890C` |
| `inter-bus` | inter-tile interconnect | NavyBlue | `#1F3A93` |
| `core-accent` | processing-core fill accent | Aquamarine / ForestGreen | `#4FB8A8` |
| `process-accent` | flow transform-stage accent | NavyBlue | `#1F3A93` |
| `param-accent` | parameter/artifact box accent | ForestGreen | `#228B22` |

**Typography tokens** (a backend maps to its font model):
`body-font` = match host manuscript body (settled: newtx Times, never Computer Modern);
`domain-label` = small italic; `role-label` = footnotesize; `sidenote` = ~6.5pt gray.

**Arrowhead token:** `arrow = Stealth` (all directed edges).

---

## 3. Settled-decisions record schema

A per-figure-family, version-controlled record of decisions that MUST hold across every
figure in the set. Its purpose: stop settled semantics from silently regressing when a change
is propagated across figures (ADR-0004 R2.3). A backend consumes it as a per-figure
verification gate.

### 3a. Generic placement-primitive core (backend-agnostic, the 6 primitives) — `1.2.0`

Placement semantics across all three figure families decompose into **one small shared
vocabulary of six primitives** (cp-4870 prior-art survey, triangulating analog-EDA
building-block/symmetry/signal-flow layout, graph-drawing ports/containment/orthogonality,
and Sugiyama layering/crossing-minimization). This vocabulary is **frozen contract content**:
it is named ONCE here, every per-family `placement_grammar` rule (§3b below) is tagged with the
primitive(s) it instantiates (`primitives: [...]`), and **every backend realizes each
primitive natively** (TikZ `positioning`/`calc`/`fit`/`\foreach`; ELK/opentikz Sugiyama
layering + orthogonal port routing; draw.io containers + fixed ports + orthogonal router).
Freezing the **primitives, not coordinates** is what makes layout transfer across backends and
stops Phases 2/3 re-deriving divergent layout rules (**closes R3.5**). The same six primitives
are also the constraint classes an auto-layout engine consumes, so this vocabulary doubles as
the seed of the cp-4849 DSL→semantic-IR→auto-layout constraint IR (ADR-0004 R2.1/R3.6).

| # | Primitive (`id`) | Generic meaning (backend-agnostic) | Circuit realization | Architecture realization | Flow / DAG / timeline realization |
|---|---|---|---|---|---|
| 1 | **`direction-axis`** | a monotone ordering/flow axis the figure reads along | signal flow: inputs L → outputs R | dataflow across the datapath | monotone stage direction; time axis |
| 2 | **`containment`** | hierarchy / grouping: an element is *inside* / *a member of* another | substructure / building block (current mirror, diff pair, cascode; VMM array) | tile ⊃ PE; shared-memory locus | subgraph / grouped stages |
| 3 | **`alignment-symmetry`** | equal-role elements share a coordinate / mirror across an axis | matched-pair symmetry axis | grid alignment of tiles | layer assignment; aligned lifelines |
| 4 | **`relative-placement`** | position stated relative to a neighbor / anchor, never absolute | rows=inputs, cols=cells; KCL at column foot | PEs inside tile; legend in corner | fork/join alignment; params off-axis |
| 5 | **`typed-routing`** | typed connections routed (orthogonal, no stray crossings) | typed wires (awire/dwire/vwire), orthogonal | orthogonal intra/inter-bus at ports | edges follow data direction; crossing minimization |
| 6 | **`pinned-axis`** | one axis pinned to a fixed external coordinate/edge | power/ground rails pinned top/bottom | interface/port row pinned on a tile edge | shared time axis (timeline) |

**Rule.** A `placement_grammar` rule states a **concrete, checkable** relationship over the
family's §1 named components AND tags the generic primitive(s) it realizes. The primitives are
the shared spine; the per-family rules are its projection at the granularity the re-check gate
needs (a fully generic rule like "currents sum downward into a KCL node" cannot be *checked*
against a render). A backend never invents a placement primitive this core does not name —
same extensibility discipline as §1: add to the core here first, then realize per backend.

### 3b. Per-family record schema

Schema (see `settled-decisions-template.md` for a filled instance):

```yaml
family: <flow | architecture | circuit-schematic>
version: <semver; bump when any decision changes>
placement_grammar:      # how the NAMED components position/connect relative to each
                        # other to be semantically correct (relationship rules, NOT
                        # coordinates); each rule checkable against a render (see below)
  - id: <slug>
    primitives: [<one or more §3a primitive ids this rule instantiates>]
    rule: <a relationship/relative-position rule over named components>
    rationale: <what reading it prevents>
style_decisions:        # color/line/label/typography conventions
  - id: <slug>
    decision: <the rule, stated so a render can be checked against it>
    rationale: <why — who required it / what it prevents>
semantic_decisions:     # what the figure MEANS (regresses if unrecorded)
  - id: <slug>
    decision: <the rule>
    rationale: <why>
constraints:            # binding external rules (e.g. IP/topology safety)
  - id: <slug>
    decision: <the rule>
    source: <citation / policy reference>
```

**Placement grammar is first-class settled-decisions content, projecting the §3a core.** The
`placement_grammar` block states, per family, *how the semantic components should be
positioned and connected relative to one another to be semantically correct* — the
relationship-and-relative-position rules over the **named** vocabulary components of §1, each
**tagged with the §3a generic primitive(s) it instantiates** (hybrid model: one shared
primitive spine, per-family checkable projections). It is authored as seed content in
`settled-decisions-template.md` (one worked default instance per family) and, like every
other block here, a backend **MUST honor it**: it is checked per figure in the same re-check
gate, and it is backend-agnostic (it names components and relationships, never `(x,y)`), so
Phases 2/3 transfer it unchanged. It lives here — not as a separate contract element — because
§3 is the backend-agnostic *container* for cross-figure decisions and the placement grammar is
one kind of such decision (cp-4867/cp-4873 resolved contract-vs-skill-body in favor of the
contract). Together with §3a it **closes the Phase-2/3-kickoff layout-divergence risk R3.5**:
without a named primitive core + grammar a second backend would re-invent placement and diverge
semantically from backend #1.

> **Status: survey-grounded settled defaults (cp-4870), EXTENSIBLE — not a closed list.**
> The `v1.2.0` per-family grammars and the §3a primitive core are grounded in the cp-4870
> prior-art survey (analog-EDA building-block/symmetry/signal-flow layout; graph-drawing
> ports/containment/orthogonality; Sugiyama layering/crossing-minimization) — the blanket
> "PROVISIONAL first-cut" framing is retired. They remain **EXTENSIBLE** (add rules as new
> cases arise; add primitives to §3a first, then realize per backend). **One boundary stays
> roadmap-level:** *general* netlist→schematic layout synthesis (arbitrary netlist → a
> well-placed schematic) is a genuinely open research problem (Schemato arXiv:2411.13899,
> EEschematic arXiv:2510.17002; ADR-0004 R1.5) and belongs to the cp-4849 DSL→IR→auto-layout
> roadmap, **not** Phase 1 — the circuit grammar here hand-authors the concrete VMM/crossbar
> topology this chapter family needs, it does not solve the general problem.

**Re-check rule (contract-level):** when a `placement_grammar` or `*_decisions` entry
changes, `version` bumps and **every figure in the family is re-checked** against the new
record before the change is considered done. This gate is backend-independent.

---

## 4. Intent-record format

The per-figure serialized semantic model + intent — the durable answer to *"what is this
figure trying to say?"* that survives across sessions and enables intent-aware edits. It is
**lighter than a generative layout spec**: it does NOT regenerate the figure (the backend's
master — for TikZ, the `.tex` — is the generative source of truth). It records intent, not
geometry. (ADR-0004 R1.2.) See `intent-record-template.md` for the fillable form.

```yaml
slug: <figure slug>
family: <flow | architecture | circuit-schematic>
subject: <what the figure is of, one line>
thesis: <the ONE thing the figure must make the reader believe>
visual_argument: <how the layout carries the thesis — the argument, not coordinates>
entities:               # the semantic model: components and their ROLES
  - name: <component>
    role: <what it IS in the argument>
relationships:          # edges among entities and what flows on each
  - from: <entity>
    to: <entity>
    carries: <what flows / the dependency>
check_questions:        # 3-5 questions answerable from the RENDER ALONE (semantic gate)
  - <question>
provenance:             # carried ALSO as a header comment in the backend master
  sources: [<citations the figure is derived from>]
  constraints: [<binding topology/IP rules that apply>]
```

**Master-header rule (contract-level):** the intent record's `subject`, `thesis`, and
`provenance` are ALSO carried as a header comment block inside the backend master, so intent
travels with the source across backends.

---

## 5. What is NOT in the contract (backend-private)

Coordinates, anchors, node distances, build-dir mechanics, the compile command, the PNG
self-check tooling — all backend-private. A backend may implement them any way it likes.
The contract is the semantic model, the tokens, and the two records; nothing below the line.

---

## Change control

This contract is **frozen** for Phase 1. Phases 2/3 consume it; they do not edit it
unilaterally. A change requires a new contract version and re-notifying all backends
(the cross-backend analog of the R2.3 re-check rule). Additive component/token entries are a
minor bump; changing an existing role/token meaning is a major bump.

**Change log**

- `1.2.0` (cp-4873, additive — minor bump; no existing role/token meaning changed): the
  **6-primitive generic placement-semantics core** named as frozen contract content (§3a:
  `direction-axis · containment · alignment-symmetry · relative-placement · typed-routing ·
  pinned-axis`); each per-family `placement_grammar` rule tagged with the primitive(s) it
  instantiates via a new `primitives: [...]` field (hybrid model, cp-4870). Per-family
  extensions applied in `settled-decisions-template.md` (circuit: substructure/building-block
  recognition, symmetry axis, device orientation, power/ground rail placement, signal-flow
  direction; architecture: port/interface placement + explicit hierarchy/containment;
  flow: Sugiyama layer-assignment + crossing-minimization; timeline: named a pinned-axis
  layered layout). "PROVISIONAL first-cut" framing relaxed to "survey-grounded settled default,
  extensible" (§3 status note); only *general* netlist→schematic layout stays roadmap-level
  (cp-4849). Resolves the cp-4870 triage flag (contract vs skill-body) in favor of the contract.
  Backends #2/#3 not yet implemented at the bump, so re-notification is a no-op recorded here.
- `1.1.0` (cp-4868, additive — minor bump per the rule above; no existing role/token
  meaning changed): per-family placement grammar named first-class settled-decisions content
  a backend MUST honor (§3, closes R3.5) — shipped as PROVISIONAL initial default
  conventions, extensible, survey-refinement pending (a prior-art survey is dispatched
  separately to refine/generalize into `v1.2`; NOT a solved/definitive grammar, and
  explicitly not a general circuit-layout solver — see §3 status note); `time-axis` /
  `lifeline` / `sync-marker` / `life-message` added to the flow vocabulary (§1b); a neutral
  hex added per style token for non-TeX backends (§2). Backends #2/#3 were not yet
  implemented at the bump, so re-notification is a no-op recorded here.
- `1.0.0` — Phase-1 exit deliverable: initial frozen seam (ADR-0004 R3.1).
