# Blue Contracts 1.0

**Edition:** `blue-contracts/2026-09-26-standalone-1`  
**Normative form:** one complete specification with executable algorithm appendices

## Abstract

Blue Contracts defines deterministic, gas-bounded transitions over exact Blue documents. It specifies channels, operation selection, sequential workflows, local updates, child-first managed composition, cyclic component rounds, initialization, atomic failure, replay and completion reuse. Effects are published only after a complete successful transition.

## Contents

- [1. Scope and conformance](#scope)
- [2. Exact dependencies and interpretation](#dependencies)
- [3. Scope and central rule](#section-3)
- [4. Public API, outcomes and document representation](#section-4)
- [5. Exact graph and occurrence records](#section-5)
- [6. Standard categories and complete type catalogue](#section-6)
- [7. Actual-value filtering](#section-7)
- [8. One selected operation call](#section-8)
- [9. External channel acceptance, lifetimes and checkpoints](#section-9)
- [10. Deterministic completion machine](#section-10)
- [11. Nested steps and BEX effects](#section-11)
- [12. Patches, validation and local Document Updates](#section-12)
- [13. Local FIFO, output batches and lifecycle](#section-13)
- [14. Dynamic graphs, collections, shared members and cycles](#section-14)
- [15. Generalization and explicit valid retyping](#section-15)
- [16. Lazy content and installed runtime extensions](#section-16)
- [17. Logical gas and host-independent resource semantics](#section-17)
- [18. Atomicity, replay and chunking equivalence](#section-18)
- [19. Conformance and integration](#section-19)
- [20. Normative algorithms and provenance](#section-20)
- [21. Generic Coordination integration boundary](#section-21)
- [22. Lazy immutable host values](#section-22)
- [23. Exact-value transfer accounting](#section-23)
- [24. Selected descendant evidence](#section-24)
- [Appendix A. Complete transition model](#transitions)
- [Appendix B. Logical metering and schedule](#metering)
- [Appendix C. Complete executable algorithms](#algorithms)

<a id="scope"></a>
## 1. Scope and conformance

This specification defines the protocol identified by this edition. Its prose, tables and algorithm appendices form one normative contract. It is independent of source-repository branches, release tags, installation paths and prior discussions. Named external semantics are selected exactly in §2. Where an implementation uses another programming language, it MUST preserve the same specified observations; matching internal classes or diagnostic wording is not required unless explicitly identified as an observation.

**MUST** and **REQUIRED** express requirements. **MUST NOT** and **PROHIBITED** express prohibitions. **SHOULD** and **SHOULD NOT** express recommendations whose departures require understood consequences. **MAY** and **OPTIONAL** express permissions. Examples marked informative do not add requirements. A conflict between normative prose and algorithms is a defect, not permission to choose an outcome. A finite conformance corpus is evidence, not a proof for every possible input.

A package distributes this specification; it does not install a processor. The package's BlueId, this specification Text's BlueId and the OCI/archive digests identify different content. This document does not contain its own calculated identity or the generated identities of types that refer to it.

<a id="dependencies"></a>
## 2. Exact dependencies and interpretation

This edition selects Blue Language package `8XGYNufx24r7Dc5bGoeobcGNCn9roLzSfZCQyHBTaTx4` and its complete specification Text `H7WiYQ6GiWypRdFyWRcv99dsvTv6WnJYnu9eLYPQmWnc`. Language is a direct prerequisite: document admission, effective types, specialization, exact references, specification metadata, cyclic identities and BlueIds use its defined operations.

This edition requires Blue BEX package `BvEGHEYgu4pg5QrW6cNcPho8tTBjcUuVtX645CmwDid8`, protocol specification `Bw4AZNwewBkkWcbAak2XZtHuQyPisS7PNvQfux3tESUj`, and normative rules Text `FcGJPnNHZ9KzB8JSwXsdvrbXQSqBYXrESPZJF35brUUk`. Every BEX-bearing position in an invocation uses that evaluator contract and the host interfaces defined here. Selecting another package or operator table MUST NOT substitute another BEX mode. BEX values and proposed effects are not automatically admitted Blue values; the output boundaries below are mandatory.

Coordination is not a prerequisite of Contracts. A higher-level host may establish external ordering, authority and durable histories; it supplies the original accepted event and timestamp through the public transition defined here. Contracts does not query a timeline provider or assign actor authority on its own.

Package imports supply exact content. Authoring prefixes are local bindings and do not leak through transitive imports. An imported definition retains its exact references. Mounting another package cannot change the selected interpreter or replace an existing type reference. Within this edition's interpreted package graph, the selected Language release MUST agree throughout; cross-Language conversion and mixed-rule cyclic sets are not defined. One selected Language governs a complete cyclic identity set and its owning proof.

<a id="section-3"></a>
## 3. Scope and central rule

**C01.** The public transition remains:

```text
process(document, event, eventTimestamp)
    -> resulting document, emitted events, gas
```

`document` is the selected exact root and its required managed graph. The event is one complete original external Blue value. Time is supplied as integer microseconds. A successful attempt finishes required initialization, local turns, child-batch applications, cyclic feedback and exact finalization. All returned changes remain one atomic result.

**Completion boundary.** Within a document, updates are immediate and application events are queued. Across a managed boundary, only a **sealed completion** is observable. A sealed completion contains the source's completed document/view and its ordered output occurrences. It is not necessarily durably committed. A child producing no events still supplies its resulting state.

No standalone channel parameter, delivery-list ingress, payload selector or alternate request selector is introduced. The chunk protocol in the annex is a processor-internal decomposition of this same transition; a completion is not an external event and cannot invoke an operation by masquerading as one.

**C02.** Contracts defines all processing described here, including child incorporation and cycle turns. Obtaining, ordering and authorizing external inputs, worker ownership, persistent-history scheduling, billing and external delivery are outside this specification.

**C03.** Language retains sole authority for Source, exact content, identities, resolution, cyclic sets and type validity. BEX retains its evaluation, numbers, functions, bindings and effect accumulation. Contracts chooses views and applies effects. Missing exact evidence is not an empty object or an ordinary filter mismatch.

<a id="section-4"></a>
## 4. Public API, outcomes and document representation

### 2.1 Three inputs

The Python-compatible public API remains `Processor.process(document, event, eventTimestamp)`. Its bound method has exactly these three parameters. Processor construction configures the exact runtime registry, resolver, gas ceiling and optional member-local ceilings; those are fixed execution configuration rather than extra per-event routing arguments.

`document` can be a verified `Snapshot`, the SDK representation of the selected exact rooted document, or a fresh Source object. The latter is admitted and initialized within the attempt. It is not permissible to author protected processor markers in a fresh Source object. Use verified snapshot restoration for an already managed document.

The required SDK-compatible returned `Outcome.document` is the resulting `Snapshot`. Its selected root BlueId is `result.document.documents[result.document.root].blue_id`. `processor.read(result.document, path)` reads business content. `Outcome.emitted_events` contains exact references to the selected root's publicly emitted values. `processor.emitted(result)` opens those values for display. Tuple unpacking yields `(document, emitted_events, gas)` in the order in C01; the `Outcome` additionally carries diagnostics and replay evidence.

These SDK records do not add inputs to the Contracts transition. Optional `begin / next_chunk / execute_chunk / accept_chunk / finish` methods implement the internal protocol in the executable appendix; they do not publish partial state or add another external ingress. A storage host may use a different representation if it preserves the same exact content, managed-occurrence evidence and semantics.

### 2.2 Time and identities

**C04.** `eventTimestamp` MUST be an integer from 0 through 2^53−1, in microseconds. Booleans, floating-point values, strings, negative numbers and out-of-range integers are rejected. Contracts never substitutes a wall clock or an event field for this argument. This range preserves the defined's portable timestamp representation; BEX Integer arithmetic is not narrowed by it.

The original event's identity is established with the unchanged validated Language operations. Selection of an inner call does not alter this identity. Equal timestamps do not imply equal events. No timestamp-only external ordering relation is inferred.

### 2.3 Result states

| Status | Document and public events | Meaning |
|---|---|---|
| `APPLIED` | Complete resulting state and selected-root emissions | The attempt can commit, including graceful termination. |
| `FAILED` | Original input snapshot; no public events | Invalid call, invalid effect, validation failure, explicit BEX failure, unsupported demanded executable or another defined Contracts error. |
| `GAS_LIMIT_EXCEEDED` | Original input snapshot; no public events | The next logical charge exceeds the shared or owner-local remaining allowance. The admitted prefix and rejected charge are reported. |
| `NEEDS_RESOURCES` | Original input snapshot; no public events | Required exact content or managed-view evidence is unavailable. This suspended attempt reports no completed semantic gas ledger; rerun from the original inputs after evidence is supplied. |
| `TERMINATED` | Original input snapshot; no public events | The selected root was already legitimately terminated. |

Invalid SDK arguments, invalid fresh Source admission and invalid configuration may raise `ContractError` before a runnable attempt exists. They are never a successful partial processing result. Gas and traces returned with a failed runnable attempt are diagnostic, not committed application effects.

An explicit `initialize(document)` lifecycle action is also provided. It has no invented external event or timestamp. It returns an `Outcome`. `create(document)` is a convenience that requires successful initialization and returns its document. `admit(members, root, bindings)` is a graph authoring facility, not an alternative event ingress. Its `Link` objects and symbolic member labels are not legal runtime patch values.

<a id="section-5"></a>
## 5. Exact graph and occurrence records

**C05.** A snapshot contains a root member key, exact document records, exact embedding edges, revision and topology-generation numbers, the Contracts specification identity and installed runtime bindings. Member keys and these commitments are platform records, not replacement BlueIds.

A member record contains its stable key, exact body and BlueId, current external-channel lifetimes, monotonically increasing channel and edge serials, and an optional immutable creation-cause token. A cause token is the original event identity, not an external ordering proof. The initial member set is finite.

An embedding edge is `(source member, relative path, target member, generation)`. That tuple identifies an occurrence. The same child may have several explicit incoming occurrences. A member's state changes can change its BlueId without changing its member key or continuing occurrences. Conversely, removing and recreating an occurrence at the same path must not revive an earlier occurrence's work.

The snapshot wire form is defined by `Snapshot.wire`, `Document.metadata`, `ChannelLife.wire` and `Edge.wire`. These field shapes and validation obligations are retained, with the commitment domains in A00. This design package does not supply published new replay identities. The platform commitment uses a tagged canonical JSON representation and SHA-256; **it is not the BlueId algorithm**. Language remains the sole authority for document and cyclic-member BlueIds.

Restoring a snapshot verifies its commitment, release, runtime bindings, every exact body, each edge's selected content and target identity, channel lifetime signatures and protected markers. Possession of an unverified body containing `initialized` or `checkpoint` is insufficient to restore a managed history. Unknown or ambiguous managed-view bindings fail or require evidence; they are not silently bound to the latest document.

### 3.1 Private working state versus sealed views

For each active member, keep its last exact **sealed view** separate from the writable **local frame** used for one turn. A frame may read its own evolving state (stable during one Compute) and the exact dependency views selected for the turn. It cannot read another active frame, an ambient latest pointer, a container's unsealed state, or a resolver alias that changes behind an exact BlueId.

In a DAG, children finish before their container's turn. In a cycle, peer reads use the preceding completed component-round view. Ordinary self-reference through a separately managed self-edge also means that completed view, not an alias to the writable frame.

Exact managed bindings are updated from completed results by the processor. This changes containing content identities, but is **not** a business patch, does not recreate child Document Updates and does not invoke arbitrary callbacks.

### 3.2 Completion records

`TurnCompletion`, `RoundSeal` and `UnitCompletion` are closed processor records defined in the annex, not new top-level contract categories or user-authored business documents. A completion binds exact before/after views, the original cause, relevant frozen local inputs, the profile, ordered event occurrences and its logical work segment. Its source events contain no parent paths. Each receiver supplies and checks its own captured occurrence tickets.

A value shaped like a completion is not evidence it was executed. Accept only a result produced through the current attempt's verified chunk protocol, or an implementation's explicitly verified equivalent result with all the same bindings. Merely verifying the after-document's BlueId does not establish the calculation. This revision defines no public third-party proof-admission protocol.

<a id="section-6"></a>
## 6. Standard categories and complete type catalogue

**C06.** Only **Marker**, **Channel** and **Handler** are permitted top-level contract categories. `Contract` is an abstract common ancestor. `Operation` specializes Handler. A Sequential Workflow Operation is therefore a Handler. Process Embedded is a Marker. Standard steps inherit the abstract Contract definition solely to share declarations; their executable role is nested step, and placing them directly in `contracts` is invalid.

All registered definitions include the exact specification reference. `name` and `description` are Language labels, not inherited business defaults. Runtime contracts may carry these labels. `order` is an optional signed 32-bit Integer; omitted means zero. Unknown standard runtime fields are rejected, including `when`. Catalogue declaration holes do not cause absent options to appear configured.

The catalogue retains these **32 definition shapes**, including the reusable Compute Definition marker. The `publish_catalogue` algorithm in the executable appendix defines the complete Language Source field-definition recipe of each. Tables below specify the additional closed runtime field and presence rules which cannot be expressed by an unvalued optional declaration alone. The current publication contains validated BlueIds and exact definition bodies. The catalogue generator in the executable appendix supplies the standard definitions.

### Core authoring names

Language scalar/container types and this Contracts catalogue are mandatory in the
standard Python authoring environment. Use bare names: `Integer`, `Channel`,
`Compute`, `Compute Definition`, `Sequential Workflow`, and so on. Every catalogue
name is installed before application repositories. Conflicting aliases fail;
repositories cannot silently replace a core name. Legacy `Contracts/NAME` spellings
remain aliases for the same current exact definition. This is name resolution,
not execution registration or network discovery. Exact documents store BlueIds.
`Language(core_contracts=False)` is the explicit low-level bootstrap/historical
profile, not the standard application environment. A Processor always installs
and binds its exact Contracts catalogue, including bare names.

### 4.1 Abstract categories and executable handlers

| Type | Parent | Fields and rules |
|---|---|---|
| Contract | none | Optional `order: Integer`. Abstract; not a top-level runtime implementation. |
| Marker | Contract | Abstract structural/policy/processing category. |
| Channel | Contract | Abstract observation category. |
| Handler | Contract | `channel: Text`; concrete executable handlers require a nonempty valid channel key. |
| Operation | Handler | Abstract named external-call handler. |
| Sequential Workflow | Handler | Required `channel`, required `steps: List`; optional `event` actual-value filter. |
| Sequential Workflow Operation | Operation | Required `channel`, required `steps: List`; optional `request` argument definition. No `event` or `when` field. Its name for dispatch is its raw key in `contracts`, not its label. |

Empty `steps: []` is permitted. Step order is list order. Standard handler discovery loads the header and verifies that steps are configured but does not compile an unused executable body. A selected operation MUST exist and be bound to the request's target external channel.

### 4.2 Channels

| Type | Parent | Fields, defaults and observed family |
|---|---|---|
| External Channel | Channel | Optional `event` filter against the complete original event. Without a filter, accepts every external event offered to this member. No special source, actor or outer routing field. |
| Composite External Channels | Channel | `channels: List[Text]`, default empty. Names other external primitive or composite/all channels in this member. Duplicate names and composition cycles are invalid. Acceptance is a set union. |
| All External Channels | Channel | No additional fields. Union of this member's primitive External Channels and installed external-channel extensions. Excludes internal channels. |
| Triggered Event Channel | Channel | Optional `event` filter. Observes application emissions from this same member while its local queue drains; never calls a container. |
| Embedded Node Channel | Channel | Optional `sourcePath: Text` exact relative direct-edge path; optional `event` filter on the child's inner application emission. With no sourcePath, observes all direct-child occurrences. Delivery occurs only after the child completion is incorporated. |
| Document Update Channel | Channel | Optional `path: Text`, default empty pointer; optional `event` filter against Document Update. Path matches that location and ordinary descendants within this managed document, not changes within separately managed descendants or an update to an ancestor. |
| Lifecycle Event Channel | Channel | Optional `event` filter against the current initialization or termination notification. |

A composite's members must be external channels in the same document. All External Channels is not a subscription to every internal event. A union's role is observation and optional explicit operation binding; traversing a union never redispatches an operation bound to one of its members.

External selection and runtime acceptance are specified in sections 6–8. Applications discriminate external recipients with actual event fields, for example `event: {location: desk}`. The processor does not extract a payload or supply a channel value that the external event lacks.

### 4.3 Nested steps

| Type | Required fields | Optional fields and effect |
|---|---|---|
| Compute | A valid BEX program using `expr` or `do`, as required by BEX | `constants`, `functions`, `definition`, `entry`; optional step `name`; executes unchanged BEX, returns a value and proposed changes/events. |
| Update Document | `changeset`, an effect-free BEX expression evaluating to a List of patches | Optional step `name`; applies evaluated patches in order. |
| Trigger Event | `event`, an effect-free BEX expression evaluating to a valid Blue value | Optional step `name`; creates one immutable application-event occurrence. Explicit `{}` is present, not missing. |
| Terminate Processing | `cause: Text` | Optional `reason: Text`, optional `name`; requests graceful termination. |

There is no `when`. A condition controlling effects must be placed in Compute around those effects. Returning no effects from one Compute does not skip a later unconditional step. A BEX `$call` is an intra-program function call, not a synchronous call to another managed document's operation.

### 4.4 Markers

| Type | Required fields and placement | Semantics |
|---|---|---|
| Compute Definition | Optional `constants` and `functions` objects | Nonexecuting reusable BEX declaration; may be a named member of `contracts`. No initialization or effects. |
| Process Embedded | Raw key `embedded`; optional `paths: List[Text]` and `collectionPaths: List[Text]`, each default empty | Declares managed boundaries. Existing explicit paths and each direct map member under a collection path become occurrences. |
| Processing Initialized Marker | Raw key `initialized`; `document: {blueId: exactPreInitializationDocument}` | Protected processor state; written silently after initialization work. |
| Processing Terminated Marker | Raw key `terminated`; `cause: Text`, optional `reason: Text` | Protected successful graceful termination; blocks future ordinary processing. |
| Channel Event Checkpoint | Raw key `checkpoint`; `entries: Dictionary` | Protected map from external channel keys to exact checkpoint records. |
| Type Generalization Policy | Raw key `generalization`; `defaultMode`, default `reject`; `rules: List[Type Generalization Rule]`, default empty | Protected policy for controlled automatic ancestor selection. |

Checkpoint entries are closed records:

```yaml
timestamp: 1000000
event:
  blueId: <exactOriginalExternalEvent>
```

The angle-bracket value is descriptive notation, not an admitted BlueId. Runnable conformance fixtures must use actual admitted identities. A checkpoint row has exactly `timestamp` and `event`; `event` is a pure exact reference. An absent checkpoint is not synthesized before successful consumption. A checkpoint with no entries may be omitted. Internal notifications do not obtain external checkpoints.

Generalization Rule has required `path: Text`, required `mode` equal to `reject` or `nearest-valid-ancestor`, and optional `mustRemainSubtypeOf: {blueId: exactTypeDefinition}`. The policy's own definition and inherited effective identity are protected from ordinary patches.

### 4.5 Requests, notifications and effect records

| Type | Fields and complete shape |
|---|---|
| Operation Request | Required `channel: Text`, required `operation: Text`; optional `request`; optional `document` exact reference; optional `requireExactDocumentVersion: Boolean`, default false. True requires document. The precondition is not a target-selection instruction. |
| Document Processing Initiated | `document: {blueId: exactPreInitializationDocument}`. Internal lifecycle notification. |
| Document Processing Terminated | `cause: Text`, optional `reason: Text`. Internal lifecycle notification. |
| Document Update | `op` in add/replace/remove; relative `path`; `beforePresent: Boolean`, `afterPresent: Boolean`; `before` iff present; `after` iff present. Sides are exact immutable values, inline or exact references. |
| Embedded Event Delivery | `sourcePath: Text` identifying one direct child edge; `event`, the immutable inner child application emission, inline or exact reference. |
| Json Patch Entry | Closed record `{op, path, val}` for add/replace; `{op, path}` for remove. `val` is a runtime value, not Source syntax to preprocess again. |
| Contract Execution Result | Optional `patches: List[Json Patch Entry]` and `events: List`, each default empty; optional `termination: {cause, reason?}`; optional runtimeLedger subject to the extension metering protocol. Unknown keys are invalid. |
| Type Generalization Rule | The policy-entry definition described above. |

Standard Operation Request recognition requires the registered type or a valid installed descendant recognized by its ancestry, not merely similar fields. Runtime request members are closed to the five standard fields, inherited `specification`, and Language labels. A typed but malformed request fails rather than silently becoming an ordinary event.

<a id="section-7"></a>
## 7. Actual-value filtering

**C07.** A filter is a Language definition tested against the actual event. It MUST NOT be merged into the event as a way to create missing event data. The selected exact algorithm is `Bridge.matches`:

1. Obtain the actual exact value and validate it as a value; obtain the filter as a definition. Resolve required exact evidence.
2. Walk actual and filter recipes together. For every authored or concrete inherited filter field, require the corresponding actual field and a present actual value. Typed declaration holes contributed only by a standard definition are not invented required business fields.
3. For filter list positions, require the corresponding actual positions. Extra actual positions or fields are allowed unless applicable Language constraints forbid them.
4. When the pattern names an explicit type, require that exact type in the actual value's type ancestry. This prevents unrelated registered notification types with structurally compatible fields from becoming indistinguishable. This is a Contracts filter guard, not a change to Language structural refinement.
5. With presence established, apply the selected Language refinement/validation operation to check fixed values, types and constraints. Return false for the defined compatibility, fixed-value, schema, list-shape and present-value mismatch categories. Propagate missing resources, invalid evidence and unsupported conditions as errors rather than false matches.
6. Never replace or alter the actual value.

Pairwise visited-recipe tracking makes repeated/cyclic structure finite. There is no universal filter-depth ceiling. Demand-driven matching charges its prescribed logical work, retains repeated-pair cycle detection, and may be physically interrupted only as incomplete execution. Event fields inherited from the actual event's own valid type count as actual fields. Fields introduced only by the filter do not.

A filter `{kind: paid, amount: {type: Integer, schema: {minimum: 100}}}` matches an actual paid event with amount 120, not one with amount 20 or no amount. A filter on a containing event must use its actual nested shape. `call` does not silently redirect ordinary filters to the operation request.

For Embedded Node Channel only, its channel-level filter tests the inner application event. Its workflow-level filter and `$event` see the complete Embedded Event Delivery wrapper. This difference is explicit and does not apply to external events.

<a id="section-8"></a>
## 8. One selected operation call

**C08.** Before external handler effects, perform precisely this recognition:

```text
if originalEvent is a recognized Operation Request:
    call := originalEvent
else if originalEvent's immediate operation field is a recognized Operation Request:
    call := that complete field value
else:
    call := absent
```

The first branch has precedence. There is no recursive search, configurable selector, message extraction or second processing invocation. Unrelated ordinary events may still trigger ordinary workflows.

Validate a recognized request's complete shape, nonempty channel and operation keys, optional Boolean precondition flag, and required exact-document reference when the flag is true. Its request arguments are not synthesized. During accepted-channel selection, freeze ordinary observer channels separately from operation recipients. An unaddressed request selects members whose accepted external channel key equals its channel; the named operation is checked only after selecting those candidates. A differently named observing channel does not make its member an operation target. For an explicitly addressed request, the installed verifier establishes the target lineage, independently of ordinary observation rights. On an actual recipient require the target channel to exist and be accepted. When that target channel is fresh, require the named Sequential Workflow Operation, its exact declared channel, and its optional argument definition to match the actual request value. All selected calls are validated before any event's business handler effects in this attempt.

**C09.** `requireExactDocumentVersion: true` compares `document.blueId` with the exact target member BlueId from the **input graph**, before this attempt's initialization, another member's work or handler effects. Equality of resolved business projections is insufficient. No retargeting occurs. When the flag is false or absent, the optional document field imposes no exact-version restriction.

When the operation's declared request definition is present, actual `request` must be present and satisfy actual-field matching. Without a declared request definition, absent request arguments are permitted. On an actual recipient a wrong type, missing required field, unknown operation or target-channel mismatch rejects before observer effects; it is not a partially accepted call.

**C10.** At external execution, combine the named operation and all matching ordinary workflows on each consuming channel in their defined handler order. Only the operation on its declared fresh target channel is eligible. Observing this event through another primitive or union channel does not invoke it again. A new observer union seeing an already consumed call does not repeat the target channel's operation, request validation or exact-version precondition.

<a id="section-9"></a>
## 9. External channel acceptance, lifetimes and checkpoints

### 7.1 Deterministic acceptance

**C11.** Offer the complete external event to primitive external channels in every active member of the input graph. A standard External Channel accepts when its optional filter matches. An installed deterministic external-channel runtime returns a Boolean acceptance decision from its frozen header, complete original event, timestamp, previous checkpoint and explicitly declared peer access. It cannot replace the event.

Compute each union's transitive primitive-leaf set, rejecting non-external members, missing names, duplicate direct members and composition cycles. A union accepts if at least one of its leaves accepted. Set semantics ensure that overlapping paths contribute one acceptance for that union. Empty composites and All External Channels over no primitives accept nothing.

A document that accepts no primitive does not execute or validate a local named call. A document that accepts the event must have a compatible target for its recognized call when fresh work is selected. Thus broad bare channels on several members deliberately expose the same event to those members; intended discrimination belongs in channel acceptance filters, not a hidden documentPath parameter.

### 7.2 Freshness and no invented ordering protocol

**C12.** This revision's built-in local checkpoint rule suppresses an exact repeat of the **last successfully consumed event** in a channel lifetime. If checkpoint event ID equals incoming original event ID, timestamps must also equal; equality produces no new consumption, and a changed timestamp produces `EVENT_TIMESTAMP_CONFLICT`. If the event ID differs, the input is fresh for this built-in rule.

This is not an all-history deduplication service or a source-order protocol. Contracts does not reject a distinct event solely because its timestamp is lower. A host requiring ordered history or permanent occurrence uniqueness must establish it outside Contracts, or install a precisely bound deterministic channel runtime that verifies the relevant actual event evidence. Equal business payloads used as different external occurrences need distinct original external content; changing only the supplied timestamp does not give an identical checkpointed event a new identity.

Primitive and union checkpoints are independent. Consuming a union does not advance a leaf that did not consume this event. Accepted input with no matching business handler still advances its checkpoint. Internal events do not.

### 7.3 Channel lifetime identity

A primitive lifetime signature binds its exact runtime type and acceptance definition. Extension signatures also bind the complete extension specification and header fields. A union signature binds its exact type, sorted leaf names and the current leaf signatures. A changed acceptance or membership signature starts a new serial generation; removal retires the lifetime. Ordering-only edits do not create a fresh acceptance lifetime.

A frozen seed is eligible only while the same member activation and channel generation remain live. Removal, replacement or changed acceptance cancels remaining old work. Checkpoints belonging to retired generations are reset during final settlement. This prevents an old checkpoint from being silently transferred to a different channel at the same key.

<a id="section-10"></a>
## 10. Deterministic completion machine

**C13.** All implementations execute the same logical machine:

```text
verify exact inputs, configuration and the input graph
freeze primitive/union acceptance and validate selected calls
if the root is already terminated: return TERMINATED
establish input initialization using completed child results
process dependency units before their containers
    run document-local turns
    drain only that document's local queue
    settle its eligible markers and checkpoints
    seal the completed result
    incorporate completed child results before their parent observes events
finish required cyclic rounds and dynamic initialization
finalize the exact graph and verify every affected containing context
return one atomic APPLIED result
```

A dependency unit is initially a strongly connected component of the active managed graph. A singleton without a self-edge is an acyclic unit. Units run dependency-first. Internal graph membership and queues are private processor state; no public delivery wrapper is added.

For a static DAG and one input phase, a member with work has one local turn: it first incorporates all required completed direct-child results, processes their queued events, then handles its frozen external seeds. Its output is not handed upward between channels, patches, steps or event handlers. Initialization is a separate no-external-input phase; its output is not replayed as external work.

A member with neither new child state/events, initialization nor fresh seeds is carried unchanged. Every required header and acceptance fact is still verified; an optimization cannot skip ordinary workflows or another accepting channel merely because one operation name is known.

### 8.1 Fixed ordering

Use the defined exact member keys, NFC token rules, decoded pointer rules and Unicode code-point comparisons. Condensation dependencies precede containers; among ready components choose the lexicographically smallest sorted member-key tuple. Within a cyclic round, visit members in key order. Physical completion order is never a tie-break.

For each receiving turn, order source completions by source member key; within a source, order its completed batches by source turn serial. Within a batch, iterate event ordinal first, then the receiver's eligible occurrence paths and generations. Thus two occurrences of one child see `E1/path1, E1/path2, E2/path1, E2/path2`. Equal-content emissions remain distinct occurrences.

Install all required incoming source states before invoking any receiving handler, validate the resulting receiving view, and append all initial incoming event occurrences in that order before draining. Events emitted by the receiver append to its queue tail. After that drain, execute its surviving external seeds in channel order, draining local events after each seed as in the defined. Incoming work can terminate the receiver or retire a seed before its direct external handling.

Channels and handlers retain `(order, raw contract key, exact runtime type ID)` with zero default order. The stable bottom-up merge comparator in `LogicalWork.ordered` fixes comparison gas. Freeze channel-dispatch candidates and their headers; check each actual-value filter immediately before that handler. Newly installed handlers cannot join an already frozen dispatch.

### 8.2 Execution contexts

**C14.** Context access is unchanged except for the newly specified sealed dependency views:

| Access | External handling | Internal/lifecycle handling |
|---|---|---|
| `$event` | Complete original external event. | Current update, lifecycle or embedded delivery / local event. |
| `$binding: call` | Complete selected Operation Request, where applicable. | Absent. An embedded event cannot become another operation. |
| `$binding: call/request/amount` | Selected request argument. | Not an alternative internal-event accessor. |
| `$binding: processingEvent` | Original external event. | Same attempt cause, when one exists; absent for explicit initialization. |
| `$binding: timestamp` | Supplied microseconds. | Same causal timestamp when present; no fabricated initialization time. |
| `$document` | Current member's frame and pinned exact dependencies. | Same rule. |
| `$steps: name` | Prior named step result in this handler. | Same rule; each handler has its own result map. |

There are no `operationRequest` or `request` bindings. Immediate local continuations restore the suspended event context. A child-batch receiver sees the existing Embedded Event Delivery shape, not a source intermediate read view. The immutable event payload can report an earlier value while `$document` reads the child's completed state.

<a id="section-11"></a>
## 11. Nested steps and BEX effects

**C15.** A handler initializes an empty named-results map and executes its steps in written order. A step result key is its `name`, or its decimal list index when unnamed. Duplicate keys within that handler fail. Names and numeric defaults share one namespace. Returning from Compute returns from that program, not from the whole workflow.

For Compute, execute the existing BEX program and collect its value, changeset and events. The defined's return-object convention remains: when the returned value is an object, present `changeset` and `events` members override the corresponding accumulated result lists; otherwise the accumulated lists are used. Both lists must validate. This convention is a Contracts interpretation of a BEX result, not a BEX operator change. Store the named result, apply all selected patches with their immediate local continuations, then enqueue its events in order.

`$document` remains stable during a single Compute; `$resultValue` reads that Compute's accumulated changes over its starting value according to BEX. A later step sees the applied state and all completed immediate **local** update continuations. A program that alternates appendChange and appendEvent still returns separate changes and events; Contracts applies its changes before recording those returned events.

### Shared Compute definitions

`definition` is optional. An inline object or exact Blue reference selects a
library of `constants` and `functions`. A nonempty Text beginning with `/` is a
Language JSON Pointer relative to the current managed document; other nonempty
Text names a sibling in that document's `contracts` map. A named sibling can use
`type: Compute Definition`. No registry alias, external URL or mutable global
lookup is performed. Resolve the operand afresh when the step executes, after
all preceding steps and their completed local continuations. Unused handlers do
not resolve or compile their definition bodies.

Only `constants`, `functions` and ordinary Blue labels/type/specification/order
metadata are allowed in a definition. Its maps must be objects. Missing paths,
wrong shapes, cyclic executable definitions and unavailable exact evidence never
become an empty library. Missing evidence retains the existing NEEDS_RESOURCES
classification; malformed inputs fail atomically.

Merge each imported map with the step-local map, with local names taking
precedence. Validate/compile the merged program, including its function graph.
`entry` selects a zero-argument function; otherwise the step's inline `expr` or
`do` is used. A definition supplies no implicit entry or executable root body.
Functions use this step's context, effect accumulators and shared gas. `$resultValue`
in an imported function sees the same step overlay as an inline function.
Definition lookup/extraction charges the existing manifest, member/item-read and
Text-work counters before reads; compilation retains its zero semantic tariff.
No program cache may skip these charges or use an earlier document's definition.
`$currentContract` observes the configured step; imported functions are available
for execution without being invented as locally configured step fields.
Effects commit only through the existing atomic Contracts result.

Update Document evaluates its changeset expression with no allowed BEX effects, validates the resulting list, saves `{changeset: ...}` as its step result and applies each patch in sequence. Trigger Event similarly requires an effect-free expression and records one resulting immutable value. Terminate Processing enters termination handling and stops further ordinary steps for that member.

<a id="section-12"></a>
## 12. Patches, validation and local Document Updates

**C16.** Retain add, replace and remove; nonempty relative JSON pointers; exact `~0`/`~1` decoding; canonical list indices; normalized list append; absent before/after sides; and exact no-op detection from the defined. Root replacement through an empty patch path remains invalid. Runtime list pointers are `/lines/0`, not Source `/items` paths.

A parent cannot patch strictly inside a separately managed child. It may replace/remove the whole attachment or an allowed ordinary enclosing structure. A patch validates the current member's own exact local result under Language and its retained generalization policy; it does not mutate or validate a containing member against the source's intermediate state.

Retain the defined protected-state checks. Ordinary effects cannot forge/change initialization, termination, checkpoints or protected policy. Apply the requested patch and any permitted generalization as one valid tentative local change. A failed local validity obligation fails the attempt. There is no temporary-invalid-patch exemption.

Reconcile the current member's occurrence declarations after a structural patch. Retire old generations immediately. Initialize genuinely new children to local completion through the initialization barrier in the annex, using only sealed dependency views. Incorporate their completed state silently; enqueue their completed event batches without re-entering the current handler. Then deliver the creating member's local patch notifications. The next normal step cannot see an uninitialized newly created child. If a newly forming cycle prevents recursive initialization, initialize its uninitialized members in deterministic rounds against their last exact pre-initialization views, as defined in A08; do not recurse indefinitely or expose the creator's live frame.

**C17.** A Document Update is delivered **only in the managed document that produced the business patch**. First deliver generated generalization type updates, then the triggering value update. Each notification completes its immediate local continuations before the next patch, step or ordinary handler.

A channel path matches a change iff its decoded segments are a prefix of that change's decoded local pointer. Ordinary nesting is still observable. A separately managed boundary is not ordinary nesting. No reverse embedding-route traversal, translated `/child/...` path or forwarded update occurs.

For `A → B`, B changing `/count` invokes B's local update handlers only. A's own explicit replacement/removal of `/b` is an A-local patch and can invoke A's handler at `/b`; an A handler at `/b/count` does not hear an ancestor replacement. Automatic incorporation of B's completed state invokes neither.

### Receiving validation is separate from source calculation

B must be valid under B's own exact admitted definition and dependency context. When A incorporates B's completed state, A must remain valid under **all** its own local/inherited contextual requirements. Incorporation does not erase a constraint, generalize automatically, or replay intermediate child changes. An invalid completed incorporation fails before A's observers run and rolls back this attempt. Parent-specific constraints therefore can reject the composed attempt without changing B's local calculation. Any enclosing refinement that Language includes in B's extracted exact local definition/context must travel with B and still constrains B's intermediate local patches. Do not strip such requirements to make a cached result reusable; a differently refined B is a different chunk input.

<a id="section-13"></a>
## 13. Local FIFO, output batches and lifecycle

### 11.1 Application emissions

**C18.** Maintain a FIFO and an output list **per local turn**. Emission captures an exact immutable Blue value, allocates a source-local occurrence ordinal, appends it to that turn's output list and enqueues it for that document's Triggered Event Channels. An event produced by local handling is another output occurrence and joins the tail. Draining local work never removes an occurrence from the output list.

No origin callback routes directly into a container. A source turn finishes all required local work and marker settlement before its output is sealed. The receiver first incorporates the completed source state, then queues the complete incoming batch through its own eligible direct-child occurrences. Queue the whole batch before executing any handler for it. Queue entries are tagged LOCAL or EMBEDDED: imported events are not automatically this receiver's own emissions, do not use its Triggered Event Channels, and do not enter its output list.

Embedded Node Channel's filter checks the inner exact child event. Its workflow sees `Embedded Event Delivery {sourcePath, event}` through `$event`; its local emitted responses subsequently use the receiver's own Triggered Event Channels. Internal Operation Request-shaped events never trigger external operation recognition.

Only direct-child application events cross an embedding boundary. In `P → A → B`, P hears B only if A explicitly emits its own corresponding event. B's completed state can still change A's and P's exact contained content **silently**, including when every output batch is empty.

Example: B emits E1; its E1 handler emits E2. B drains E1 and E2 before A receives `[E1,E2]`. A queues both. If A's E1 handler emits P1, A handles embedded E2 before local P1. All A reads of B use B's completed view, not B's view when E1 was emitted. Receiving one event, draining A, and only then supplying the next event is nonconforming.

Source-local occurrences and receiver occurrences are different identities. A source packet contains no ancestor paths. The receiver binds `(source completion, event ordinal, edge occurrence)` and consumes each such delivery at most once inside this attempt. Snapshot reuse alone must not redeliver it. In a cycle, newly emitted responses are new occurrences; loop suppression is not global deduplication by event content.

### 11.2 Initialization

**C19.** Capture every newly discovered uninitialized member's exact pre-initialization BlueId **before any initialization in that discovered group changes its content**, including initialization of its descendants. For input members this is the initialization-phase starting view; for runtime-created members it is their discovered creation view. A current exact cyclic set is captured as a set before any member's lifecycle writes. Mark initialization in progress before invoking callbacks. Deliver Document Processing Initiated with `document: {blueId: capturedPreInitializationDocument}`; no external event or timestamp is invented.

An acyclic initializer first obtains completed child initialization results. It silently incorporates their states, runs its own initialization lifecycle dispatch, then drains the prequeued child events and locally generated events in FIFO order. Child events that were prequeued remain ahead of events emitted by that lifecycle handler. Settle its protected initialized/termination markers before sealing its initialization result. Cyclic initialization uses the round rules in section 12 and A08, with exactly one initialization dispatch per new activation.

During an ordinary handler, a newly created child's initialization is a nested completion barrier, not a second external seed. The creating parent retains its suspended frame; the child reads only exact sealed targets, never that frame. The child result is incorporated before the creator's next normal step; its events join the creator's local queue in a complete batch. The creator does not publish a result until this work and its own queue finish.

Already legitimately initialized members are not initialized again. Attaching a supplied initialized version does not replay old output. Failed initialization rolls back all effects and protected markers. Initialization marker writes themselves are silent.

### 11.3 Termination

**C20.** Request termination once; run the member's termination lifecycle handlers through the same local effect rules. They may produce valid changes and events. Stop further ordinary processing in that member, discard its not-yet-dispatched ordinary local work, settle its protected termination marker, and seal the resulting output if the attempt succeeds. Already emitted values remain in the output list; termination is not erasure of the source's completed emissions.

The parent may observe a terminated child's final state/output only after completion. A terminated parent installs required completed reference changes silently if its containing state remains required, but does not run ordinary handlers. A root already terminated at entry returns TERMINATED as before. An error or gas failure is rollback, not an emergency termination marker.

<a id="section-14"></a>
## 14. Dynamic graphs, collections, shared members and cycles

**C21.** The `paths` and `collectionPaths` expansion rules require maps for collections, absent paths contribute none, lists at collection paths fail, nonempty valid pointers outside `contracts`, no duplicate or overlapping boundaries. Reconcile structural changes and allocate new edge generations in member/path order. There is no fixed maximum on active documents, edges, contracts, steps, effects, routes, turns or rounds. Retired history is not active work. Charge the required logical graph and processing work to the same invocation ledger before its charged action. Actual membership, complete validation and occurrence lifetime rules still apply; omitting a count check does not authorize pruning the graph or skipping recipients.

**C22.** Resolve a target using an unambiguous current exact binding, then an explicitly selected verified archived exact view, otherwise a valid unmarked fresh child. Marked content without required managed-state evidence needs resources. No automatic latest-state lookup and no merging members merely because business values match. Explicit equal-content distinct members and repeated occurrences of one shared member remain representable.

For a shared DAG child, calculate its compatible local result once for the selected attempt, then bind it separately to each surviving parent occurrence. Repeated references do not duplicate its operation. Distinct exact starting views or seed/context requirements are not one reusable calculation. Stable keys and occurrence generations are never replaced by a bare content-hash deduplication rule.

**C23.** Use the real Language cyclic-set builder and owning-set proofs for exact cyclic content. Distinguish identity finalization from handler execution: rebuilding cyclic references does not emit a business update or by itself schedule another turn. A10 → B7 → A5 keeps A5; it is not a live A10 alias.

### 12.1 Cyclic processing: complete turns, common rounds

An acyclic document can finish before its containers. Members of a live cyclic component cannot all finish before each other. A cyclic **unit** therefore runs deterministic rounds:

1. Freeze a coherent exact component view for the round. All peer/self managed reads use that completed round view.
2. Take the pending batches for each member and, on its one eligible seed round, its still-live frozen external seeds. Process each member's complete local turn in member-key order. No peer sees that member's intermediate state or locally generated events.
3. At the round boundary, merge member-local owned changes, not whole overlapping graph snapshots; reconcile generations and finalize the actual cyclic sets with Language. Validate the resulting exact component. New member outputs become complete input batches for eligible peers in the **next** round, ordered as in section 8.1.
4. Repeat while an internal batch, pending initialization or unconsumed eligible seed remains. A state-only reference refresh does not create an endless sequence of empty rounds.

External seeds and initialization notifications occur at most once per live activation/generation. Feedback can cause further local turns but not redispatch the original operation. The common gas budget bounds feedback. No member commits independently inside the unit.

All outputs to containers outside the unit are held until it quiesces. An outside parent receives the final exact component view plus the ordered output occurrences of the member(s) it directly embeds. It does not receive snapshots from intermediate rounds. A one-member self-cycle follows these same rules.

The preceding-round peer view is an explicit new rule, not a claim that the old shared FIFO already behaved this way. It prevents deadlock and gives a precise completed-view meaning in cycles.

### 12.2 Dynamic joins and splits

Apply topology changes at the safe boundaries in A09. Existing occurrences retire immediately in their producing frame and at the next relevant dispatch check. A newly created child is initialized through its creation barrier; it gets no retroactive external seed.

At a sealed local/round boundary recompute the live SCC partition. If a new cycle spans current execution units, merge those units, retain already consumed seed/delivery identities and sealed local states, and continue round processing for their pending work. A suspended creator is not a sealed peer: new children use its pre-turn sealed view until the creator itself finishes. Do not release a completion across a boundary now inside an unfinished merged unit.

Once units merge, keep that execution-unit union until this attempt ends, even if an edge is later removed. Final **Language identity** components still use the actual resulting graph, not the retained execution grouping. Next invocations start with the new graph's ordinary partition.

New routes cannot receive past output merely because a packet is retained. Initial-phase routes are captured before its source work; a fresh child's initialization routes are captured when that attachment becomes active. At each use require the same occurrence generation. A join carries pending eligible deliveries; it does not regenerate previously delivered ones or replay completed seeds.

**C24.** Removing/replacing an occurrence invalidates its pending **receiving** work. It cannot undo an already sealed source turn or interrupt that turn retrospectively. If A removes B while handling E1 from `[E1,E2]`, the E2 delivery through that retired occurrence is discarded; a replacement does not inherit it. Another surviving occurrence can still receive its batch. A source no longer reachable gets no later local turns through the retired route; its retained sealed evidence is not active capacity.

These rules cover both collections and cycles. An indefinitely responding loop must reach deterministic gas exhaustion through the prescribed positive per-turn/event/round charges. A physical interruption before that boundary is incomplete execution, not a semantic resource-limit failure. No partial success per lap, member or component is introduced.

<a id="section-15"></a>
## 15. Generalization and explicit valid retyping

**C25.** A patch must leave a valid document under the selected Language. The default automatic-generalization mode is reject. Invalid documents are not admitted just because a workflow requested them.

When a change fails only a defined semantic compatibility, fixed-value or schema check, inspect the changed subtree bottom-up and then its containing spine. For each affected explicitly typed node, select the most specific matching policy path by decoded prefix length; equal-specificity ties choose the first rule in the policy list. `defaultMode` applies when no rule matches.

In nearest-valid-ancestor mode, try the current type first, then immediate ancestors in order. At each candidate, charge candidate work and require the implementation to remain a subtype of the policy floor when present. Validate the implementation node with its unchanged local and enclosing requirements; a local rule, enclosing schema or required field cannot disappear just because a type is generalized. Stop at the first permitted valid candidate. An evidence error is not permission to keep searching. Detect type ancestry cycles. There is no independent candidate-count ceiling: charge each candidate and required validation through the existing logical meter before continuing. Stop at the first permitted valid candidate, established failure of the permitted search, or actual gas exhaustion. Missing evidence or operational interruption is not proof that no valid ancestor exists.

Collect generated `/type` changes for all repaired affected nodes; finally validate the complete changed **local member**. Commit the requested value plus generated type changes as one valid tentative result. Local observers see the valid result; notify the type changes before the requested change's update. Failure of any remaining requirement rejects the whole patch and attempt.

**C26.** Explicit retyping is a normal controlled patch: a valid target definition and resulting content may be installed when the inherited/local context permits it and protected policy and managed boundaries are preserved. It does not imply automatic widening. Unknown target types, contradictory fixed requirements and incompatible enclosing declarations fail. A complete replacement can avoid depending on an invalid intermediate two-patch state; individually invalid intermediate patches are not temporarily accepted.


Enclosing constraints **within** the member continue to apply. A separate container is validated when it incorporates the completed member; it does not contribute an invisible mutable parent context to source execution. This changes the Contracts observation/validation boundary, not Language's validity relation.

<a id="section-16"></a>
## 16. Lazy content and installed runtime extensions

### 14.1 Lazy executable bodies

**C27.** Every contract header must resolve to an understood exact role. The runtime may retain separately addressed data and executable-body references. At discovery, read required headers, configured fields and type evidence, not every unused BEX body. At selection, demand the chosen workflow steps and each executable step, and compile/validate the demanded BEX. An invalid unused program is not executed speculatively; calling it must expose the error.

This is not a claim that first-time admission validates nothing beneath a reference. Full initial Language admission and cold restoration may require referenced content. Initial admission and restoration establish complete admitted state; executable loading and compilation occur when demanded. A physical page cache does not change these obligations. Previously established exact evidence may be reused only when bound to the same content, requirements and release. Missing required resources suspend rather than becoming empty objects or zero-cost successful work.

An unchanged large value retains its exact BlueId. Any eager/cached implementation must preserve the same state, events and logical gas. Cache warmth and network time are not semantic gas tariffs.

### 14.2 Extension registry and immutable bindings

**C28.** A RuntimeBinding pins the exact custom type ID, exact semantics-document ID, role, header/body field names, private gas namespace and tariff, optional inheritance to descendants, explicit peer fields, and live or ledger meter mode. The full record is immutable and committed in snapshots. Installing new types does not install their executable behavior. Standard implementations cannot be rebound. Conflicting bindings fail.

Roles are external-channel, processor-channel, handler, marker and nested step. These are runtime roles within the three top-level categories, not additional contract categories. A channel type must descend from Channel; a handler from Handler; a marker from Marker; a step from Contract. Standard abstract catalogue types do not count as concrete implementations. Descendant inheritance is enabled only by the binding's explicit flag.

An external-channel callback receives read-only header, complete original event, integer timestamp, prior checkpoint, bounded declared-peer lookup and live meter. It returns exactly a Boolean. It cannot return another event, a payload path or a delivery plan.

A processor-channel extension explicitly declares one or more internal families from TRIGGERED, EMBEDDED, UPDATE, INITIALIZATION and TERMINATION. Its accepted current internal payload is constructed through its installed deterministic `channelize_internal` semantics; this is internal notification handling, not external request extraction. Peer lookup is limited to fields explicitly declared in the immutable binding. All callback behavior is part of the installed semantics.

Handler/step extensions receive frozen event, header, selected body, previous step results, original cause identity, timestamp, member-local read function, gas meter and selected external call when applicable. They return a closed Contract Execution Result. Validate the entire staged result before applying effects, then use the same patch, continuation, FIFO, termination, boundary and rollback machinery as standard handlers.

Runtime implementations are trusted deterministic code; read-only Python wrappers are not a security sandbox. They must not depend on unrecorded clocks, randomness, I/O or hidden global state. A production host must provide the corresponding isolation outside these Contracts semantics. No authorization power follows from installing an extension.


All extension callbacks obey the same frame and completion boundary. An UPDATE extension sees local updates only. An EMBEDDED extension sees complete-batch entries after sealed source incorporation. No callback receives a live parent frame, enters another member recursively as an event side effect, or mutates the output list after sealing. Runtime ledger merging uses the same ordered logical work protocol as standard handlers.

<a id="section-17"></a>
## 17. Logical gas and host-independent resource semantics

**C29.** the logical gas schedule appendix and the metering appendix define the exact logical meter. The shared maximum and default remain **100,000**. There are no unrelated structural/resource ceilings. Gas MUST NOT be increased beyond the specified maximum, disabled, or charged by host time or memory. Existing numerical tariffs are retained unless an explicitly recorded and qualified metering correction is necessary. Any such correction must define its exact counter, units, charge position and order before publication; preserve BEX value/evaluation semantics and distinguish the changed gas edition from physical optimization.

One shared ledger covers the complete rooted attempt; the default/maximum shared allowance remains 100000. Member ceilings are additional constraints on that same logical ledger. A charge is `(ordinal, namespace, counter, units, amount, owner)` and is debited before its work. Retain the defined shared/local exhaustion tie-break and rejected-charge accounting. Rollback does not refund admitted work.

The canonical logical schedule is the dependency order, local turn order and component-round order in the annex. Chunk dispatch, transport, wall time and physical cache reads create no extra semantic charges. A cached chunk supplies the same verified logical segment; replay it against the attempt's current ledger **before** accepting any effects. It cannot skip work, reset allowances, erase a rejected prefix or be merged twice. Runtime callback namespaces and sealed runtimeLedger rules follow the metering appendix.

A standalone `process(B, e, t)` includes its own setup and root projection. Its scalar gas is not blindly added to another standalone `process(A, ...)`. Full equivalence uses one normalized attempt: shared preflight/finalization once, each logical member computation once per prescribed turn, each receiver's required application work, and the selected root's projection once.

The protocol has no separate maximum document/edge count, contract-map size, workflow-step count, patch/emission/route/dispatch count, turn/round count, content/path/filter/program depth, executable-body size, token length or generalization-search length. Keep the required syntax/normalization and exact value/format rules; remove only the unrelated resource ceilings. Explicit authored constraints and supported stricter member gas budgets remain enforceable.

The standard whole-attempt gas maximum is still 100,000, not 100,000 per member, page, chunk or component round. Existing explicitly selected lower test/invocation budgets and member-local ceilings remain supported and bound into execution evidence; a machine-specific shortage must not silently lower the authoritative budget. Exactly spending the remaining gas is allowed if no further charged work is required; the next unaffordable charge is rejected before its corresponding work. Do not change the existing tie-break or first-rejected-charge record.

All repeatable semantic progress formerly protected only by a removed count guard must have a defined positive logical charge or a finite structural termination argument. A scalar-expression base charge is not evidence that arbitrary-size arithmetic, copying or materialization is adequately metered. Review these paths before claiming gas-bounded processing. Reuse defined counters/quantities where they already describe the work; do not derive costs from Language's physical step count, a worker timeout, cache warmth or bytes actually fetched from a warm/cold database.

Gas is a portable work rule, not a promise of a fixed number of milliseconds, bytes of RAM or I/O calls. A correctly supplied under-budget invocation remains the same computation on every conforming host. Local inability to finish it is not a new semantic outcome; the host must improve capacity or implementation and retry the original pending work without increasing its gas allowance.

<a id="section-18"></a>
## 18. Atomicity, replay and chunking equivalence

**C30.** A sealed child or component completion is a **calculated value**, not a separately committed document. All affected state, output, protected markers, channel lifetimes and graph identities remain tentative until the entire selected attempt succeeds. Any failure rolls back the entire attempt; public events are empty on failure. Retain admitted gas diagnostics under the stated failure policy.

**Physical interruption is not a completed failure.** Memory/stack exhaustion, a configured host work cutoff, timeout/cancellation, unavailable storage or a failed worker before completion must not be translated into `GAS_LIMIT_EXCEEDED`, semantic `FAILED`, `TERMINATED` or invalid input merely because execution stopped. Unwind or abandon the tentative attempt and communicate a typed host/incomplete condition outside the canonical Outcome. The original committed state and input remain authoritative. A partial gas trace is diagnostic evidence only, not a completed receipt or terminal input disposition. Missing exact content continues to use the supported `NEEDS_RESOURCES` mechanism. If publication may already have committed, reconcile its original identity before another execution.

Checkpoint settlement occurs at the end of the eligible member turn so its completed state contains the consumed-original-event checkpoint. Validate the same activation and channel generation; retire old checkpoints on generation change. Later structural edits cannot transfer these records to a replacement. Final graph verification still runs before returning APPLIED. A parent that merely receives a child batch gets no external checkpoint from that receipt.

**C31.** Replay fixes the exact starting snapshot, original event, microsecond time, release, Language/BEX profiles, runtime bindings, selected exact dependency views and gas policy. It reproduces the exact resulting documents, root output occurrence order, checkpoints, status and canonical logical work/gas trace. Physical task identifiers, storage fetch order and cache statistics are not semantic trace fields.

### 16.1 Required composition property

For identical fixed inputs under this edition:

```text
reference rooted processing
    ==
execution of its ready complete chunks, followed by verified incorporation
```

The equality covers exact Blue documents, event occurrences/order, legitimate processing metadata, success/failure and logical gas. Both paths execute the same A01–A12 algorithms. A monolithic processor is an eager driver of that machine; it is not an alternate interleaving implementation.

For an acyclic `A → B` where only B accepts the input, obtain B's complete compatible result, incorporate its state and complete batch in A, and finish A. For `P → A → B`, use A's **own** resulting batch in P. A's other children are pinned dependencies, not automatically operation recipients. The processor nevertheless checks every relevant accepting header, validation and read requirement.

An independently calculated B result is reusable only when its exact before-view, cause/time, local seed selection, runtime profile, dependency bindings, completion boundary and logical work agree. Retyping context, distinct archived view, another source turn, old channel lifetime or cyclic peers can invalidate reuse. A final state plus event values is the semantic payload; exact bindings and work evidence make it safe to substitute. No intermediate source-patch transcript is required under this new boundary.

The guarantee is not that arbitrary standalone commits, arbitrary root relabelling, arbitrary per-event application, or arbitrary graph cuts are equivalent. A cyclic component is a complete external chunk; its internal turns use the specified rounds. A dynamic join removes a former acyclic cut and must expand the chunk boundary before further external exposure. Chunk partitioning cannot change these boundaries.

### 16.2 Read-only exact content and persistence

Existing snapshot/invocation export concepts remain, but their release and changed record domains must be regenerated. A saved chunk is not accepted as a public event. Missing or incompatible evidence fails closed. Immutable bytes can be stored before success without publishing application state. Storage may atomically commit the final snapshot, receipt and output; it may not publish a chunk prefix as the whole attempt.

<a id="section-19"></a>
## 19. Conformance and integration

`CONFORMANCE.md` is the required acceptance matrix. `EXAMPLES.md` gives worked expected results and small Source YAML examples. The illustrative model retained under `inputs/contracts-completion-1-design/model/` is not the runtime. The actual executable qualification uses `tests/contracts_event/` and the website’s shared guide fixtures.

A conforming runtime must compare a direct driver and a chunked driver of this same new machine for exact state, occurrence order, checkpoint state, gas and failures. Conformance cases MUST cover local Document Update boundaries, child-first completion and parent observation of completed child states. Do not silently delete lifetime, shared-graph, cycle, resource or extension tests.

The executable appendix contains the exact reference algorithms; the package supplies finite conformance evidence separately.

<a id="section-20"></a>
## 20. Normative algorithms and provenance

The prose, detailed transitions, executable algorithms and gas schedule in this document form one normative contract. A contradiction is a specification defect, not an alternative implementation mode.


`inputs/contracts-completion-1-design/CURSOR_PROMPT.md` records the implementation and publication assignment. It does not delegate the decisions about local updates, batch placement, final child read views, cycle rounds, occurrence retirement or atomicity: those are specified above and in A01–A12.

<a id="section-21"></a>
## 21. Generic Coordination integration boundary

This edition adds read-only runtime context and controlled retained completion application. It does not add Timeline semantics to Contracts and does not alter `process(document, event, eventTimestamp)`.

An external channel receives its exact member, input document, channel key and generation, and a deeply immutable admission observation. The installed runtime verifier derives that observation from frozen evidence bound to the input snapshot, original event/time and registered runtime semantics before any seed is selected. A caller-supplied Boolean is not evidence. Portable invocation restoration repeats verification. Primitive channel acceptance remains Boolean and cannot replace the original event or the selected complete call.

`capture_source_outcome` issues an opaque capability only for an unchanged successful outcome produced by this Processor. `install_completion_reader` is a privileged one-time host integration hook for protected local storage, never an upload API. A reader must establish the retained before/after snapshot, exact receipt, event/time and runtime bindings. Unverified foreign results cannot enter through it. Retained receiving application requires the exact source predecessor, original member identities and complete inseparable source unit. It installs all eligible source state before callbacks, routes complete own-event batches through the same local kernel and supplies no receiver external seed or source business execution. Duplicates, incompatible runtime bindings, conflicting views and unsupported cyclic cuts fail atomically. This edition defines no portable receiving-export protocol; implementations MUST NOT fabricate such evidence.

`begin_live_application(document, source_completions, evidence=...)` is the corresponding combined LIVE preparation. It verifies admission and freezes external seeds against the original receiver input, then installs the complete required retained dependency results. Adopted owners and their already completed dependency closure are excluded from local execution. Receiving reactions run before the receiver's surviving own seeds, as required by C13. Only the completed invocation is publishable. Historical receiving remains seedless. Both preparation paths require the same protected completion provenance and exact predecessor checks; neither changes the public three-input processor interface or combines independent gas totals.

The hardening edition corrects a reference defect in the source-turn commitment used by emitted occurrences. Execution certificates include invocation-wide logical work and remain bound and checked as execution evidence. Such a certificate must not rename a member's application emissions merely because a different containing root drove the same semantic turn. The semantic incoming commitment binds each ordered batch's source member, serial, completed after-view, ordered emitted occurrences and captured occurrence tickets, together with the turn's existing cause, local before-view, dependencies, seeds, phase and lifecycle. The complete certificate remains in `turnInput` for replay verification. The full certificate remains required execution evidence; its encoding is distinct from the semantic occurrence key.

The local driver can complete an untouched local attempt without allocating portable token/candidate envelopes. It executes the same readiness, work-unit and finalization transitions, including every logical charge and first rejected charge. An attempt that has issued a token or accepted chunk history cannot change driver. Transport identifiers and copies are not logical work. Equivalence qualification compares outcomes, occurrence order, checkpoints, gas traces, rollback and low-budget failures.

Committed local turns retain exact handler/declaration attribution for each patch. This is protected execution evidence used by higher-layer lifecycle policies; submitted documents cannot author trusted attribution. Archive imports preserve original managed-member keys when unambiguous, so independently selected historical roots retain occurrence identity. Exact historical addresses still select their archived state, never an arbitrary newer live alias.


<a id="section-22"></a>
## 22. Lazy immutable host values

An event, call, processingEvent or selected document collection is an immutable exact view bound to its effective Language recipe and captured resolver. Scalars are ordinary BEX values. Reading a root returns a view, not a recursively expanded JSON tree. Member/item access follows only the demanded path. Keys and presence retain Language meaning, including inherited values and absent declaration holes; missing evidence needed to establish presence remains a resource dependency. References are not ordinary business objects containing a blueId key. `$get`, `$keys`, `$var`, function arguments and subsequent pointer reads use the same collection interface as direct paths. Copies retain the captured view.

Serialization across a Blue output boundary retains the selected exact node and finite reference boundaries. It must not unfold predecessor history, replace a referenced value by null, truncate its meaning, or hash a display projection as its exact identity. Referenced and inline values have the same effective observation. Cyclic exact references retain their owning evidence. User programs cannot manufacture host capabilities.

Logical document/event member and item reads use the Contracts counters; node manifests are charged once per invocation logical inventory, independent of physical cache warmth. BEX arithmetic and control tariffs are unchanged. Size-dependent BEX output charges for an exact host value use the canonical exact-transfer accounting token specified in the metering appendix, independent of its inline/reference storage form; demanded traversal has separate logical charges. The shared meter does not reset on path reads. Any explicitly selected physical Language control remains out of band and cannot create a semantic rejection. Explicit BEX `$fail` / `$failIf` reports EXECUTION_REJECTED, distinct from invalid executable syntax or an internal runtime error.

There is no protocol depth ceiling on demanded access. A selected subview keeps its exact resolver, logical meter and read context when copied, bound to a variable or passed as an argument; splitting a path cannot reset gas or skip required logical member/item charges. Untouched reference ancestry remains unopened. Host recursion failure is an implementation inability to complete, not proof that a valid deep value violates Contracts.

A well-formed unaddressed request with zero operation candidates does not invoke an operation. Eligible ordinary observers can still run, preserving the original event and call. A same-channel candidate missing the operation remains an error. Union observation does not repeat an already consumed operation. Runtime-certified operation audiences are internal verified data bound to input snapshot, original event, exact runtime and channel generations, not a fourth caller input.


<a id="section-23"></a>
## 23. Exact-value transfer accounting

Compute may transfer an existing exact object or list without recursively pricing
its physically inline body. The captured Language recipe selects the exact
originating value, not its effective display and not a mutable latest head.
A single complete contribution carries verified admission/opening identity
evidence; a composition of contributions must first establish its exact result
with the prepaid runtime normalization/identity boundary. Requirements inherited
from a container do not rename its originating exact identity.

The BEX host accounting form is `{blueId: exactIdentity}`. This is a private
host interface, not another authored protocol or a validation assertion.
Generic host values and authored reference-shaped objects receive no admission
privilege. Scalars retain BEX scalar semantics; literal metadata and a bare
items slot are not independent exact-node capabilities. Runtime effect
normalization, target-context certification, and exact content/owning-proof
retention remain mandatory. Missing/invalid evidence has its specified
outcome. Captured cyclic identities stay finite and preserve their owning sets.

This metering selection does not redefine Language identity or BEX value semantics. A receipt is bound to its selected specification and tariff; it MUST NOT be reinterpreted under another edition.

<a id="section-24"></a>
## 24. Selected descendant evidence

A Language child recipe contains existing exact contributions, even when a
cached effective head returns different immutable instances of those contributions.
For a witnessed parent recipe, successful Language selection derives exact identity
evidence for each selected complete child part. Type/requirement resolution must
have succeeded against the captured resolver. Derive this evidence at the selected
boundary; do not recursively prescan or mark unrelated descendants. A physical
handle indexes the derived evidence but does not define it. Reconstruct it from
bound parent evidence after transport, independently of cache and cut placement.

This derivation applies to complete ordinary members, list elements and the
complete contracts node, not literal metadata or the items sequence slot. It does
not combine multiple contributions or discharge contextual requirements. Unknown
parents confer no descendant capability. A genuinely synthesized exact result
still uses prepaid establishment; only its successful ordinary result may issue
a reusable identity witness. A cyclic token-context hash is not an ordinary
identity. Incomplete or rejected establishment must not issue a result witness.

Canonical transfer tokens and value semantics are defined by the exact-value transfer accounting rules. Read,
normalization, validation and effect tariffs still apply in their prescribed order.
The same selected exact descendant has equal traces and rejection behavior under
inline, reference, mixed, cached, restored and transported representations.
<a id="transitions"></a>
## Appendix A. Complete transition model

### A00. Values, identities and retained helpers

Use the selected Language bridge for exact values, contextual recipes, actual-field matching, valid type ancestry, pointer reads/writes and cyclic-set finalization. Retain BEX evaluation unchanged. The executable appendix supplies the complete helper implementations; A12 defines their integration responsibilities. Do not use a mutation pattern that exposes working state through `Run.patch`, `Run.drain` or global graph finalization to reintroduce parent observation of a working frame.

Comparison of member keys and raw keys is Unicode code-point comparison after the Language validity/NFC checks. Pointers compare by decoded segment tuple; segment strings use that comparator. Integer ordinals compare numerically. Empty values, absence and null retain their different defined meanings.

For private processor commitments, use the defined `canonical` and `digest` functions, with the following domains. These SHA-256 commitments are **not BlueIds**:

```text
contracts.snapshot/completion-1
contracts.invocation/completion-1
contracts.turn-input/completion-1
contracts.turn-result/completion-1
contracts.round-result/completion-1
contracts.event/completion-1
contracts.embedded-observation/completion-1
contracts.work/completion-1
contracts.unit-result/completion-1
contracts.chunk/completion-1
```

The invocation descriptor binds the exact input snapshot commitment, original event identity or absence, supplied timestamp or absence, profile and gas policy. A snapshot uses the stable member/edge/serial records, with the selected release and record domain. Scheduling state is not injected into business documents.

### Private records

| Record | Closed required contents |
|---|---|
| `Cause` | `kind` PROCESS or INITIALIZE; PROCESS has exact `event` and `timestamp`; INITIALIZE has neither. |
| `OccurrenceTicket` | `parent`, `parentActivation`, `path`, `source`, `sourceActivation`, `generation`. |
| `TurnInput` | `member`, `activation`, `beforeView`, `profile`, `cause`, `phase`, `turnSerial`, ordered `dependencies`, ordered `incoming`, ordered `seeds`, `lifecycle` (`{kind:NONE}` or `{kind:INITIALIZE,document:exactPreInitializationRef}`), and exact `logicalContext`. |
| `EventOccurrence` | `sourceTurn`, zero-based `ordinal`, exact `event`, `identity`. |
| `TurnCompletion` | `turnInput`, `afterView`, ordered `output`, `memberMetadata`, ordered `edgeChanges`, `consumedSeeds`, `retiredTickets`, `workSegment`, `identity`. |
| `RoundSeal` | exact preceding and resulting component vectors, round ordinal, ordered local completion identities, their finalized member projection, changed live bindings and identity. |
| `UnitCompletion` | sorted `members`, exact `beforeViews` and `afterViews`, ordered per-member `turnResults`, per-member `output`, `workSegment`, `identity`. |
| `QueueItem` | `kind` LOCAL or EMBEDDED; exact `event`; LOCAL has source occurrence identity; EMBEDDED additionally has source completion and occurrence ticket. |
| `Frame` | owned working body/metadata; immutable dependency view; local FIFO; own output; suspended handler stack; pending initialization barriers; retired routes; consumed seeds. Mutable and never exported. |
| `ChunkToken` | attempt identity, selected unit, exact TurnInput/round descriptors, logical sequence position, expected input/output dependencies, meter/logical-proof prefix commitments; one-use token. |

`beforeView`/`afterView` mean exact local content **plus** selected managed bindings/required component proof, not only a projected business object. An `incoming` row is closed: `{kind:DAG, sourceCompletion, tickets}` for an acyclic/outside-unit source, or `{kind:CYCLIC, sourceCompletion, roundSeal, tickets}` for an intra-unit source. `tickets` is the ordered receiver-ticket list. The cyclic variant carries the exact finalized source projection and is not a new external event. Seeds keep the existing member, activation, channel, generation and selected operation identity/key facts. `logicalContext` binds the canonical metering proof/manifest inventory, not physical cache residency.

Compute `sourceTurn = digest(turn-input-domain, semantic TurnInput fields excluding logicalContext)`; accounting-prefix evidence must not change the identity of the same semantic local turn; `EventOccurrence.identity = digest(event-domain, {sourceTurn, ordinal, event})`. The source key is retained when rerooting an existing managed snapshot. Do not rebuild B as a fresh differently initialized root and call it the same reusable turn. A receiver observation identity binds the source occurrence identity and the full occurrence ticket. Turn-result identities bind the listed content excluding their own identity field; unit and round identities likewise bind all listed fields except their own identity field, using their respective versioned domains. Work rows inside a completion use relative ordinals; flatten them into the common attempt's canonical work order on acceptance. Snapshot record roots/revisions remain attempt-specific.

Before a closed record is admitted, reject unknown fields and invalid variants, verify content identities, validate monotonic serials and prove every referenced component/binding. `identity` fields never authenticate execution by themselves.

### A01. Public PROCESS / INITIALIZE

```text
PROCESS(input, event, time):
    validate SDK arguments and configured immutable runtime bindings
    establish exact event identity and original input graph
    S := new isolated Attempt(input, Cause(PROCESS, event, time))
    charge processInvocation; charge closureInvocation
    verify input graph and required contract headers
    freeze input member activations and external channel acceptance
    select and validate all fresh calls using input member identities
    if root was already terminated: return original-state TERMINATED
    INITIALIZATION_PHASE(S)
    PROCESS_PHASE(S)
    require no runnable local work, unsealed frame or pending init barrier
    finalize changed exact components and containing references
    validate all affected owned/containing contexts and protected records
    settle topology/revision bookkeeping once for this invocation
    project only selected-root output occurrences in canonical creation order
    return APPLIED with the complete graph, output and normalized gas ledger

INITIALIZE(input):
    open the same isolated machine with Cause(INITIALIZE)
    no external event, time, call, seed or external checkpoint is invented
    perform INITIALIZATION_PHASE and final validation/projection as above
```

Every exception follows A10. Initial operation recognition and input-version checking stay in the unchanged C08–C12 helpers. A child produced during this attempt cannot enter the frozen original seed set. A dynamically created channel cannot accept this same external event retroactively.

`INITIALIZATION_PHASE` runs before `PROCESS_PHASE`; each has its own dependency-unit work set. Initializer output is handled exactly once in the initialization phase and is not re-imported during the process phase. Capture the pre-initialization references for all newly discovered uninitialized members before initializing any member of that discovered group, including descendants. Initial cyclic-member captures use the coherent input component. These captured values are carried in lifecycle descriptors and never replaced by a post-child-initialization view.

The selected root's total output concatenates its own initialization-phase outputs and process-phase outputs in canonical order. No child's values become public merely by passing through a parent.

### A02. Build and drive the dependency units

1. Derive the exact finite managed-edge graph with the defined explicit/map-collection rules and verified bindings. Maintain a separate active-processing mask: terminated members accept no ordinary work; their declared content is still verified where required. Never enumerate external incoming observers to enlarge the selected rooted graph.
2. Compute SCCs. An initial unit is an SCC; order dependencies before containers. Keep the lexicographically smallest ready member-key tuple as the canonical next unit.
3. For a singleton with no self-edge, wait until all its required outgoing dependency units for the phase have sealed. Carry untouched dependencies without opening unused bodies. Then run A03 once for all its pending input-phase work.
4. For a cyclic unit run A07. Every unit outside it sees only its final UnitCompletion.
5. Feed a sealed source result to each eligible containing unit in the selected graph. A source may have many consumers, but its compatible selected calculation is not rerun for each edge. Bind per-edge receiver tickets separately.
6. A structural change calls A09. A changed pending dependency prevents sealing the affected unit until its required initialization/view work has completed. Unchanged exact historical references are not silently redirected.
7. Process units until the selected root and every required pending consequence have sealed. Retired, unreachable work is discarded by its recorded lifetime; discarded work is not reassigned.

A unit can be carried without a business turn if it has no incoming changed state/events, no initialization and no fresh seed. Exact containing-reference changes still make a result available upward, even without handlers or emissions. In a static DAG all changed direct dependencies are installed before the container's input-phase turn. Thus sibling completion timing cannot affect a parent's reads or queue order.

### A03. Complete one local document turn

```text
RUN_LOCAL(TurnInput I):
    verify the exact before-view, dependencies and input binding
    charge localTurnOpened
    F := private frame for I.member; no other frame is writable or readable
    INSTALL_INPUTS(F, I.incoming)                 # A04, all source states first
    if I.lifecycle.kind == INITIALIZE:
        use I.lifecycle.document captured at discovery, not the current frame
        mark this activation initialization-in-progress
        dispatch local lifecycle initialization once
        # incoming child events were prequeued; lifecycle emissions append
    DRAIN_LOCAL(F)                               # A05
    for seed in I.seeds in prescribed channel order:
        if same activation/channel generation survives and member can run:
            dispatch selected operation + ordinary workflows
            DRAIN_LOCAL(F)
            mark this seed consumed
    finish required initialization barriers and local continuations
    DRAIN_LOCAL(F)
    settle this member's eligible markers/checkpoints
    verify local state/protected records and required bindings
    require empty local queue and no unfinished handler/barrier
    charge localTurnSealed
    return immutable TurnCompletion
```

The lifecycle dispatch uses existing handler/channel ordering and effects. A frame's local queue is empty on entry except for the preloaded incoming batches. After a normal seed dispatch, locally emitted events drain as before. No parent is called during this routine.

If the member was legitimately terminated before its turn, skip ordinary/lifecycle reinitialization work, discard its ordinary incoming deliveries, and only synchronize required completed references/bookkeeping under the validation rules. If termination is requested during the turn, run termination lifecycle once, stop ordinary work and retain already emitted output. In all cases the completed result must be valid; termination is not a validity bypass.

Within each handler, use the defined dispatch/step semantics. A Compute sees a stable view of the member at that Compute's start; BEX evaluates with its existing result overlay. It returns separate effects. Apply its patches with immediate **local** continuations, then record its events. Subsequent steps see completed local continuations. No new BEX operator or cross-document operation call is introduced.

### A04. Incorporate completed source states and queue complete batches

For a DAG or outside-unit incoming set, perform the following steps. For an intra-cycle batch, first verify its RoundSeal and use that seal's finalized source member in the coherent previous-round view; A07 specifies the receiving view and prohibits installing an isolated old member over it. The same queue, route and event rules still apply.

1. Verify each source completion against the selected exact source before-view, cause, profile and phase. Verify every selected source dependency, body, component proof and completion capability. A completed result from another incompatible view cannot satisfy the ticket.
2. Reject a mixed/conflicting set: one continuing occurrence cannot be advanced along two incompatible source outcomes. A declared sequence of source turns must form its exact predecessor chain; preserve its ordinal order. Within a static DAG phase there is one final result per source. An outside consumer of a cyclic unit receives its final view and accumulated output, not intermediate round states.
3. Filter retired receiver tickets. Require the same parent activation, source binding and edge generation. A removed occurrence has no work; it is not an integrity failure to discard already captured but now retired work. Wrong supplied evidence for a **live** ticket is an error.
4. Replace only the surviving occurrence's selected reference/binding with the completion's exact after-view. Keep the occurrence generation. This is structural incorporation, not a business patch. Rebuild affected containing identity paths. When several dependencies arrive, install the complete coherent set before validation or callbacks.
5. Validate the complete receiving document with Language, including its enclosing constraints. Do not generalize automatically or send Document Updates. Failure aborts this selected attempt before receivers run.
6. For each ordered source batch, for each event ordinal, for each sorted eligible occurrence ticket, append an EMBEDDED QueueItem. Perform this full append before invoking any receiving handler. Charge completionBatchInstalled once per installed source batch/receiver and completionRouteChecked per considered ticket.
7. Bind each pending row to its exact source occurrence and receiver generation. Record queue membership, not successful delivery, now. A05 rechecks lifetime before dispatch.

An empty event list still performs steps 1–5 and updates state. A state-identical source that emits events still performs steps 6–7. Duplicate event **values** do not collapse occurrences. Already accepted packet replay in the same attempt cannot append its rows twice; use the explicit receiver observation keys, never just event BlueId.

Do not put a completion packet into `$event`. An EMBEDDED item constructs exactly the existing `Embedded Event Delivery {sourcePath, event}`. Incoming occurrences do not enter the receiving output list.

### A05. Per-document emission and FIFO

```text
EMIT(F, exactValue):
    capture and verify the immutable exact event
    allocate next source-local ordinal in F.output
    append EventOccurrence to F.output
    charge internalEventEnqueued
    append LOCAL occurrence to F.queue

DRAIN_LOCAL(F):
    while F.queue is not empty:
        item := pop_front(F.queue)
        if item.kind == LOCAL:
            charge internalEventDequeued
            if member can receive ordinary events:
                dispatch its matching Triggered Event Channels/extensions
        else:
            recheck the same source/receiver occurrence lifetime
            if retired or receiver terminated: continue
            construct existing Embedded Event Delivery
            dispatch matching Embedded Node Channels/extensions only
        finish each dispatch's immediate local update continuations
        # any event emitted above was appended to the tail by EMIT
```

Freeze candidate channels/handlers at their prescribed discovery point. Check route liveness before every resumed embedded handler and step; a handler can retire the occurrence. If A's E1 handler removes B, A's queued E2 from that occurrence is dropped. B's E2 local handler already ran before B sealed; A cannot undo that. Other surviving occurrences retain their own work.

LOCAL events never call parent observers. EMBEDDED events never call the receiver's Triggered Event Channels unless a receiver explicitly emits a new value. All output is captured at creation, remains immutable and is kept even after its local notification has been drained.

For input batches `[E1,E2]`, A's E1-generated P1 is behind E2. If two source batches are preloaded, A's emitted work also stays behind the rest of the initial incoming queue. The standard does not permit processing each input value as a separate standalone attempt.

### A06. Local patch and exact view isolation

```text
APPLY_LOCAL_PATCH(F, patch):
    validate effect shape; account the existing patch/boundary work through the shared meter (no patch-count ceiling)
    normalize pointer/list append; charge boundary/path/patch work
    reject strictly-inside-managed-child and protected-record writes
    capture exact before-side and protection identity
    apply patch to F.ownedBody only
    run retained generalization search, if permitted, on this local document
    validate exact local result; protection identity must be unchanged
    reconcile this member's declared edges and retire replaced generations
    run A08 for newly created uninitialized children
    silently install their completed views; queue their complete ready batches
    capture the final exact after-side of the completed local patch boundary
    if exact before/after equal: no business update
    dispatch generated type updates locally, then original local update
    complete these immediate local continuations before returning
```

Capture `after` after the new-child initialization barrier, so a handler reacting to the parent's own `/child` attachment patch does not observe an unfinished new child. A user-authored patch to an ordinary enclosing object remains locally observable. A descendant's own patches and automatic exact-reference rebuilding remain unobservable to the parent as Document Updates.

`Graph.finalize` must not synchronize source working bodies into other member frames at every patch. Replace that use with (a) local exact validation against pinned dependencies, and (b) safe-boundary sealed graph finalization. The finalizer can construct temporary Language values/proofs to validate a local view, but those objects are not externally visible member completions and cannot authorize peer callbacks.

### A07. Cyclic units

A unit has a pending inbox per member, a consumed seed/init set, a turn serial per member, a coherent last sealed component view, and buffered external output.

```text
RUN_CYCLIC_UNIT(U):
    repeat:
        charge componentRoundOpened before the round; no independent round-count ceiling
        V := immutable coherent view of U's last completed round
        inputs := snapshot pending per-member batches and remaining seed/init work
        clear only those pending items included in inputs
        results := []
        for member in U.members in key order:
            if member has eligible inputs:
                results += RUN_LOCAL(input using V for all peer reads)
        merge each result's OWNED member changes into V
        reconcile member edge declarations and retire invalid generations
        use Language to finalize ACTUAL resulting cyclic components
        validate the resulting coherent component; create immutable RoundSeal
        # RoundSeal maps local after-views to the exact finalized member vector
        retain output per source in round/member/turn/local-ordinal order
        route each new output batch to surviving captured intra-unit tickets
        place those batches, each bound to RoundSeal, in NEXT-round inboxes
        # never invoke this round's peer callbacks
        absorb topology joins and pending initialization via A08/A09
    until no pending batch, initialization or external seed remains
    expose one UnitCompletion to outside containers
```

A member without work does not rerun its external operation merely because a peer changed state. At the round boundary all member references are made coherent; pure identity/reference changes do not create another round. Internally generated events and lifecycle work do. All applicable member-local gas ceilings and the shared 100,000 maximum remain live across rounds; no independent structural turn/round limit applies.

Within a round, peer and self-edge reads use V, never a result produced earlier in the member-key loop. Local owned-field reads use the current frame as usual. At the next round, peers see the just sealed V'. This is deterministic even if turn calculations are physically parallel; logical acceptance/metering remains member-key ordered.

Cyclic incoming messages are notifications of completed prior turns. Their immutable payload remains exact. The receiving cyclic frame reads the current coherent previous-round component view, which includes all completed sources at that boundary; it does not install an older isolated peer body over a newer coherent component. Each pending batch is verified through its source completion and RoundSeal; its source turn must be included in the current component history. A local after-view before cyclic reference rebinding is not asserted equal to the finalized member BlueId. RoundSeal supplies that exact projection without changing or forging the immutable local output. The final outside batch always uses the final complete component view. This explicitly states the cyclic read rule instead of pretending a single member can independently finish a feedback loop.

A split keeps U's execution group until quiescence, but finalizes identities under the actual split graph. New joins are handled below. No special wave, epoch or host scheduling concept is part of this algorithm.

### A08. Initialization and dynamic creation barrier

For initial initialization, build dependency units and capture all discovered uninitialized member references before any initialization writes or descendant refreshes. Initialized members are carried, not reinitialized. A03 lifecycle dispatch happens once per new activation. Cyclic initialization uses A07's round-0 lifecycle work and subsequent local-event feedback.

For a child created by an in-progress parent patch:

1. Record its exact creation body, new occurrence generation and creation cause. Do not invent an external input or checkpoint. `created during this attempt` alone does not change Language admission rules.
2. Discover its uninitialized dependency closure. Distinguish new members from existing initialized members and ancestors already initializing. The latter are **read-only pins to their last sealed/pre-initialization exact views**, not recursive initialization requests.
3. Initialize the new-only closure dependency-first; use rounds for SCCs among the new members. Capture all such members' pre-initialization IDs once. A back-reference to the suspended creator reads its sealed pre-turn view, never its private patched body. Mark any resulting live join for A09 rather than recursively entering the creator.
4. Seal the newly initialized members and supply their completed states to the suspended creator. Queue all eligible direct-child initialization outputs as complete batches behind existing queue items. Do not drain the creator's queue inside its current handler; local Document Update continuations still run at A06's boundary.
5. Resume the creator's patch/handler. Its next normal step sees the child initialized. It cannot seal upward until this barrier and its own work are complete.
6. When the creator seals, activate the pending live bindings coherently and recompute units. A cyclic join uses the completed creator view and retained child result; internal messages already delivered during the barrier are not redelivered. Remaining feedback becomes subsequent group-round work.

If evidence is missing, fail/suspend the whole attempt under A10 rather than expose an incomplete child. The same deterministic gas ledger applies to this process. Any physical allocation/work interruption remains an incomplete attempt, not a child-initialization rejection. A child later removed by its creator can have consumed calculation gas without surviving in the resulting active graph.

### A09. Topology changes, unit promotion and route capture

Maintain monotonically increasing member-activation and edge-generation counters as in the defined. Whenever a declared edge changes, retire the previous occurrence and allocate the next generation in deterministic source/path order. Keep retired records for evidence without treating their inventory as active processing work. There is no universal active-graph capacity ceiling.

**Route capture:** for original phase work, capture the source's incoming edge tickets from the coherent phase-start graph. For newly initialized children, capture the newly active direct tickets at the creation barrier. A later edge never acquires source events already emitted/sealed before it existed. A continuing source's subsequent turn captures then-current tickets. Source output values themselves contain no route paths.

At a sealed turn/round boundary:

```text
compute actual active SCC partition
for any actual SCC touching more than one current execution unit:
    U := union of all touched units (including prior sticky unions)
    retain each member's last sealed local state and any in-progress creator pin
    collect undelivered intra-U tickets and unconsumed seeds/init work
    remove pending outward packets whose receivers are now inside U
    retain their unconsumed observations as U inbox work
    retain already consumed observation IDs; do not enqueue them again
    continue U using A07 after all current frames reach their local boundary
mark all affected containing pending units as depending on U
```

Unit merges are monotonic inside an attempt; at most the finite number of member unions can occur. A split changes actual edges/identities but not the current execution-unit union. At the next input start there is no sticky grouping from the previous attempt.

Previously sealed source turns remain valid completed turns. A merge does not replay their operation or undo past local observation. It changes which further work is internal before the unit may expose its **final** result outside. If a receiving member already ran in this attempt, new eligible incoming work creates a new reaction turn with no repeated external seed; its accumulated output retains the prior turn order.

A unit may not seal outward while it has a pending dependency that can still supply required work. A whole-root result waits for all required units even if a chunk finished earlier. This is why arbitrary database task completion is not the chunk-ready predicate.

### A10. Atomic failure and finalization

Keep the original input snapshot immutable. APPLIED alone authorizes publication of the full attempt result. Any invalid request, patch, received completion, identity, protected state, callback or final containing constraint rolls back every tentative frame/completion/marker/output in the attempt. Deterministic gas exhaustion has its existing exact rollback and rejected-charge behavior. A physical resource/cancellation exception abandons the tentative attempt without constructing a canonical semantic failure.

For GAS_LIMIT_EXCEEDED preserve admitted rows and the first rejected charge, not speculative suffix work. For NEEDS_RESOURCES preserve the original state and the defined missing-resource disposition; do not invent a completed gas receipt or a successful prefix. A physical cancellation is not a fabricated protocol gas error. Propagate a typed incomplete/host condition through every callback, Language bridge, BEX boundary, chunk driver and receiving adapter; do not let a broad exception wrapper turn it into invalid evidence or invalid input. No terminal result, input-disposition or checkpoint is issued from the unfinished attempt.

Finalization uses only sealed owned states. Substitute current verified member-local edges, run the real Language cyclic-set finalizer, retain owning-set proofs, rebuild outside references dependency-first, validate every affected context, and write invocation revision/topology generation once. No finalizer invokes business update/event handlers. Root projection records only root-origin occurrences; other completions remain internal result evidence.

A source turn calculated earlier can remain retained as non-authoritative immutable evidence after a larger attempt fails; its mere existence does not change the returned original state or commit any effect. A separate earlier successful standalone call has its own atomic boundary and is not rolled back by an unrelated later call.

### A11. Chunked execution and the equivalence argument

The optional chunk driver is:

```text
begin(document, event, time) -> opaque Attempt
next_chunk(Attempt) -> verified ChunkToken | no-more-work
execute_chunk(ChunkToken) -> sealed candidate completion
accept_chunk(Attempt, ChunkToken, completion) -> updated private Attempt
finish(Attempt) -> the same public Outcome as PROCESS
```

This is not a second public event format. `next_chunk` chooses exactly the ready unit/turn/round prescribed above; it supplies frozen local seeds and dependency views, not a caller-selected external delivery list. `accept_chunk` checks the one-use token, exact inputs, profile, result capability, occurrence lifetimes and logical work prefix. Duplicate acceptance cannot duplicate effects or charges. `finish` rejects unfinished attempts.

An acyclic subgraph may be calculated in a separate process and transported as exact completed data when all token bindings remain the same. Parent-independent semantic payloads are final state and own output. Binding metadata, initial exact view and metering evidence prevent stale/forged substitution. A root-level standalone Outcome is not accepted blindly as a local completion: its setup/root projection and snapshot-root commitments differ and must be normalized through the supported extraction/verification path.

**Induction for a static DAG:** leaves execute identical local turns; therefore their state/output pairs agree. Given identical completed dependencies, their container installs the same states, prequeues the same occurrences, executes the same BEX and handlers against the same views, and seals the same result. Induct to the root. Every logical charge is accepted in the same normal-form sequence, yielding identical successful and failing prefixes. There is no parent callback into an unfinished source frame, so an interleaving cannot invalidate the substitution.

**Cycles:** induct over A07 rounds instead of graph depth. Each round begins with the same component vector and inboxes, runs identical local turns and finalizes the same exact component. Stop or fail on the same boundary. The component, not an individual cyclic member, is the independently completed external chunk.

**Dynamic graphs:** chunk acceptance follows A08/A09. A join can invalidate a formerly independent cut. Preserve completed turns and promote the remaining work; never force a precomputed stale partition to finish as if topology had not changed. Equivalence covers identical execution of this state machine, not arbitrary regrouping that changes its semantic turns.

A native implementation can use a single heap, an explicit continuation object, serialization between chunks, or verified computation reuse. It must have no visibility into another member's unsealed frame and must preserve the logical trace. Parallel wall-clock completion order is ignored.

### A12. Helper contracts and integration

| Helper operation | Required meaning |
|---|---|
| `reference/channels.py` | Retain recognition, exact-input precondition, actual checkpoint freshness, union membership and lifetime signatures. Build seeds once from input state; route no completed child as external input. |
| `reference/registry.py`, `catalogue.py` | Retain 31 type shapes, roles, closed headers, step discovery and actual-value filters. Bind regenerated definitions to completion-1. |
| `reference/language.py` | Retain exact reads/writes, identity, admission, reference and cyclic proofs. Supply pinned frames/dependencies; never latest-state aliases. |
| `reference/policy.py`, `generalization.py` | Retain policy matching/floor/nearest-valid search. Apply to owned local patches only; receiving validation is not automatic generalization. |
| `reference/runtime.py` | Retain deterministic role registration and sealed ledger contract. Restrict contexts to local frames/completed dependencies and route outputs through A05. |
| `reference/work.py` | Retain low-level charge formulas and stable sort. Split logical proof inventories from physical caches and attach their exact prefix to chunk tokens. |
| `reference/model.py` | Retain tokens, safe integers, pointers, charge/rejection and public Outcome shape. Add private completions/frames and version commitment domains. |
| `reference/processor.py` | Replace global queue, cross-boundary updates, lifecycle/seed loop and final-only checkpoints with A01–A11. Retain actual handler/step execution inside the local kernel. |
| `reference/graph.py` | Replace eager cross-frame propagation during patches with local reconciliation and sealed finalization. Preserve true cyclic identities, explicit bindings and retirement; fix active-count accounting. |
| `reference/storage.py` | Rebind snapshot/receipt/invocation formats and compare the new canonical observations. Never claim the old digest/release certifies new records. |

The helper reference defines primitive operations; it does not license old scheduling side effects. All helper accesses go through the frame/sealed boundary. The primary runtime migration is a structural refactor, not deleting one call to `graph.routes` while leaving a shared mutable graph visible through readers.

### A13. Gas-only protocol bound and interruption discipline

This is an integration rule for A00–A12, not a second document-processing algorithm.

```text
for the next prescribed logical work item:
    derive its counter and units from exact inputs and the specified logical inventory
    debit the unchanged shared/member meter before the corresponding charged action
    if the meter rejects:
        retain the admitted prefix and exact rejected charge
        roll back the whole selected attempt using existing GAS_LIMIT_EXCEEDED rules
    perform the work without a second universal size/depth/cardinality guard

on physical resource interruption before completion:
    do not create a canonical Outcome or charge a synthetic gas suffix
    unwind/discard mutable frames and any unpublished candidate
    retain only host diagnostics and the original pending obligation
    if a publication was attempted and may have committed, reconcile first
```

Logical-work inventory is not physical cache inventory. Keep the old meter for work whose charge is already specified; optional cached results must produce the same successful/rejected prefix as uncached execution. Any uncovered input-dependent primitive needs an explicitly specified metering correction before final conformance is claimed, not an arbitrary size ceiling or a hardware-dependent tariff. Work done by a standalone Language authoring call or provider prefix acquisition is not silently put into an unrelated Contracts invocation's 100,000 ledger.

<a id="metering"></a>
## Appendix B. Logical metering and schedule

### Common ledger

There is one shared live ledger for the entire `process` or `initialize` attempt, maximum/default 100000, plus optional member-local ceilings. Charge before work. Retain the defined owner field, admitted prefix, first rejected charge, tie-break, domain-integer checks and extension namespace rules in `reference/model.py` and `reference/runtime.py`.

Failed state rolls back, not admitted work. NEEDS_RESOURCES has an incompatible's no-completed-ledger disposition. Physical queue storage, network transfer, cache hits and task IDs are not tariffs. Logical input facts and validation proofs are distinct from physical caches.

### Counter placement

| Counters | Exact placement in the new machine |
|---|---|
| `processInvocation`, `closureInvocation` | Once each at A01 entry, ownerless; not once per chunk or component. |
| `scopeOpened`, `managedDocumentOpened` | Once per active member first opened by this attempt; retain the defined opened-set rule. |
| `contractHeaderRecognized`, `objectMemberRead`, `typeEdgeFollowed` | At complete required header discovery; dedupe by the same exact member/header key, not physical cache. |
| `deliverySnapshotEntry`, channel candidate/acceptance/checkpoint counters | At frozen external selection and exact freshness/precondition work in retained channels helpers. |
| `localTurnOpened` = 2 | Before starting each actual local turn, owner = its member. No charge for carrying a wholly untouched node. |
| `localTurnSealed` = 2 | After its final local validation and marker work, immediately before sealing that turn, owner = its member. No successful seal charge for failed turns. |
| `completionBatchInstalled` = 2 | Once per source batch installed in a receiving turn, including an empty-event state-changing batch; owner = receiver. Several paths to that source batch do not multiply this counter. |
| `completionRouteChecked` = 1 | Per occurrence ticket checked at installation, before each pending embedded occurrence, and before each resumed embedded handler/step; owner = receiver. Retired tickets still cost their check. |
| `componentRoundOpened` = 2 | At the beginning of every nonempty-work cyclic round, ownerless. No final empty polling round. |
| `patchBoundaryChecked`, `pointerSegmentTraversed`, patch add/remove | Retain the defined normalized pointer and per-patch charging in A06. Automatic completed-reference installation is not charged as a business patch. |
| `documentUpdateDelivered` | Per actual local Document Update channel dispatch only. There are no deep parent-update delivery charges. |
| `internalEventEnqueued`, `internalEventDequeued` | At own emission and LOCAL FIFO removal, respectively. Each locally emitted occurrence incurs these once; incoming EMBEDDED rows use completion/delivery counters instead. |
| `triggeredEventDelivered`, `embeddedEventDelivered`, `lifecycleDelivered` | Per actual dispatched matching channel, using the defined `work_record` counter placement. |
| `closureWorkOccurrenceEnqueued`, `closureWorkOccurrenceDequeued` | Once each per actual channel work record. Retain channel/handler candidate and call counters at discovery/dispatch. |
| `rootEventRecorded` | Once per selected-root own occurrence at final successful root projection. Never for a child merely because its output packet is stored. |
| `processorMarkerWritten`, `checkpointWritten` | At actual changed marker/eligible checkpoint write at the corresponding member seal. No artificial writes per receiving child event. |
| `terminationRequested`, `scopeInitialization` | At their once-per-activation lifecycle entry, retaining defined repeated-request suppression. |
| `processEmbeddedEdgeExamined`, `closureExpanded` | At changed edge reconciliation and newly active member introduction, respectively; keep defined source ownership. |
| `managedOccurrenceBindingVerified` | At first exact binding verification per occurrence within the attempt. |
| `componentMemberPartitioned`, `componentEdgePartitioned`, `componentPartitionChanged` | When A02/A09 establishes a new actual partition, use defined per-member/per-edge quantities and the explicit changed-partition test. Logical graph edges, not an all-history inventory. |
| `containingReferenceUpdated` | Per changed live exact attachment reference at sealed incorporation/finalization, owner = containing member. Deduplicate the identical update within that boundary. No charge for an unchanged exact reference. |
| `tentativeComponentFinalization`, `cyclicMemberFinalized` | For each required changed Language cyclic-set finalization at a sealed round/unit/final boundary. Acyclic finalization does not receive the cyclic counters. A final already exact unchanged set is not refinalized/charged again. |
| Low-level identity, list-fold, comparison, schema, validation, sort counters | Retain exact quantities in `LogicalWork`/generalization helpers. Execute those logical calls against the specified local or sealed view, never against a prematurely refreshed ancestor. |

For new-child initialization, source initialization work belongs to the child; receiver batch/incorporation/update work belongs to the creator. A cyclic round has ownerless round/whole-component overhead and member-owned local work. Distinct parent receiving work is not charged to the source.

### Normal form and cached completions

The reference logical order is A01 setup, initialization units, input units, member/round order, and final projection. Every local work segment has relative ordinals, stable owner keys and an input logical-proof prefix. On chunk acceptance, validate and append that same segment in the canonical order; physical completion order is irrelevant.

A cached segment with a different logical proof inventory, dependency context, profile, seed selection or budget-prefix semantics cannot be copied unchanged. Re-execute the local kernel or derive/verify its exact normal-form work through the implementation's supported equivalent path. It is never sufficient to set gas to the cache lookup cost. A previously admitted segment cannot merge twice for the same logical chunk; distinct receiving occurrences still have their own application costs.

Retain the defined rejected-charge behavior: stop before the first work item that exceeds shared or owner-local remaining gas, return its exact rejected charge, and expose no state/output. Speculative work beyond that point is physical diagnostic work only. Do not execute an unbounded speculative callback merely to discover a ledger. It must follow the declared live or verifiable work-ledger contract; the 100,000 shared ceiling is not reset for it. Physical interruption abandons speculation and is not a semantic rejection.

Consequently:

```text
gas(rooted attempt) = gas(chunked execution of that attempt)
```

but not necessarily:

```text
gas(standalone B call) + gas(standalone A call)
```

The latter contains repeated top-level setup/root projection and can be a different declared atomic context. Use the shared attempt driver for exact total/rejected-prefix comparisons.

### Required gas qualification

Run direct/chunk differential cases at ample gas, exact-success allowance, one unit below it, and restrictive member-local ceilings. Compare ordered rows, admitted total, first rejection, owner attribution, state and public output. Include zero-event state propagation, duplicate paths, cold storage, callbacks, cyclic rounds, initialization, late failure and a retired receipt. Generated runtime totals must come from that implemented profile; none are supplied as invented golden numbers here.

### No unrelated protocol ceilings

The structural `limits` entries are removed from the current manifest. Preserve `sharedMaximum: 100000`, all existing numerical weights, the default maximum, legitimate smaller bound budgets and member ceilings. Keep caches and I/O pages bounded independently: their size changes neither legal content nor completed logical gas.

A valid computation may exceed an old document, step, depth or numeric-text limit while remaining within gas. It must not hit that obsolete semantic guard. A computation whose prescribed logical work exceeds 100,000 still fails at the real first unaffordable charge. Neither a bigger machine nor more chunks changes that boundary.

A host unable to calculate or retain a valid under-budget outcome has not established a gas failure. Report incompleteness/operational fault, preserve pending input and stable state, and retry only with valid captured semantics. Do not publish a completed ledger assembled from a partial trace or estimate missing work using CPU time.

### Metering conformance

Meter every operation before performing its charged work. Existing graph/header, turn/round, effect, path, schema/validation, text, Integer-limb and identity counters already cover substantial work. Check their actual placement: post-hoc measurements do not necessarily prevent the expensive work before its rejection. In particular review BEX Integer conversion/arithmetic, collection copying/construction, `estimated_size`, comparison scans, validation, exact hashing and graph preflight. Conformance evidence MUST identify counter coverage and the position of every required charge. Do not invent a new public profile/limit document to hide this obligation.

### Resource-proportional charging

The standard/default maximum remains 100000. Structural `limits` is empty.
BEX adds the unit-weight counters `integerWork`, `textWork`, `valueMember`, with
quantities and debit ordering defined in its resource-revision section. The same
Contracts meter and current owner receive those debits; no nested budget resets.

`textBlockExamined` now debits one block for each operand before comparing that
at-most-64-code-point block, stopping at the first different block. The prior
implementation scanned the matching prefix before charging; the new rejection
prefix is intentional. Identity lookup is protected by the prerequisite debits defined below. The original child work, text construction and established-identity accounting retains its logical reuse rules. `objectMemberRebuilt` precedes helper construction; `directIdentityHashBlock` precedes the final serialization/hash. Canonical helper size is computed
from bounded fragments after their text/member accounting, before hashing.
Previously established exact identities keep the same invocation-local reuse rule.

Gas quantity and amount arithmetic uses unbounded nonnegative Integers. This
changes internal receipt number encoding only beyond the former safe-integer
quantity range; it does not widen Timeline timestamps or any authored domain.
Operational inability has no canonical completed receipt or terminal disposition.

### Canonical identity prerequisites

The finite exact-value walk uses the stopping
at Ref boundaries made storage projection change the tariff. Use the direct
logical Merkle manifest and the invocation's bound identity evidence instead.
The Language identity algorithm is unchanged.

At an `establish` entry, obtain the direct exact manifest (a Ref is opened through
the verified Language interface; an owning-set cyclic Ref or Local is already an
exact token). Debit `identityInputMember` by its field count before enumerating
fields. In Language field order, debit `identityInputTextBlock` by
ceil(codePointCount/64) for each key, then the same quantity for a direct Text
literal or mergePolicy Text. For an items tuple debit `identityInputMember` by
its item count before examining items. Both counters have weight 1 and the
current Contracts member owns the charge. Child identities are tokens in this
manifest, regardless of whether their verified bodies are inline. This root
prerequisite remains payable even when the subsequent delta is empty.

Identity construction follows the exact-ID delta against the supplied previous
subject. An unchanged child, a previously established identity in this invocation,
a core identity, a carried admitted root/original event, or an exactly installed
standard type/specification identity needs no descendant reconstruction. The
installed-definition inventory is bound in the logical-prefix commitment and
MUST NOT be used as completed-value validation evidence. Arbitrary resolver or
physical-cache contents are not reusable logical evidence. Ordinary and cyclic
(token plus component scope) establishment keys remain separate.

For any other new/changed descendant, use its direct verified manifest even when
it is a Ref, pay the same direct prerequisite before processing that manifest,
and perform the existing recursive identity-construction accounting. Thus a new
reference does not erase required construction work. Previously proved exact identities are reusable within the invocation; an unknown
candidate must first establish its identity by the prepaid procedure below. The
reuse inventory is independent of cache warmth. Preserve the existing pure-list prefix/fold rules, Text construction,
node establishment, object-member rebuild and direct hash-block quantities.
`objectMemberRebuilt` precedes helper construction; count canonical UTF-8 helper
size without allocating its serialization, then debit `directIdentityHashBlock`
before that serialization/hash. Contextual validation keeps its separately bound
subject, goal, requirements and coverage obligations.

Exact-input verification/identity evidence comes from Language admission and
verified exact opening; it is not inferred from presence in a physical cache.
An unavailable or invalid required manifest remains a resource/evidence failure.
Do not open an unchanged referenced child or an unselected body simply to imitate
an inline traversal. Physical recomputation of already established Language facts
is not another semantic construction debit. New candidate direct-manifest work
is paid before the corresponding inspection; no whole-tree prerequisite walk or
post-hoc total adjustment is permitted.

For a direct manifest with one `value` field containing 65 ASCII characters,
the entry prerequisite is 1 member and 3 text blocks (key plus two value blocks).
The first unaffordable charge is rejected before its action, under the unchanged
shared/member cap precedence. These quantities are deliberate tariff corrections,
not new document-size, recursion-depth or elapsed-time limits.


### Guarded identity construction and runtime normalization

A sealed dependency installation or graph-finalization pass reads each source
document's existing body and collects its disjoint containing-reference changes.
Debit `containingReferenceUpdated` once per changed occurrence in the prescribed
edge order. Apply those replacements together and establish the resulting
candidate once, before retaining, hashing or exposing it. No partial dependency
inventory is observable and its intermediate identities are not constructed.
This rule does not batch authored patches, event reactions or checkpoint writes.

This section corrects the implementation order of the preceding rules. It is
normative for all runtime-produced values, patches, processor markers, emitted
records, generated type changes and changed containing references. Compilation,
external exact admission and verified acquisition remain outside execution;
normalizing a new execution result is **not** external admission.

`establish` pays the direct root prerequisites described above. For each direct
Integer literal it additionally pays `integerLimbOperation=limbs^2`, with
`limbs=max(1,ceil(bitLength(abs(value))/32))`, before decimal helper sizing.
Reuse an identity without visiting its descendants only when it is bound by
verified admission/opening, a successfully established construction, or a
protected completed-result transfer. Physical cache membership and an arbitrary
authored ID are insufficient. An admitted parent's children inherit identity
witnesses on opening its direct manifest; these are not value-validation proofs.
Copying a protected completed result preserves that witness through its sealed
exact identity. Weak native handles are just indexes to that evidence.

For an **unknown** candidate, never call Language identity, use it as an
identity-cache key, or recursively search for cyclic locals before the guards.
Visit its fields in Language canonical field order, paying each new descendant's
direct prerequisite before its work. Propagate a cyclic-local flag from this
paid traversal; do not perform a separate free scan. Literal Text construction
retains its existing changed-value block debit. Recursively establish child IDs
before constructing a parent helper. Build that helper from literals and child
**tokens**, never by recursively hashing the original candidate. Admit
`nodeIdentityEstablished`, then for a non-pure-list node `objectMemberRebuilt`
by the direct field count, and `directIdentityHashBlock=ceil((canonicalUTF8Size+9)/64)`
before serialization and hashing. Helper size scanning is covered by the prepaid
literal/key blocks; the scanner does not allocate the whole serialized Text.
Do not publish the establishment inventory entry if any guard or host operation
fails. A repeated unknown occurrence still executes this procedure; it cannot
reuse a proof solely because the host reused a Python object.

A pure list starts with the fixed empty-list identity. Establish each item token
before comparing it with the corresponding **verified previous** item token.
An unchanged verified prefix may reuse its fold; after the first different or
appended item, admit one `listFoldStepRecomputed` before each append hash. The
logical node-establishment charge follows the items. A non-pure-list `items`
field uses a pure-list child helper. `mergePolicy` uses its Text-node helper.
These are the existing Language helper/fold algorithms, not a new identity.
Local edges use the supplied token function. Ordinary and cyclic entries are
separate; a cyclic entry binds component members and their sealed before IDs.
All member `cyclicMemberFinalized` charges are admitted in component order before
the actual Language component finalization begins.

Runtime normalization is bottom-up and deterministic. Each value occurrence pays
`identityInputMember=1` before inspection. Native or host object normalization pays
`identityInputMember=n` before enumerating its direct keys, then
`identityInputMember=n*r` and
`identityInputTextBlock=(r+1)*sum(ceil(keyCodePoints/64))` before Language UTF-16
key ordering (`r=ceil(log2(n))`, zero for empty objects). Read values in that
order. Literal/Text inputs pay `identityInputTextBlock=ceil(codePoints/64)` before
Unicode checking, encoding or conversion; Integers pay the limb-square debit
before decimal conversion. Lists and explicit `items` tuples pay
`identityInputMember=itemCount` before child traversal, then normalize each
occurrence in index order. Omitted Undefined and null fields retain their
existing absence rules. Runtime type aliases remain rejected.

Already exact operands retain their reference boundaries. For newly normalized
nodes, the Language remember callback first invokes prepaid establishment;
only then may it retain/hash the node or convert it into a type-position token.
Value certification keeps the separately metered contextual validation path.
No full free recursive prewalk, serialization or materialization is permitted.
Normalization and later changed-ancestor establishment are distinct operations,
so their explicit prerequisites remain payable at each prescribed call site.
All charges belong to the current Contracts member and use the same live ledger,
first rejection and rollback rules. An interruption is HostIncomplete, never a
completed identity or validation certificate. A rejection cannot perform the
operation it failed to pay for, even when that operation would have been followed
by rollback.


### Canonical exact-value transfers

A BEX ExactObject/ExactList is a captured Language recipe with its resolver
and, during execution, this invocation's logical ledger. Access has already
opened its contributing manifests under the ordinary read charges. Admission,
verified opening or successfully prepaid construction supplies identity evidence,
not a physical cache hit. For one exact contribution, use its established ID.
The accounting form is the one-field object `{blueId: ID}`; apply the BEX
ordered finite-sizing algorithm to that form. A plain 44-character ID costs
60 in an append sizing call: base 5, size fragments 1+6+44, valueMember 1+0,
and textWork 1+1+1. A cyclic member token uses its actual full identity length.
Do not traverse or serialize the materialized body to determine that size.

For multiple contributing parts, first refine them in Language's existing
ordered exact-recipe algorithm. Its normalization remember callback invokes
prepaid establishment before retaining or hashing every synthesized node.
Only complete node bodies may populate the body's identity index; references
retain their verified provider target. Remember the successfully composed result
in an invocation-local inventory keyed by the ordered exact part identities
and contextual requirement identities (the Language recipe key). This inventory
carries the established identity alongside its immutable body, including through
continuation copies. Bind the recipe key and established identity into the
protected logical-prefix commitment. Rebind that construction witness after
transport; a changed native handle must not trigger new construction charges.
This is logical evidence, not resolver cache state.
Repeating that recipe reuses its established result; failed/interrupted
composition adds no entry. Its identity does not incorporate effective fields
that the exact recipe never contributed.

The effect base is admitted before requesting this accounting form. Required
composition/identity work occurs next, on the same owner and shared/member-local
ledger, before token sizing. All ordinary fragment, key-order, text and rejection
rules then apply. Native new containers continue to pay normalization and
construction; nested established children use the same transfer token. Newly
constructed native BEX data cannot claim that token before establishment.
Demanded reads, transformations, effects, certification, checkpoints and
publication retain their independent tariffs and order.

This rule applies uniformly to singular/plural append operators, step/binding
values, result overlays and effect snapshots. The emitted/copied exact value
remains the captured value, with necessary provider content and cyclic proofs
retained for cold restoration. Destination-context constraints must still be
validated. Arbitrary authored blueId syntax and generic HostValue implementations
do not confer the Contracts evidence capability.

### Selected descendant evidence

Opening a witnessed exact manifest propagates evidence to its immediate complete
children. Effective Language head/child selection can return equivalent instances
from a captured resolution plan. When every parent contribution has established
identity evidence and Language resolution succeeds, derive that same evidence for
the selected child's exact contributions. No new logical construction charge is
introduced by a changed handle or reference cut. No unrelated child traversal is
required. Metadata literals and a bare items slot cannot receive this capability.

Known exact identity and the invocation's established-construction inventory are
distinct: identity provenance allows a canonical transfer token but does not erase
normalization prerequisites, first-use logical establishment or target validation.
A multi-contribution exact result is still synthesized using the exact-transfer accounting prepaid
path, rather than assigning an existing child's ID to its effective projection.
After successful ordinary postorder establishment, retain its exact identity
witness. An interrupted/rejected hash cannot issue that witness; a token-context
cyclic identity remains scoped to its cyclic construction proof.

Native continuation copies rederive selected contribution evidence from the bound
parent/recipe; successfully composed results additionally retain the existing
recipe-key/established-ID inventory. Portable continuations verify execution by
replay. Neither a resolver cache nor native handle survival changes the ledger.
The canonical 44-character transfer sizing vector remains 60 gas; this specification
removes accidental duplicate establishment, not actual reads or new construction.

### Exact counter schedule

```json
{
  "profile": "contracts-deterministic-gas-4",
  "status": "Fourth corrective edition: representation-independent selected-descendant identity evidence and exact-value transfers; retains occurrence-based comparison, prepaid construction and shared maximum 100000.",
  "sharedMaximum": 100000,
  "weights": {
    "processInvocation": 20,
    "deliverySnapshotEntry": 1,
    "scopeOpened": 5,
    "contractHeaderRecognized": 1,
    "channelCandidateTested": 1,
    "channelAccepted": 1,
    "handlerCandidateTested": 1,
    "handlerCall": 5,
    "scopeInitialization": 2,
    "embeddedPathEntryRead": 1,
    "embeddedPathSegmentValidated": 1,
    "pointerSegmentTraversed": 1,
    "patchBoundaryChecked": 1,
    "patchAddOrReplace": 5,
    "patchRemove": 5,
    "documentUpdateDelivered": 2,
    "internalEventEnqueued": 2,
    "internalEventDequeued": 2,
    "triggeredEventDelivered": 2,
    "embeddedEventDelivered": 2,
    "rootEventRecorded": 2,
    "lifecycleDelivered": 2,
    "checkpointCompared": 1,
    "checkpointWritten": 2,
    "processorMarkerWritten": 2,
    "terminationRequested": 2,
    "closureInvocation": 100,
    "managedDocumentOpened": 10,
    "managedOccurrenceBindingVerified": 5,
    "processEmbeddedEdgeExamined": 2,
    "componentMemberPartitioned": 2,
    "componentEdgePartitioned": 1,
    "closureWorkOccurrenceEnqueued": 5,
    "closureWorkOccurrenceDequeued": 5,
    "closureExpanded": 20,
    "componentPartitionChanged": 20,
    "tentativeComponentFinalization": 20,
    "cyclicMemberFinalized": 10,
    "containingReferenceUpdated": 10,
    "nodeManifestOpened": 1,
    "objectMemberRead": 1,
    "listItemRead": 1,
    "textBlockExamined": 1,
    "textBlockConstructed": 1,
    "scalarComparison": 1,
    "integerLimbOperation": 1,
    "sortComparison": 1,
    "typeEdgeFollowed": 1,
    "schemaPredicateEvaluated": 1,
    "validationMemberExamined": 1,
    "validationProofReused": 1,
    "subtypeCandidateTested": 5,
    "nodeIdentityEstablished": 1,
    "objectMemberRebuilt": 1,
    "listFoldStepRecomputed": 1,
    "directIdentityHashBlock": 1,
    "localTurnOpened": 2,
    "localTurnSealed": 2,
    "completionBatchInstalled": 2,
    "completionRouteChecked": 1,
    "componentRoundOpened": 2,
    "identityInputMember": 1,
    "identityInputTextBlock": 1
  },
  "limits": {}
}
```

<a id="algorithms"></a>
## Appendix C. Complete executable algorithms

The following module blocks define this edition's reference procedures. File names identify modules within the abstract reference system; they are not external normative downloads. The selected Language and BEX operations have the exact bindings in §2. The host-value module is included where used.

### `src/blue_contracts/reference/__init__.py`

```python
"""Selected document-local completion Contracts implementation."""
from .processor import Processor
from .chunks import Attempt, ChunkToken, ChunkResult
from .receiving import SourceCompletion
from .runtime import RuntimeBinding, RuntimeContext, ExternalChannelContext
from .graph import Link
from .model import ContractError, NeedResources, Snapshot, Outcome, DEFAULT_LIMIT
from .storage import Journal, export_snapshot, import_snapshot, compare_replay, export_invocation, import_invocation
__all__ = ['Processor','Attempt','ChunkToken','ChunkResult','SourceCompletion','RuntimeBinding','RuntimeContext','ExternalChannelContext','Link','ContractError','NeedResources','Snapshot','Outcome','DEFAULT_LIMIT','Journal','export_snapshot','import_snapshot','compare_replay','export_invocation','import_invocation']
```

### `src/blue_contracts/reference/catalogue.py`

```python
"""Parameterized publication recipes; no invented or reused immutable IDs.

The caller supplies the actual Language definition-admission operation and the
exact BlueId of this revision's complete specification Text. Returned IDs must
come from that operation, not a structural-hash-only fallback.
"""
from typing import Callable, Mapping

PARENTS = {
    'Contract': None,
    'Marker': 'Contract',
    'Channel': 'Contract',
    'Handler': 'Contract',
    'Operation': 'Handler',
    'External Channel': 'Channel',
    'Composite External Channels': 'Channel',
    'All External Channels': 'Channel',
    'Triggered Event Channel': 'Channel',
    'Embedded Node Channel': 'Channel',
    'Document Update Channel': 'Channel',
    'Lifecycle Event Channel': 'Channel',
    'Sequential Workflow': 'Handler',
    'Sequential Workflow Operation': 'Operation',
    'Compute': 'Contract',
    'Compute Definition': 'Marker',
    'Update Document': 'Contract',
    'Trigger Event': 'Contract',
    'Terminate Processing': 'Contract',
    'Process Embedded': 'Marker',
    'Processing Initialized Marker': 'Marker',
    'Processing Terminated Marker': 'Marker',
    'Channel Event Checkpoint': 'Marker',
    'Operation Request': None,
    'Document Processing Initiated': None,
    'Document Processing Terminated': None,
    'Document Update': None,
    'Embedded Event Delivery': None,
    'Json Patch Entry': None,
    'Contract Execution Result': None,
    'Type Generalization Rule': None,
    'Type Generalization Policy': 'Marker',
}


def publish_catalogue(admit_definition: Callable[[dict], str], specification_id: str,
                      core_ids: Mapping[str,str]) -> dict[str,str]:
    if not specification_id:
        raise ValueError('SPECIFICATION_ID_REQUIRED')
    for name in ('Text','Integer','Boolean','List','Dictionary'):
        if not core_ids.get(name):raise ValueError('MISSING_CORE_TYPE:'+name)
    result: dict[str,str] = {}
    def field(name):return {'type':{'blueId':core_ids[name]}}
    # An unrestricted runtime operand has no Language declaration constraint.
    # A description-only child would become an inherited contribution and
    # change exact source/event/program identities. The closed field rules in
    # the specification and runtime validators own these slot requirements.
    def any_value(description):return None
    def seq(item=None):
        value=field('List')
        if item is not None:value['itemType']={'blueId':result[item]}
        return value
    for name,parent in PARENTS.items():
        body={'name':name,'specification':{'blueId':specification_id}}
        if parent is not None:body['type']={'blueId':result[parent]}
        if name=='Contract':body['order']=field('Integer')
        elif name in ('Handler','Operation'):body['channel']=field('Text')
        elif name=='External Channel':body['event']=any_value('Optional actual-original-event filter.')
        elif name=='Composite External Channels':body['channels']=seq()
        elif name in ('Triggered Event Channel','Lifecycle Event Channel'):body['event']=any_value('Optional Language event definition.')
        elif name=='Embedded Node Channel':body.update(sourcePath=field('Text'),event=any_value('Optional event definition.'))
        elif name=='Document Update Channel':body.update(path=field('Text'),event=any_value('Optional event definition.'))
        elif name=='Sequential Workflow':body.update(steps=seq(),event=any_value('Optional event definition.'))
        elif name=='Sequential Workflow Operation':body.update(steps=seq(),request=any_value('Optional request definition, including unvalued typed definitions.'))
        elif name=='Compute':
            for key in ('expr','do','constants','functions','entry','definition'):body[key]=any_value('BEX program slot; executable validation occurs at demand.')
        elif name=='Compute Definition':
            for key in ('constants','functions'):body[key]=any_value('Reusable BEX declaration.')
        elif name=='Update Document':body['changeset']=any_value('Required effect-free BEX changeset expression.')
        elif name=='Trigger Event':body['event']=any_value('Required BEX event expression; empty objects are present values.')
        elif name in ('Terminate Processing','Processing Terminated Marker','Document Processing Terminated'):body.update(cause=field('Text'),reason=field('Text'))
        elif name=='Process Embedded':body.update(paths=seq(),collectionPaths=seq())
        elif name in ('Processing Initialized Marker','Document Processing Initiated'):body['document']=any_value('Exact pre-initialization document.')
        elif name=='Channel Event Checkpoint':
            entries=field('Dictionary');entries['valueType']={'timestamp':field('Integer'),'event':any_value('Pure reference to the original external event.')};body['entries']=entries
        elif name=='Operation Request':body.update(operation=field('Text'),channel=field('Text'),document=any_value('Optional exact document precondition.'),requireExactDocumentVersion=field('Boolean'),request=any_value('Optional exact request value.'))
        elif name=='Document Update':body.update(op=field('Text'),path=field('Text'),beforePresent=field('Boolean'),afterPresent=field('Boolean'),before=any_value('Exact before value when present.'),after=any_value('Exact after value when present.'))
        elif name=='Embedded Event Delivery':body.update(sourcePath=field('Text'),event=any_value('Exact immutable nested event.'))
        elif name=='Json Patch Entry':body.update(op=field('Text'),path=field('Text'),val=any_value('Required for add/replace, forbidden for remove.'))
        elif name=='Contract Execution Result':body.update(patches=seq('Json Patch Entry'),events=seq(),termination=any_value('Optional graceful termination.'),runtimeLedger=any_value('Optional bounded child ledger, only without live debit.'))
        elif name=='Type Generalization Rule':body.update(path=field('Text'),mode=field('Text'),mustRemainSubtypeOf=any_value('Optional exact ancestor-floor type.'))
        elif name=='Type Generalization Policy':body.update(defaultMode=field('Text'),rules=seq('Type Generalization Rule'))
        if name=='Channel Event Checkpoint':
            body['entries']['valueType']={k:v for k,v in body['entries']['valueType'].items() if v is not None}
        body={k:v for k,v in body.items() if v is not None}
        value=admit_definition(body)
        if not isinstance(value,str) or not value:raise ValueError('ADMISSION_DID_NOT_RETURN_BLUEID')
        result[name]=value
    return result
```

### `src/blue_contracts/reference/channels.py`

```python
"""Whole-event recognition, deterministic channel acceptance and local checkpoints.

There is no transport, permission, source-order or external-delivery protocol in
this module. Seeds are private frozen work records, never processor arguments.
"""
from dataclasses import dataclass
from algorithms import blue as L
from .model import ChannelLife, ContractError, require, token, digest, integer
from .registry import EXTERNAL

PRIMITIVE = {'external', 'extension_external'}
REQUEST_FIELDS = {'operation', 'channel', 'document', 'requireExactDocumentVersion', 'request'}

@dataclass(frozen=True)
class Seed:
    document: str
    channel: str
    generation: int
    operation: str | None = None


def leaves(cs, key, active=()):
    require(key in cs and cs[key]['_role'] in EXTERNAL, 'INVALID_COMPOSITE_MEMBER', key=key)
    require(key not in active, 'CYCLIC_CHANNEL_COMPOSITION')
    role = cs[key]['_role']
    if role in PRIMITIVE:
        return (key,)
    members = (sorted(k for k, c in cs.items() if c['_role'] in PRIMITIVE)
               if role == 'all' else cs[key].get('channels', []))
    require(type(members) is list and all(type(k) is str for k in members), 'INVALID_COMPOSITE_MEMBERS')
    require(len(members) == len(set(members)), 'DUPLICATE_COMPOSITE_MEMBER')
    return tuple(sorted({leaf for member in members for leaf in leaves(cs, member, active + (key,))}))


def signature(cs, key):
    declaration = cs[key]
    role = declaration['_role']
    record = {'type': declaration['type']['blueId'], 'leaves': list(leaves(cs, key))}
    if role == 'external':
        if 'event' in declaration:
            record['event'] = declaration['event']
    elif role == 'extension_external':
        runtime = declaration['_extension']
        record['runtime'] = runtime.binding.wire()
        record['header'] = {k: declaration[k] for k in runtime.binding.header_fields if k in declaration}
    else:
        # Membership AND the leaf acceptance semantics define a union lifetime.
        record['members'] = {k: signature(cs, k) for k in leaves(cs, key)}
    return digest('contracts.channel/completion-1', record)


def refresh_lifetimes(graph, birth=None, *, members=None):
    for member in sorted(graph.reachable(active=True) if members is None else members):
        doc = graph.state.documents[member]
        cs = graph.registry.contracts(doc.body)
        headers = {k: signature(cs, k) for k, c in cs.items() if c['_role'] in EXTERNAL}
        for key in sorted(set(doc.channel_lives) - set(headers)):
            del doc.channel_lives[key]
            graph.resets.add((member, key))
        for key, sig in sorted(headers.items()):
            old = doc.channel_lives.get(key)
            if old is None or old.signature != sig:
                generation = integer(doc.channel_serials.get(key, 0) + 1)
                doc.channel_serials[key] = generation
                doc.channel_lives[key] = ChannelLife(generation, sig)
                graph.resets.add((member, key))


def checkpoint(registry, doc, key):
    marker = registry.marker(doc.body, 'checkpoint')
    if marker is None:
        return None
    raw = registry.blue.literal(marker)
    require(type(raw) is dict and set(raw) <= {'type', 'entries'}, 'INVALID_CHECKPOINT')
    entries = raw.get('entries', {})
    require(type(entries) is dict, 'INVALID_CHECKPOINT')
    row = entries.get(key)
    if row is None:
        return None
    require(type(row) is dict and set(row) == {'timestamp', 'event'}, 'INVALID_CHECKPOINT')
    integer(row['timestamp'])
    require(type(row['event']) is dict and set(row['event']) == {'blueId'}, 'INVALID_CHECKPOINT')
    registry.blue.open(L.Ref(row['event']['blueId']))
    return row


def is_new(registry, doc, key, event_id, timestamp):
    """Only exact last-occurrence suppression; no invented external ordering."""
    previous = checkpoint(registry, doc, key)
    if previous is None or previous['event']['blueId'] != event_id:
        return True
    require(previous['timestamp'] == timestamp, 'EVENT_TIMESTAMP_CONFLICT')
    return False


def operation_request(registry, node):
    """Read a complete typed Operation Request; never synthesize missing fields."""
    if registry.role(node) != 'request':
        return None
    blue = registry.blue
    head = blue.head(node)
    require(head.items is None and head.value is L.ABSENT and head.contracts is None,
            'INVALID_OPERATION_REQUEST')
    require(set(head.fields) <= REQUEST_FIELDS | {'specification'}, 'INVALID_OPERATION_REQUEST')
    result = {'type': {'blueId': head.type_id}}
    for name in ('operation', 'channel', 'requireExactDocumentVersion'):
        child = blue.child(node, name)
        if child is not None and L.present_recipe(child, blue.context):
            result[name] = blue.project(child)
    result['operation'] = token(result.get('operation'))
    result['channel'] = token(result.get('channel'))
    exact = result.get('requireExactDocumentVersion', False)
    require(type(exact) is bool, 'INVALID_OPERATION_REQUEST')
    for name in ('document', 'request'):
        child = blue.child(node, name)
        if child is not None and L.present_recipe(child, blue.context):
            value = blue.exact(child)
            blue.certify(value)
            blue.remember(value)
            result[name] = {'blueId': blue.identity(value)}
    require(not exact or 'document' in result, 'INVALID_OPERATION_REQUEST')
    return result


def recognize_call(registry, event):
    """The only two recognition sites: event, otherwise event.operation."""
    if registry.role(event) == 'request':
        return event, operation_request(registry, event)
    candidate = registry.blue.child(event, 'operation')
    if candidate is not None and registry.role(candidate) == 'request':
        selected = registry.blue.exact(candidate)
        return selected, operation_request(registry, selected)
    return None, None


def event_observation(registry, event, *, logical=None):
    """Read the actual event, including outer and inherited fields."""
    return registry.blue.view(event, logical=logical)


def select_seeds(run):
    """Freeze dependency-first recipients and validate all named calls first."""
    graph, reg, blue = run.graph, run.reg, run.blue
    from .graph import components
    result = []
    for member in [k for group in components(graph.reachable(active=True), graph.state.edges.values()) for k in group]:
        doc = run.input.documents[member]
        cs = reg.contracts(doc.body)
        primitive = set()
        run.meter.owner = member
        ordered = run.ordered(cs)
        for key, channel in ordered:
            if channel['_role'] not in PRIMITIVE:
                continue
            run.meter.contracts('channelCandidateTested')
            if channel['_role'] == 'external':
                accepted = 'event' not in channel or blue.matches(run.event, channel['event'])
            else:
                accepted = channel['_extension'].accept_external(
                    channel, cs, reg, run.event, run.timestamp, checkpoint(reg, doc, key), run.meter, member,
                    document=doc.blue_id, channel=key, generation=doc.channel_lives[key].generation,
                    evidence=run.external_admissions.get(channel['_extension'].binding.type_id))
            if accepted:
                primitive.add(key)
        accepted = set(primitive)
        for key, channel in ordered:
            if channel['_role'] not in {'composite', 'all'}:
                continue
            run.meter.contracts('channelCandidateTested')
            if primitive.intersection(leaves(cs, key)):
                accepted.add(key)
        fresh = set()
        for key, channel in ordered:
            if key not in accepted:
                continue
            run.meter.contracts('channelAccepted')
            run.meter.contracts('checkpointCompared')
            if is_new(reg, doc, key, run.event_id, run.timestamp):
                fresh.add(key)
        if not fresh:
            continue
        target, operation = None, None
        if run.call_record is not None and primitive:
            request = run.call_record
            selected = request['channel']
            audience = [e['operationAudience'][member] for e in run.external_admissions.values()
                        if member in e.get('operationAudience', {})]
            addressed = 'document' in request
            # A trusted runtime can establish lineage membership. In generic
            # Contracts an explicit exact target names the selected member.
            in_audience = all(audience) if audience else (not addressed or
                request['document']['blueId'] == doc.blue_id or len(run.input.documents) == 1)
            candidate = in_audience and (addressed or selected in accepted and cs[selected]['_role'] in EXTERNAL)
            if candidate:
                target, operation = selected, request['operation']
                require(target in cs and target in accepted and cs[target]['_role'] in EXTERNAL,
                        'INVALID_TARGET_CHANNEL', document=member, channel=target)
            # A union that is newly observing an already-consumed call does not
            # repeat the operation, its precondition or its request validation.
            if candidate and target in fresh:
                require(operation in cs and cs[operation]['_role'] == 'operation'
                        and cs[operation]['channel'] == target,
                        'INVALID_TARGET_OPERATION', document=member, operation=operation)
                if request.get('requireExactDocumentVersion', False):
                    require(request['document']['blueId'] == doc.blue_id,
                            'STALE_DOCUMENT_PRECONDITION', document=member)
                if 'request' in cs[operation]:
                    require('request' in request and blue.matches(request['request'], cs[operation]['request']),
                            'INVALID_REQUEST', document=member, operation=operation)
        for key, channel in ordered:
            if key in fresh:
                result.append(Seed(member, key, doc.channel_lives[key].generation,
                                   operation if key == target else None))
                run.meter.contracts('deliverySnapshotEntry')
    run.meter.owner = ''
    return tuple(result)
```

### `src/blue_contracts/reference/chunks.py`

```python
"""Verified sequential chunks of the same atomic completion machine (A11).

Native candidates carry an issuer-held execution capability. At a data-only
boundary, acceptance verifies by deterministic re-execution under the bound
inputs, installed runtimes and gas prefix. A digest alone is never execution
proof. Physical verification work is not appended a second time to logical gas.
"""
from copy import copy, deepcopy
from dataclasses import asdict
from algorithms import blue as L
from .model import Outcome, Meter, require, closed, digest, canonical
from .completion import vector, committed
from .storage import export_snapshot, import_snapshot


def clone_run(run):
    require(run.frame is None and not run.suspended, 'OPEN_LOCAL_FRAME')
    result=copy(run)
    shared={'engine','blue','reg','input','graph'}
    for key,value in vars(run).items():
        if key not in shared:setattr(result,key,deepcopy(value))
    result.graph=copy(run.graph)
    for key,value in vars(run.graph).items():
        if key not in {'state','registry','blue','archive','meter','logical'}:
            setattr(result.graph,key,deepcopy(value))
    result.graph.state=result.state;result.graph.meter=result.meter;result.graph.changes=result.changes
    result.graph.logical=copy(run.graph.logical)
    for key,value in vars(run.graph.logical).items():
        if key not in {'blue','meter'}:setattr(result.graph.logical,key,deepcopy(value))
    result.graph.logical.meter=result.meter
    return result


class ChunkToken:
    """Opaque native capability. to_data() is the explicit portable boundary."""
    def __init__(self,attempt,descriptor):
        self._attempt=attempt
        self._descriptor=deepcopy(descriptor)
    @property
    def identity(self):return self._descriptor['identity']
    @property
    def descriptor(self):return deepcopy(self._descriptor)
    def to_data(self):
        attempt=self._attempt
        require(attempt._token is self, 'STALE_CHUNK_TOKEN')
        return {'format':'contracts.chunk-input/completion-1','token':self.descriptor,
                'input':attempt.input_data(), 'history':deepcopy(attempt._history)}


class ChunkResult:
    def __init__(self,wire):self._wire=deepcopy(wire)
    def to_data(self):return deepcopy(self._wire)


class Attempt:
    def __init__(self,run):
        self.run=run
        self.outcome=run.guard(run.begin_work)
        self._token=None
        self._candidates={}
        self._history=[]
        self._finished=False
        self._input_data=None

    def next_chunk(self):
        require(not self._finished, 'ATTEMPT_FINISHED')
        if self.outcome is not None:return None
        if self._token is not None:return self._token
        members=self.run.guard(self.run.ready)
        if isinstance(members,Outcome):self.outcome=members;return None
        if members is None:return None
        run=self.run;phase=run.phase
        record=committed('chunk',dict(attempt=run.invocation,unit=sorted(members),phase=phase.name,
            position=len(self._history),beforeViews=vector(run.state,members),
            dependencies=vector(run.state,{e.target for e in run.state.edges.values() if e.source in members}),
            pending={k:[dict(source=b.source,serial=b.serial,completion=b.completion,output=list(b.output),
                             tickets=[t.wire() for t in b.tickets],after=b.after,roundSeal=b.round_seal)
                        for b in phase.pending[k]] for k in sorted(members)},
            lifecycle={k:phase.initialization[k] for k in sorted(members) if k in phase.initialization},
            seeds={k:[asdict(s) for s in phase.seeds.get(k,[])] for k in sorted(members)},
            routes={k:[ticket.wire() for ticket in phase.initial_routes.get(k,run.capture_routes(k))] for k in sorted(members)},
            activations=dict(sorted(run.activation.items())),
            profile=run.meter.policy(),logicalPrefix=run.logical_commitment(),
            runtimeBindings=list(run.reg.runtime_bindings)))
        self._token=ChunkToken(self,record)
        return self._token

    def execute_chunk(self,token):
        require(token is self._token and token is not None, 'STALE_CHUNK_TOKEN')
        run=clone_run(self.run)
        unit=set(token._descriptor['unit'])
        outcome=run.guard(lambda:run.run_unit(run.phase,unit))
        wire=committed('chunk-result',dict(token=token.identity,
            outcome=outcome.observations() if outcome is not None else None,
            snapshot=run.state.wire(),events=run.events,work=run.work,changes=run.changes,
            checkpoints=run.writes,gas=run.meter.used,gasTrace=run.meter.trace,rejected=run.meter.rejected,
            turns=run.turns,rounds=run.rounds,units=run.units,logicalPrefix=run.logical_commitment()))
        result=ChunkResult(wire)
        # Store a separate immutable wire copy. Mutating a returned object cannot
        # turn an unexecuted result into an admitted execution capability.
        self._candidates[wire['identity']]=(deepcopy(wire),run,outcome)
        return result

    def accept_chunk(self,token,completion):
        require(not self._finished and self.outcome is None, 'ATTEMPT_FINISHED')
        descriptor=token.descriptor if isinstance(token,ChunkToken) else closed(token,{'format','token','input','history'})['token']
        require(self._token is not None and descriptor==self._token._descriptor, 'STALE_CHUNK_TOKEN')
        wire=completion.to_data() if isinstance(completion,ChunkResult) else deepcopy(completion)
        closed(wire,{'identity','token','outcome','snapshot','events','work','changes','checkpoints','gas','gasTrace','rejected','turns','rounds','units','logicalPrefix'})
        require(wire['token']==self._token.identity, 'CHUNK_INPUT_MISMATCH')
        require(committed('chunk-result',{k:v for k,v in wire.items() if k!='identity'})==wire,'INVALID_CHUNK_COMMITMENT')
        candidate=self._candidates.get(wire['identity'])
        if candidate is None:
            # A portable worker's result has no in-process capability. Verify the
            # entire execution, including failure/gas prefix, with local code.
            self.run.engine.observe_execution('verificationReplay', token=self._token.identity)
            self.run.engine._verifying_completion=True
            try:verified=self.execute_chunk(self._token)
            finally:self.run.engine._verifying_completion=False
            require(canonical(verified.to_data())==canonical(wire),'INVALID_CHUNK_EXECUTION')
            candidate=self._candidates[verified.to_data()['identity']]
        require(canonical(candidate[0])==canonical(wire), 'INVALID_CHUNK_EXECUTION')
        self._history.append({'token':self._token.identity,'result':wire['identity']})
        self.run,self.outcome=candidate[1],candidate[2]
        self._token=None;self._candidates={}
        return self

    def finish(self):
        require(not self._finished, 'ATTEMPT_FINISHED')
        require(self.outcome is not None or self.next_chunk() is None, 'UNFINISHED_ATTEMPT')
        if self.outcome is None:self.outcome=self.run.guard(self.run.finish_work)
        self._finished=True
        return self.outcome

    def finish_local(self):
        """Drive the same machine without crossing a portable chunk boundary.

        Only an untouched, locally owned attempt can take this path. Logical
        unit completion, preflight, gas charges and rollback are unchanged;
        transport commitments and defensive copies are unnecessary when no
        token or candidate has escaped to a worker.
        """
        require(not self._finished, 'ATTEMPT_FINISHED')
        require(self._token is None and not self._history and not self._candidates,
                'CHUNKED_ATTEMPT_ALREADY_STARTED')
        while self.outcome is None:
            members=self.run.guard(self.run.ready)
            if isinstance(members,Outcome):self.outcome=members;break
            if members is None:break
            self.outcome=self.run.guard(lambda:self.run.run_unit(self.run.phase,members))
        if self.outcome is None:self.outcome=self.run.guard(self.run.finish_work)
        self._finished=True
        return self.outcome

    def input_data(self):
        require(not getattr(self.run, 'receiving', False), 'RECEIVING_PORTABLE_EXPORT_UNSUPPORTED')
        if self._input_data is None:
            run=self.run;engine=run.engine
            # Carry provider evidence for BlueIds constructed by an executable
            # body as well as structurally reachable exact input records.
            content=engine.blue.language.provider.snapshot()
            self._input_data=committed('chunk-origin',dict(
                snapshot=export_snapshot(engine,run.input,require_initialized=False),
                event=run.event_id,timestamp=run.timestamp,admission=run.admission,
                views=[export_snapshot(engine,engine.archive.versions[sid]) for _,sid in run.views],
                content=content,policy=run.meter.policy(),externalEvidence=run.admission_evidence))
        return deepcopy(self._input_data)


def restore_origin(engine,data):
    from .processor import Run
    closed(data,{'identity','snapshot','event','timestamp','admission','views','content','policy'},{'externalEvidence'})
    require(committed('chunk-origin',{k:v for k,v in data.items() if k!='identity'})==data,'INVALID_CHUNK_ORIGIN')
    require(type(data['admission']) is bool,'INVALID_RECORD')
    require((data['event'] is None and data['timestamp'] is None) if data['admission'] else
            type(data['event']) is str and type(data['timestamp']) is int,'INVALID_RECORD')
    for view in data['views']:
        snapshot=import_snapshot(engine,view,view['identity'])
        engine.archive.bind(snapshot.documents[snapshot.root].blue_id,snapshot.identity)
    snapshot=import_snapshot(engine,data['snapshot'],data['snapshot']['identity'],require_initialized=False)
    engine.blue.language.provider.merge_responses(data['content']);engine.blue.refresh()
    event=L.Ref(L.final_id(data['event'])) if data['event'] is not None else None
    if event is not None:engine.blue.certify(event)
    policy=closed(data['policy'],{'shared','local','profile'})
    require(Meter(policy['shared'],policy['local'],snapshot.documents).policy()==policy,'INVALID_GAS_POLICY')
    run=Run(engine,snapshot,event,data['timestamp'],policy['shared'],admission=data['admission'],local_limits=policy['local'],admission_evidence=data.get('externalEvidence'))
    # import_snapshot may add the original uninitialized snapshot to the archive;
    # the selected evidence inventory remains exactly that supplied at begin.
    bindings=tuple((v['snapshot']['documents'][next(i for i,d in enumerate(v['snapshot']['documents']) if d['key']==v['snapshot']['root'])]['blueId'],v['identity']) for v in data['views'])
    run.views=tuple(sorted(bindings));run.graph.archive=engine.archive.restrict(run.views)
    return Attempt(run)


def execute(engine,token):
    if isinstance(token,ChunkToken):
        require(token._attempt.run.engine is engine,'WRONG_CHUNK_EXECUTOR')
        return token._attempt.execute_chunk(token)
    closed(token,{'format','token','input','history'})
    require(token['format']=='contracts.chunk-input/completion-1','INCOMPATIBLE_CHUNK_FORMAT')
    attempt=restore_origin(engine,token['input'])
    require(type(token['history']) is list,'INVALID_CHUNK_HISTORY')
    for row in token['history']:
        closed(row,{'token','result'})
        current=attempt.next_chunk()
        require(current is not None and current.identity==row['token'],'INVALID_CHUNK_HISTORY')
        result=attempt.execute_chunk(current)
        require(result.to_data()['identity']==row['result'],'INVALID_CHUNK_HISTORY')
        attempt.accept_chunk(current,result)
    current=attempt.next_chunk()
    require(current is not None and canonical(current.descriptor)==canonical(token['token']),'CHUNK_INPUT_MISMATCH')
    return attempt.execute_chunk(current)
```

### `src/blue_contracts/reference/completion.py`

```python
"""Document-local turns and dependency-unit scheduling (completion-1 A01–A10).

Only owned results cross a frame boundary. Exact Blue references pin all reads;
no callback can look up another member's mutable frame. Cyclic turns read a
single preceding round, and Language seals the merged owned changes together.
"""
from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from algorithms import blue as L
from .model import require, integer, digest, canonical, LIMITS, trampoline
from .graph import Graph, components
from .channels import refresh_lifetimes


def committed(domain, row):
    return {**row, 'identity': digest('contracts.' + domain + '/completion-1', row)}


def vector(state, members):
    return {k: {'document': state.documents[k].metadata(),
                'edges': [e.wire() for e in sorted(state.edges.values(), key=lambda e:(e.source, e.path)) if e.source == k]}
            for k in sorted(members)}


@dataclass(frozen=True)
class Ticket:
    parent: str
    parentActivation: int
    path: str
    source: str
    sourceActivation: int
    generation: int

    def wire(self):
        return asdict(self)


@dataclass
class Batch:
    source: str
    serial: int
    completion: str
    output: tuple
    tickets: tuple
    after: dict
    round_seal: str | None = None


@dataclass
class Frame:
    key: str
    before: object
    input: dict
    source_turn: str
    queue: deque = field(default_factory=deque)
    output: list = field(default_factory=list)
    ticket: Ticket | None = None
    consumed: list = field(default_factory=list)
    writer: dict | None = None
    writes: list = field(default_factory=list)


@dataclass
class Phase:
    name: str
    allowed: set
    groups: list
    initial_routes: dict
    initialization: dict
    seeds: dict
    pending: dict = field(default_factory=lambda: defaultdict(list))
    done: set = field(default_factory=set)
    held: list = field(default_factory=list)
    outside: list = field(default_factory=list)
    barrier: bool = False


class CompletionMachine:
    def setup_completion(self):
        self.frame = None
        self.phase = None
        self.serials = defaultdict(int)
        self.turns = []
        self.rounds = []
        self.units = []
        self.routed = set()
        self.consumed_observations = set()
        self.turn_count = 0
        self.round_count = 0
        self.allocation = 0
        self.changes = []
        self.topology_changed = False
        self.suspended = []

    def fork_graph(self, state):
        old = self.graph
        graph = Graph(state, self.reg, old.archive, self.meter, self.invocation)
        graph.logical = old.logical
        graph.path_headers = old.path_headers
        graph.verified_bindings = old.verified_bindings
        graph.resets = old.resets
        graph.allocation = self.allocation
        graph.changes = self.changes
        return graph

    def capture_routes(self, source, state=None):
        from .model import segments
        state = self.state if state is None else state
        rows = []
        for edge in sorted(state.edges.values(), key=lambda e:(e.source, segments(e.path), e.generation)):
            if edge.target == source:
                rows.append(Ticket(edge.source, self.activation.get(edge.source, 0), edge.path,
                                   source, self.activation.get(source, 0), edge.generation))
        return tuple(rows)

    def ticket_live(self, ticket, *, charge=False):
        if charge:
            self.meter.owner = ticket.parent
            self.meter.contracts('completionRouteChecked')
        edge = self.state.edges.get((ticket.parent, ticket.path))
        return (edge is not None and edge.target == ticket.source and edge.generation == ticket.generation
                and self.activation.get(ticket.parent, 0) == ticket.parentActivation
                and self.activation.get(ticket.source, 0) == ticket.sourceActivation)

    def continuation_live(self, key, generation, allow_terminating=False):
        if self.frame is not None and self.frame.ticket is not None:
            if not self.ticket_live(self.frame.ticket, charge=True):
                return False
        return allow_terminating or self.live(key) and self.activation.get(key, 0) == generation

    def live(self, key):
        if self.frame is not None and key == self.frame.key:
            return key not in self.terminating and not self.graph.terminated(key)
        return key in self.graph.reachable(active=True, terminating=self.terminating)

    def new_phase(self, name, *, allowed=None, barrier=False):
        self.graph.observe_partition()
        allowed = set(self.graph.reachable() if allowed is None else allowed)
        active=self.graph.reachable(active=True)
        captures = {k: self.state.documents[k].blue_id for k in sorted(allowed)
                    if self.reg.marker(self.state.documents[k].body, 'initialized') is None
                    and k not in self.initializing and (barrier or k in active)}
        if name != 'INITIALIZE':
            captures = {}
        self.initialized.update(captures)
        return Phase(name, allowed, [set(g) for g in components(allowed, self.state.edges.values())],
                     {k: self.capture_routes(k) for k in allowed}, captures,
                     {k: [s for s in self.seeds if s.document == k] for k in allowed}
                     if name == 'PROCESS' else {}, barrier=barrier)

    def drive_phase(self, name, *, allowed=None, barrier=False):
        previous = self.phase
        phase = self.new_phase(name, allowed=allowed, barrier=barrier)
        self.phase = phase
        try:
            while self.next_unit(phase) is not None:
                self.run_unit(phase, self.next_unit(phase))
            return phase.outside
        finally:
            self.phase = previous

    def promote(self, phase, members):
        # Execution units only merge. Actual Language SCCs can still split.
        if not phase.barrier:
            phase.allowed.update(self.graph.reachable())
        known = set().union(*phase.groups) if phase.groups else set()
        phase.groups.extend({k} for k in sorted(phase.allowed - known))
        for component in components(phase.allowed, self.state.edges.values()):
            touched = [g for g in phase.groups if g.intersection(component)]
            if len(touched) > 1:
                union = set().union(*touched)
                phase.groups = [g for g in phase.groups if g not in touched] + [union]
                phase.done.difference_update(tuple(sorted(g)) for g in touched)
        return next((g for g in phase.groups if g.intersection(members)), set(members))

    def next_unit(self, phase):
        self.promote(phase, set())
        active = self.graph.reachable()
        ready = []
        owner = {k: tuple(sorted(g)) for g in phase.groups for k in g}
        for group in phase.groups:
            identity = tuple(sorted(group))
            if identity in phase.done:
                continue
            if not phase.barrier and not group.intersection(active):
                phase.done.add(identity)
                continue
            dependencies = {owner[e.target] for e in self.state.edges.values()
                            if e.source in group and e.target in owner and e.target not in group}
            if dependencies <= phase.done:
                ready.append(identity)
        if ready:
            return set(min(ready))
        require(all(tuple(sorted(g)) in phase.done for g in phase.groups), 'UNSEALED_DEPENDENCY')
        return None

    def has_inputs(self, phase, key):
        return bool(phase.pending[key] or key in phase.initialization or phase.seeds.get(key))

    def run_unit(self, phase, members):
        start = len(self.meter.trace)
        before = vector(self.state, members)
        turn_start = len(self.turns)
        while True:
            members = self.promote(phase, members)
            inputs = [k for k in sorted(members) if self.has_inputs(phase, k)]
            if not inputs:
                break
            cyclic = len(members) > 1 or any(e.source == e.target and e.source in members for e in self.state.edges.values())
            if cyclic:
                self.round_count += 1
                self.meter.owner = ''
                self.meter.contracts('componentRoundOpened')
            preceding = self.state.copy()
            results = []
            for key in inputs:
                incoming = phase.pending.pop(key, [])
                lifecycle = phase.initialization.pop(key, None)
                seeds = phase.seeds.pop(key, [])
                routes = (phase.initial_routes.get(key, self.capture_routes(key))
                          if not any(t['turnInput']['member'] == key and t['turnInput']['phase'] == phase.name for t in self.turns)
                          else self.capture_routes(key, preceding))
                result = self.run_local(preceding, key, incoming, lifecycle, seeds, phase.name, routes)
                results.append(result)
            for result in results:
                self.merge_owned(result)
            previous_reachable=Graph(preceding,self.reg,self.graph.archive).reachable()
            for key in previous_reachable ^ self.graph.reachable():
                self.activation[key]=self.activation.get(key,0)+1
            members = self.promote(phase, members)
            self.graph.dirty.update(r['key'] for r in results)
            self.graph.finalize(members=members)
            self.preflight(members=members)
            round_seal = None
            if cyclic or len(members) > 1:
                round_seal = committed('round-result', {
                    'beforeViews': vector(preceding, set(members) & set(preceding.documents)),
                    'afterViews': vector(self.state, members), 'ordinal': len(self.rounds),
                    'turns': [r['completion']['identity'] for r in results],
                    'members': vector(self.state, members),
                    'bindings': [e.wire() for e in sorted(self.state.edges.values(), key=lambda e:e.key) if e.source in members]})
                self.rounds.append(round_seal)
            for result in results:
                completion = result['completion']
                batch = Batch(result['key'], completion['turnInput']['turnSerial'], completion['identity'],
                              tuple(completion['output']), result['routes'], vector(self.state, [result['key']]),
                              round_seal['identity'] if round_seal else None)
                phase.held.append(batch)
            for batch in phase.held:
                self.route_batch(phase, batch, members, internal=True)
            # A join can introduce an as-yet unprocessed external dependency.
            owner = {k: tuple(sorted(g)) for g in phase.groups for k in g}
            dependencies = {owner[e.target] for e in self.state.edges.values()
                            if e.source in members and e.target in owner and e.target not in members}
            if not dependencies <= phase.done:
                return
        identity = tuple(sorted(members))
        phase.done.add(identity)
        output = []
        for batch in phase.held:
            if batch.source not in members:
                continue
            batch.after = vector(self.state, [batch.source])
            self.route_batch(phase, batch, members, internal=False)
            output.append({'source': batch.source, 'completion': batch.completion, 'output': list(batch.output)})
        self.units.append(committed('unit-result', {
            'members': list(identity), 'beforeViews': before, 'afterViews': vector(self.state, members),
            'turnResults': [t['identity'] for t in self.turns[turn_start:]], 'output': output,
            'workSegment': self.relative_segment(start)}))

    def route_batch(self, phase, batch, members, *, internal):
        grouped = defaultdict(list)
        for ticket in batch.tickets:
            if (ticket.parent in members) != internal:
                continue
            # Pure cyclic identity refresh never schedules an empty round.
            if internal and not batch.output:
                continue
            identity = (batch.completion, digest('ticket', ticket.wire()))
            if identity in self.routed:
                continue
            self.routed.add(identity)
            grouped[ticket.parent].append(ticket)
        for parent, tickets in sorted(grouped.items()):
            selected = Batch(batch.source, batch.serial, batch.completion, batch.output, tuple(tickets),
                             deepcopy(batch.after), batch.round_seal if internal else None)
            if parent in phase.allowed:
                phase.pending[parent].append(selected)
                phase.done.discard(next((tuple(sorted(g)) for g in phase.groups if parent in g), (parent,)))
            else:
                phase.outside.append(selected)

    def relative_segment(self, start):
        return [{**row, 'ordinal': i} for i, row in enumerate(self.meter.trace[start:])]

    def install_inputs(self, key, incoming):
        from .model import segments
        # State is the already sealed coherent dependency inventory. In a cycle
        # this is the previous round, never the isolated source local after-view.
        previous = self.state.documents[key].body
        replacements = []
        for edge in sorted(self.state.edges.values(), key=lambda e:(e.source, segments(e.path))):
            if edge.source != key:
                continue
            node = self.blue.exact(self.blue.select(previous, edge.path))
            target = self.state.documents[edge.target].blue_id
            if self.blue.identity(node) != target:
                self.meter.owner = key
                self.meter.contracts('containingReferenceUpdated')
                replacements.append((edge.path, L.Ref(target)))
        # These paths are disjoint. No handler observes a partially installed
        # dependency inventory, so establish its one completed candidate.
        if replacements:
            candidate = self.blue.substitute(previous, replacements)
            self.graph.logical.establish(candidate, previous)
            self.state.documents[key].body = candidate
        self.graph.finalize_local(key)
        for batch in sorted(incoming, key=lambda b:(b.source, b.serial)):
            self.meter.owner = key
            self.meter.contracts('completionBatchInstalled')
            tickets = [t for t in sorted(batch.tickets, key=lambda t:(segments(t.path), t.generation))
                       if self.ticket_live(t, charge=True)]
            for event in batch.output:
                for ticket in tickets:
                    observation = digest('contracts.embedded-observation/completion-1',
                                         {'source': event['identity'], 'ticket': ticket.wire()})
                    if observation not in self.consumed_observations:
                        self.frame.queue.append(('EMBEDDED', event, ticket, observation))

    def run_local(self, sealed, key, incoming, lifecycle, seeds, phase, routes):
        self.engine.observe_execution('localTurn', member=key, event=self.event_id,
            before=sealed.documents[key].blue_id, phase=phase, initialization=bool(lifecycle),
            receiving=bool(incoming), verifying=getattr(self.engine,'_verifying_completion',False))
        saved = self.state, self.graph, self.frame, self.activation
        self.activation=deepcopy(self.activation)
        self.state = sealed.copy()
        self.graph = self.fork_graph(self.state)
        start = len(self.meter.trace)
        work_start = len(self.work)
        changes_start = len(self.changes)
        serial = self.serials[key]
        self.serials[key] += 1
        descriptor = dict(member=key, activation=self.activation.get(key, 0), beforeView=vector(sealed, [key]),
                          profile=self.meter.policy()['profile'],
                          cause={'kind': 'INITIALIZE'} if self.admission else {'kind': 'PROCESS', 'event': self.event_id, 'timestamp': self.timestamp},
                          phase=phase, turnSerial=serial,
                          dependencies=vector(sealed, {e.target for e in sealed.edges.values() if e.source == key}),
                          incoming=[{'kind':'CYCLIC' if b.round_seal else 'DAG', 'sourceCompletion':b.completion,
                                     **({'roundSeal':b.round_seal} if b.round_seal else {}), 'tickets':[t.wire() for t in b.tickets]}
                                    for b in sorted(incoming, key=lambda b:(b.source,b.serial))],
                          seeds=[asdict(s) for s in seeds],
                          lifecycle={'kind':'INITIALIZE','document':{'blueId':lifecycle}} if lifecycle else {'kind':'NONE'})
        # Execution certificates include invocation-wide logical gas/evidence.
        # They authenticate a batch, but are not its semantic occurrence: an
        # unrelated containing root must not rename the child's next emission.
        # Bind the actual completed state, ordered output and occurrence tickets
        # here; retain the complete certificate above for verification/replay.
        semantic_input = {**descriptor, 'incoming': [dict(
            kind='CYCLIC' if b.round_seal else 'DAG', source=b.source, serial=b.serial,
            after=b.after, output=list(b.output), tickets=[t.wire() for t in b.tickets])
            for b in sorted(incoming, key=lambda b:(b.source,b.serial))]}
        source_turn = digest('contracts.turn-input/completion-1', semantic_input)
        descriptor['logicalContext'] = self.logical_commitment()
        self.frame = Frame(key, deepcopy(sealed.documents[key]), descriptor, source_turn)
        self.suspended.append(self.frame)
        try:
            self.turn_count += 1
            self.meter.owner = key
            self.meter.contracts('localTurnOpened')
            self.install_inputs(key, incoming)
            if lifecycle and self.live(key):
                self.initializing.add(key)
                self.meter.owner = key
                self.meter.contracts('scopeInitialization')
                node = self.runtime_node(self.reg.typed('Document Processing Initiated', document={'blueId':lifecycle}))
                cs = self.reg.contracts(self.state.documents[key].body)
                for channel, declaration in self.ordered(cs):
                    if declaration['_role'] == 'lifecycle' and ('event' not in declaration or self.runtime_matches(node, declaration['event'])):
                        trampoline(self.dispatch(key, channel, node, 'INITIALIZATION'))
                trampoline(self.custom_internal(key, 'INITIALIZATION', node, cs))
            trampoline(self.drain())
            for seed in seeds:
                doc = self.state.documents[key]
                life = doc.channel_lives.get(seed.channel)
                if (self.live(key) and self.activation.get(key, 0) == 0 and life is not None and life.generation == seed.generation):
                    trampoline(self.dispatch(key, seed.channel, self.event, 'EXTERNAL', seed.operation, call=self.call))
                    trampoline(self.drain())
                    self.frame.consumed.append(seed)
            self.settle_local(key, lifecycle)
            self.graph.finalize_local(key)
            self.preflight(members={key})
            require(not self.frame.queue, 'NONQUIESCENT_LOCAL_RESULT')
            self.state.documents[key].blue_id = self.blue.identity(self.state.documents[key].body)
            self.meter.owner = key
            self.meter.contracts('localTurnSealed')
            completion = committed('turn-result', dict(
                turnInput=descriptor, afterView=vector(self.state, [key]), output=deepcopy(self.frame.output),
                memberMetadata=self.state.documents[key].metadata(), edgeChanges=deepcopy(self.changes[changes_start:]),
                consumedSeeds=[asdict(s) for s in self.frame.consumed],
                writes=deepcopy(self.frame.writes),
                retiredTickets=[t.wire() for b in incoming for t in b.tickets if not self.ticket_live(t)],
                workSegment=self.relative_segment(start)))
            self.turns.append(completion)
            new = set(self.state.documents) - set(sealed.documents)
            owned = new | {key}
            return {'key':key, 'documents':{k:deepcopy(self.state.documents[k]) for k in owned},
                    'edges':{k:e for k,e in self.state.edges.items() if e.source in owned},
                    'completion':completion, 'routes':routes}
        finally:
            self.allocation = max(self.allocation, self.graph.allocation)
            self.topology_changed |= self.graph.topology_changed
            self.suspended.pop()
            self.state, self.graph, self.frame, self.activation = saved

    def logical_commitment(self):
        logical = self.graph.logical
        # These keys are already exact identities/recipes, never cache addresses.
        return digest('contracts.logical-prefix/completion-1', {
            'gas': self.meter.trace, 'work': self.work,
            'manifests': sorted(logical.manifests),
            'established': sorted(logical.established,key=canonical),
            'proofs': sorted(logical.proofs,key=canonical),
            'partition': logical.partition,
            'boundIdentities': sorted(logical.bound_identities),
            'exactValues': sorted(((key,identity) for key,(_,identity) in logical.exact_values.items()),key=canonical),
            'carried': sorted(logical.carried_roots)})

    def merge_owned(self, result):
        owned = set(result['documents'])
        self.state.documents.update(result['documents'])
        for document in result['documents'].values():
            if isinstance(document.body,L.Node):self.blue.note_identity(document.body,document.blue_id)
        for edge in list(self.state.edges):
            if edge[0] in owned:
                self.state.edges.pop(edge)
        self.state.edges.update(result['edges'])
        self.graph.allocation = self.allocation
        self.graph.refresh_aliases()

    def settle_local(self, key, lifecycle):
        if lifecycle and self.reg.marker(self.state.documents[key].body, 'initialized') is None:
            self.meter.owner = key
            self.meter.contracts('processorMarkerWritten')
            self.direct_marker(key, 'initialized', self.reg.typed('Processing Initialized Marker', document={'blueId':lifecycle}))
        if key in self.termination and self.reg.marker(self.state.documents[key].body, 'terminated') is None:
            self.meter.owner = key
            self.meter.contracts('processorMarkerWritten')
            cause, reason = self.termination[key]
            self.direct_marker(key, 'terminated', self.reg.typed('Processing Terminated Marker', cause=cause,
                                                             **({'reason':reason} if reason is not None else {})))
        doc = self.state.documents[key]
        marker = self.reg.marker(doc.body, 'checkpoint')
        entries = deepcopy(self.blue.literal(marker).get('entries', {}) if marker else {})
        before = deepcopy(entries)
        for channel in list(entries):
            if channel not in doc.channel_lives or (key, channel) in self.graph.resets:
                entries.pop(channel)
        for seed in self.frame.consumed:
            life = doc.channel_lives.get(seed.channel)
            if life is not None and life.generation == seed.generation:
                entries[seed.channel] = {'timestamp':self.timestamp, 'event':{'blueId':self.event_id}}
        for channel in sorted(set(before) | set(entries)):
            if before.get(channel) != entries.get(channel):
                self.meter.owner = key
                self.meter.contracts('checkpointWritten')
                self.writes.append(dict(document=key,channel=channel,before=before.get(channel),after=entries.get(channel)))
        if entries != before:
            self.direct_marker(key, 'checkpoint', self.reg.typed('Channel Event Checkpoint', entries=entries) if entries else None)

    def emit(self, key, node):
        self.meter.owner = key
        self.graph.logical.establish(node)
        self.meter.contracts('internalEventEnqueued')
        occurrence = committed('event', dict(sourceTurn=self.frame.source_turn, ordinal=len(self.frame.output),
                                             event=self.blue.identity(node)))
        self.frame.output.append(occurrence)
        self.events.append(dict(ordinal=len(self.events), identity=occurrence['identity'], document=key,
                                event=occurrence['event'], sourceTurn=occurrence['sourceTurn'], sourceOrdinal=occurrence['ordinal']))
        self.frame.queue.append(('LOCAL', occurrence, None, occurrence['identity']))

    def drain(self):
        key = self.frame.key
        while self.frame.queue:
            kind, occurrence, ticket, observation = self.frame.queue.popleft()
            self.meter.owner = key
            if kind == 'LOCAL':
                self.meter.contracts('internalEventDequeued')
            else:
                self.consumed_observations.add(observation)
                if not self.ticket_live(ticket, charge=True):
                    continue
            if not self.live(key):
                continue
            node = L.Ref(occurrence['event'])
            cs = self.reg.contracts(self.state.documents[key].body)
            self.frame.ticket = ticket
            try:
                if kind == 'LOCAL':
                    for channel, declaration in self.ordered(cs):
                        if not self.live(key):
                            break
                        if declaration['_role'] == 'triggered' and ('event' not in declaration or self.runtime_matches(node, declaration['event'])):
                            yield self.dispatch(key, channel, node, 'TRIGGERED')
                    yield self.custom_internal(key, 'TRIGGERED', node, cs)
                else:
                    payload = self.runtime_node(self.reg.typed('Embedded Event Delivery', sourcePath=ticket.path,
                                                           event={'blueId':occurrence['event']}))
                    for channel, declaration in self.ordered(cs):
                        if not self.ticket_live(ticket) or not self.live(key):
                            break
                        if declaration['_role'] != 'embedded_event':
                            continue
                        if 'sourcePath' in declaration and declaration['sourcePath'] != ticket.path:
                            continue
                        if 'event' in declaration and not self.runtime_matches(node, declaration['event']):
                            continue
                        yield self.dispatch(key, channel, payload, 'EMBEDDED')
                    yield self.custom_internal(key, 'EMBEDDED', payload, cs)
            finally:
                self.frame.ticket = None

    def creation_barrier(self):
        # Save the creator's private body. Existing members are read-only pins;
        # only newly uninitialized members enter this nested initialization.
        creator = self.frame
        missing = {k for k in self.graph.reachable() if self.reg.marker(self.state.documents[k].body, 'initialized') is None
                   and k not in self.initializing and k not in {f.key for f in self.suspended}}
        if not missing:
            return
        private_state, private_graph = self.state, self.graph
        self.state = private_state.copy()
        for frame in self.suspended:
            self.state.documents[frame.key] = deepcopy(frame.before)
        self.graph = self.fork_graph(self.state)
        try:
            batches = self.drive_phase('INITIALIZE', allowed=missing, barrier=True)
            owned = set(self.state.documents) - set(private_state.documents) | missing
            for key in owned:
                private_state.documents[key] = deepcopy(self.state.documents[key])
            for edge in list(private_state.edges):
                if edge[0] in owned:
                    private_state.edges.pop(edge)
            private_state.edges.update({k:e for k,e in self.state.edges.items() if e.source in owned})
        finally:
            self.state, self.graph = private_state, private_graph
            self.graph.allocation = self.allocation
        self.frame = creator
        self.install_inputs(creator.key, [b for b in batches if any(t.parent == creator.key for t in b.tickets)])
        if self.phase is not None:
            for batch in batches:
                for parent in {t.parent for t in batch.tickets} - {creator.key}:
                    self.phase.pending[parent].append(batch)
        self.graph.refresh_aliases()
```

### `src/blue_contracts/reference/compute.py`

```python
"""Demanded, deterministic shared Compute definitions in the current frame."""
from algorithms import blue as L
from .model import require, segments


def resolve_definition(attempt,key,step):
    if 'definition' not in step:return None
    blue=attempt.blue;logical=attempt.graph.logical
    operand=step['definition'];head=blue.head(operand)
    if head.value is not L.ABSENT:
        name=head.value
        require(type(name) is str and bool(name),'INVALID_COMPUTE_DEFINITION')
        path=name if name.startswith('/') else '/contracts/'+name.replace('~','~0').replace('/','~1')
        selected=L.recipe(attempt.state.documents[key].body)
        for part in segments(path):
            for node in selected.parts:logical.open(node)
            logical.meter.contracts('objectMemberRead')
            selected=blue.child(selected,part)
            require(selected is not None,'MISSING_COMPUTE_DEFINITION',path=path)
        operand=selected
    # Traverse only this selected executable definition. The existing finite
    # manifest counters charge reads before extraction; no user code runs here.
    seen=set()
    def visit(recipe):
        if recipe.key() in seen:
            require(False,'CYCLIC_COMPUTE_DEFINITION')
        seen.add(recipe.key())
        for node in recipe.parts:logical.open(node)
        h=blue.head(recipe)
        if h.value is not L.ABSENT:
            if type(h.value) is str:logical.meter.charge('textWork',(len(h.value)+63)//64)
        elif h.items is not None:
            logical.meter.contracts('listItemRead',len(h.items))
            for i in range(len(h.items)):visit(L.child_recipe(h,i))
        else:
            logical.meter.contracts('objectMemberRead',len(h.fields))
            for field in sorted(h.fields):
                # Static exact type references are retained by bex_data.
                if field not in L.TYPES:visit(L.child_recipe(h,field))
        seen.remove(recipe.key())
    head=blue.head(operand)
    require(head.value is L.ABSENT and head.items is None,'INVALID_COMPUTE_DEFINITION')
    require(set(head.fields)<={'constants','functions','specification','order'},'INVALID_COMPUTE_DEFINITION')
    out={}
    for field in ('constants','functions'):
        child=blue.child(operand,field)
        if child is not None:
            visit(child);out[field]=blue.bex_data(child)
            require(type(out[field]) is dict,'INVALID_COMPUTE_DEFINITION',field=field)
    return out
```

### `src/blue_contracts/reference/generalization.py`

```python
"""Policy-controlled type changes, validated by the actual Language context."""
from algorithms import blue as L
from .model import ContractError,require,segments,pointer
from .policy import GeneralizationError,choose_type

SEMANTIC_FAILURES={'TypeCompatibilityViolation','SchemaViolation','FixedValueConflict'}


def direct_at(blue,node,parts):
    for key in parts:
        body=blue.open(node)
        if body.has('items'):
            if not key.isdigit() or int(key)>=len(body.get('items')):return None
            node=body.get('items')[int(key)]
        else:
            node=body.get(key)
            if node is L.ABSENT or not isinstance(node,(L.Node,L.Ref)):return None
    return node


def replace_direct(blue,node,parts,value):
    if not parts:return value
    body=blue.open(node);fields=dict(body.fields);key=parts[0]
    if body.has('items'):
        items=list(body.get('items'));i=int(key)
        items[i]=replace_direct(blue,items[i],parts[1:],value);fields['items']=tuple(items)
    else:fields[key]=replace_direct(blue,fields[key],parts[1:],value)
    return L.node(fields)


def repair(blue,before,changed,path,policy,meter,validate=None,establish=None):
    """Return a valid changed root and ordered exact generated type writes.

    Visit the changed subtree bottom-up, then its containing spine. Candidate
    validation keeps contextual requirements and each containing schema. This
    permits two invalid children in one replacement to be repaired separately,
    without treating either child's failure as permission to weaken the other.
    """
    validate=validate or blue.certify
    try:validate(changed);return changed,[]
    except ContractError as failure:
        if failure.code not in {'LANGUAGE_'+name for name in SEMANTIC_FAILURES}:raise
        original=failure
    parts=segments(path)
    paths=[];writes=[]
    def affected(node,prior,at,depth=0):
        if node is None:return
        if prior is not None and blue.identity(node)==blue.identity(prior):return
        if isinstance(node,L.Node):
            old=blue.open(prior) if isinstance(prior,(L.Node,L.Ref)) else None
            for key,value in node.fields:
                if key=='items':
                    previous=old.get('items') if old else L.ABSENT
                    for i,child in enumerate(value):affected(child,previous[i] if isinstance(previous,tuple) and i<len(previous) else None,at+(str(i),),depth+1)
                elif key not in L.LITERALS|L.TYPES|{'schema','mergePolicy','contracts'}:
                    previous=old.get(key) if old else L.ABSENT
                    affected(value,None if previous is L.ABSENT else previous,at+(key,),depth+1)
        paths.append(at)
    affected(direct_at(blue,changed,parts),direct_at(blue,before,parts),parts)
    paths.extend(parts[:size] for size in range(len(parts)-1,-1,-1))
    for at in paths:
        node=direct_at(blue,changed,at)
        if node is None:continue
        body=blue.open(node);typ=body.get('type')
        if not isinstance(typ,L.Ref):continue
        selected=policy.select(pointer(at))
        if selected.mode=='reject':continue
        candidates={}
        def valid(_,tid):
            candidate=replace_direct(blue,changed,at,L.changed(body,type=L.Ref(tid)))
            try:
                if establish:establish(candidate)
                selected=blue.select(candidate,pointer(at))
                L.validate(selected,blue.context,'value')
                for size in range(len(at)-1,-1,-1):
                    enclosing=blue.select(candidate,pointer(at[:size]));head=blue.head(enclosing)
                    L.validate_schema(head,True,'value',size==0,blue.context)
            except L.Failure as exc:
                if exc.category in SEMANTIC_FAILURES:return False
                blue.translate(exc)
            except ContractError as exc:
                if exc.code in {'LANGUAGE_'+name for name in SEMANTIC_FAILURES}:return False
                raise
            candidates[tid]=candidate;return True
        def ancestor(tid):
            parent=blue.open(L.Ref(tid)).get('type')
            if isinstance(parent,L.Ref):meter.contracts('typeEdgeFollowed');return parent.id
            return None
        try:
            tid=choose_type(typ.id,body,pointer(at),policy,immediate_ancestor=ancestor,
                            valid_with_type=valid,is_subtype=lambda a,b:L.check_subtype(a,b,blue.context),
                            charge_candidate=lambda _:meter.contracts('subtypeCandidateTested'))
        except GeneralizationError as exc:raise ContractError(str(exc),path=pointer(at)) from exc
        if tid!=typ.id:
            changed=candidates[tid];writes.append({'path':pointer(at+('type',)),'before':typ,'after':L.Ref(tid)})
    if not writes:raise original
    validate(changed)
    return changed,writes
```

### `src/blue_contracts/reference/graph.py`

```python
"""Finite rooted views, dynamic reconciliation, routes and Language SCC identity."""
from dataclasses import dataclass
from copy import deepcopy
from algorithms import blue as L
from .model import Document,Snapshot,Edge,NeedResources,require,token,integer,segments,pointer,prefix,digest,LIMITS

@dataclass(frozen=True)
class Link:
    """SDK-only bundle reference, never a Blue runtime patch value."""
    document:str

def components(vertices,edges):
    """Iterative SCC partition and deterministic deepest-first condensation order."""
    vs=sorted(vertices);out={v:[] for v in vs};rev={v:[] for v in vs}
    for e in sorted(edges,key=lambda e:(e.source,e.path,e.target)):
        if e.source in out and e.target in out:out[e.source].append(e.target);rev[e.target].append(e.source)
    seen=set();finish=[]
    for start in vs:
        if start in seen:continue
        stack=[(start,False)]
        while stack:
            v,leaving=stack.pop()
            if leaving:finish.append(v);continue
            if v in seen:continue
            seen.add(v);stack.append((v,True));stack.extend((w,False) for w in reversed(sorted(set(out[v]))) if w not in seen)
    seen=set();groups=[]
    for start in reversed(finish):
        if start in seen:continue
        group=[];stack=[start]
        while stack:
            v=stack.pop()
            if v in seen:continue
            seen.add(v);group.append(v);stack.extend(sorted(set(rev[v])-seen,reverse=True))
        groups.append(tuple(sorted(group)))
    owner={v:g for g in groups for v in g};deps={g:{owner[w] for v in g for w in out[v] if owner[w]!=g} for g in groups};result=[];done=set()
    while len(done)<len(groups):
        ready=sorted(g for g in groups if g not in done and deps[g]<=done);require(bool(ready),'INTERNAL_COMPONENT_ORDER');g=ready[0];done.add(g);result.append(g)
    return result

class Archive:
    """Verified immutable views with explicit choice; never a latest-head lookup."""
    def __init__(self):self.versions={};self.roots={};self.choices={}
    def add(self,snapshot):
        identity=snapshot.identity;root_id=snapshot.documents[snapshot.root].blue_id;old=self.versions.get(identity)
        require(old is None or old.wire()==snapshot.wire(),'CONFLICTING_PROCESS_VIEW');self.versions[identity]=snapshot.copy();self.roots.setdefault(root_id,set()).add(identity)
    def bind(self,blue_id,snapshot_id):
        require(snapshot_id in self.roots.get(blue_id,set()),'UNKNOWN_PROCESS_VIEW');self.choices[blue_id]=snapshot_id
    def bindings(self):
        result=[]
        for key,ids in sorted(self.roots.items()):
            selected=self.choices.get(key)
            if selected is None and len(ids)==1:selected=next(iter(ids))
            if selected is not None:result.append((key,selected))
        return tuple(result)
    def restrict(self,bindings):
        require(len(bindings)==len({x[0] for x in bindings}),'DUPLICATE_PROCESS_VIEW_BINDING');out=Archive()
        for key,identity in bindings:
            require(identity in self.roots.get(key,set()),'UNKNOWN_PROCESS_VIEW',blueId=key,identity=identity)
            out.add(self.versions[identity]);out.bind(key,identity)
        return out
    def get(self,blue_id):
        if blue_id not in self.roots:return None
        selected=dict(self.bindings()).get(blue_id);require(selected is not None,'AMBIGUOUS_PROCESS_VIEW',blueId=blue_id)
        return self.versions[selected].copy()

class Graph:
    def __init__(self,snapshot,registry,archive,meter=None,cause=None):
        self.state=snapshot;self.registry=registry;self.blue=registry.blue;self.archive=archive;self.meter=meter;self.cause=cause
        self.aliases={};self.resets=set();self.added=[];self.changes=[];self.topology_changed=False;self.allocation=0;self.refresh_aliases()
        self.dirty=set();self.finalized={k:d.body for k,d in snapshot.documents.items() if d.blue_id};self.partition=None
        self.path_headers=set();self.verified_bindings=set()
        from .work import LogicalWork
        self.logical=LogicalWork(self.blue,meter) if meter else None
        if self.logical:
            for d in snapshot.documents.values():
                if d.blue_id and isinstance(d.body,L.Node):self.blue.note_identity(d.body,d.blue_id)
            self.logical.carried_roots.update(d.blue_id for d in snapshot.documents.values() if d.blue_id)
            # Exact installed definitions are identity evidence, not evidence
            # that a definition is a valid completed business value.
            self.logical.bound_identities.update(registry.types.values())
            self.logical.bound_identities.add(registry.specification)
    def charge(self,c,n=1):
        if self.meter:self.meter.contracts(c,n)
    def refresh_aliases(self):
        # Only identities currently bound to a vertex are live references.
        # Continuing occurrences have explicit edges; an old exact address is
        # resolved through the selected archive, never through a newer vertex.
        self.aliases={}
        live=self.reachable()
        for k,d in self.state.documents.items():
            if k not in live:continue
            if d.blue_id:self.aliases.setdefault(d.blue_id,set()).add(k)
    def terminated(self,key):return self.registry.marker(self.state.documents[key].body,'terminated') is not None
    def reachable(self,*,active=False,terminating=frozenset()):
        seen=set();pending=[self.state.root]
        while pending:
            k=pending.pop()
            if k in seen:continue
            if active and (k in terminating or self.terminated(k)):continue
            seen.add(k);pending.extend(e.target for _,e in sorted(self.state.edges.items(),reverse=True) if e.source==k)
        return seen
    def paths(self,body):
        e=self.registry.contracts(body).get('embedded')
        if e is None:return ()
        require(e['_role']=='embedding','INVALID_EMBEDDING');paths=[]
        header=self.blue.identity(self.blue.exact(e['_recipe']))
        first=header not in self.path_headers
        if first:self.path_headers.add(header)
        for p in e.get('paths',[]):
            if first:
                self.charge('embeddedPathEntryRead')
                for _ in segments(p):self.charge('embeddedPathSegmentValidated')
            require(type(p) is str and segments(p) and all(segments(p)) and segments(p)[0]!='contracts','INVALID_EMBEDDED_PATH')
            if self.blue.select(body,p) is not None:paths.append(p)
        for base in e.get('collectionPaths',[]):
            if first:
                self.charge('embeddedPathEntryRead')
                for _ in segments(base):self.charge('embeddedPathSegmentValidated')
            require(type(base) is str and segments(base) and segments(base)[0]!='contracts','INVALID_EMBEDDED_PATH');r=self.blue.select(body,base)
            if r is None:continue
            h=self.blue.head(r);require(h.kind in ('object','none') and h.items is None and h.value is L.ABSENT,'EMBEDDED_COLLECTION_NOT_OBJECT')
            for name in sorted(h.fields):paths.append(base+pointer([name]))
        require(len(paths)==len(set(paths)),'DUPLICATE_EMBEDDED_PATH');paths=sorted(paths,key=segments)
        for i,p in enumerate(paths):
            for q in paths[i+1:]:require(not prefix(p,q),'OVERLAPPING_EMBEDDED_PATH')
        return tuple(paths)
    def fresh_key(self,source,path,tid):
        self.allocation+=1
        return digest('contracts.vertex/1',{'input':self.cause or self.state.identity,'source':source,'path':path,'ordinal':self.allocation,'value':tid})
    def import_target(self,source,path,node,birth):
        tid=self.blue.identity(node);known=self.aliases.get(tid,set());require(len(known)<=1,'AMBIGUOUS_LIVE_REFERENCE',blueId=tid)
        if known:return next(iter(known))
        imported=self.archive.get(tid)
        if imported is not None:
            mapping={}
            for key,doc in sorted(imported.documents.items()):
                same=self.aliases.get(doc.blue_id,set());candidates=[s for s in same if self.state.documents[s].channel_lives==doc.channel_lives]
                require(len(candidates)<=1,'AMBIGUOUS_LIVE_REFERENCE',blueId=doc.blue_id)
                # Preserve established member origins when an archived view is
                # embedded in another root. A simultaneous different view of
                # the same key still needs a distinct local occurrence vertex.
                mapping[key]=(candidates[0] if candidates else key if key not in self.state.documents
                              else self.fresh_key(source,path+'/'+key,doc.blue_id))
            for key,doc in sorted(imported.documents.items()):
                new=mapping[key]
                if new in self.state.documents:continue
                clone=deepcopy(doc);clone.key=new;self.state.documents[new]=clone;self.added.append(new)
            for edge in sorted(imported.edges.values(),key=lambda e:e.key):
                mapped=Edge(mapping[edge.source],edge.path,mapping[edge.target],edge.generation);old=self.state.edges.get(mapped.key)
                require(old is None or old==mapped,'IMPORTED_GRAPH_CONFLICT');self.state.edges[mapped.key]=mapped
            observer=getattr(self.registry,'observe_attachment',None)
            if observer is not None:
                observer({mapping[key]:doc.blue_id for key,doc in imported.documents.items()})
            self.refresh_aliases();return mapping[imported.root]
        body=self.blue.open(node);h=self.blue.head(body);require(h.kind in ('object','none') and h.items is None and h.value is L.ABSENT,'EMBEDDED_DOCUMENT_NOT_OBJECT')
        for reserved in ('initialized','terminated','checkpoint'):
            if self.registry.marker(body,reserved) is not None:raise NeedResources(tid)
        key=self.fresh_key(source,path,tid);self.state.documents[key]=Document(key,body,tid,birth=birth);self.aliases.setdefault(tid,set()).add(key);self.added.append(key);return key
    def reconcile(self,birth=None,*,owner=None,replaced=()):
        # A frame owns one declaration map. Existing peers are pinned; only
        # newly discovered children may be traversed during its reconciliation.
        original=set(self.state.documents)
        visited=set();todo=[owner if owner is not None else self.state.root]
        while todo:
            key=todo.pop(0)
            if key in visited:continue
            visited.add(key);d=self.state.documents[key];required=self.paths(d.body);current={p:e for (s,p),e in self.state.edges.items() if s==key}
            for path in sorted(set(current)-set(required)):
                e=self.state.edges.pop((key,path));self.record('REMOVE',e,None)
            for path in required:
                r=self.blue.select(d.body,path);require(r is not None,'MISSING_EMBEDDED_PATH');n=self.blue.exact(r);tid=self.blue.identity(n);e=self.state.edges.get((key,path))
                target=e.target if e and tid==self.state.documents[e.target].blue_id else self.import_target(key,path,n,birth)
                if e is None or target!=e.target or any(prefix(p,path) for p in replaced):
                    if e:self.record('REMOVE',e,None)
                    generation=d.edge_serials.get(path,0)+1;integer(generation);d.edge_serials[path]=generation
                    new=Edge(key,path,target,generation);self.state.edges[(key,path)]=new;self.record('ADD',None,new)
                if owner is None or target not in original:todo.append(target)
        self.refresh_aliases()
    def record(self,kind,before,after):
        self.topology_changed=True;self.changes.append(dict(ordinal=len(self.changes),kind=kind,before=before.wire() if before else None,after=after.wire() if after else None))
        edge=after or before;self.dirty.update((edge.source,edge.target))
        if self.meter:self.meter.owner=edge.source
        self.charge('processEmbeddedEdgeExamined')
        if kind=='ADD' and edge.target in self.added:self.charge('closureExpanded')
    def observe_partition(self):
        relevant=self.reachable()
        partition=components(relevant,self.state.edges.values())
        previous=self.logical.partition if self.logical else self.partition
        if previous!=partition:
            prior=set(previous or ())
            for group in partition:
                if group in prior:continue
                if self.meter and not set(group)&relevant:continue
                for key in group:
                    if self.meter:self.meter.owner=key
                    self.charge('componentMemberPartitioned')
                for edge in sorted(self.state.edges.values(),key=lambda e:e.key):
                    if edge.source in group:
                        if self.meter:self.meter.owner=edge.source
                        self.charge('componentEdgePartitioned')
                if prior:self.charge('componentPartitionChanged')
            self.partition=partition
            if self.logical:self.logical.partition=partition
        return partition
    def finalize(self,*,validate=True,members=None):
        selected=set(self.state.documents) if members is None else set(members)
        self.observe_partition()
        partition=components(selected,self.state.edges.values())
        for group in partition:
            members=set(group);edges=[e for e in self.state.edges.values() if e.source in members];bodies={k:self.state.documents[k].body for k in group}
            replacements={k:[] for k in group}
            for e in sorted(edges,key=lambda e:(e.source,e.path)):
                if e.target not in members:
                    current=self.blue.exact(self.blue.select(bodies[e.source],e.path))
                    if self.blue.identity(current)!=self.state.documents[e.target].blue_id:
                        if self.meter:self.meter.owner=e.source
                        self.charge('containingReferenceUpdated')
                        replacements[e.source].append((e.path,L.Ref(self.state.documents[e.target].blue_id)))
            for k in group:
                if replacements[k]:
                    if self.meter:self.meter.owner=k
                    candidate=self.blue.substitute(bodies[k],replacements[k])
                    if self.logical:self.logical.establish(candidate,bodies[k])
                    bodies[k]=candidate
            changed=bool(members&self.dirty) or any(self.blue.identity(bodies[k])!=self.state.documents[k].blue_id for k in group)
            if not changed:continue
            cyclic=len(group)>1 or any(e.source==e.target for e in edges);positions={k:i for i,k in enumerate(group)}
            if cyclic:
                if self.meter:self.meter.owner=''
                self.charge('tentativeComponentFinalization')
            for k in group:
                if self.meter:self.meter.owner=k
                n=bodies[k]
                if cyclic:n=self.blue.substitute(n,[(e.path,L.Local(positions[e.target])) for e in sorted(edges,key=lambda e:(e.source,e.path)) if e.source==k and e.target in positions])
                if self.logical:self.logical.establish(n,None if cyclic else self.finalized.get(k),token=(lambda i:'this#'+str(i)) if cyclic else None,scope=tuple((member,self.state.documents[member].blue_id) for member in group) if cyclic else None)
            if cyclic:
                for k in group:
                    if self.meter:self.meter.owner=k
                    self.charge('cyclicMemberFinalized')
                for k,(tid,body) in self.blue.finalize_component(group,bodies,edges).items():
                    self.state.documents[k].body=L.Ref(tid,body);self.state.documents[k].blue_id=tid
            else:
                k=group[0];body=bodies[k];self.blue.remember(body);self.state.documents[k].body=body;self.state.documents[k].blue_id=self.blue.identity(body)
            if validate:
                for k in group:
                    if self.meter:self.meter.owner=k
                    if self.logical:self.logical.validate(self.state.documents[k].body,self.finalized.get(k))
                    else:self.blue.certify(self.state.documents[k].body)
            for k in group:self.finalized[k]=self.state.documents[k].body
        self.dirty.difference_update(selected);self.refresh_aliases()
        return self.state

    def finalize_local(self,key):
        """Validate an owned body without refreshing any peer or self pin.

        The document's blue_id remains its sealed input address until its turn
        seals. A private body is never registered as a live managed alias.
        """
        doc=self.state.documents[key]
        self.blue.remember(doc.body)
        if self.logical:self.logical.validate(doc.body,self.finalized.get(key))
        else:self.blue.certify(doc.body)
        self.finalized[key]=doc.body
    def verify_edges(self):
        for k,d in sorted(self.state.documents.items()):
            require(k==d.key and (self.blue.identity(d.body)==d.blue_id or '#' in d.blue_id),'INVALID_DOCUMENT_RECORD')
            if '#' in d.blue_id:
                proved=self.blue.open(L.Ref(d.blue_id));require(self.blue.identity(proved)==self.blue.identity(self.blue.open(d.body)),'INVALID_CYCLIC_BODY')
            self.blue.certify(d.body);paths=set(self.paths(d.body));actual={p for s,p in self.state.edges if s==k};require(paths==actual,'INVALID_GRAPH_BINDINGS')
            for p in sorted(paths):
                e=self.state.edges[(k,p)];require(e.target in self.state.documents,'MISSING_GRAPH_VERTEX')
                require(self.blue.identity(self.blue.exact(self.blue.select(d.body,p)))==self.state.documents[e.target].blue_id,'INVALID_GRAPH_BINDING',path=p)
                require(e.generation==d.edge_serials.get(p),'INVALID_EDGE_GENERATION')
    def routes(self,origin):
        active=self.reachable(active=True)
        if origin not in active:return []
        incoming={k:[] for k in self.state.documents}
        for e in self.state.edges.values():
            if e.source in active and e.target in active:incoming[e.target].append(e)
        todo=[(origin,(),frozenset({origin}))];result=[]
        while todo:
            node,route,seen=todo.pop()
            for e in sorted(incoming[node],key=lambda e:(e.source,e.path,e.generation),reverse=True):
                if e.source in seen and e.source!=origin:continue
                self.charge('processEmbeddedEdgeExamined');new=(e,)+route;result.append((e.source,''.join(x.path for x in new),new))
                if e.source!=origin:todo.append((e.source,new,seen|{e.source}))
        return sorted(result,key=lambda x:(x[0],x[1],tuple(e.occurrence for e in x[2])))
    def direct_routes(self, origin):
        active=self.reachable(active=True)
        if origin not in active:return []
        result=[]
        for edge in sorted(self.state.edges.values(),key=lambda e:(e.source,e.path,e.generation)):
            if edge.target==origin and edge.source in active:
                self.charge('processEmbeddedEdgeExamined')
                result.append((edge.source,edge.path,(edge,)))
        return result

    def route_live(self,route):
        active=self.reachable(active=True)
        return all(self.state.edges.get(e.key)==e and e.source in active and e.target in active for e in route)

def prepare_bundle(registry,members,root,bindings=None,archive=None):
    blue=registry.blue;token(root);require(root in members,'MISSING_ROOT');explicit={} if bindings is None else dict(bindings);nodes={}
    for key,raw in sorted(members.items()):
        token(key)
        def unpack(x,path=()):
            if isinstance(x,Link):explicit[(key,pointer(path))]=x.document;return {}
            if isinstance(x,dict):return {k:unpack(v,path+(k,)) for k,v in x.items()}
            if isinstance(x,list):return [unpack(v,path+(str(i),)) for i,v in enumerate(x)]
            return x
        try:n=L.prepare_source(blue.normalize_input(unpack(raw)),blue.context)
        except L.Failure as e:blue.translate(e)
        h=blue.head(n);require(h.kind in ('object','none') and h.items is None and h.value is L.ABSENT,'PROCESSING_DOCUMENT_NOT_OBJECT')
        for reserved in ('initialized','terminated','checkpoint'):require(registry.marker(n,reserved) is None,'AUTHORED_PROCESSOR_STATE',key=reserved)
        nodes[key]=Document(key,n)
    s=Snapshot(root,nodes,release=registry.specification,runtimes=registry.runtime_bindings)
    for (source,path),target in sorted(explicit.items()):
        require(source in nodes and target in nodes,'MISSING_GRAPH_VERTEX');nodes[source].edge_serials[path]=1;s.edges[(source,path)]=Edge(source,path,target,1)
    g=Graph(s,registry,archive or Archive());g.finalize(validate=False);g.reconcile();g.finalize();g.verify_edges();require(set(members)<=g.reachable(),'DISCONNECTED_AUTHORING_BUNDLE');blue.retain([d.body for _,d in sorted(s.documents.items())]);return s
```

### `src/blue_contracts/reference/language.py`

```python
"""Bridge to pinned Language operations. No separate BlueId algorithm."""
from __future__ import annotations
from copy import deepcopy, copy
import weakref
from collections.abc import Mapping, Sequence
from blue_host import HostIncomplete, HOST_FAILURES, incomplete, host_boundary
from algorithms import blue as L
from blue_language import Language
from blue_bex.values import UNDEFINED,blue_value,HostValue,pointer_get,kind
from .model import ContractError,NeedResources,require,segments,LIMITS

def compact(raw):
    if isinstance(raw,list):return [compact(v) for v in raw]
    if not isinstance(raw,dict):return raw
    if set(raw)=={'type','value'} and raw['type'] in ({'blueId':L.CORE[n]} for n in ('Text','Integer','Double','Boolean')):
        if raw['type']=={'blueId':L.CORE['Integer']} and type(raw['value']) is str:return L.parse_integer(raw['value'])
        return raw['value']
    if set(raw) in ({'items'},{'items','type'}) and raw.get('type',{'blueId':L.CORE['List']})=={'blueId':L.CORE['List']}:
        return [compact(v) for v in raw['items']]
    return {k:compact(v) for k,v in raw.items()}


class ExactValue(HostValue):
    """Immutable effective value over one captured exact-resolution context.

    Reading a collection never projects its descendants. Exact serialization
    retains references; it is not a lossy dictionary standing in for the value.
    """
    __slots__ = ('_blue', '_recipe', '_logical', '_depth')

    def __init__(self, blue, recipe, logical, depth=0):
        object.__setattr__(self, '_blue', blue)
        object.__setattr__(self, '_recipe', recipe)
        object.__setattr__(self, '_logical', logical)
        object.__setattr__(self, '_depth', depth)

    def __setattr__(self, name, value):
        raise TypeError('Exact values are immutable')

    def __repr__(self): return '<ExactValue>'
    def comparison_key(self): return (id(self._blue.context),self._recipe.key())
    def blue_output(self):
        return self._blue.raw(self._blue.exact(self._recipe))
    def output_view(self):
        return wire_view(self._blue.exact(self._recipe))
    def accounting_view(self):
        # A complete captured node, not its effective/display projection. A
        # composed recipe may construct a new exact value and must establish it
        # under the invocation ledger before it can supply a transfer token.
        node = (self._logical.exact(self._recipe, self._blue) if self._logical
                else self._blue.exact(self._recipe))
        identity = self._blue.known_identity(node)
        if identity is None:
            if self._logical is None:
                return wire_view(node)  # No evidence: no cheap transfer claim.
            identity = self._logical.establish(node)
        return {'blueId': identity}

    def _head(self):
        if self._logical:
            for part in self._recipe.parts:self._logical.open(part)
        return self._blue.head(self._recipe)

    def _child(self, key):
        h = self._head()
        if self._logical:
            self._logical.meter.contracts('listItemRead' if h.items is not None else 'objectMemberRead')
        child = self._blue.child(self._recipe, key)
        return self._blue.view(child, logical=self._logical,depth=self._depth+1)


class ExactObject(ExactValue, Mapping):
    def value_kind(self): return 'object'
    def __iter__(self):
        h = self._head()
        for key in sorted(h.fields):
            if L.present_recipe(L.child_recipe(h, key), self._blue.context):yield key
        n = self._blue.open(self._blue.exact(self._recipe)) if self._recipe.parts else None
        for key in ('name', 'description'):
            if n is not None and n.has(key):yield key
        if h.contracts is not None:yield 'contracts'
        if h.type_id and h.type_id not in L.CORE_NAME:yield 'type'
    def __len__(self): return sum(1 for _ in self)
    def __getitem__(self, key):
        h = self._head()
        if key == 'type' and h.type_id and h.type_id not in L.CORE_NAME:return {'blueId': h.type_id}
        if key == 'contracts' and h.contracts is not None:
            return self._blue.view(self._blue.child(self._recipe,key), logical=self._logical,depth=self._depth+1)
        if key in ('name', 'description'):
            n = self._blue.open(self._blue.exact(self._recipe))
            if n.has(key):return n.get(key)
        if key not in h.fields:raise KeyError(key)
        result = self._child(key)
        if result is UNDEFINED:raise KeyError(key)
        return result


class ExactList(ExactValue, Sequence):
    def value_kind(self): return 'list'
    def __len__(self): return len(self._head().items)
    def __getitem__(self, index):
        if isinstance(index, slice):return [self[i] for i in range(*index.indices(len(self)))]
        if not 0 <= index < len(self):raise IndexError(index)
        return self._child(index)

class WireObject(HostValue, Mapping):
    """A finite exact output manifest; references stay one-field objects."""
    def __init__(self,node):self.node=node
    def value_kind(self):return 'object'
    def __len__(self):return 1 if isinstance(self.node,L.Ref) else len(self.node.fields)
    def __iter__(self):return iter(('blueId',) if isinstance(self.node,L.Ref) else self.node.keys())
    def __getitem__(self,key):
        if isinstance(self.node,L.Ref):
            if key!='blueId':raise KeyError(key)
            return self.node.id
        value=self.node.get(key)
        if value is L.ABSENT:raise KeyError(key)
        if key in L.LITERALS|{'mergePolicy'}:return value
        return WireList(value) if key=='items' else wire_view(value)
    def blue_output(self):return L.export_tree(self.node)


class WireList(HostValue, Sequence):
    def __init__(self,items):self.items=items
    def value_kind(self):return 'list'
    def __len__(self):return len(self.items)
    def __getitem__(self,index):return wire_view(self.items[index])
    def blue_output(self):return [L.export_tree(v) for v in self.items]


def wire_view(node):
    if isinstance(node,L.Node) and node.keys()==('items',):return WireList(node.get('items'))
    return WireObject(node)


class Bridge:
    def __init__(self,language=None):
        self.language=language if language is not None else Language(core_contracts=False);self.context=self.language.processing_context()
        self._identity_witnesses={}
    def note_identity(self,node,identity=None):
        # An invocation-local handle indexes evidence issued by admission,
        # verified opening or prepaid construction. Cache presence is not proof.
        if isinstance(node,L.Node):
            key=id(node);rows=self._identity_witnesses
            ref=weakref.ref(node,lambda dead:rows.pop(key,None) if rows.get(key,(None,))[0] is dead else None)
            rows[key]=(ref,identity)
        return node
    def known_identity(self,node):
        if isinstance(node,L.Ref):return node.id
        row=self._identity_witnesses.get(id(node))
        if row is None or row[0]() is not node:return None
        if row[1] is None:
            self.note_identity(node,L.identity(node));row=self._identity_witnesses[id(node)]
        return row[1]
    def has_identity_evidence(self,node):
        if isinstance(node,L.Ref):return True
        row=self._identity_witnesses.get(id(node))
        return row is not None and row[0]() is node

    def selected_child(self,parent,child):
        """Carry exact provenance through Language's effective-head recipes.

        Head caches may return different immutable handles for the same exact
        contributions. Selecting their existing child parts derives evidence
        from the witnessed parent and verified type resolution, not those
        handles. This neither composes the parts nor validates their context.
        Literal metadata and the items sequence slot never enter this path.
        """
        if child is not None and all(self.has_identity_evidence(n) for n in parent.parts):
            for part in child.parts:
                if isinstance(part,L.Node) and not self.has_identity_evidence(part):
                    self.note_identity(part)
        return child
    def witnessed_children(self,node):
        if not isinstance(node,L.Node):return
        for key,value in node.fields:
            if key in L.LITERALS|{'mergePolicy'}:continue
            for child in value if key=='items' else (value,):
                if isinstance(child,L.Node) and id(child) not in self._identity_witnesses:self.note_identity(child)

    def refresh(self):self.context=self.language.processing_context()
    def translate(self,error):
        if isinstance(error,HOST_FAILURES):raise incomplete(error) from error
        if isinstance(error,L.Failure):
            if error.category=='OperationLimitExceeded':raise HostIncomplete(error.detail) from error
            if error.category=='ProviderUnavailable':raise NeedResources(*self.context.demands) from error
            raise ContractError('LANGUAGE_'+error.category,detail=error.detail) from error
        raise error
    def raw(self,node):return L.export_tree(node)
    def text(self,node):return L.wire_text(self.raw(node))
    def normalize_input(self,value,*,aliases=True):
        if type(value) is int and abs(value)>L.SAFE:return {'type':{'blueId':L.CORE['Integer']},'value':L.integer_text(value)}
        if type(value) is list:return [self.normalize_input(v,aliases=aliases) for v in value]
        if type(value) is not dict:return value
        out={}
        for k,v in value.items():
            if k=='value':out[k]=L.integer_text(v) if type(v) is int and abs(v)>L.SAFE else v
            elif k in L.TYPES and type(v) is str:
                require(aliases,'UNRESOLVED_RUNTIME_TYPE',alias=v)
                tid=self.language.aliases.get(v,L.CORE.get(v));require(tid is not None,'UNKNOWN_ALIAS',alias=v)
                out[k]={'blueId':tid}
            else:out[k]=self.normalize_input(v,aliases=aliases)
        return out
    def source(self,value,*,goal='value'):
        try:
            d=self.language.create(L.wire_text(self.normalize_input(value)),goal=goal,mode='source')
            self.language.publish_document(d);self.refresh();body=self.open(L.Ref(d.blue_id))
            return L.Ref(d.blue_id,body) if '#' in d.blue_id else body
        except L.Failure as e:
            if e.category=='ProviderUnavailable':
                # Source admission uses its own Language operation context;
                # self.context may have no demands from that failed operation.
                try:missing=L.final_id(e.detail)
                except L.Failure:self.translate(e)
                raise NeedResources(missing) from e
            self.translate(e)
    def node(self,value,*,goal='value',certify=True,logical=None):
        if logical is not None:return logical.node(value,goal=goal,certify=certify)
        try:
            if isinstance(value,ExactValue):value=value._blue.exact(value._recipe)
            n=value if isinstance(value,(L.Node,L.Ref)) else L.normalize(self.normalize_input(blue_value(value),aliases=False),self.context,'exact')
            if certify:self.certify(n,goal)
            self.remember(n);return n
        except L.Failure as e:self.translate(e)
    def remember(self,node):
        try:
            self.context.remember(node)
            if not isinstance(node,L.Ref):
                tid=L.identity(node);self.context.bodies[tid]=node;self.language.provider.set_exact(tid,self.text(node));self.note_identity(node,tid)
        except L.Failure as e:self.translate(e)
    def retain(self,nodes):
        """Retain complete admitted dependencies before rebuilding a resolver.

        Content retention does not publish any process head or checkpoint.
        """
        try:
            records={}
            for node in nodes:records.update(L.admitted_records(node,self.context))
            self.language.provider.merge_responses(records)
        except L.Failure as e:self.translate(e)
    def open(self,node):
        try:
            result=L.open_exact(node,self.context)
            if isinstance(node,L.Ref):self.note_identity(result,node.id if '#' not in node.id else None)
            if self.known_identity(result) is not None:self.witnessed_children(result)
            return result
        except L.Failure as e:self.translate(e)
    def identity(self,node):
        try:return L.identity(node)
        except L.Failure as e:self.translate(e)
    def certify(self,node,goal='value'):
        try:L.strict_certify(node,self.context,goal)
        except L.Failure as e:self.translate(e)
    def head(self,r):
        try:return L.head(r if isinstance(r,L.Recipe) else L.recipe(r),self.context)
        except L.Failure as e:self.translate(e)
    def exact(self,r):
        if not isinstance(r,L.Recipe):return r
        try:return L.recipe_exact_value(r,self.context)
        except L.Failure as e:self.translate(e)
    def child(self,r,k):
        r=r if isinstance(r,L.Recipe) else L.recipe(r)
        h=self.head(r)
        if k=='contracts':return self.selected_child(r,h.contracts)
        if k in L.TYPES:
            tid=getattr(h,{'type':'type_id','itemType':'item_type','keyType':'key_type','valueType':'value_type'}[k])
            return L.recipe(L.Ref(tid)) if tid is not None else None
        if k in L.LITERALS:
            value=h.value if k=='value' else h.labels.get(k,L.ABSENT)
            if value is L.ABSENT:return None
            return L.recipe(L.normalize(self.normalize_input(value),self.context,'exact'))
        if k in ('schema','mergePolicy'):
            node=self.open(self.exact(r));value=node.get(k)
            if value is L.ABSENT:return None
            return L.recipe(L.scalar('Text',value) if k=='mergePolicy' else value)
        if h.items is not None:
            if k=='-':return None
            if isinstance(k,str):
                require(k=='0' or k.isascii() and k.isdigit() and not k.startswith('0'),'INVALID_LIST_INDEX');k=int(k)
            return self.selected_child(r,L.child_recipe(h,k)) if 0<=k<len(h.items) else None
        return self.selected_child(r,L.child_recipe(h,k)) if k in h.fields else None
    def select(self,node,path):
        r=L.recipe(node)
        for k in segments(path):
            r=self.child(r,k)
            if r is None:return None
        return r
    def project(self,r,*,definitions=False,seen=frozenset(),depth=0,preserve_cyclic=False):
        if r is None:return UNDEFINED
        r=r if isinstance(r,L.Recipe) else L.recipe(r)
        if preserve_cyclic:
            exact=self.exact(r)
            if isinstance(exact,L.Ref) and '#' in exact.id:return {'blueId':exact.id}
        h=self.head(r)
        if h.value is not L.ABSENT:return h.value
        key=r.key()
        if key in seen:return {'blueId':self.identity(self.exact(r))}
        seen=seen|{key}
        if h.items is not None:return [self.project(L.child_recipe(h,i),definitions=definitions,seen=seen,depth=depth+1,preserve_cyclic=preserve_cyclic) for i in range(len(h.items))]
        out={}
        for k in sorted(h.fields):
            ch=L.child_recipe(h,k)
            if definitions or L.present_recipe(ch,self.context):out[k]=self.project(ch,definitions=definitions,seen=seen,depth=depth+1,preserve_cyclic=preserve_cyclic)
        n=self.open(self.exact(r)) if r.parts else None
        for k in ('name','description'):
            if n is not None and n.has(k):out[k]=n.get(k)
        if h.contracts is not None:out['contracts']=self.literal(h.contracts)
        if h.type_id and h.type_id not in L.CORE_NAME:out['type']={'blueId':h.type_id}
        if not definitions and not out and not L.concrete(h,self.context):return UNDEFINED
        return out
    def view(self, r, *, logical=None, depth=0):
        if r is None:return UNDEFINED
        r = r if isinstance(r, L.Recipe) else L.recipe(r)
        captured = copy(self)  # Capture resolver/context, not a future refresh.
        if logical:
            for part in r.parts:logical.open(part)
        h = captured.head(r)
        if h.value is not L.ABSENT:return h.value
        if h.items is not None:return ExactList(captured, r, logical,depth)
        if not (h.contracts is not None or h.type_id and h.type_id not in L.CORE_NAME or
                h.labels.get('name') is not None or h.labels.get('description') is not None or
                L.concrete(h, captured.context)):return UNDEFINED
        return ExactObject(captured, r, logical,depth)
    def literal(self,r):return compact(self.raw(self.open(self.exact(r))))
    def bex_data(self,r,*,seen=frozenset(),depth=0):
        n=self.exact(r)
        if isinstance(n,L.Ref):
            if '#' in n.id or n.id in seen:return {'blueId':n.id}
            seen=seen|{n.id}
        n=self.open(n);out={}
        for k,v in n.fields:
            if k in L.LITERALS or k=='mergePolicy':out[k]=v
            elif k in L.TYPES:out[k]=self.raw(v)
            elif k=='items':out[k]=[self.bex_data(x,seen=seen,depth=depth+1) for x in v]
            else:out[k]=self.bex_data(v,seen=seen,depth=depth+1)
        return compact(out)
    def read(self,node,path,view='canonical'):
        require(view in ('canonical','resolved'),'INVALID_VIEW');r=self.select(node,path)
        return self.project(r) if r is not None else UNDEFINED
    def read_bex(self,value,path):
        if isinstance(value, HostValue):return pointer_get(value,path)
        at=value
        for k in segments('' if path=='/' else path):
            if isinstance(at,dict) and set(at)=={'blueId'}:at=self.view(L.Ref(at['blueId']))
            if kind(at)=='object':at=at.get(k,UNDEFINED)
            elif kind(at)=='list':
                if not k.isdigit() or k!='0' and k.startswith('0'):return UNDEFINED
                i=int(k);at=at[i] if i<len(at) else UNDEFINED
            else:return UNDEFINED
        return deepcopy(at)
    def matches(self,value,pattern,*,logical=None):
        """Actual-field matching; Language validates types and constraints.

        The presence pass prevents refine_exact from supplying the event with
        fields contributed only by the filter. Invalid evidence is an error,
        not an ordinary false match. No Language operation is modified.
        """
        n=self.node(self.exact(value),logical=logical);p=self.node(self.exact(pattern),goal='definition',logical=logical)
        def present(actual, wanted, seen=frozenset(), depth=0):
            pair=(actual.key(),wanted.key())
            if pair in seen:return True
            seen=seen|{pair}; ah=self.head(actual); ph=self.head(wanted)
            if ph.type_id is not None:
                if ah.type_id is None:return False
                if ph.type_id not in L.ancestry(ah.type_id,self.context):return False
            authored=self.open(self.exact(wanted))
            if ph.items is not None:
                if ah.items is None or len(ah.items)<len(ph.items):return False
                for i in range(len(ph.items)):
                    if not present(L.child_recipe(ah,i),L.child_recipe(ph,i),seen,depth+1):return False
            for key in sorted(ph.fields):
                expected=L.child_recipe(ph,key)
                # Catalogue type-only optional declarations are not explicitly
                # supplied filter fields. Concrete inherited values do count.
                if not authored.has(key) and not L.present_recipe(expected,self.context):continue
                actual_child=self.child(actual,key)
                if actual_child is None or not L.present_recipe(actual_child,self.context):return False
                if not present(actual_child,expected,seen,depth+1):return False
            return True
        if not present(L.recipe(n),L.recipe(p)):return False
        try:
            L.refine_exact(p,n,self.context)
            return True
        except L.Failure as e:
            if e.category in ('TypeCompatibilityViolation','SchemaViolation','FixedValueConflict',
                              'CollectionCompatibilityViolation','InvalidCollectionType','IncompatibleTypes'):
                return False
            self.translate(e)
    def set_at(self,root,path,val=None,*,op='replace'):
        parts=segments(path);require(parts and all(parts),'INVALID_PATCH_PATH',path=path)
        return self._set(root,L.recipe(root),parts,val,op)
    def _set(self,n,r,parts,val,op):
        n=self.open(n);h=self.head(r);key=parts[0];require(isinstance(n,L.Node),'INVALID_PATCH_PARENT');m=dict(n.fields)
        if h.items is not None:
            require(key=='-' and op=='add' and len(parts)==1 or key=='0' or key.isascii() and key.isdigit() and not key.startswith('0'),'INVALID_LIST_INDEX')
            values=[self.exact(L.child_recipe(h,i)) for i in range(len(h.items))];i=len(values) if key=='-' else int(key)
            require(i<=len(values) if op=='add' and len(parts)==1 else i<len(values),'INVALID_LIST_INDEX')
            if len(parts)>1:values[i]=self._set(values[i],L.child_recipe(h,i),parts[1:],val,op)
            elif op=='remove':values.pop(i)
            elif op=='add':values.insert(i,val)
            else:values[i]=val
            m['items']=tuple(values)
        elif key in L.LITERALS:
            require(len(parts)==1,'INVALID_PATCH_PATH')
            if op=='remove':require(key in m,'MISSING_PATCH_TARGET');m.pop(key)
            else:
                v=self.head(val).value;require(v is not L.ABSENT,'INVALID_LITERAL');m[key]=v
        else:
            child=self.child(r,key)
            if len(parts)>1:
                require(child is not None,'MISSING_PATCH_PARENT');m[key]=self._set(self.exact(child),child,parts[1:],val,op)
            elif op=='remove':require(key in m,'MISSING_PATCH_TARGET');m.pop(key)
            else:
                if key in L.TYPES:
                    self.remember(val);m[key]=L.Ref(self.identity(val))
                else:m[key]=val
        try:return L.node(m)
        except L.Failure as e:self.translate(e)
    def substitute(self,root,replacements):
        """Set disjoint symbolic edges together; never hash a partial Local graph."""
        rows=[(segments(path),value) for path,value in replacements]
        def visit(n,r,rows):
            n=self.open(n);h=self.head(r);m=dict(n.fields);grouped={}
            for path,value in rows:
                require(path,'INVALID_SYMBOLIC_PATH');grouped.setdefault(path[0],[]).append((path[1:],value))
            if h.items is not None:
                values=[self.exact(L.child_recipe(h,i)) for i in range(len(h.items))]
                for key,items in sorted(grouped.items()):
                    require(key.isdigit() and (key=='0' or not key.startswith('0')),'INVALID_LIST_INDEX');i=int(key);require(i<len(values),'INVALID_LIST_INDEX')
                    if not items[0][0]:require(len(items)==1,'OVERLAPPING_SYMBOLIC_PATH');values[i]=items[0][1]
                    else:values[i]=visit(values[i],L.child_recipe(h,i),items)
                m['items']=tuple(values)
            else:
                for key,items in sorted(grouped.items()):
                    if not items[0][0]:require(len(items)==1,'OVERLAPPING_SYMBOLIC_PATH');m[key]=items[0][1]
                    else:
                        ch=self.child(r,key);require(ch is not None,'MISSING_SYMBOLIC_PATH');m[key]=visit(self.exact(ch),ch,items)
            return L.node(m)
        return visit(root,L.recipe(root),rows) if rows else root
    def finalize_component(self,keys,bodies,edges):
        position={k:i for i,k in enumerate(keys)};raw=[]
        for k in keys:
            replacements=[(e.path,L.Local(position[e.target])) for e in sorted(edges,key=lambda e:(e.source,e.path)) if e.source==k and e.target in position]
            raw.append(self.raw(self.substitute(bodies[k],replacements)))
        try:
            result=L.finalize_set(raw,self.context);proof={'members':[self.raw(n) for n in result['canonical']]};out={}
            for i,k in enumerate(keys):
                tid=result['ids'][i];n=result['bodies'][int(tid.split('#')[1])];response={'proof':L.wire_text(proof),'body':self.text(n)}
                self.language.provider.set_response(tid,response);self.context.provider[tid]=response;self.context.bodies[tid]=n;self.context.proofs[tid]=proof;out[k]=(tid,n)
            return out
        except L.Failure as e:self.translate(e)
```

### `src/blue_contracts/reference/model.py`

```python
"""Closed records, portable commitments, errors, limits and a shared live meter."""
from __future__ import annotations
from dataclasses import dataclass, field
from copy import deepcopy
import hashlib, json, unicodedata
from pathlib import Path
from typing import Any
from blue_bex import GasExhausted
from blue_bex.gas import DEFAULT as BEX_GAS

SAFE=(1<<53)-1
DEFAULT_LIMIT=100000
LIMITS = {}  # No universal structural ceilings; retained compatibility export.
GAS_PROFILE=json.loads((Path(__file__).resolve().parents[1]/'GAS_MANIFEST.json').read_text())
TARIFF=GAS_PROFILE['weights']

class ContractError(Exception):
    def __init__(self,code,**context):
        self.code=code;self.context=deepcopy(context)
        super().__init__(code+(': '+str(context) if context else ''))
class NeedResources(ContractError):
    def __init__(self,*ids):super().__init__('NEEDS_RESOURCES',required=sorted(set(ids)))
def require(condition,code,**context):
    if not condition:raise ContractError(code,**context)
def token(value):
    require(type(value) is str and bool(value) and '\0' not in value and unicodedata.normalize('NFC',value)==value,'INVALID_TOKEN')
    return value
def integer(value,minimum=0,maximum=SAFE):
    require(type(value) is int and value>=minimum and (maximum is None or value<=maximum),'INVALID_INTEGER',minimum=minimum,maximum=maximum);return value
def closed(value,required,optional=frozenset()):
    require(type(value) is dict and set(required)<=set(value)<=set(required)|set(optional),'INVALID_RECORD')
    return value

def canonical(value):
    """Canonical platform bytes; deliberately not the BlueId algorithm."""
    if value is None:return b'null'
    if type(value) is bool:return b'true' if value else b'false'
    if type(value) is int:
        from decimal import Decimal
        return str(Decimal(value)).encode('ascii')
    if type(value) is str:
        value.encode('utf-8');return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    if type(value) in (list,tuple):return b'['+b','.join(canonical(v) for v in value)+b']'
    require(type(value) is dict and all(type(k) is str for k in value),'INVALID_RECORD')
    return b'{'+b','.join(canonical(k)+b':'+canonical(value[k]) for k in sorted(value))+b'}'
def digest(kind,value):return 'sha256:'+hashlib.sha256(canonical({'kind':kind,'value':value})).hexdigest()
def segments(path):
    require(type(path) is str and unicodedata.normalize('NFC',path)==path,'INVALID_POINTER')
    if path=='':return ()
    require(path.startswith('/'),'INVALID_POINTER');parts=[]
    for raw in path[1:].split('/'):
        out='';i=0
        while i<len(raw):
            if raw[i]=='~':
                require(i+1<len(raw) and raw[i+1] in '01','INVALID_POINTER');out+='~' if raw[i+1]=='0' else '/';i+=2
            else:out+=raw[i];i+=1
        parts.append(out)
    return tuple(parts)
def pointer(parts):return ''.join('/'+p.replace('~','~0').replace('/','~1') for p in parts)
def prefix(a,b):
    x,y=segments(a),segments(b);return y[:len(x)]==x

@dataclass(frozen=True)
class ChannelLife:
    generation:int
    signature:str
    def wire(self):return dict(generation=self.generation,signature=self.signature)
@dataclass(frozen=True)
class Edge:
    source:str
    path:str
    target:str
    generation:int
    @property
    def key(self):return self.source,self.path
    @property
    def occurrence(self):return self.source,self.path,self.target,self.generation
    def wire(self):return dict(source=self.source,path=self.path,target=self.target,generation=self.generation)
@dataclass
class Document:
    key:str
    body:Any
    blue_id:str=''
    channel_lives:dict=field(default_factory=dict)
    channel_serials:dict=field(default_factory=dict)
    edge_serials:dict=field(default_factory=dict)
    birth:str|None=None
    def metadata(self):return dict(key=self.key,blueId=self.blue_id,channels={k:v.wire() for k,v in sorted(self.channel_lives.items())},channelSerials=dict(sorted(self.channel_serials.items())),edgeSerials=dict(sorted(self.edge_serials.items())),birth=self.birth)
@dataclass
class Snapshot:
    root:str
    documents:dict
    edges:dict=field(default_factory=dict)
    generation:int=0
    revision:int=0
    release:str=''
    runtimes:tuple=()
    def copy(self):return deepcopy(self)
    def wire(self):return dict(root=self.root,documents=[d.metadata() for _,d in sorted(self.documents.items())],edges=[e.wire() for _,e in sorted(self.edges.items())],generation=self.generation,revision=self.revision,release=self.release,runtimes=list(self.runtimes))
    @property
    def identity(self):return digest('contracts.snapshot/completion-1',self.wire())
class Meter:
    def __init__(self,limit=DEFAULT_LIMIT,local_limits=None,known_members=None):
        integer(limit,0,DEFAULT_LIMIT);self.limit=limit;self.used=0;self.trace=[];self.rejected=None;self.owner='';self.schedule=dict(BEX_GAS)
        require(local_limits is None or type(local_limits) is dict,'INVALID_LOCAL_LIMITS')
        self.local_limits=dict(local_limits or {});self.local_used={};self.runtime_schedules={}
        for member,ceiling in self.local_limits.items():
            token(member);integer(ceiling,0,limit)
            require(known_members is None or member in known_members,'UNKNOWN_CAP_TARGET',member=member)
    def policy(self):return {'shared':self.limit,'local':dict(sorted(self.local_limits.items())),'profile':GAS_PROFILE['profile']}
    def debit(self,namespace,counter,units,amount):
        if self.rejected is not None:raise GasExhausted(self.rejected['counter'])
        integer(units,maximum=None);integer(amount,maximum=None)
        row=dict(ordinal=len(self.trace),namespace=namespace,counter=counter,units=units,amount=amount,owner=self.owner)
        shared=self.limit-self.used;local=self.local_limits[self.owner]-self.local_used.get(self.owner,0) if self.owner in self.local_limits else None
        if amount>shared or local is not None and amount>local:
            local_first=local is not None and local<shared
            self.rejected=dict(row,remaining=local if local_first else shared,cap='LOCAL' if local_first else 'SHARED',sharedRemaining=shared,localRemaining=local)
            raise GasExhausted(counter)
        self.trace.append(row);self.used+=amount
        if self.owner:self.local_used[self.owner]=self.local_used.get(self.owner,0)+amount
    def charge(self,counter,units=1,*,amount=None):self.debit('bex',counter,units,self.schedule[counter]*units if amount is None else amount)
    def contracts(self,counter,units=1):
        integer(units,maximum=None)
        if units:self.debit('contracts',counter,units,TARIFF[counter]*units)
@dataclass
class Outcome:
    status:str
    snapshot:Snapshot
    input_identity:str
    invocation:str
    public_events:list=field(default_factory=list)
    event_trace:list=field(default_factory=list)
    work_trace:list=field(default_factory=list)
    changes:list=field(default_factory=list)
    checkpoints:list=field(default_factory=list)
    gas:int=0
    gas_trace:list=field(default_factory=list)
    rejected:Any=None
    diagnostic:Any=None
    completions:list=field(default_factory=list)
    rounds:list=field(default_factory=list)
    units:list=field(default_factory=list)
    @property
    def document(self):
        return self.snapshot
    @property
    def emitted_events(self):
        """Exact emitted values, in FIFO creation order, for this selected root."""
        return tuple({'blueId': row['event']} for row in self.public_events)
    def __iter__(self):
        yield self.document
        yield self.emitted_events
        yield self.gas
    @property
    def commits(self):return self.status=='APPLIED'
    def observations(self):return dict(status=self.status,input=self.input_identity,output=self.snapshot.identity,invocation=self.invocation,publicEvents=self.public_events,events=self.event_trace,work=self.work_trace,changes=self.changes,checkpoints=self.checkpoints,gas=self.gas,gasTrace=self.gas_trace,rejected=self.rejected,diagnostic=self.diagnostic,completions=self.completions,rounds=self.rounds,units=self.units)
    @property
    def receipt(self):return digest('contracts.result/completion-1',self.observations())
def trampoline(generator):
    stack=[generator]
    try:
        while stack:
            try:
                child=next(stack[-1])
                if child is not None:stack.append(child)
            except StopIteration:stack.pop()
    finally:
        for pending in reversed(stack):pending.close()
```

### `src/blue_contracts/reference/policy.py`

```python
"""Exact selection rule; node validity and subtype relation belong to Language."""
from dataclasses import dataclass
from typing import Callable, Optional, Any
import unicodedata

class GeneralizationError(ValueError):
    """A policy or a permitted ancestor search cannot establish a valid result."""


def pointer_segments(path: str) -> tuple[str, ...]:
    if not isinstance(path, str) or unicodedata.normalize('NFC',path)!=path:
        raise GeneralizationError('INVALID_POINTER')
    if path == '':
        return ()
    if not path.startswith('/'):
        raise GeneralizationError('INVALID_POINTER')
    result = []
    for raw in path[1:].split('/'):
        if raw == '':
            raise GeneralizationError('INVALID_POINTER')
        i = 0
        while i < len(raw):
            if raw[i] == '~':
                if i + 1 >= len(raw) or raw[i + 1] not in '01':
                    raise GeneralizationError('INVALID_POINTER')
                i += 2
            else:
                i += 1
        result.append(raw.replace('~1', '/').replace('~0', '~'))
    return tuple(result)


@dataclass(frozen=True)
class GeneralizationRule:
    path: str
    mode: str
    must_remain_subtype_of: Optional[str] = None

    def __post_init__(self) -> None:
        pointer_segments(self.path)
        if self.mode not in ('reject', 'nearest-valid-ancestor'):
            raise GeneralizationError('INVALID_MODE')
        if self.must_remain_subtype_of is not None and not isinstance(self.must_remain_subtype_of, str):
            raise GeneralizationError('INVALID_FLOOR')


@dataclass(frozen=True)
class GeneralizationPolicy:
    rules: tuple[GeneralizationRule, ...] = ()
    default_mode: str = 'reject'

    def __post_init__(self) -> None:
        if self.default_mode not in ('reject', 'nearest-valid-ancestor'):
            raise GeneralizationError('INVALID_MODE')
        if not isinstance(self.rules, tuple):
            raise GeneralizationError('RULES_MUST_BE_IMMUTABLE')
        if any(not isinstance(rule, GeneralizationRule) for rule in self.rules):
            raise GeneralizationError('INVALID_RULE')

    def select(self, path: str) -> GeneralizationRule:
        segments = pointer_segments(path)
        selected = GeneralizationRule('', self.default_mode)
        depth = -1
        for rule in self.rules:
            candidate = pointer_segments(rule.path)
            if len(candidate) > depth and segments[:len(candidate)] == candidate:
                selected, depth = rule, len(candidate)
        return selected


def choose_type(
    current_type: str,
    changed_node: Any,
    path: str,
    policy: GeneralizationPolicy,
    *,
    immediate_ancestor: Callable[[str], Optional[str]],
    valid_with_type: Callable[[Any, str], bool],
    is_subtype: Callable[[str, str], bool],
    charge_candidate: Callable[[str], None] = lambda _: None,
) -> str:
    """Return the unchanged type or the nearest policy-permitted valid ancestor.

    valid_with_type MUST include unchanged local requirements and the exact
    containing context. Missing evidence must raise, not return False. This
    function does not rewrite a node, weaken a schema or issue a checkpoint.
    The owning transaction applies and validates the generated type write.
    """
    rule = policy.select(path)
    seen: set[str] = set()
    candidate: Optional[str] = current_type
    while candidate is not None:
        if candidate in seen:
            raise GeneralizationError('CYCLIC_TYPE_ANCESTRY')
        seen.add(candidate)
        charge_candidate(candidate)
        floor_ok = rule.must_remain_subtype_of is None or is_subtype(candidate, rule.must_remain_subtype_of)
        if floor_ok and valid_with_type(changed_node, candidate):
            return candidate
        if rule.mode == 'reject':
            raise GeneralizationError('TYPE_COMPATIBILITY_VIOLATION')
        if not floor_ok:
            raise GeneralizationError('TYPE_GENERALIZATION_FLOOR')
        candidate = immediate_ancestor(candidate)
    raise GeneralizationError('TYPE_GENERALIZATION_FAILURE')
```

### `src/blue_contracts/reference/processor.py`

```python
"""One event, one isolated rooted transition and one atomic result.

The continuation machine defines graph/lifecycle behavior; it is not a callback
asking a host to invent missing semantics.
"""
from collections import deque
from copy import deepcopy
import json
from blue_host import HostIncomplete, HOST_FAILURES, incomplete, host_boundary
from algorithms import blue as L
from blue_bex import Engine as Bex,Context,GasExhausted,BexError
from blue_bex.values import UNDEFINED
from .model import Outcome,Meter,ContractError,NeedResources,require,closed,integer,segments,pointer,prefix,digest,LIMITS,trampoline
from .language import Bridge
from .registry import Registry,EXTERNAL,EXECUTABLE,MARKERS
from .graph import Graph,Archive,prepare_bundle,components
from .channels import refresh_lifetimes,signature,checkpoint,event_observation,recognize_call,select_seeds

class Processor:
    def __init__(self, language=None, *, gas_limit=100000, local_limits=None, local_driver=False):
        self.blue=Bridge(language); self.registry=Registry(self.blue)
        self.archive=Archive(); self.bex=Bex()
        from .receiving import CompletionStore
        self._completion_store=CompletionStore()
        self._completion_reader=None
        self.local_driver=bool(local_driver)
        integer(gas_limit, 0, 100000)
        self.gas_limit=gas_limit; self.local_limits=deepcopy(local_limits or {})
    def typed(self,type_name,**fields):return self.registry.typed(type_name,**fields)
    def install_runtime(self,binding,implementation):self.registry.install(binding,implementation)
    @host_boundary
    def admit(self,members,root='root',*,bindings=None,gas_limit=None,local_limits=None):
        s=prepare_bundle(self.registry,members,root,bindings,archive=self.archive);g=Graph(s,self.registry,self.archive);refresh_lifetimes(g)
        return Run(self,s,None,None,self.gas_limit if gas_limit is None else gas_limit,admission=True,local_limits=self.local_limits if local_limits is None else local_limits).attempt()
    @host_boundary
    def create(self,document,*,gas_limit=None):
        result=self.admit({'root':document},gas_limit=gas_limit);require(result.commits,'ADMISSION_FAILED',status=result.status,diagnostic=result.diagnostic);return result.snapshot
    @host_boundary
    def validate(self,snapshot,*,require_initialized=True):
        require(snapshot.release==self.registry.specification,'INCOMPATIBLE_RELEASE');require(snapshot.root in snapshot.documents,'MISSING_ROOT');integer(snapshot.revision);integer(snapshot.generation)
        require(digest('runtime-bindings',snapshot.runtimes)==digest('runtime-bindings',self.registry.runtime_bindings),'INCOMPATIBLE_RUNTIME_BINDINGS')
        g=Graph(snapshot,self.registry,self.archive);g.verify_edges()
        for key,doc in sorted(snapshot.documents.items()):
            h=self.blue.head(doc.body);require(h.kind in ('object','none') and h.items is None and h.value is L.ABSENT,'PROCESSING_DOCUMENT_NOT_OBJECT')
            for reserved in MARKERS:
                marker=self.registry.marker(doc.body,reserved)
                if marker is None:continue
                value=self.blue.literal(marker)
                if reserved=='initialized':
                    closed(value,{'type','document'});closed(value['document'],{'blueId'});self.blue.open(L.Ref(value['document']['blueId']))
                elif reserved=='terminated':
                    closed(value,{'type','cause'},{'reason'});require(type(value['cause']) is str and ('reason' not in value or type(value['reason']) is str),'INVALID_TERMINATION')
                else:
                    closed(value,{'type','entries'});require(type(value['entries']) is dict,'INVALID_CHECKPOINT')
                    for channel,row in sorted(value['entries'].items()):
                        require(channel in doc.channel_lives,'INVALID_CHECKPOINT_CHANNEL');closed(row,{'timestamp','event'});integer(row['timestamp']);closed(row['event'],{'blueId'});self.blue.open(L.Ref(row['event']['blueId']))
        for key in sorted(g.reachable(active=True)):
            doc=snapshot.documents[key];cs=self.registry.contracts(doc.body);actual={k:signature(cs,k) for k,c in cs.items() if c['_role'] in EXTERNAL}
            require(set(actual)==set(doc.channel_lives),'INVALID_CHANNEL_LIFETIMES')
            for k,sig in sorted(actual.items()):
                life=doc.channel_lives[k];require(life.signature==sig and life.generation==doc.channel_serials.get(k),'INVALID_CHANNEL_LIFETIME')
                checkpoint(self.registry,doc,k)
            if require_initialized:require(self.registry.marker(doc.body,'initialized') is not None,'UNINITIALIZED_SNAPSHOT')
        return True
    @host_boundary
    def initialize(self, document):
        """Explicit lifecycle action. It supplies no external event or time."""
        from .model import Snapshot
        if isinstance(document, Snapshot):
            return Run(self,document,None,None,self.gas_limit,admission=True,local_limits=self.local_limits).attempt()
        return self.admit({'root':document})

    @host_boundary
    def process(self, document, event, eventTimestamp):
        """Process the complete original event. Exactly three input arguments.

        A Snapshot is the SDK's verified selected document/graph representation.
        A fresh Source object is admitted and initialized within this attempt.
        Gas policy, exact content and installed runtimes are processor configuration.
        """
        from .model import Snapshot
        integer(eventTimestamp)
        if not isinstance(document, Snapshot):
            document=prepare_bundle(self.registry,{'root':document},'root',archive=self.archive)
            refresh_lifetimes(Graph(document,self.registry,self.archive))
        original=self.blue.node(event) if isinstance(event,(L.Node,L.Ref)) else self.blue.source(event)
        return Run(self,document,original,eventTimestamp,self.gas_limit,local_limits=self.local_limits).attempt()

    @host_boundary
    def begin(self, document, event, eventTimestamp):
        """Open an atomic chunked invocation; no chunk publishes state."""
        from .chunks import Attempt
        from .model import Snapshot
        integer(eventTimestamp)
        if not isinstance(document,Snapshot):
            document=prepare_bundle(self.registry,{'root':document},'root',archive=self.archive)
            refresh_lifetimes(Graph(document,self.registry,self.archive))
        original=self.blue.node(event) if isinstance(event,(L.Node,L.Ref)) else self.blue.source(event)
        return Attempt(Run(self,document,original,eventTimestamp,self.gas_limit,local_limits=self.local_limits))
    @host_boundary
    def next_chunk(self,attempt):return attempt.next_chunk()
    @host_boundary
    def prepare_invocation(self, document, event, eventTimestamp, *, evidence):
        """Verify frozen external-runtime evidence for a chunked invocation.

        This is configuration of the installed runtime. process itself remains
        the three-input document/event/timestamp operation.
        """
        from .chunks import Attempt
        integer(eventTimestamp)
        self.validate(document)
        original=self.blue.node(event) if isinstance(event,(L.Node,L.Ref)) else self.blue.source(event)
        return Attempt(Run(self,document,original,eventTimestamp,self.gas_limit,
                           local_limits=self.local_limits,admission_evidence=evidence))
    @host_boundary
    def execute_chunk(self,token):
        from .chunks import execute
        return execute(self,token)
    @host_boundary
    def accept_chunk(self,attempt,token,completion):return attempt.accept_chunk(token,completion)
    @host_boundary
    def finish(self,attempt):return attempt.finish()
    @host_boundary
    def complete_local(self,attempt):
        require(attempt.run.engine is self,'WRONG_CHUNK_EXECUTOR')
        return attempt.finish_local()
    def capture_source_outcome(self, outcome, owned_members=None):
        return self._completion_store.capture(outcome, owned_members or [outcome.snapshot.root])
    @host_boundary
    def begin_receiving_application(self, document, source_completions):
        from .receiving import begin_receiving
        return begin_receiving(self, document, source_completions)
    @host_boundary
    def begin_live_application(self, document, source_completions, *, evidence):
        """Complete a LIVE cause with retained children and frozen own seeds.

        Historical application uses begin_receiving_application instead. Both
        paths require locally established completion capabilities; the public
        three-input process API is unchanged.
        """
        from .receiving import begin_receiving
        return begin_receiving(self, document, source_completions, live=True, evidence=evidence)
    def install_completion_reader(self, reader):
        """Configure a trusted local publication store, never request evidence.

        The adapter must authenticate its own protected committed records and
        exact runtime binding. Foreign serialized results require replay first.
        Like install_runtime, this is privileged host configuration.
        """
        require(self._completion_reader is None,'COMPLETION_READER_ALREADY_INSTALLED')
        require(callable(getattr(reader,'read_completed',None)),'INVALID_COMPLETION_READER')
        self._completion_reader=reader
    def load_source_completion(self, reference, owned_members):
        require(self._completion_reader is not None,'NO_LOCAL_COMPLETION_READER')
        before,outcome,event,timestamp=self._completion_reader.read_completed(self,reference)
        require(outcome.commits and outcome.input_identity==before.identity,'INVALID_STORED_COMPLETION')
        self.validate(before);self.validate(outcome.snapshot)
        self._completion_store.remember(before,outcome,event,timestamp)
        return self.capture_source_outcome(outcome,owned_members)

    def emitted(self, result):
        return [self.blue.project(L.Ref(e['event']),preserve_cyclic=True) for e in result.public_events]

    def read(self,snapshot,path='',*,document=None):return self.blue.read(snapshot.documents[document or snapshot.root].body,path)

    def observe_execution(self, kind, **record):
        """Optional host diagnostics; records are detached from runtime state."""
        observer = getattr(self, 'execution_observer', None)
        if observer is not None:observer(kind, deepcopy(record))

from .completion import CompletionMachine

class Run(CompletionMachine):
    def __init__(self,engine,state,event,timestamp,gas_limit,admission=False,local_limits=None,admission_evidence=None):
        self.engine=engine;self.blue=engine.blue;self.reg=engine.registry
        self.input=state;self.state=state.copy();self.event=event;self.timestamp=timestamp
        self.event_id=self.blue.identity(event) if event is not None else None
        self.call=None;self.call_record=None;self.seeds=()
        self.admission_evidence=deepcopy(admission_evidence or {});self.external_admissions={}
        self.admission=admission;self.meter=Meter(gas_limit,local_limits,state.documents)
        self.views=engine.archive.bindings()
        self.invocation=digest('contracts.invocation/completion-1',dict(input=state.identity,event=self.event_id,
            timestamp=timestamp,gas=self.meter.policy(),release=engine.registry.specification))
        self.graph=Graph(self.state,self.reg,engine.archive.restrict(self.views),self.meter,self.invocation)
        if self.event_id:self.graph.logical.carried_roots.add(self.event_id)
        self.queue=deque();self.events=[];self.work=[];self.public=[];self.writes=[]
        self.initializing=set();self.initialized={};self.terminating=set();self.termination={}
        self.settlements=[];self.effect_count=0
        self.opened=set();self.headers=set();self.activation={k:0 for k in state.documents}
        self.setup_completion();self.graph.changes=self.changes
    def runtime_node(self,value,**kwargs):
        if self.frame is not None:self.meter.owner=self.frame.key
        return self.blue.node(value,logical=self.graph.logical,**kwargs)
    def runtime_matches(self,value,pattern):
        if self.frame is not None:self.meter.owner=self.frame.key
        return self.blue.matches(value,pattern,logical=self.graph.logical)
    @property
    def cause_order(self):
        # An immutable cause token, NOT an external ordering relation.
        return self.event_id
    def fail_result(self,status,diagnostic):
        return Outcome(status,self.input.copy(),self.input.identity,self.invocation,event_trace=deepcopy(self.events),work_trace=deepcopy(self.work),gas=self.meter.used,gas_trace=deepcopy(self.meter.trace),rejected=deepcopy(self.meter.rejected),diagnostic=diagnostic)
    def attempt(self):
        from .chunks import Attempt
        attempt=Attempt(self)
        if self.engine.local_driver:return attempt.finish_local()
        while (token:=attempt.next_chunk()) is not None:
            attempt.accept_chunk(token,attempt.execute_chunk(token))
        return attempt.finish()
    def guard(self,action):
        try:return action()
        except HOST_FAILURES as e:raise incomplete(e) from e
        except GasExhausted:return self.fail_result('GAS_LIMIT_EXCEEDED',{'code':'GAS_LIMIT_EXCEEDED'})
        except NeedResources as e:return Outcome('NEEDS_RESOURCES',self.input.copy(),self.input.identity,self.invocation,diagnostic={'code':e.code,**e.context})
        except ContractError as e:return self.fail_result('FAILED',{'code':e.code,**e.context})
        except L.Failure as e:
            if e.category=='OperationLimitExceeded':raise HostIncomplete(e.detail) from e
            if e.category=='ProviderUnavailable':return Outcome('NEEDS_RESOURCES',self.input.copy(),self.input.identity,self.invocation,diagnostic={'code':'NEEDS_RESOURCES','required':sorted(set(self.blue.context.demands))})
            return self.fail_result('FAILED',{'code':'LANGUAGE_'+e.category,'detail':e.detail})
        except BexError as e:return self.fail_result('FAILED',{'code':'BEX_'+getattr(e,'code',type(e).__name__)})
    def begin_work(self):
        self.meter.contracts('processInvocation');self.meter.contracts('closureInvocation')
        self.preflight();self.engine.validate(self.input,require_initialized=False)
        if not self.admission:
            from .runtime import prepare_admissions
            prepare_admissions(self)
            self.call,self.call_record=recognize_call(self.reg,self.event)
            self.seeds=select_seeds(self)
        self.meter.owner=''
        if self.graph.terminated(self.state.root):return self.fail_result('TERMINATED',None)
        self.phase=self.new_phase('INITIALIZE')
    def ready(self):
        while self.phase is not None:
            unit=self.next_unit(self.phase)
            if unit is not None:return unit
            self.phase=self.new_phase('PROCESS') if self.phase.name=='INITIALIZE' and not self.admission else None
        return None
    def finish_work(self):
        self.graph.finalize();self.preflight()
        self.state.revision=integer(self.input.revision+1)
        if self.topology_changed:self.state.generation=integer(self.input.generation+1)
        self.engine.validate(self.state)
        for event in self.events:
            if event['document']==self.state.root:
                self.meter.owner=self.state.root;self.meter.contracts('rootEventRecorded');self.public.append(deepcopy(event))
        result=Outcome('APPLIED',self.state,self.input.identity,self.invocation,public_events=deepcopy(self.public),event_trace=deepcopy(self.events),work_trace=deepcopy(self.work),changes=deepcopy(self.changes),checkpoints=deepcopy(self.writes),gas=self.meter.used,gas_trace=deepcopy(self.meter.trace),completions=deepcopy(self.turns),rounds=deepcopy(self.rounds),units=deepcopy(self.units))
        self.blue.retain([d.body for _,d in sorted(self.state.documents.items())]);self.engine.archive.add(self.state)
        self.engine._completion_store.remember(self.input,result,self.event_id,self.timestamp)
        return result
    def preflight(self,*,members=None):
        for key in sorted(self.graph.reachable(active=True) if members is None else members):
            self.meter.owner=key
            if key not in self.opened:
                self.meter.contracts('scopeOpened');self.meter.contracts('managedDocumentOpened');self.opened.add(key)
            cs=self.reg.contracts(self.state.documents[key].body)
            fresh=[]
            for name,c in sorted(cs.items()):
                identity=(key,name,self.blue.identity(self.blue.exact(c['_recipe'])))
                if identity not in self.headers:fresh.append((identity,c))
            if fresh:self.graph.logical.headers(self.state.documents[key].body,cs)
            for identity,c in fresh:
                self.meter.contracts('contractHeaderRecognized');self.headers.add(identity)
                for field in sorted(k for k in c if not k.startswith('_')):self.meter.contracts('objectMemberRead')
            for edge in sorted(self.state.edges.values(),key=lambda e:e.key):
                if edge.source==key and edge.occurrence not in self.graph.verified_bindings:
                    self.meter.contracts('managedOccurrenceBindingVerified');self.graph.verified_bindings.add(edge.occurrence)
        self.meter.owner=''
    def ordered(self,cs):return self.graph.logical.ordered(cs)
    @staticmethod
    def program(step):return {k:deepcopy(step[k]) for k in ('expr','do','constants','functions') if k in step}
    def compute_definition(self,key,step):
        from .compute import resolve_definition
        return resolve_definition(self,key,step)
    def context(self,key,payload,contract,steps,call=None,*,overlay_program=None):
        def overlays(value):
            if type(value) is list:return any(overlays(x) for x in value)
            if type(value) is dict:return '$resultValue' in value or any(overlays(x) for k,x in value.items() if k!='$literal')
            return False
        body=self.state.documents[key].body
        view=self.blue.view(body,logical=self.graph.logical) if overlays(self.program(contract) if overlay_program is None else overlay_program) else body
        event=event_observation(self.reg,payload,logical=self.graph.logical)
        binding={'processingEvent':event_observation(self.reg,self.event,logical=self.graph.logical) if self.event is not None else UNDEFINED,
                 'timestamp':self.timestamp if self.timestamp is not None else UNDEFINED,
                 'call':event_observation(self.reg,call,logical=self.graph.logical) if call is not None else UNDEFINED}
        return Context(document=view,resolved_document=deepcopy(view),event=event,current_contract={k:(self.blue.view(v,logical=self.graph.logical) if k=='definition' else deepcopy(v)) for k,v in contract.items() if not k.startswith('_')},steps=steps,bindings=binding,scope='/',read_document=lambda p,v,d:self.graph.logical.read(d,'' if p=='/' else p) if isinstance(d,(L.Node,L.Ref)) else self.blue.read_bex(d,p),matcher=self.runtime_matches,node_blue_id=self.graph.logical.node_blue_id)
    def evaluate(self,key,payload,contract,steps,expr,call=None):
        self.meter.owner=key;result=self.engine.bex.execute({'expr':expr},self.context(key,payload,contract,steps,call),gas=self.meter);require(not result.changeset and not result.events,'EFFECTFUL_EXPRESSION');return result.value
    def work_record(self,key,channel,payload,kind):
        self.meter.owner=key;self.meter.contracts('closureWorkOccurrenceEnqueued');self.meter.contracts('closureWorkOccurrenceDequeued');row=dict(ordinal=len(self.work),document=key,channel=channel,kind=kind,payload=self.blue.identity(payload));row['identity']=digest('contracts.work/completion-1',{'invocation':self.invocation,**row});self.work.append(row)
        counter={'UPDATE':'documentUpdateDelivered','TRIGGERED':'triggeredEventDelivered','EMBEDDED':'embeddedEventDelivered','INITIALIZATION':'lifecycleDelivered','TERMINATION':'lifecycleDelivered'}.get(kind)
        if counter:self.meter.contracts(counter)
    def custom_internal(self,key,kind,node,cs,route=(),allow_terminating=False):
        from .runtime import frozen
        for channel,d in self.ordered(cs):
            if d['_role']!='extension_channel':continue
            if not self.continuation_live(key,self.activation.get(key,0),allow_terminating):return
            extension=d['_extension'];implementation=extension.implementation
            if kind not in implementation.families:continue
            self.meter.owner=key;self.meter.contracts('channelCandidateTested')
            header=extension.header(d);event=frozen(self.blue.bex_data(node));peers=extension.peers(d,cs)
            try:
                accepted=implementation.accept_internal(header,kind,event,peers)
                require(type(accepted) is bool,'INVALID_RUNTIME_ACCEPTANCE')
                if accepted:
                    self.meter.contracts('channelAccepted')
                    value=implementation.channelize_internal(header,kind,event,peers)
            except HOST_FAILURES as exc:raise incomplete(exc) from exc
            except (GasExhausted,ContractError):raise
            except Exception as exc:
                raise ContractError('RUNTIME_FAILURE',exception=type(exc).__name__) from exc
            if accepted:
                yield self.dispatch(key,channel,self.runtime_node(value),kind,allow_terminating=allow_terminating)
    def dispatch(self,key,channel,payload,kind,operation=None,allow_terminating=False,call=None):
        frame=self.frame;ticket=frame.ticket;writer=frame.writer
        if kind!='EMBEDDED':frame.ticket=None
        try:
            yield self.dispatch_local(key,channel,payload,kind,operation,allow_terminating,call)
        finally:frame.ticket=ticket;frame.writer=writer
    def dispatch_local(self,key,channel,payload,kind,operation=None,allow_terminating=False,call=None):
        if not self.live(key) and not (allow_terminating and key in self.terminating):return
        self.work_record(key,channel,payload,kind);cs=self.reg.contracts(self.state.documents[key].body);require(channel in cs,'MISSING_HANDLER_CHANNEL');frozen=[]
        for hkey,h in self.ordered(cs):
            if h['_role'] not in EXECUTABLE or h['channel']!=channel:continue
            if h['_role']=='operation' and (kind!='EXTERNAL' or operation is None or hkey!=operation):continue
            frozen.append((hkey,{k:v if k in ('_recipe','_extension') else deepcopy(v) for k,v in h.items()}))
        event=payload
        generation=self.activation.get(key,0)
        for hkey,h in frozen:
            if not self.continuation_live(key,generation,allow_terminating):break
            self.meter.owner=key;self.meter.contracts('handlerCandidateTested')
            if 'event' in h and not self.runtime_matches(event,h['event']):continue
            declaration=self.blue.exact(h['_recipe']);self.blue.remember(declaration)
            self.frame.writer=dict(handler=hkey,declaration=self.blue.identity(declaration),channel=channel,
                kind=kind,event=self.blue.identity(event),call=self.blue.identity(call) if call is not None else None)
            self.meter.contracts('handlerCall');steps={}
            if h['_role']=='extension_handler':
                yield self.execute_extension(key,payload,h,steps,generation,allow_terminating,call)
                continue
            for i,recipe in enumerate(self.reg.steps(h)):
                if not self.continuation_live(key,generation,allow_terminating):break
                self.meter.owner=key;step=self.reg.declaration(recipe);name=step.get('name',str(i));role=step['_role']
                require(name not in steps,'DUPLICATE_STEP_NAME')
                configured={k:v for k,v in step.items() if not k.startswith('_')}
                if role=='compute':
                    definition=self.compute_definition(key,step)
                    program=self.program(step)
                    # Overlay detection includes imported function bodies.
                    overlay_program={**program,'functions':{**(definition or {}).get('functions',{}),**step.get('functions',{})}}
                    result=self.engine.bex.execute(program,self.context(key,payload,step,steps,call,overlay_program=overlay_program),gas=self.meter,entry=step.get('entry'),definition=definition);value=result.value
                    if type(value) is dict:changes=value.get('changeset',result.changeset);events=value.get('events',result.events)
                    else:changes=result.changeset;events=result.events
                    self.validate_effects(changes,events);steps[name]=deepcopy(value)
                    for p in changes:
                        if not self.continuation_live(key,generation,allow_terminating):break
                        yield self.patch(key,p)
                    for e in events:
                        if not self.continuation_live(key,generation,allow_terminating):break
                        self.emit(key,self.runtime_node(e))
                elif role=='patch_step':
                    require('changeset' in step,'MISSING_CHANGESET')
                    changes=self.evaluate(key,payload,step,steps,step['changeset'],call);self.validate_effects(changes,[]);steps[name]={'changeset':deepcopy(changes)}
                    for p in changes:
                        if not self.continuation_live(key,generation,allow_terminating):break
                        yield self.patch(key,p)
                elif role=='emit_step':
                    require('event' in step,'MISSING_EVENT')
                    event_value=self.evaluate(key,payload,step,steps,step['event'],call);self.emit(key,self.runtime_node(event_value));steps[name]=deepcopy(event_value)
                elif role=='terminate_step':
                    cause=step['cause'];reason=step.get('reason');require(type(cause) is str and (reason is None or type(reason) is str),'INVALID_TERMINATION');yield self.terminate(key,cause,reason);break
                elif role=='extension_step':
                    yield self.execute_extension(key,payload,step,steps,generation,allow_terminating,call)
                    steps[name]={}
                else:raise ContractError('UNSUPPORTED_STEP')
    def execute_extension(self,key,payload,declaration,steps,generation,allow_terminating=False,call=None):
        from .runtime import RuntimeMeter,RuntimeContext,frozen,validate_result
        extension=declaration['_extension'];binding=extension.binding
        selected=self.reg.declaration(declaration['_recipe']);body=self.state.documents[key].body
        meter=RuntimeMeter(self.meter,binding,key)
        context=RuntimeContext(frozen(event_observation(self.reg,payload)),extension.header(selected),
            frozen({k:deepcopy(selected[k]) for k in binding.body_fields if k in selected}),frozen(deepcopy(steps)),
            self.event_id,self.timestamp,lambda path:frozen(self.blue.read(body,path)),meter,
            frozen(event_observation(self.reg,call)) if call is not None else None)
        try:raw=extension.implementation.execute(context)
        except HOST_FAILURES as exc:raise incomplete(exc) from exc
        except (GasExhausted,ContractError):
            meter.merge(failed=True);raise
        except Exception as exc:
            meter.merge(failed=True)
            raise ContractError('RUNTIME_FAILURE',exception=type(exc).__name__) from exc
        # Merge admitted runtime work even when the returned effect shape is
        # invalid. Effects remain staged until the entire result is checked.
        meter.merge(raw.get('runtimeLedger') if type(raw) is dict else None)
        result=validate_result(raw)
        self.validate_effects(result['patches'],result['events'])
        def alive():return self.continuation_live(key,generation,allow_terminating)
        for patch in result['patches']:
            if not alive():return
            yield self.patch(key,patch)
        for event in result['events']:
            if not alive():return
            self.emit(key,self.runtime_node(event))
        if 'termination' in result and alive():
            end=result['termination'];yield self.terminate(key,end['cause'],end.get('reason'))
    def validate_effects(self,patches,events):
        require(type(patches) is list and type(events) is list,'INVALID_EFFECT_RESULT')
        for p in patches:
            require(type(p) is dict and p.get('op') in ('add','replace','remove'),'INVALID_PATCH');closed(p,{'op','path'} if p['op']=='remove' else {'op','path','val'});require(bool(segments(p['path'])),'INVALID_PATCH_PATH')
            if p['op']!='remove':self.runtime_node(p['val'],certify=False)
        for e in events:self.runtime_node(e)
    def protected(self,body):
        return self.reg.policy(body)[1],{k:self.blue.identity(v) if (v:=self.reg.marker(body,k)) is not None else None for k in MARKERS}
    def patch(self,key,patch):
        self.effect_count+=1;self.meter.owner=key;path=patch['path'];doc=self.state.documents[key]
        # Normalize list append to the concrete index. An inserted position
        # has no before value; a removed position has no after value even when
        # a following list item shifts into the same numerical index.
        parts=segments(path);parent=self.blue.select(doc.body,pointer(parts[:-1]))
        list_parent=parent is not None and self.blue.head(parent).items is not None
        if list_parent and parts[-1]=='-' and patch['op']=='add':
            path=pointer(parts[:-1]+(str(len(self.blue.head(parent).items)),))
        self.meter.contracts('patchBoundaryChecked')
        for _ in segments(path):self.meter.contracts('pointerSegmentTraversed')
        self.meter.contracts('patchRemove' if patch['op']=='remove' else 'patchAddOrReplace')
        for (source,p),edge in self.state.edges.items():
            if source==key:require(not(prefix(p,path) and p!=path),'MANAGED_BOUNDARY_VIOLATION',path=path)
        before_r=None if list_parent and patch['op']=='add' else self.blue.select(doc.body,path);before=self.blue.exact(before_r) if before_r is not None else None;protection=self.protected(doc.body)
        value=self.runtime_node(patch['val'],certify=False) if patch['op']!='remove' else None;next_body=self.blue.set_at(doc.body,path,value,op=patch['op'])
        self.graph.logical.establish(next_body,doc.body)
        requested_body=next_body
        from .generalization import repair
        next_body,generated=repair(self.blue,doc.body,next_body,path,self.reg.policy(doc.body)[0],self.meter,validate=lambda candidate:self.graph.logical.validate(candidate,doc.body),establish=lambda candidate:self.graph.logical.establish(candidate,doc.body))
        require(self.protected(next_body)==protection,'PROTECTED_STATE_MUTATION',path=path)
        for write in generated:
            self.meter.contracts('patchBoundaryChecked')
            for _ in segments(write['path']):self.meter.contracts('pointerSegmentTraversed')
            self.meter.contracts('patchAddOrReplace')
        if generated:self.graph.logical.establish(next_body,requested_body)
        self.blue.remember(doc.body);self.blue.remember(next_body)
        self.frame.writes.append(dict(writer=deepcopy(self.frame.writer),op=patch['op'],path=path,
            before=self.blue.identity(doc.body),after=self.blue.identity(next_body)))
        reachable=self.graph.reachable()
        doc.body=next_body
        self.graph.reconcile(self.cause_order,owner=key,replaced=(path,))
        for member in reachable ^ self.graph.reachable():self.activation[member]=self.activation.get(member,0)+1
        self.allocation=max(self.allocation,self.graph.allocation)
        refresh_lifetimes(self.graph,self.cause_order,members={key}|set(self.graph.added))
        self.graph.finalize_local(key);self.preflight(members={key}|set(self.graph.added))
        self.creation_barrier()
        self.graph.finalize_local(key)
        after_r=None if patch['op']=='remove' else self.blue.select(doc.body,path)
        after=self.blue.exact(after_r) if after_r is not None else None
        before_id=self.blue.identity(before) if before is not None else None;after_id=self.blue.identity(after) if after is not None else None
        if before_id==after_id:return
        # A contextual selection (especially after generated type writes) can
        # materialize a new exact subtree which is not a stored root. Retain
        # both immutable observations before an update refers to their IDs.
        if before is not None:self.blue.remember(before)
        if after is not None:self.blue.remember(after)
        payload={'op':'add' if before is None else 'remove' if after is None else 'replace','path':path,'beforePresent':before is not None,'afterPresent':after is not None}
        if before is not None:payload['before']={'blueId':before_id}
        if after is not None:payload['after']={'blueId':after_id}
        for write in generated:
            change={'op':'replace','path':write['path'],'beforePresent':True,'afterPresent':True,'before':{'blueId':self.blue.identity(write['before'])},'after':{'blueId':self.blue.identity(write['after'])}}
            yield self.update(key,change,())
        yield self.update(key,payload,())
    def update(self,key,payload,route):
        if not self.graph.route_live(route) or not self.live(key):return
        generation=self.activation.get(key,0)
        node=self.runtime_node(self.reg.typed('Document Update',**payload));cs=self.reg.contracts(self.state.documents[key].body)
        channels=[k for k,c in self.ordered(cs) if c['_role']=='update' and prefix(c.get('path',''),payload['path']) and ('event' not in c or self.runtime_matches(node,c['event']))]
        for k in channels:
            if not self.graph.route_live(route) or self.activation.get(key,0)!=generation:break
            yield self.dispatch(key,k,node,'UPDATE')
        if self.activation.get(key,0)==generation:yield self.custom_internal(key,'UPDATE',node,cs,route)
    def terminate(self,key,cause,reason):
        if key in self.terminating or self.graph.terminated(key):return
        self.meter.owner=key;self.meter.contracts('terminationRequested')
        self.terminating.add(key);self.termination[key]=(cause,reason);raw=self.reg.typed('Document Processing Terminated',cause=cause)
        if reason is not None:raw['reason']=reason
        node=self.runtime_node(raw);cs=self.reg.contracts(self.state.documents[key].body)
        for k,c in self.ordered(cs):
            if c['_role']=='lifecycle' and ('event' not in c or self.runtime_matches(node,c['event'])):yield self.dispatch(key,k,node,'TERMINATION',allow_terminating=True)
        yield self.custom_internal(key,'TERMINATION',node,cs,allow_terminating=True)
    def direct_marker(self,key,name,value):
        doc=self.state.documents[key];root=self.blue.open(doc.body);cs=root.get('contracts');cs=L.node({}) if cs is L.ABSENT else self.blue.open(cs);fields=dict(cs.fields)
        if value is None:fields.pop(name,None)
        else:fields[name]=self.runtime_node(value,certify=False)
        candidate=L.changed(root,contracts=L.node(fields))
        self.graph.logical.establish(candidate,doc.body)
        doc.body=candidate
```

### `src/blue_contracts/reference/receiving.py`

```python
"""Retained source completion delivery through the document-local kernel.

Capabilities are issued only for locally completed successful invocations. Data
received from another process is replayed before it can acquire that provenance.
A receiving invocation installs source state and batches before any receiver turn;
it never supplies external seeds or re-executes the source's business handlers.
"""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from secrets import token_hex
from blue_host import HostIncomplete, HOST_FAILURES, incomplete, host_boundary
from algorithms import blue as L
from .model import require, digest
from .completion import Batch, vector
from .graph import Graph


@dataclass(frozen=True)
class SourceCompletion:
    _store: object
    _token: str

    @property
    def descriptor(self):
        return deepcopy(self._store.read(self)['descriptor'])


class CompletionStore:
    """Bounded, process-local provenance. A digest alone is never authority."""
    def __init__(self, capacity=128):
        self.capacity = capacity
        self._outcomes = OrderedDict()
        self._capabilities = OrderedDict()

    def remember(self, before, outcome, event, timestamp):
        self._outcomes[outcome.receipt] = (before.copy(), deepcopy(outcome), event, timestamp)
        while len(self._outcomes) > self.capacity:
            self._outcomes.popitem(last=False)

    def capture(self, outcome, members):
        record = self._outcomes.get(outcome.receipt)
        require(record is not None and record[1].observations() == outcome.observations(),
                'UNESTABLISHED_SOURCE_COMPLETION')
        before, result, event, timestamp = record
        members = frozenset(members)
        require(members and members <= result.snapshot.documents.keys(), 'INVALID_SOURCE_MEMBERS')
        require(members <= before.documents.keys(), 'SOURCE_BIRTH_REQUIRES_OWNER_COMMIT')
        # An existing cyclic execution unit is inseparable.
        for unit in result.units:
            owned = set(unit['members'])
            require(not owned.intersection(members) or owned <= members, 'PARTIAL_SOURCE_UNIT')
        descriptor = dict(receipt=result.receipt, before=vector(before, members),
                          after=vector(result.snapshot, members), members=sorted(members),
                          event=event, timestamp=timestamp, release=before.release,
                          runtimes=list(before.runtimes))
        descriptor['identity'] = digest('contracts.retained-completion/1', descriptor)
        token = token_hex(24)
        self._capabilities[token] = dict(descriptor=descriptor, before=before, outcome=result,
                                         event=event, timestamp=timestamp, members=members)
        while len(self._capabilities) > self.capacity:
            self._capabilities.popitem(last=False)
        return SourceCompletion(self, token)

    def read(self, capability):
        require(type(capability) is SourceCompletion and capability._store is self,
                'FOREIGN_SOURCE_COMPLETION')
        require(capability._token in self._capabilities, 'EXPIRED_SOURCE_COMPLETION')
        return self._capabilities[capability._token]


def begin_receiving(processor, snapshot, completions, *, live=False, evidence=None):
    try:
        attempt = _begin_receiving(processor, snapshot, completions, live=live, evidence=evidence)
    except HOST_FAILURES as error:raise incomplete(error) from error
    except Exception as error:
        processor.observe_execution('adoptionRejected', code=getattr(error, 'code', type(error).__name__))
        raise
    if attempt.outcome is not None and not attempt.outcome.commits:
        processor.observe_execution('adoptionRejected', code=attempt.outcome.status)
    return attempt


def _begin_receiving(processor, snapshot, completions, *, live=False, evidence=None):
    from .processor import Run
    from .chunks import Attempt
    require(type(completions) in (list, tuple) and completions, 'MISSING_SOURCE_COMPLETIONS')
    records = [processor._completion_store.read(c) for c in completions]
    require(len({r['descriptor']['identity'] for r in records}) == len(records), 'DUPLICATE_SOURCE_COMPLETION')
    causes = {(r['event'], r['timestamp']) for r in records}
    require(len(causes) == 1, 'MIXED_SOURCE_CAUSES')
    event, timestamp = next(iter(causes))
    owners = set()
    for record in records:
        require(not owners.intersection(record['members']), 'OVERLAPPING_SOURCE_COMPLETIONS')
        owners.update(record['members'])
        require(record['before'].release == snapshot.release and record['before'].runtimes == snapshot.runtimes,
                'INCOMPATIBLE_SOURCE_RUNTIME')
    require(snapshot.root not in owners, 'CYCLIC_RECEIVING_REQUIRES_ATOMIC_INVOCATION')

    class ReceivingRun(Run):
        def begin_work(self):
            self.meter.contracts('processInvocation')
            self.meter.contracts('closureInvocation')
            self.preflight()
            self.engine.validate(self.input)
            if live:
                # Freeze admission against the original receiver input, before
                # installing any completed child. Incoming handlers can then
                # retire a seed through the normal Contracts lifetime checks.
                from .runtime import prepare_admissions
                from .channels import recognize_call, select_seeds
                prepare_admissions(self)
                self.call, self.call_record = recognize_call(self.reg, self.event)
                self.seeds = tuple(s for s in select_seeds(self) if s.document not in owners)
            before_routes = {k: self.capture_routes(k) for k in owners}
            carried = {}
            for record in records:
                source_after = record['outcome'].snapshot
                pending = list(record['members'])
                closure = set()
                while pending:
                    member = pending.pop()
                    if member in closure:continue
                    closure.add(member)
                    pending.extend(e.target for e in source_after.edges.values() if e.source == member)
                require(self.input.root not in closure, 'CYCLIC_RECEIVING_REQUIRES_ATOMIC_INVOCATION')
                for member in closure - owners:
                    document = source_after.documents[member]
                    if member in carried:
                        require(carried[member].metadata() == document.metadata(), 'INCOMPATIBLE_SOURCE_DEPENDENCIES')
                    carried[member] = document
                    self.state.documents[member] = deepcopy(document)
                    for edge in list(self.state.edges):
                        if edge[0] == member:del self.state.edges[edge]
                    self.state.edges.update({k:deepcopy(e) for k,e in source_after.edges.items() if e.source == member})
            for record in records:
                source_before, source_after = record['before'], record['outcome'].snapshot
                for member in sorted(record['members']):
                    require(member in self.input.documents, 'MISSING_RECEIVING_SOURCE')
                    require(vector(self.input, [member]) == vector(source_before, [member]),
                            'SOURCE_PREDECESSOR_MISMATCH', member=member)
                    self.state.documents[member] = deepcopy(source_after.documents[member])
                    for edge in list(self.state.edges):
                        if edge[0] == member:
                            del self.state.edges[edge]
                    self.state.edges.update({k: deepcopy(e) for k, e in source_after.edges.items() if e.source == member})
                # Births cannot be installed as a detached fragment. Their
                # complete verified source owner outcome includes the birth.
                newborn = set(source_after.documents) - set(source_before.documents)
                for member in sorted(newborn):
                    require(member not in self.input.documents, 'CONFLICTING_MEMBER_BIRTH')
                    self.state.documents[member] = deepcopy(source_after.documents[member])
                self.state.edges.update({k: deepcopy(e) for k, e in source_after.edges.items() if e.source in newborn})
            self.graph = self.fork_graph(self.state)
            self.graph.refresh_aliases()
            completed_closure = owners | set(carried)
            if live:
                self.seeds = tuple(s for s in self.seeds if s.document not in completed_closure)
            # Containing references intentionally still name the selected
            # predecessor here. install_inputs updates them before the local
            # receiving turn; the complete outcome validates the resulting graph.
            self.phase = self.new_phase('PROCESS' if live else 'RECEIVE')
            for group in self.phase.groups:
                require(not group.intersection(owners) or group <= owners,
                        'CYCLIC_RECEIVING_REQUIRES_ATOMIC_INVOCATION')
                if group <= completed_closure:
                    self.phase.done.add(tuple(sorted(group)))
            for record in records:
                result = record['outcome']
                for member in sorted(record['members']):
                    turns = [t for t in result.completions if t['turnInput']['member'] == member]
                    # State-only steps still deliver an empty batch.
                    output = tuple(e for t in turns for e in t['output'])
                    batch = Batch(member, 0, record['descriptor']['identity'], output,
                                  before_routes[member], vector(self.state, [member]))
                    self.route_batch(self.phase, batch, owners, internal=False)
            self.engine.observe_execution('adoption', count=len(records), members=sorted(owners), live=live)

    run = ReceivingRun(processor, snapshot, L.Ref(event) if event else None, timestamp,
                       processor.gas_limit, admission=event is None, local_limits=processor.local_limits,
                       admission_evidence=evidence)
    run.receiving = True
    run.invocation = digest('contracts.receiving/1', dict(input=snapshot.identity,
        sources=[r['descriptor']['identity'] for r in records], policy=run.meter.policy()))
    run.graph.invocation = run.invocation
    return Attempt(run)
```

### `src/blue_contracts/reference/registry.py`

```python
"""Exact catalogue, contextual headers and deferred executable bodies."""
from pathlib import Path
from algorithms import blue as L
from .model import ContractError,require,token,integer,segments,LIMITS
from .catalogue import PARENTS,publish_catalogue
ROLES={'Contract':'abstract','Marker':'abstract','Channel':'abstract','External Channel':'external','Composite External Channels':'composite','All External Channels':'all','Triggered Event Channel':'triggered','Embedded Node Channel':'embedded_event','Document Update Channel':'update','Lifecycle Event Channel':'lifecycle','Process Embedded':'embedding','Handler':'abstract','Operation':'abstract','Sequential Workflow':'workflow','Sequential Workflow Operation':'operation','Operation Request':'request','Compute':'compute','Compute Definition':'compute_definition','Update Document':'patch_step','Trigger Event':'emit_step','Terminate Processing':'terminate_step','Channel Event Checkpoint':'checkpoint','Processing Initialized Marker':'initialized','Processing Terminated Marker':'terminated','Document Processing Initiated':'initiated','Document Processing Terminated':'ended','Document Update':'updated','Embedded Event Delivery':'embedded_delivery','Json Patch Entry':'patch_record','Contract Execution Result':'execution_result','Type Generalization Rule':'generalization_rule','Type Generalization Policy':'generalization'}
EXTERNAL={'external','composite','all','extension_external'}
INTERNAL={'triggered','embedded_event','update','lifecycle','extension_channel'}
EXECUTABLE={'workflow','operation','extension_handler'}
MARKERS={'initialized':'initialized','terminated':'terminated','checkpoint':'checkpoint'}
DATA_ROLES={'request','initiated','ended','updated','embedded_delivery','patch_record','execution_result','generalization_rule'}
LITERAL_FIELDS={'do','expr','constants','functions','event','changeset','request'}
ALLOWED={'external':{'event'},'composite':{'channels'},'all':set(),'triggered':{'event'},'embedded_event':{'sourcePath','event'},'update':{'path','event'},'lifecycle':{'event'},'embedding':{'paths','collectionPaths'},'workflow':{'channel','event','steps'},'operation':{'channel','request','steps'},'compute':{'expr','do','constants','functions','entry','definition'},'compute_definition':{'constants','functions'},'patch_step':{'changeset'},'emit_step':{'event'},'terminate_step':{'cause','reason'},'generalization':{'defaultMode','rules'}}
BODY_FIELDS={'workflow':{'steps'},'operation':{'steps'},'compute':{'expr','do','constants','functions','entry','definition'},'compute_definition':{'constants','functions'},'patch_step':{'changeset'},'emit_step':{'event'},'terminate_step':{'cause','reason'}}

class Registry:
    def __init__(self,bridge):
        self.blue=bridge;self.types={};self.by_id={};self.extensions={};document=Path(__file__).resolve().parents[1]/'COMPLETE_SPECIFICATION.md'
        require(document.is_file(),'MISSING_SPECIFICATION');self.specification=self.blue.identity(self.blue.source(document.read_text(encoding='utf-8')))
        def admit(raw):return self.blue.identity(self.blue.source(raw,goal='definition'))
        self.types=publish_catalogue(admit,self.specification,L.CORE)
        self.by_id={tid:ROLES[name] for name,tid in self.types.items()}
        aliases={alias:tid for name,tid in self.types.items() for alias in (name,'Contracts/'+name)}
        for alias,tid in aliases.items():
            require(self.blue.language.aliases.get(alias,tid)==tid,'CORE_ALIAS_CONFLICT',alias=alias)
        self.blue.language.aliases.update(aliases)
        self.blue.refresh()
    def typed(self,type_name,**fields):return {'type':{'blueId':self.types[type_name]},**fields}
    @property
    def runtime_bindings(self):return tuple(self.extensions[k].binding.wire() for k in sorted(self.extensions))
    def install(self,binding,implementation):
        from .runtime import Runtime
        self.blue.certify(L.Ref(binding.type_id),'definition');self.blue.certify(L.Ref(binding.semantics_id))
        require(binding.type_id not in self.by_id,'STANDARD_RUNTIME_REBIND')
        parent={'external-channel':'Channel','processor-channel':'Channel','handler':'Handler','marker':'Marker','step':'Contract'}[binding.role]
        require(self.types[parent] in L.ancestry(binding.type_id,self.blue.context),'INVALID_RUNTIME_CATEGORY',category=parent)
        previous=self.extensions.get(binding.type_id)
        if previous is not None:
            require(previous.binding==binding and previous.implementation is implementation,'RUNTIME_BINDING_CONFLICT');return
        self.extensions[binding.type_id]=Runtime(binding,implementation)
    def binding(self,r):
        h=self.blue.head(r);tid=h.type_id
        if tid is None:return None
        try:
            for ancestor in L.ancestry(tid,self.blue.context):
                if ancestor in self.extensions:
                    extension=self.extensions[ancestor]
                    if tid==ancestor or extension.binding.inherits_to_subtypes:return extension
                if ancestor in self.by_id:return self.by_id[ancestor]
        except L.Failure as e:self.blue.translate(e)
        return None
    def role(self,r):
        binding=self.binding(r)
        return binding if isinstance(binding,str) or binding is None else binding.role
    def configured(self,r,key):
        """Authored syntax may be empty; catalogue declaration holes are absent.

        Stop at installed catalogue definitions. Custom inherited contributions
        still count, including type-only patterns and explicit empty objects.
        """
        recipe=r if isinstance(r,L.Recipe) else L.recipe(r)
        for part in recipe.parts:
            seen=set();node=part
            while node is not None:
                tid=self.blue.identity(node)
                if tid in seen or tid in self.by_id:break
                seen.add(tid);body=self.blue.open(node)
                if body.has(key):return True
                parent=body.get('type');node=parent if isinstance(parent,L.Ref) else None
        return False
    def declaration(self,r,*,demand=True):
        h=self.blue.head(r);binding=self.binding(r);role=self.role(r);require(role is not None,'UNSUPPORTED_CONTRACT_TYPE',type=h.type_id)
        out={'type':{'blueId':h.type_id},'_role':role,'_recipe':r}
        extension=None if isinstance(binding,str) else binding
        body_fields=set(extension.binding.body_fields) if extension else BODY_FIELDS.get(role,set())
        allowed=(set(extension.binding.header_fields)|body_fields) if extension else ALLOWED.get(role)
        if allowed is not None:require(set(h.fields)<=allowed|{'specification','order'},'UNKNOWN_RUNTIME_FIELD',role=role,fields=sorted(set(h.fields)-allowed-{'specification','order'}))
        for k in sorted(h.fields):
            if k=='specification' or k=='steps' and role in ('workflow','operation'):continue
            if not demand and k in body_fields:continue
            ch=L.child_recipe(h,k)
            if k=='definition':
                if self.configured(r,k):out[k]=ch
            elif k in LITERAL_FIELDS or k in body_fields:
                if self.configured(r,k):out[k]=self.blue.bex_data(ch)
            elif L.present_recipe(ch,self.blue.context):out[k]=self.blue.project(ch)
        n=self.blue.open(self.blue.exact(r))
        for label in ('name','description'):
            if n.has(label):out[label]=n.get(label)
        if 'order' in out:integer(out['order'],-(1<<31),(1<<31)-1)
        if extension:out['_extension']=extension
        if role=='embedding':
            for k in ('paths','collectionPaths'):
                xs=out.get(k,[]);require(type(xs) is list and all(type(p) is str for p in xs),'INVALID_EMBEDDED_PATHS');require(len(xs)==len(set(xs)),'DUPLICATE_EMBEDDED_PATH')
                for p in xs:require(segments(p) and all(segments(p)) and segments(p)[0]!='contracts','INVALID_EMBEDDED_PATH')
        if role in ('embedded_event','update'):
            field='sourcePath' if role=='embedded_event' else 'path'
            if field in out:segments(out[field])
        if role=='terminate_step' and demand:
            require(type(out.get('cause')) is str,'INVALID_TERMINATION_CAUSE')
            if 'reason' in out:require(type(out['reason']) is str,'INVALID_TERMINATION_REASON')
        if role in EXECUTABLE:
            token(out.get('channel'))
            if role!='extension_handler':
                require(self.configured(r,'steps'),'MISSING_STEPS')
                if demand:out['steps']=[self.declaration(s) for s in self.steps(out)]
        return out
    def steps(self,handler):
        r=handler['_recipe'];h=self.blue.head(r);sh=self.blue.head(L.child_recipe(h,'steps'))
        require(sh.items is not None,'INVALID_STEPS')
        return (L.child_recipe(sh,i) for i in range(len(sh.items)))
    def contracts(self,body):
        h=self.blue.head(body)
        if h.contracts is None:return {}
        ch=self.blue.head(h.contracts);require(ch.kind in ('object','none'),'INVALID_CONTRACT_MAP');result={}
        for k in sorted(ch.fields):
            token(k);r=L.child_recipe(ch,k);role=self.role(r)
            if k in MARKERS:require(role==MARKERS[k],'INVALID_PROCESSOR_STATE',key=k);continue
            require(role not in set(MARKERS.values()),'MISPLACED_PROCESSOR_STATE',key=k);d=self.declaration(r,demand=False);require(d['_role'] in EXTERNAL|INTERNAL|EXECUTABLE|{'embedding','generalization','extension_marker','compute_definition'},'INVALID_CONTRACT_ROLE',role=d['_role'])
            if d['_role']=='embedding':require(k=='embedded','EMBEDDING_KEY')
            if d['_role']=='generalization':require(k=='generalization','GENERALIZATION_KEY');self.policy(body)
            result[k]=d
        for k,d in result.items():
            if d['_role'] in EXECUTABLE:require(d['channel'] in result and result[d['channel']]['_role'] in EXTERNAL|INTERNAL,'INVALID_HANDLER_CHANNEL',handler=k)
        return result
    def policy(self,body):
        from .policy import GeneralizationPolicy,GeneralizationRule,GeneralizationError
        h=self.blue.head(body)
        if h.contracts is None:return GeneralizationPolicy(),None
        r=self.blue.child(h.contracts,'generalization')
        if r is None:return GeneralizationPolicy(),None
        require(self.role(r)=='generalization','INVALID_GENERALIZATION_POLICY')
        d=self.declaration(r);rules=[];rh=self.blue.head(r);sequence=self.blue.child(r,'rules')
        try:
            sh=self.blue.head(sequence) if sequence is not None else None
            if sh is not None:
                require(sh.items is not None or not self.configured(r,'rules'),'INVALID_GENERALIZATION_RULES')
            for i in range(len(sh.items or ()) if sh is not None else 0):
                item=L.child_recipe(sh,i);ih=self.blue.head(item)
                require(set(ih.fields)<={'specification','path','mode','mustRemainSubtypeOf'},'INVALID_GENERALIZATION_RULE')
                path=self.blue.child(item,'path');mode=self.blue.child(item,'mode');floor=self.blue.child(item,'mustRemainSubtypeOf')
                if floor is not None:
                    floor=self.blue.identity(self.blue.exact(floor));self.blue.certify(L.Ref(floor),'definition')
                rules.append(GeneralizationRule(self.blue.project(path),self.blue.project(mode),floor))
            policy=GeneralizationPolicy(tuple(rules),d.get('defaultMode','reject'))
        except GeneralizationError as exc:raise ContractError('INVALID_GENERALIZATION_POLICY',detail=str(exc)) from exc
        return policy,self.blue.identity(self.blue.exact(r))
    @staticmethod
    def ordered(cs):return sorted(cs.items(),key=lambda kv:(kv[1].get('order',0),kv[0],kv[1]['type']['blueId']))
    def marker(self,body,key):
        n=self.blue.open(body);cs=n.get('contracts')
        if cs is L.ABSENT:return None
        cs=self.blue.open(cs);value=cs.get(key)
        if value is L.ABSENT:return None
        require(self.role(value)==MARKERS[key],'INVALID_PROCESSOR_STATE',key=key);return value


# Build mandatory authoring content independently of caller operation limits.
# The cached data is immutable release content; executable roles still belong
# to the Processor's own Registry, never to a repository upload.
from functools import lru_cache

@lru_cache(maxsize=1)
def core_catalogue():
    from .language import Bridge
    blue=Bridge()
    Registry(blue)
    return dict(blue.language.aliases),blue.language.provider.snapshot()
```

### `src/blue_contracts/reference/runtime.py`

```python
"""Explicit trusted runtime bindings with read-only inputs and staged effects."""
from dataclasses import dataclass,asdict
from copy import deepcopy
from types import MappingProxyType
from blue_host import HostIncomplete, HOST_FAILURES, incomplete, host_boundary
from algorithms import blue as L
from blue_bex import GasExhausted
from .model import require,closed,token,integer,segments,digest,ContractError


def frozen(value):
    if type(value) is dict:return MappingProxyType({k:frozen(v) for k,v in value.items()})
    if type(value) in (list,tuple):return tuple(frozen(v) for v in value)
    return value


def data_copy(value):
    """Copy verified data returned from a read-only context, never capabilities."""
    if isinstance(value, (dict, MappingProxyType)):
        return {k: data_copy(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [data_copy(v) for v in value]
    require(value is None or type(value) in (str, int, float, bool), 'INVALID_VERIFIED_ADMISSION')
    return value


@dataclass(frozen=True)
class RuntimeBinding:
    type_id:str
    semantics_id:str
    role:str
    header_fields:tuple
    body_fields:tuple
    namespace:str
    tariff:tuple
    inherits_to_subtypes:bool=False
    peer_fields:tuple=()
    meter_mode:str='live'

    def __post_init__(self):
        L.final_id(self.type_id);L.final_id(self.semantics_id);token(self.namespace)
        require(self.namespace not in ('bex','contracts'),'RESERVED_GAS_NAMESPACE')
        require(self.role in ('external-channel','processor-channel','handler','marker','step'),'INVALID_RUNTIME_ROLE')
        require(type(self.inherits_to_subtypes) is bool,'INVALID_RUNTIME_BINDING')
        require(self.meter_mode in ('live','ledger'),'INVALID_RUNTIME_METER_MODE')
        for value in (self.header_fields,self.body_fields,self.tariff,self.peer_fields):require(type(value) is tuple,'MUTABLE_RUNTIME_BINDING')
        fields=self.header_fields+self.body_fields
        require(len(fields)==len(set(fields)),'AMBIGUOUS_RUNTIME_FIELDS')
        for name in fields:token(name);require(not name.startswith('_') and name not in ('type','specification','name','description','order'),'INVALID_RUNTIME_FIELD')
        require(set(self.peer_fields)<=set(self.header_fields),'INVALID_PEER_FIELDS')
        require(len(dict(self.tariff))==len(self.tariff),'DUPLICATE_RUNTIME_COUNTER')
        for name,weight in self.tariff:token(name);integer(weight)

    def wire(self):
        def lists(value):
            if type(value) is dict:return {k:lists(v) for k,v in value.items()}
            if type(value) in (list,tuple):return [lists(v) for v in value]
            return value
        return lists(asdict(self))


class RuntimeMeter:
    """A runtime cannot change ownership, tariffs, or the parent allowance."""
    def __init__(self,parent,binding,owner):
        self.__parent=parent;self.__binding=binding;self.__owner=owner
        self.__start=parent.used;self.__rows=[];self.__rejected=None;self.__finished=False;self.__merged=False
        shared=parent.limit-parent.used
        local=parent.local_limits.get(owner,parent.limit)-parent.local_used.get(owner,0)
        self.__allowance=min(shared,local) if owner in parent.local_limits else shared

    @property
    def remaining(self):
        return self.__allowance-sum(row[2] for row in self.__rows)

    def charge(self,counter,units=1):
        require(not self.__finished and self.__rejected is None,'CLOSED_RUNTIME_LEDGER')
        integer(units,maximum=None);weights=dict(self.__binding.tariff);require(counter in weights,'UNDECLARED_RUNTIME_COUNTER',counter=counter)
        amount=weights[counter]*units
        if self.__binding.meter_mode=='live':
            self.__parent.owner=self.__owner;self.__parent.debit(self.__binding.namespace,counter,units,amount)
        elif amount>self.remaining:
            self.__rejected=(counter,units,amount);raise GasExhausted(counter)
        self.__rows.append((counter,units,amount))

    def finish(self):
        require(self.__binding.meter_mode=='ledger','DOUBLE_GAS_DEBIT')
        self.__finished=True;return self

    def merge(self,returned=None,*,failed=False):
        require(not self.__merged,'DOUBLE_GAS_DEBIT');self.__merged=True
        if self.__binding.meter_mode=='live':require(returned is None,'DOUBLE_GAS_DEBIT');return
        require(failed or returned is self and self.__finished,'INVALID_RUNTIME_LEDGER')
        require(self.__parent.used==self.__start,'RUNTIME_LEDGER_ALLOWANCE_CHANGED')
        self.__parent.owner=self.__owner
        for counter,units,amount in self.__rows:self.__parent.debit(self.__binding.namespace,counter,units,amount)
        if self.__rejected:
            counter,units,amount=self.__rejected
            self.__parent.debit(self.__binding.namespace,counter,units,amount)
            raise ContractError('RUNTIME_LEDGER_REJECTION_MISMATCH')
        self.__finished=True


@dataclass(frozen=True)
class RuntimeContext:
    event:object
    header:object
    body:object
    steps:object
    processing_event:str|None
    timestamp:int|None
    read:object
    gas:RuntimeMeter
    call:object=None


class Runtime:
    """An installed implementation is trusted deterministic code, not a sandbox."""
    def __init__(self,binding,implementation):
        self.binding=binding;self.implementation=implementation
        self.role={'external-channel':'extension_external','processor-channel':'extension_channel','handler':'extension_handler','marker':'extension_marker','step':'extension_step'}[binding.role]
        if binding.role in ('handler','step'):require(callable(getattr(implementation,'execute',None)),'MISSING_RUNTIME_EXECUTOR')
        if binding.role=='external-channel':
            require(callable(getattr(implementation,'accept',None)),'MISSING_RUNTIME_CHANNEL_FUNCTION',function='accept')
            require(binding.meter_mode=='live','EXTERNAL_RUNTIME_REQUIRES_LIVE_METER')
        if binding.role=='processor-channel':
            families=getattr(implementation,'families',())
            require(type(families) is tuple and families and set(families)<={'TRIGGERED','EMBEDDED','UPDATE','INITIALIZATION','TERMINATION'},'INVALID_RUNTIME_EVENT_FAMILIES')
            for name in ('accept_internal','channelize_internal'):require(callable(getattr(implementation,name,None)),'MISSING_RUNTIME_CHANNEL_FUNCTION',function=name)

    def header(self,declaration):
        return frozen({k:deepcopy(declaration[k]) for k in self.binding.header_fields if k in declaration})

    def peers(self,declaration,contracts):
        names=set()
        for field in self.binding.peer_fields:
            values=declaration.get(field,[]);require(type(values) is list and all(type(x) is str for x in values),'INVALID_PEER_DECLARATION')
            names.update(values)
        def lookup(name):
            require(name in names,'UNDECLARED_PEER_LOOKUP',peer=name)
            value=contracts.get(name)
            if value is None:return frozen({'status':'absent'})
            if value['_role'] not in {'external','all','composite','triggered','embedded_event','update','lifecycle','extension_external','extension_channel'}:return frozen({'status':'non-channel'})
            return frozen({'status':'present','header':{k:v for k,v in value.items() if not k.startswith('_')}})
        return lookup

    def accept_external(self, declaration, contracts, registry, event, timestamp, checkpoint, meter, owner,
                        *, document=None, channel=None, generation=None, evidence=None):
        from .channels import event_observation
        runtime_meter = RuntimeMeter(meter, self.binding, owner)
        context = ExternalChannelContext(
            self.header(declaration), frozen(event_observation(registry, event)),
            timestamp, frozen(checkpoint), self.peers(declaration, contracts), runtime_meter,
            owner, document, channel, generation, frozen(evidence))
        try:
            accepted = self.implementation.accept(context)
            require(type(accepted) is bool, 'INVALID_RUNTIME_ACCEPTANCE')
        except (GasExhausted, ContractError):
            runtime_meter.merge(failed=True)
            raise
        except HOST_FAILURES as exc:raise incomplete(exc) from exc
        except Exception as exc:
            runtime_meter.merge(failed=True)
            raise ContractError('RUNTIME_FAILURE', exception=type(exc).__name__) from exc
        runtime_meter.merge()
        return accepted


@dataclass(frozen=True)
class ExternalChannelContext:
    header: object
    event: object
    timestamp: int
    checkpoint: object
    peers: object
    gas: RuntimeMeter
    member: str | None = None
    document: str | None = None
    channel: str | None = None
    generation: int | None = None
    evidence: object = None


@dataclass(frozen=True)
class AdmissionContext:
    """Exact invocation facts passed to an installed evidence verifier.

    The verifier, not the submitting client, establishes channel decisions.
    Its result is private to this invocation and exposed read-only to accept().
    A serialized invocation retains the original evidence and verifies it again.
    """
    snapshot: str
    event: str
    timestamp: int
    runtime: object
    members: object
    evidence: object


def prepare_admissions(run):
    """Verify configured evidence without introducing a fourth process input."""
    from .channels import checkpoint
    supplied = run.admission_evidence
    require(type(supplied) is dict, 'INVALID_ADMISSION_EVIDENCE')
    runtimes = {}
    for member in sorted(run.graph.reachable(active=True)):
        doc = run.input.documents[member]
        for key, declaration in sorted(run.reg.contracts(doc.body).items()):
            if declaration['_role'] != 'extension_external':
                continue
            runtime = declaration['_extension']
            if not callable(getattr(runtime.implementation, 'verify_admission', None)):
                continue
            binding = runtime.binding.type_id
            _, rows = runtimes.setdefault(binding, (runtime, []))
            rows.append(dict(member=member, document=doc.blue_id, channel=key,
                             declaration=run.blue.identity(run.blue.exact(declaration['_recipe'])),
                             generation=doc.channel_lives[key].generation,
                             header={k: declaration[k] for k in runtime.binding.header_fields if k in declaration},
                             checkpoint=checkpoint(run.reg, doc, key)))
    require(set(supplied) <= set(runtimes), 'UNUSED_ADMISSION_EVIDENCE')
    result = {}
    for binding, (runtime, rows) in sorted(runtimes.items()):
        context = AdmissionContext(run.input.identity, run.event_id, run.timestamp,
                                   frozen(runtime.binding.wire()), frozen(rows), frozen(supplied.get(binding)))
        try:
            verified = runtime.implementation.verify_admission(context)
            require(type(verified) is dict, 'INVALID_VERIFIED_ADMISSION')
            # Retain a private data copy; accept_external freezes each read.
            result[binding] = data_copy(verified)
        except ContractError:
            raise
        except HOST_FAILURES as exc:raise incomplete(exc) from exc
        except Exception as exc:
            raise ContractError('INVALID_ADMISSION_EVIDENCE', exception=type(exc).__name__) from exc
    run.external_admissions = result


def validate_result(value):
    closed(value,set(),{'patches','events','termination','runtimeLedger'})
    patches=value.get('patches',[]);events=value.get('events',[])
    require(type(patches) is list and type(events) is list,'INVALID_EXECUTION_RESULT')
    for patch in patches:
        require(type(patch) is dict and patch.get('op') in ('add','replace','remove'),'INVALID_PATCH')
        closed(patch,{'op','path'} if patch['op']=='remove' else {'op','path','val'})
        require(segments(patch['path']) and all(segments(patch['path'])),'INVALID_PATCH_PATH')
    if 'termination' in value:
        termination=closed(value['termination'],{'cause'},{'reason'})
        require(type(termination['cause']) is str and ('reason' not in termination or type(termination['reason']) is str),'INVALID_TERMINATION')
    return {'patches':patches,'events':events,**{k:v for k,v in value.items() if k not in ('patches','events')}}
```

### `src/blue_contracts/reference/storage.py`

```python
"""Verified snapshots, portable invocation capsules and atomic local publication.

Expected commitments must come from a trusted source. Serialization and hashing
are not provider authentication or authorization.
"""
from copy import deepcopy
import json,sqlite3
from algorithms import blue as L
from .model import Snapshot,Document,Edge,ChannelLife,ContractError,require,closed,digest,canonical,integer,token,Meter

def export_snapshot(engine,snapshot,*,require_initialized=True):
    engine.validate(snapshot,require_initialized=require_initialized);records={}
    for _,doc in sorted(snapshot.documents.items()):records.update(L.admitted_records(doc.body,engine.blue.context))
    # Implementations are installed separately, but their exact declarative
    # bindings and semantic resources must survive a portable cold restore.
    for binding in snapshot.runtimes:
        for name in ('type_id','semantics_id'):
            records.update(L.admitted_records(L.Ref(binding[name]),engine.blue.context))
    return {'snapshot':snapshot.wire(),'identity':snapshot.identity,'content':records}
def import_snapshot(engine,package,expected_identity,*,require_initialized=True):
    closed(package,{'snapshot','identity','content'});require(package['identity']==expected_identity,'UNTRUSTED_SNAPSHOT_COMMITMENT');wire=closed(package['snapshot'],{'root','documents','edges','generation','revision','release','runtimes'})
    require(digest('contracts.snapshot/completion-1',wire)==expected_identity,'INVALID_SNAPSHOT_COMMITMENT');require(wire['release']==engine.registry.specification,'INCOMPATIBLE_RELEASE')
    language=engine.blue.language;c=language.processing_context();c.provider.update(deepcopy(package['content']));docs={}
    for row in wire['documents']:
        closed(row,{'key','blueId','channels','channelSerials','edgeSerials','birth'});key=token(row['key']);require(key not in docs,'DUPLICATE_DOCUMENT_KEY');n=L.Ref(L.final_id(row['blueId']));L.open_exact(n,c);L.strict_certify(n,c,'value');lives={}
        for k,v in row['channels'].items():
            token(k);closed(v,{'generation','signature'});integer(v['generation'],1);lives[k]=ChannelLife(v['generation'],v['signature'])
        for counters in (row['channelSerials'],row['edgeSerials']):
            require(type(counters) is dict,'INVALID_GENERATIONS')
            for k,v in counters.items():token(k);integer(v,1)
        docs[key]=Document(key,n,row['blueId'],lives,dict(row['channelSerials']),dict(row['edgeSerials']),token(row['birth']) if row['birth'] is not None else None)
    edges={}
    for row in wire['edges']:
        e=Edge(**closed(row,{'source','path','target','generation'}));integer(e.generation,1);require(e.key not in edges,'DUPLICATE_EDGE');edges[e.key]=e
    state=Snapshot(wire['root'],docs,edges,integer(wire['generation']),integer(wire['revision']),wire['release'],tuple(wire['runtimes']));require(state.identity==expected_identity,'INVALID_SNAPSHOT_COMMITMENT');old=engine.blue.context
    try:engine.blue.context=c;engine.validate(state,require_initialized=require_initialized)
    finally:engine.blue.context=old
    language.provider.merge_responses(package['content']);engine.blue.refresh();engine.archive.add(state);return state

def compare_replay(saved,actual):
    closed(saved,{'observations','receipt'});require(digest('contracts.result/completion-1',saved['observations'])==saved['receipt'],'INVALID_RECEIPT')
    return {'verified':canonical(saved['observations'])==canonical(actual.observations()),'expected':saved['receipt'],'actual':actual.receipt}

class Journal:
    def __init__(self,path,engine):
        self.engine=engine;self.db=sqlite3.connect(str(path),isolation_level=None);self.db.execute('PRAGMA foreign_keys=ON');self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS heads(name TEXT PRIMARY KEY, identity TEXT NOT NULL, package TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY, slot TEXT NOT NULL, evidence TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY, receipt TEXT NOT NULL, event TEXT NOT NULL, acknowledged INTEGER NOT NULL DEFAULT 0);
        ''')
    def close(self):self.db.close()
    def initialize(self,name,snapshot):
        package=export_snapshot(self.engine,snapshot)
        try:self.db.execute('INSERT INTO heads VALUES(?,?,?)',(token(name),snapshot.identity,json.dumps(package,ensure_ascii=False)))
        except sqlite3.IntegrityError as e:raise ContractError('SLOT_ALREADY_EXISTS') from e
    def load(self,name):
        row=self.db.execute('SELECT identity,package FROM heads WHERE name=?',(name,)).fetchone();require(row is not None,'UNKNOWN_SLOT');return import_snapshot(self.engine,json.loads(row[1]),row[0])
    def commit(self,name,result,*,fail_before_commit=False):
        require(result.commits,'NONCOMMITTING_RESULT');package=export_snapshot(self.engine,result.snapshot);record={'observations':result.observations(),'receipt':result.receipt};self.db.execute('BEGIN IMMEDIATE')
        try:
            prior=self.db.execute('SELECT evidence,slot FROM receipts WHERE id=?',(result.receipt,)).fetchone()
            if prior is not None:
                require(prior[1]==name,'RECEIPT_SLOT_MISMATCH');require(json.loads(prior[0])==record,'RECEIPT_COLLISION');self.db.execute('ROLLBACK');return 'ALREADY_COMMITTED'
            row=self.db.execute('SELECT identity FROM heads WHERE name=?',(name,)).fetchone();require(row is not None and row[0]==result.input_identity,'COMPARE_AND_SWAP_CONFLICT')
            self.db.execute('UPDATE heads SET identity=?,package=? WHERE name=?',(result.snapshot.identity,json.dumps(package,ensure_ascii=False),name));self.db.execute('INSERT INTO receipts VALUES(?,?,?)',(result.receipt,name,json.dumps(record,ensure_ascii=False)))
            for event in result.public_events:self.db.execute('INSERT INTO outbox(id,receipt,event) VALUES(?,?,?)',(event['identity'],result.receipt,json.dumps(event,ensure_ascii=False)))
            if fail_before_commit:raise ContractError('INJECTED_STORAGE_FAILURE')
            self.db.execute('COMMIT');return 'COMMITTED'
        except Exception:
            if self.db.in_transaction:self.db.execute('ROLLBACK')
            raise
    def pending(self):return [json.loads(row[0]) for row in self.db.execute('SELECT event FROM outbox WHERE acknowledged=0 ORDER BY rowid')]
    def acknowledge(self,occurrence):self.db.execute('UPDATE outbox SET acknowledged=1 WHERE id=?',(occurrence,))

def export_invocation(engine, snapshot, event, eventTimestamp):
    """Portable replay input, not a second processor interface."""
    integer(eventTimestamp)
    event = engine.blue.node(event) if isinstance(event,(L.Node,L.Ref)) else engine.blue.source(event)
    content = L.admitted_records(event,engine.blue.context)
    views = [export_snapshot(engine,engine.archive.versions[sid]) for _,sid in engine.archive.bindings()]
    data = {'input':export_snapshot(engine,snapshot),'event':{'blueId':engine.blue.identity(event)},
            'eventTimestamp':eventTimestamp,'views':views,'content':content,
            'gasPolicy':Meter(engine.gas_limit,engine.local_limits,snapshot.documents).policy()}
    return {'invocation':data,'identity':digest('contracts.capsule/completion-1',data)}


def import_invocation(engine, package, expected_identity):
    """Verify the capsule, restore its configured gas policy, return three inputs."""
    closed(package,{'invocation','identity'})
    require(package['identity']==expected_identity and
            digest('contracts.capsule/completion-1',package['invocation'])==expected_identity,
            'INVALID_CAPSULE_COMMITMENT')
    data=closed(package['invocation'],{'input','event','eventTimestamp','views','content','gasPolicy'})
    integer(data['eventTimestamp']);closed(data['event'],{'blueId'})
    language=engine.blue.language;c=language.processing_context()
    c.provider.update(deepcopy(data['content']))
    event=L.Ref(L.final_id(data['event']['blueId']))
    L.strict_certify(event,c,'value')
    language.provider.merge_responses(data['content']);engine.blue.refresh()
    for view in data['views']:
        snapshot=import_snapshot(engine,view,view['identity'])
        engine.archive.bind(snapshot.documents[snapshot.root].blue_id,snapshot.identity)
    snapshot=import_snapshot(engine,data['input'],data['input']['identity'])
    policy=closed(data['gasPolicy'],{'shared','local','profile'})
    require(Meter(policy['shared'],policy['local'],snapshot.documents).policy()==policy,'INVALID_GAS_POLICY')
    engine.gas_limit=policy['shared'];engine.local_limits=deepcopy(policy['local'])
    return snapshot,event,data['eventTimestamp']
```

### `src/blue_contracts/reference/work.py`

```python
"""Run-local logical work, independent of physical resolver/cache warmth."""
from algorithms import blue as L

EMPTY_LIST_ID=L.H({'$list':'empty'})


def canonical_size(value):
    """Exact canonical UTF-8 size, without allocating serialized Text."""
    def quoted(text):
        size=2
        for char in text:
            n=ord(char)
            size += (2 if char in '\"\\\b\f\n\r\t' else 6 if n<32 else
                     1 if n<128 else 2 if n<2048 else 3 if n<65536 else 4)
        return size
    pending=[value];size=0
    while pending:
        current=pending.pop()
        if isinstance(current,dict):
            size+=2+max(0,len(current)-1)+len(current)
            for key,item in current.items():size+=quoted(key);pending.append(item)
        elif isinstance(current,(tuple,list)):
            size+=2+max(0,len(current)-1);pending.extend(current)
        elif isinstance(current,str):size+=quoted(current)
        else:size+=len(L.canonical_text(current))
    return size


class LogicalWork:
    def __init__(self,blue,meter):
        self.blue=blue;self.meter=meter;self.manifests=set();self.established=set();self.proofs=set()
        self.carried_roots=set()
        self.bound_identities=set()
        self.exact_values={}
        self.partition=None

    def exact(self,recipe,blue):
        """Captured exact content; prepay synthesis of multi-part recipes.

        Single contributions already have admission/opening evidence. Contextual
        requirements are not part of their exact identity. Refining several
        contributions creates content, even if a physical resolver is warm.
        """
        if len(recipe.parts)==1:return recipe.parts[0]
        from copy import copy
        key=recipe.key()
        if key not in self.exact_values:
            context=copy(blue.context)
            def remember(node):
                identity=self.establish(node)
                if isinstance(node,L.Node):
                    context.bodies[identity]=node
                    blue.note_identity(node,identity)
                return node
            context.remember=remember
            try:node=L.recipe_exact_value(recipe,context)
            except L.Failure as error:blue.translate(error)
            # Carry the prepaid identity explicitly. Native continuation copies
            # can change handles; a physical cache must not decide whether this
            # construction evidence survives transport.
            self.exact_values[key]=(node,blue.known_identity(node))
        node,identity=self.exact_values[key]
        if isinstance(node,L.Node):blue.note_identity(node,identity)
        return node

    def open(self,node):
        identity=self.blue.identity(node)
        if identity not in self.manifests:
            self.meter.contracts('nodeManifestOpened');self.manifests.add(identity)
        return self.blue.open(node)

    def compare(self,left,right):
        self.meter.contracts('scalarComparison')
        if type(left) is str and type(right) is str:
            for offset in range(0,min(len(left),len(right)),64):
                self.meter.contracts('textBlockExamined')
                self.meter.contracts('textBlockExamined')
                a,b=left[offset:offset+64],right[offset:offset+64]
                if a!=b:return (a>b)-(a<b)
            return (len(left)>len(right))-(len(left)<len(right))
        elif type(left) is int and type(right) is int:
            self.meter.contracts('integerLimbOperation',max(1,(abs(left).bit_length()+31)//32)+max(1,(abs(right).bit_length()+31)//32))
        return (left>right)-(left<right)

    def ordered(self,contracts):
        """The prescribed stable bottom-up merge schedule, from key order."""
        rows=sorted(contracts.items());width=1
        def compare(a,b):
            self.meter.contracts('sortComparison')
            for left,right in zip((a[1].get('order',0),a[0],a[1]['type']['blueId']),
                                  (b[1].get('order',0),b[0],b[1]['type']['blueId'])):
                result=self.compare(left,right)
                if result:return result
            return 0
        while width<len(rows):
            output=[]
            for start in range(0,len(rows),2*width):
                left=rows[start:start+width];right=rows[start+width:start+2*width];i=j=0
                while i<len(left) and j<len(right):
                    if compare(left[i],right[j])<=0:output.append(left[i]);i+=1
                    else:output.append(right[j]);j+=1
                output.extend(left[i:]);output.extend(right[j:])
            rows=output;width*=2
        return rows

    def headers(self,body,contracts):
        """Inspect immutable ancestor contributions without compiling bodies."""
        seen=set();node=body
        while node is not None:
            identity=self.blue.identity(node)
            if identity in seen:break
            seen.add(identity);manifest=self.open(node)
            if manifest.has('contracts'):
                contribution=self.open(manifest.get('contracts'))
                self.meter.contracts('objectMemberRead',len(contribution.fields))
            parent=manifest.get('type')
            if parent is L.ABSENT:break
            self.meter.contracts('typeEdgeFollowed');node=parent

    def read(self,node,path):
        from .model import segments,require,LIMITS
        r=L.recipe(node)
        depth=0
        for name in segments(path):
            depth+=1
            for part in r.parts:self.open(part)
            head=self.blue.head(r)
            self.meter.contracts('listItemRead' if head.items is not None else 'objectMemberRead')
            r=self.blue.child(r,name)
            if r is None:break
        return self.blue.view(r,logical=self,depth=depth)

    def establish(self,node,previous=None,*,token=None,scope=None):
        # Input witnesses come from admission/opening, never a resolver cache.
        # Unknown candidates are visited postorder before any identity lookup.
        if isinstance(node,L.Local):return token(node.index)
        if isinstance(node,L.Ref):
            if '#' in node.id:return node.id
            node=self.blue.open(node)
        self._identity_input(node)
        identity,_=self._establish(node,previous,token=token,scope=scope,prerequisite=True)
        return identity

    def _identity_input(self,node):
        self.meter.contracts('identityInputMember',len(node.fields))
        for key,value in node.fields:
            self.meter.contracts('identityInputTextBlock',(len(key)+63)//64)
            if isinstance(value,str):self.meter.contracts('identityInputTextBlock',(len(value)+63)//64)
            elif key=='items':self.meter.contracts('identityInputMember',len(value))
            elif type(value) is int:
                limbs=max(1,(abs(value).bit_length()+31)//32)
                self.meter.contracts('integerLimbOperation',limbs*limbs)

    def _establish(self,node,previous=None,*,token=None,scope=None,prerequisite=False):
        if isinstance(node,L.Local):return token(node.index),True
        if isinstance(previous,L.Node) and self.blue.known_identity(previous) is None:self.blue.note_identity(previous)
        known=self.blue.known_identity(node)
        prior_id=self.blue.identity(previous) if previous is not None else None
        if known is not None:
            if (('ordinary',known) in self.established or known==prior_id or
                known in self.carried_roots or known in self.bound_identities or known in L.CORE_NAME or '#' in known):
                return known,False
        # Opening an admitted inline manifest must propagate the same child
        # witnesses as opening its Ref. Otherwise prior host reads affect reuse.
        node=self.blue.open(node)
        if not prerequisite:self._identity_input(node)
        old=self.blue.open(previous) if previous is not None else None
        pure_list=node.keys()==('items',);parts=[];local=False
        for key,value in node.fields:
            prior=old.get(key) if old is not None else L.ABSENT
            if key in L.LITERALS:
                if type(value) is str and value!=prior:self.meter.contracts('textBlockConstructed',(len(value)+63)//64)
                parts.append((key,True,value))
                continue
            if key=='mergePolicy':
                child,cyclic=self._establish(L.scalar('Text',value),None if prior is L.ABSENT else L.scalar('Text',prior),token=token,scope=scope)
            elif key=='items':
                if not pure_list:
                    child,cyclic=self._establish(L.list_node(value),L.list_node(prior) if isinstance(prior,tuple) else None,token=token,scope=scope)
                else:
                    old_items=prior if isinstance(prior,tuple) else ()
                    cyclic=False;prefix=True
                    # The empty fold is fixed, not a candidate-derived hash.
                    child=EMPTY_LIST_ID
                    for i,item in enumerate(value):
                        before=old_items[i] if i<len(old_items) else None
                        item_id,item_local=self._establish(item,before,token=token,scope=scope)
                        cyclic|=item_local
                        same=before is not None and item_id==L.identity(before,token)
                        prefix=prefix and same
                        if not prefix:self.meter.contracts('listFoldStepRecomputed')
                        child=L.append_id(child,item_id)
            else:child,cyclic=self._establish(value,None if prior is L.ABSENT else prior,token=token,scope=scope)
            local|=cyclic;parts.append((key,False,child))
        self.meter.contracts('nodeIdentityEstablished')
        if pure_list:identity=parts[0][2]
        else:
            self.meter.contracts('objectMemberRebuilt',len(node.fields))
            helper={key:value if literal else {'blueId':value} for key,literal,value in parts}
            size=canonical_size(helper)
            self.meter.contracts('directIdentityHashBlock',(size+9+63)//64)
            identity=L.H(helper)
        ledger_key=('cyclic',scope,identity) if local else ('ordinary',identity)
        self.established.add(ledger_key)
        # Issue evidence only after the complete successful charge/hash prefix.
        # Cyclic token-context hashes are not ordinary exact identity witnesses.
        if not local:self.blue.note_identity(node,identity)
        return identity,local

    def node_blue_id(self,value,meter):
        from .language import ExactValue
        from .model import require
        from blue_bex.values import blue_value
        require(meter is self.meter,'IDENTITY_METER_MISMATCH')
        if isinstance(value,ExactValue):
            node=self.exact(value._recipe,value._blue)
            known=value._blue.known_identity(node)
            if known is not None:return known
            return self.establish(node)
        # Validate output semantics before normalization (null is not an empty
        # node, and source directives/aliases are not runtime identity inputs).
        # Finite output validation is metered before allocating its projection.
        from blue_bex.values import size_parts
        for _ in size_parts(value,lambda counter,units=1:self.meter.charge(counter,units)):pass
        def prepare(item):
            # Exact children carry admission/identity evidence just like an
            # exact root. Do not flatten them into storage-shaped dictionaries.
            if isinstance(item,ExactValue):return item
            from blue_bex.values import UNDEFINED
            if type(item) is dict:
                return {key:prepare(part) for key,part in item.items() if part is not UNDEFINED}
            if type(item) is list:return [prepare(part) for part in item]
            return blue_value(item)
        node=self.node(prepare(value))
        return self.blue.identity(node)

    def node(self,value,*,goal='value',certify=True):
        """Normalize runtime output with guards before copying/encoding/hashing.

        Exact references remain references. Newly built children are normalized
        bottom-up; Language's remember hook cannot run ahead of establishment.
        """
        from copy import copy
        from blue_bex.values import HostValue,kind,UNDEFINED
        from .language import ExactValue
        context=copy(self.blue.context)
        def remember(node):
            identity=self.establish(node)
            if isinstance(node,L.Node):
                context.bodies[identity]=node
                # Constructed evidence is now explicit, after the successful
                # charge prefix. Every raw occurrence still pays normalization.
                self.blue.note_identity(node,identity)
            return node
        context.remember=remember
        def literal(value):
            if type(value) is str:self.meter.contracts('identityInputTextBlock',(len(value)+63)//64)
            elif type(value) is int:
                limbs=max(1,(abs(value).bit_length()+31)//32)
                self.meter.contracts('integerLimbOperation',limbs*limbs)
            return value
        def build(value):
            self.meter.contracts('identityInputMember')
            if isinstance(value,ExactValue):value=self.exact(value._recipe,value._blue)
            if isinstance(value,(L.Node,L.Ref)):
                self.establish(value);return value
            if isinstance(value,HostValue):value=value.output_view()
            if kind(value)=='object':
                count=len(value);self.meter.contracts('identityInputMember',count)
                keys=list(value)
                rounds=(count-1).bit_length() if count else 0
                self.meter.contracts('identityInputMember',count*rounds)
                self.meter.contracts('identityInputTextBlock',sum((len(key)+63)//64 for key in keys)*(rounds+1))
                # Language's UTF-16 canonical order; keys have been prepaid.
                keys=L.ordered(keys)
                raw={}
                for key in keys:
                    part=value[key]
                    if part is UNDEFINED:continue
                    if key in L.LITERALS|{'mergePolicy','blueId'}:
                        raw[key]=literal(part)
                        if key=='value':raw[key]=self.blue.normalize_input({'value':raw[key]},aliases=False)['value']
                    elif key=='items':
                        self.meter.contracts('identityInputMember',len(part))
                        raw[key]=[build(item) for item in part]
                    else:raw[key]=None if part is None else build(part)
                # Preserve runtime rejection of string aliases in type slots.
                for key in L.TYPES & set(raw):
                    if type(value[key]) is str:
                        from .model import require
                        require(False,'UNRESOLVED_RUNTIME_TYPE',alias=value[key])
            elif kind(value)=='list':
                self.meter.contracts('identityInputMember',len(value))
                raw={'items':[build(item) for item in value]}
            else:raw=self.blue.normalize_input(literal(value),aliases=False)
            return L.normalize(raw,context,'exact')
        try:
            node=build(value)
            if certify:
                if goal=='value':self.validate(node)
                else:self.blue.certify(node,goal)
            self.blue.remember(node)
            return node
        except L.Failure as error:self.blue.translate(error)

    def validate(self,node,previous=None):
        """Account changed contextual obligations, then use Language validation.

        Unchanged children under identical requirements retain their admitted
        context. Header changes conservatively revisit descendant obligations.
        """
        pending=set()
        def visit(recipe,old=None,seen=frozenset()):
            if recipe.key() in seen:return
            # Carrying an already admitted invocation subject into an
            # unrestricted reference slot introduces no new obligation. This
            # inventory is derived from bound inputs, never resolver warmth.
            if not recipe.requirements and len(recipe.parts)==1 and self.blue.identity(recipe.parts[0]) in self.carried_roots:return
            h=self.blue.head(recipe);key=(recipe.key(),'value')
            if key in self.proofs or key in pending:self.meter.contracts('validationProofReused');return
            if old is not None and recipe.key()==old.key():return
            seen=seen|{recipe.key()};prior=self.blue.head(old) if old is not None else None
            for part in recipe.parts:self.open(part)
            constraints=h.constraints
            for _ in L.describe_constraints(constraints):self.meter.contracts('schemaPredicateEvaluated')
            if h.value is not L.ABSENT:
                value=h.value
                if type(value) in (int,float):
                    for bound in (constraints.lower,constraints.upper):
                        if bound is not None:self.compare(value,int(bound.value) if bound.value.denominator==1 else float(bound.value))
                    if constraints.multiple is not None:
                        self.meter.contracts('scalarComparison')
                        if type(value) is int:
                            limbs=max(1,(abs(value).bit_length()+31)//32)*max(1,(abs(constraints.multiple.numerator).bit_length()+31)//32)
                            self.meter.contracts('integerLimbOperation',limbs)
                elif type(value) is str and constraints.counts:
                    self.meter.contracts('textBlockExamined',(len(value)+63)//64)
                    for count in constraints.counts.values():self.compare(len(value),count)
                if constraints.enum is not None:
                    for group in constraints.enum:
                        for alternative in group:
                            self.meter.contracts('validationMemberExamined')
                            _,core,other=constraints.enum_values[alternative]
                            if type(other) is type(value) and self.compare(value,other)==0:break
            for field in sorted(h.fields):
                child=L.child_recipe(h,field);before=L.child_recipe(prior,field) if prior and field in prior.fields else None
                if before is not None and child.key()==before.key():continue
                self.meter.contracts('objectMemberRead')
                if h.value_type or h.key_type:self.meter.contracts('validationMemberExamined')
                visit(child,before,seen)
            if h.items is not None:
                for count in constraints.counts.values():self.compare(len(h.items),count)
                for i in range(len(h.items)):
                    child=L.child_recipe(h,i);before=L.child_recipe(prior,i) if prior and prior.items is not None and i<len(prior.items) else None
                    if before is not None and child.key()==before.key() and not h.constraints.unique:continue
                    self.meter.contracts('listItemRead')
                    if h.item_type or h.constraints.unique:self.meter.contracts('validationMemberExamined')
                    visit(child,before,seen)
            if h.contracts is not None:
                previous_contracts=prior.contracts if prior else None
                if previous_contracts is None or h.contracts.key()!=previous_contracts.key():visit(h.contracts,previous_contracts,seen)
            pending.add(key)
        visit(L.recipe(node),L.recipe(previous) if previous is not None else None)
        self.blue.certify(node)
        self.proofs.update(pending)
```

### `src/blue_host/__init__.py`

```python
"""Operational control flow shared by the stack; never a semantic rejection.

Hosts may retry the same input with the same gas after fixing capacity or
cancellation. This module has no dependency on any Blue semantic layer.
"""
from concurrent.futures import CancelledError
from asyncio import CancelledError as AsyncCancelledError
from functools import wraps


class HostIncomplete(Exception):
    code = 'HOST_INCOMPLETE'

    def __init__(self, reason, **context):
        self.reason = reason
        self.context = {'reason': reason, **context}
        super().__init__(reason)


HOST_FAILURES = (HostIncomplete, MemoryError, RecursionError, CancelledError, AsyncCancelledError)


def incomplete(error):
    if isinstance(error, HostIncomplete):
        return error
    return HostIncomplete(type(error).__name__)


def host_boundary(fn):
    """Convert incidental host failures without manufacturing an Outcome."""
    @wraps(fn)
    def run(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except HOST_FAILURES as error:
            raise incomplete(error) from error
    return run
```

### Source inventory

| Module | SHA-256 of supplied UTF-8 file |
|---|---|
| `src/blue_contracts/reference/__init__.py` | `78bed996244ac5fab47a02c2455614e69b920a4268f0a7fda241a54702b34bef` |
| `src/blue_contracts/reference/catalogue.py` | `51e75dfa01394a8b2493292d2dfc4c79c3b2031c8035a85882b284126c7585df` |
| `src/blue_contracts/reference/channels.py` | `1af7e3f1ba921fe0c4adac9d60f0b26e7b0e5c106d8c58fd3a801c3c0310160c` |
| `src/blue_contracts/reference/chunks.py` | `d1b3c588fb98c0ebaf5b18e2105384c3a38037dba58f2406228d994ad2e3af4e` |
| `src/blue_contracts/reference/completion.py` | `c46ac5fb09b69ba71d5284f47aed55251acff7aa958e8f1ee2f65d102ec3bd63` |
| `src/blue_contracts/reference/compute.py` | `147caf84e70bebb5e3dec2bd3f5d437a25b85e172d3d12e1b4c3725f79fa76ba` |
| `src/blue_contracts/reference/generalization.py` | `1f24b86271755ae5f1b5132c31de85d12d05d2a19c7c4b5d493201b953dff887` |
| `src/blue_contracts/reference/graph.py` | `106b07e478bf77e2314b28044e0338429958ac58397db83f142ae0d5d8247b17` |
| `src/blue_contracts/reference/language.py` | `2ae90402ede1299c0cd43c770406e0572ea8b68a384ce0d4bc01734da4b2f889` |
| `src/blue_contracts/reference/model.py` | `5dc49fa84e457f8c362b88b961e9036a1812a5697958a76cf0f3119a9dcdc145` |
| `src/blue_contracts/reference/policy.py` | `2423e9d280e20db1d08d8d6c42a8a8e4ab8e53d5f335866a27dd0eb7f2433121` |
| `src/blue_contracts/reference/processor.py` | `f9f8e70373d970f7cc0ee1a8322317418da154934af2506c8731ebbed755952c` |
| `src/blue_contracts/reference/receiving.py` | `f5d56b66afd83cc0128883018b412282145238f6a956e4077bb530996039c7ff` |
| `src/blue_contracts/reference/registry.py` | `93a3b8bad491d80782778e8032798f4671ee2a996f39694d44baa2f700bced6a` |
| `src/blue_contracts/reference/runtime.py` | `0b33f51fb2d99a01d1867ac24767b4158139de9165eef0f93f86750bf24b9196` |
| `src/blue_contracts/reference/storage.py` | `eae5dc318c226628d2a68a37175b10232846ed2611b1a8db4a007bbd6266458f` |
| `src/blue_contracts/reference/work.py` | `bdff38e23e770ce1cd47d99535cd668c59865c301f97b5622bc5c0812e64ff5f` |
| `src/blue_host/__init__.py` | `ac30b5090d56b101150b3bdb9bb05fff265308737c3ea0dd8b9caa22b0b5b607` |

