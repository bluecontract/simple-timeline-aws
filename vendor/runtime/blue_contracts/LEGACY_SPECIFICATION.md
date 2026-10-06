# Blue Contracts 1.0 — Executable Reference Candidate

**Status:** selected-document processor candidate with a rooted managed-closure integration profile, 19 September 2026. This specification describes what the included Python algorithms implement and separately records the upstream obligations they do not yet implement. It is not a claim that the pinned generic Java Contracts processor has been ported in full.

## 1. Layer and imported definitions

Contracts turns one admitted input into document reactions and a candidate result. It does not choose an arbitrary next external Timeline entry. Blue Language supplies all semantic admission, types, references, effective views, specialization, and identity. BEX supplies deterministic computation and proposed ordered effects. Coordination supplies authenticated, ordered, eligible external deliveries.

The generic processor consumes an admitted selected document, a selected input, selected channel addresses, an optional operation, the shared gas ledger, and explicit dependency-read capabilities. It returns a staged document and ordered root-scope events. The managed host owns finalization and publication of the enclosing closure.

`ALGORITHMS.md` contains executable Python file blocks corresponding exactly to `blue_contracts/`. `../../blue_coordination/closure.py` supplies the graph-level host described in the Coordination specification. It is important not to confuse local inline scopes with separately managed documents.

## 2. Documents, scopes, and executable contracts

A scope is an object within the selected document carrying effective Contracts declarations. Contract identification uses exact installed type IDs. Human-readable aliases are authoring conveniences only. A same-shaped node with an unregistered type is not silently treated as an installed runtime contract.

The effective contract view retains Language labels needed for execution, including a workflow step's name. Program bodies, event literals, changeset literals and patterns preserve admitted Source structure rather than flattening every nested type's inherited fields into executable data. Otherwise even inherited specification Text can incorrectly become an emitted field and a gas cost. It is an observation, not an exact serialization and not a new identity scheme. Document state is admitted as a definition-bearing document because operation request declarations and event filters contain patterns. Event and patch values cross the value-admission boundary separately. Integers beyond the safe native JSON range use Language's explicit Integer/text Source encoding, rather than silently rounding or transmitting an unsafe integer token. The adapter declares a 4096-character Integer text limit; a custom typed large scalar must use explicit canonical Source value text.

Unknown required contract types fail preflight. A contract is required when explicitly marked `mustUnderstand` or referenced as a channel by an executable contract. Unknown optional inert content is preserved, not executed. Ordering is by Integer `order`, then Text key. Invalid ordering metadata fails rather than relying on dictionary insertion order.

## 3. Runtime capabilities and markers

The local catalogue installs Process Embedded, embedded/triggered/update/lifecycle channels, checkpoint and initialization/termination markers, and the supported Coordination workflows and steps. These catalogue IDs bind to this candidate's specification Text. They are not the Java production catalogue IDs.

Processor-owned markers occupy canonical keys. A handler cannot write initialization, termination, checkpoint, process, managed, or runtime bookkeeping through ordinary changesets. The internal processor and managed host have separate privileged mutation paths. This privilege is not available to BEX data programs.

This candidate recognizes the Type Generalization Policy role but rejects execution requiring its nearest-valid generalization adapter. It never implements generalization by silently removing type information. Full marker-schema compatibility and all catalogue generations remain part of the production conformance gate.

## 4. Preflight and initialization

Preflight recursively discovers declared inline scopes, checks required runtime capabilities and basic contract shapes, and rejects unsupported requirements before processing gas is charged. Managed dependency boundaries are provided explicitly by the closure host and are not recursively flattened into inline scopes.

An uninitialized inline scope runs its initiation lifecycle reaction and receives the processor-owned initialized marker. The marker refers to the admitted pre-initialization document identity. Initialization is charged distinctly from ordinary scope entry and reaction work. An already terminated scope performs no new user reaction.

The managed host in this package initializes explicitly authored graph members in a separate admission phase and then finalizes the graph. **This is a fixture-oriented graph admission profile, not a port of Java's full rooted initialization-causality machinery.** Historical attachment from committed local history is supported by the managed host. Lifecycle causality across newly admitted SCCs remains unsupported.

## 5. Inline processing order

Within a selected scope, the processor first visits declared inline embedded children, then establishes initialization where required, then dispatches the selected external channel/operation, then bridges child emissions to matching parent embedded channels, and finally drains the scope's triggered-event queue. The algorithms define the precise inactive-scope checks between these phases.

Process Embedded supports individual paths and object-backed collection paths. Collection members are traversed in sorted key order. A repeated declared occurrence path is invalid. Separate paths targeting equal values remain separate occurrences; equal content does not erase an occurrence.

Managed document edges are supplied to the closure separately. Directly traversing a managed edge as if it were an inline child is forbidden. A graph-aware finite read can cross a managed edge, but full recursive flattening of an entire cycle is not required or attempted.

## 6. Channel matching and handlers

A selected external channel must exist. Workflow handlers and operations are selected by exact runtime role, channel, operation key when applicable, and Blue event specialization. Matching is performed against the current effective declarations at the relevant dispatch point; a single input does not authorize arbitrary unselected operations.

Embedded channels match the occurrence source path and optional event filter. Update channels match an affected path or descendant and optional filter. Triggered channels consume the FIFO emission queue. Lifecycle channels consume processor-generated lifecycle events. Handler order is stable by declared order and key.

This processor's direct `channels` API is a trusted internal port. It does not authenticate callers. The public in-process `Stack` routes through Coordination eligibility first. Direct use of `Processor.process` by an application must supply equivalently validated channel and operation selections.

## 7. Workflow execution and step results

A handler owns an ordered list of steps and a map of earlier step results. Supported steps are Compute, Update Document, Trigger Event, and Terminate Processing. An unsupported exact step runtime fails; it is never skipped as a no-op.

A named result is stored under its Language name label. Unnamed steps use their positional reference key. Each Compute receives a stable current document snapshot, the dispatched event, the current contract, previous results, and the current scope. Computation cannot observe its own unapplied changes through `$document`; it uses `$resultValue` for that observation.

Compute has a positive local gas limit, defaulting to 100000, and charges admitted BEX work to the same closure meter. `returnResult` controls storage of its result. `emitEvents` controls whether its events are applied. Program definition resolution is not implicit; a production adapter must fetch and validate referenced definitions before execution.

## 8. Selecting and validating Compute effects

The returned object's non-null `changeset` replaces the accumulated changeset. A present empty list therefore suppresses previously accumulated changes. Missing or null selection uses the accumulator. Events follow the same selection rule. This selector behavior does not make a null patch value or null event admissible at the Blue output boundary.

Before mutating the staged document, the processor checks every effect's structural shape and converts/admit-checks every proposed value. Changesets must be lists of add/replace/remove records with exactly the permitted keys. Remove must not carry `val`. Other mutations require it. Events are admitted values. A termination selection must have a supported cause and optional Text reason.

The algorithm then applies patches in order, followed by events, followed by a termination request, stopping when the scope becomes inactive. All effects are still tentative until the enclosing host commits. A later boundary, type, gas, or capability failure cannot authorize an earlier tentative effect to become public.

## 9. Mutation semantics

Contracts mutations are not a generic library's JSON Patch defaults. Object add and replace are upserts. Missing object intermediates can be created for non-remove operations. List add inserts, replace changes an existing position, and remove shifts later positions. Indices are canonical nonnegative decimal indices; append is available only where the operation permits it. Missing removal targets fail.

A handler cannot replace the selected root or its own scope root, escape its scope, cross a managed document boundary to mutate a child, or write reserved markers. A replacement at a managed root is still subject to graph-level admission and is admitted transactionally by the managed host, or rejected if its required evidence/capability is unavailable.

Each tentative resulting document is revalidated through Language. The processor does not return a structural hash for an invalid result. Fixed-value inheritance constraints, referenced definitions, and Language collection rules continue to apply. The candidate performs strict rejection rather than nearest-valid type generalization.

## 10. Update cascades and inline observation

After an admitted tentative patch, the processor constructs a Document Update observation containing the operation, absolute path, and present before/after values. Absence is omission, not null. Matching update reactions run immediately in the active ancestor chain before the next effect in the original changeset is applied.

This immediate cascade makes effect order observable. It must not be replaced by applying all patches first and issuing a bulk notification afterward. Cascade work uses the shared gas ledger. The candidate also imposes a portable synchronous-cascade depth limit; exceeding it is a capability failure, not success.

The current inline implementation covers the included phase/cascade examples. Complete equivalence for dynamic inline child replacement, nested externally addressed deliveries, and every upstream scope-boundary corner case is not established. The managed host owns independent child initialization, history and publication; it passes managed_children=True so the local processor does not also initialize those children as inline scopes. Dynamic cyclic ownership changes remain unsupported.

## 11. Emissions, queues, and loops

An emitted event is appended to the scope's ordered output and its triggered-event FIFO. Emission occurrences are not deduplicated by equal value or equal BlueId. Triggered queues drain iteratively until no work remains or the scope terminates/fails.

A finite self-reaction can therefore finish normally. A nonterminating self-reaction or managed-document feedback loop consumes the shared gas allowance and fails. No arbitrary "already seen this event hash" shortcut is allowed to manufacture termination. A memory/allocation guard may fail earlier but cannot claim a successful fixed point.

Child-to-parent bridging is path-sensitive. For managed graphs, the closure enumerates vertex-simple routes for each emission and then allows newly produced emissions to initiate new routes. "Simple route" prevents infinite traversal while routing one event; it does not prevent legitimate repeated business reactions around a cycle.

## 12. Termination and failure layers

Graceful termination writes a termination marker, emits lifecycle information, and stops further user reaction in the scope. Fatal termination is a distinct failure. Provider unavailability, invalid evidence, unsupported capability, semantic gas exhaustion, and ordinary contract failure must remain distinguishable to the outer driver.

**Important profile boundary:** this Python processor raises on fatal failure and lets the managed host discard its staged closure. It does not yet reproduce every upstream generic Contracts result envelope, local-fatal state projection, or parent-continuation rule. A successful graceful result can be committed; a noncommitting closure result publishes no tentative state or events.

A production adapter must preserve the difference between local scope termination, a valid committed terminated result, a failed managed closure, and an operational cancellation. These are not interchangeable outcomes and must not all be called "rollback".

## 13. Metering

The algorithm charges scope entry, initialization, handlers, patch boundaries, mutation size, validation paths, update cascades, event emission, bridging, queue dequeue, lifecycle work, termination, and BEX work. Managed scheduling and checkpoints add explicit host charges. One meter spans the full selected closure; dependency work is not free merely because it is private.

The default selected-document tariffs in this candidate are: scope entry `50 + 10*depth`; initialization 1000; handler 50; boundary 2; mutation `20 + ceil(bytes/100)` or remove 10; type-path check `5*(path segments+1)`; update cascade 10; emission `20 + ceil(bytes/100)`; bridge 10; FIFO dequeue 10; lifecycle 30; termination marker 20; explicit fatal surcharge 100. The host charges work admission 10 and checkpoint 20 per accepted source channel.

Byte counts use Language's canonical JSON text on the selected profile representation. Validation charges currently count the checked path approximation, not every internal Java type-check visit. These are **candidate tariffs**, not demonstrated Java gas parity. Gas-boundary tests verify `G-1`, `G`, and `G+1` within the same frozen Python execution profile.

## 14. Managed execution and publication interface

The host supplies selected graph members, their immutable base identities, history bases, occurrence edges, read capabilities, accepted deliveries, and publication ownership. Processing is staged. Each reaction sees earlier admitted changes in that staged selected graph. Managed cycles are handled by work queues and actual Language cyclic-set finalization.

After work converges, the host writes accepted channel checkpoints using the original Timeline Entry, finalizes changed graph content, advances the selected logical transition, and commits the owned result atomically. A dependency processed privately for another root cannot independently publish its own public state merely because the parent needed it.

The selected root's public event stream is distinct from all internal emitted events and from the set of members authorized for atomic state publication. The branching-cycle Java example tests this distinction: seven work items, five root-public events, and five changed SCC members.

## 15. Imports, recovery, and operational ports

Retained-history import requires proofs of the exact receiving occurrence, source position and predecessor chain, runtime semantics, original invocation, output closure, and publication authority. An event payload or final body hash alone is not that proof. These obligations belong in the Contracts/history adapter, not a second MyOS-specific entitlement engine.

The included managed host saves originals and receipts in memory and can replay them without republishing effects. It is not durable storage. It deliberately blocks live progress when a required retained prerequisite is declared unavailable. It does not synthesize a historical import or guess an initial source position.

Production storage must atomically persist originals, result receipts, head changes, checkpoints, terminal progress, occurrence changes, and outbox state as appropriate. Recovery must validate the saved evidence and use the same frozen semantics. A mutex and Python dictionaries are useful reference mechanics, not a production transaction protocol.

## 16. Full-conformance boundary

Implemented and tested here are the selected-document core profile, BEX workflows, static mutations, event/update/lifecycle reactions, inline examples, static managed embeddings, finite cyclic work, infinite-loop gas rollback, source isolation, and saved-input replay.

Not supplied as complete production implementations are nearest-valid generalization; full dynamic managed admission/rebinding/removal/recreation; retained-epoch import and historical catch-up; full SCC initialization causality; all nested delivery address and inline topology corner cases; exact upstream fatal-result projection; durable recovery/outbox delivery; production provider adapters; and exact Java catalogue/tariff compatibility.

The uploaded repository named `blue-contract-java` implements Coordination and hosted workflow steps. Its generic Contracts processor is a dependency whose exact pinned implementation is absent. The public generic Contracts specification and the uploaded callers/tests inform this new candidate, but cannot substitute for executing that missing implementation's complete conformance suite.

## 17. Repository-integration revision — 19 September 2026

The earlier source-availability statements above describe the initial candidate. This rebuild additionally includes the supplied pinned Java stack in `inputs/`; its exact Java suite has not been executed here. RepositoryCatalogue provides an explicit exact-ID profile for a tested subset of the published catalogue, separately from the synthetic local catalogue. It does not establish all catalogue-generation or generic-Contracts parity.

Absent optional declarations must not be interpreted as configured empty objects. Event matchers on lifecycle, triggered, update and embedded channels preserve their authored pattern contributions rather than acquiring declaration-only labels such as an inherited description. Such a label describes the matcher slot, not a requirement that every event carry that label.

A selected inline Contracts scope is the BEX document boundary. BEX reads `/x` from that selected child and returns scope-local effects. Contracts translates these paths into enclosing storage addresses and applies the normal boundary checks. `$resultValue` overlays pending changes onto that same local snapshot. A child cannot gain parent access through an absolute BEX pointer.

Newly inserted, previously unvisited inline scopes are discovered, preflighted and initialized during the same local processing invocation. Their lifecycle events may trigger the enclosing inline scope. Work is bounded by gas and an explicit occurrence-count resource limit. This supports the local factory tutorial slice, not independent managed-child admission, historical import, repeated same-path rebind semantics or durable recovery. Those remain separate host obligations.
