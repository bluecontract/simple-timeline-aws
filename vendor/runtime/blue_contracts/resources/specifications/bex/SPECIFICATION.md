# Blue BEX Specification 1.0

**Edition:** Corrective edition, 20 September 2026.  
**Normative form:** readable rules, complete executable Python annex, operator reference and exact dependency bindings.  
**Profile:** static-core, strict Blue-output boundary. This is a versioned semantic specification, not a claim of Java wire or diagnostic compatibility.

## 1. Purpose and imported language

BEX evaluates data-encoded programs against explicit, read-only inputs and produces values, ordered changesets, and ordered events. It neither fetches arbitrary resources nor publishes a document. A Contracts processor decides whether proposed effects can be applied; Coordination determines which authenticated external input is eligible.

The reader is assumed to know Blue Language 1.0. Node admission, effective types, specialization, exact versus Source representations, references, set finalization, and BlueId are imported, not redefined. A BEX value is not a Blue node. In particular, Python object identity, dictionary iteration order, and native truth testing do not define BEX semantics.

`ALGORITHMS.md` contains the executable Python algorithms. Its file blocks extract byte-for-byte to `blue_bex/`. `python tools/build_specs.py --check` (from the repository root) verifies that correspondence. Readable rules and executable algorithms together define this edition; disagreement is a defect, not permission to choose either result.

## 2. Machine and invocation

An invocation has a compiled program; an explicit context; a gas ledger; lexical function frames; an ordered changeset; and an ordered event list. Context supplies the selected document snapshot, event, current contract, previous step results, named bindings, and executing scope. Optional adapters provide finite document reads, Blue specialization checks, and exact-type intrinsics.

No process-global variable is a program binding. No Python expression is evaluated from program text. The interpreter recognizes data forms, not Python, JavaScript, or embedded shell commands. An installed intrinsic is trusted host code and is outside that sandbox boundary.

A successful invocation returns `Result(value, changeset, events, gas_used, trace)`. It does not apply its changes. Returned effects remain ordinary BEX values until the Contracts output boundary has validated and converted them.

## 3. Value domains and absence

The domains are undefined, null, Text, Integer, Double, Boolean, Object, and List. `UNDEFINED` is a singleton distinct from Python `None`, which represents internal BEX null. Boolean is not Integer. Objects have Text keys. Integers use exact integer arithmetic; Doubles use finite decimal observations and cross the Blue Double boundary as finite binary64 values.

Missing member lookup yields undefined. Undefined object members are omitted by Blue conversion. Undefined list elements, including sparse overlay holes, cannot cross that boundary. Null is not an empty object and is rejected at the corrected Blue output boundary. An actual empty object remains an actual empty object. `$emptyObject` is the explicit empty-object constructor.

`$exists` is false only for undefined. Null therefore exists. Truth is false for undefined, null, false, empty Text, empty Object, and empty List; other values are true, **including numeric zero**. `$empty` and `$isEmpty` test the inverse of this truth rule, not Python's truthiness.

## 4. Numeric and Text rules

Integer conversion accepts integers, integral finite numbers, and canonical decimal integer text. Fractional values and noncanonical integer spellings fail. Numeric conversion rejects Boolean, collections, nonfinite numbers, and malformed numeric text. Arithmetic operators in this edition produce exact Integer results, and division requires an exact Integer quotient. Division by zero or a fractional quotient fails.

Numeric equality compares numeric value across Integer and Double. Other equality is domain-sensitive and recursive. It must not be substituted for BlueId equality or Language specialization. Collections do not stringify implicitly. Null and undefined stringify to empty Text where coercion is allowed; names, paths, keys, and operation names require presence and cannot use that absence coercion.

Text-key ordering is Unicode code-point ordering. Gas size estimation counts UTF-16 code units, not Python string length or UTF-8 bytes. These are different operations and must remain separate. Nonfinite Doubles and lone Unicode surrogates are invalid runtime values at the relevant boundary.

The implementation declares portable source-depth and numeric-text limits. These are host capability limits, not mathematical changes to Integer. The supplied Blue adapter caps Integer value text at 4096 characters; this is a declared boundary capability limit, separate from standalone BEX arithmetic. A production integration must additionally cap allocation and intrinsic work; semantic gas alone is not an operating-system resource sandbox.

## 5. Source classification and static positions

A single-key object whose key starts with `$` is an executable form when encountered in expression or statement position. It must name an installed operator valid for that position. Other objects are recursively evaluated data constructors. `$literal` prevents evaluation of its payload as program data, but does not authorize executable material in static Blue definition positions.

Type-related and schema positions are static. Constants and function-argument patterns are static. Compilation rejects unknown operators, invalid operand shapes, unknown variables/constants/functions, malformed static names, reserved user-container names, invalid call argument sets, and recursive function-call graphs. Both sides of a lazy runtime construct still undergo static validation.

A function body selects `expr` ahead of `do`. An explicit named entry must exist and take no arguments. The candidate also validates the root body even when a named entry is selected. Definition constants/functions can be supplied as an already available object to the compiler; loading a referenced program definition is a host integration obligation.

## 6. Evaluation order and laziness

Object constructors evaluate keys in deterministic order; lists evaluate left to right. Function arguments evaluate in key order. Lazy operators evaluate only the branch or subsequent operand needed to establish the result. This applies to Boolean connectives, coalescing/default selection, conditionals, and lookup defaults.

A static error in an unused branch is still an error. A runtime error or gas charge in an unselected branch does not occur. Empty or missing values cannot be replaced by Python idioms such as `value or fallback` unless they implement the particular BEX operator's rule.

## 7. Reads and observations

`$document`, `$event`, `$currentContract`, `$binding`, `$steps`, `$var`, and `$const` read only their designated source. A variable or constant name containing `/` remains a name; its optional pointer is a separate operand. A named step is addressed by the step's actual Language `name` label, not its list position when a name was supplied.

A Compute invocation sees a stable selected-document snapshot. A later Compute step sees effects successfully applied by earlier steps. `$resultValue` overlays this invocation's accumulated changes on its snapshot; it does not publish them. Finite managed-document reads use the closure's selected dependency projection, never an independently advancing source's latest public head.

The context's matcher implements `$is` using Blue semantic admission and specialization. The interpreter does not guess that a JSON shape is a valid Blue type. Missing patterns, unknown required definitions, and uninstalled matcher capabilities are not accepted as successful matches.

## 8. Pointers and ordered changesets

BEX value pointers use JSON-pointer escaping. Both empty Text and `/` designate the value root in this profile. This differs from the Language query API's empty-key behavior; adapters must not delegate blindly. Relative document paths resolve against the executing scope; already absolute document paths remain absolute. A Contracts processor separately checks whether a proposed absolute path is writable by that scope.

A changeset is an ordered list of add, replace, or remove proposals. Non-remove proposals require a value. Remove ignores no hidden expression: its value operand is not evaluated by the append operation. Appending preserves duplicate operations and their order.

BEX's observation overlay is **not** Contracts mutation. Overlay removal from a List creates a sparse undefined position and does not shift later elements. Actual Contracts array removal does shift later elements. Intermediate overlay objects are constructed deterministically. A sparse result may be observed internally but cannot be serialized as a Blue List containing undefined.

## 9. Collections

Collection operations support Lists in index order and Objects in sorted key order. Query bindings are lexical for that query and are restored afterward. Statement `forEach` uses its declared iteration slots and executes its body for each selected item. An empty collection executes no iteration body.

Map and flat-map produce Lists; flat-map requires a List result per item. Filter preserves the input's collection category. Reduce threads its accumulator. Some, find, and find-entry stop after the first decisive match. Find-entry preserves the selected value and occurrence information rather than replacing occurrence identity with value identity.

Iteration gas is charged for each admitted visited item. Short-circuiting stops both later evaluation and later iteration charges. Collection construction and host memory consumption still require operational limits independent of semantic gas.

## 10. Variables, functions, and return

`let` declares function-frame slots. Parallel declarations evaluate their initializers against the old frame; an explicit declaration order enables ordered dependency between initializers. `set` updates an existing declared slot. Conditional declaration visibility is checked statically.

Function calls use isolated frames, exact declared argument-name sets, and supplied Blue argument-pattern checks. Functions share the invocation's effect accumulators and gas ledger but do not implicitly capture another function's locals. Recursion is rejected during compilation. Business-process cycles therefore arise from Contracts event work, not recursive BEX function calls.

Explicit return exits the current function/body. Without an explicit result, the interpreter returns the accumulated changeset and events. A called function's return does not terminate its caller. Failure exits the invocation and does not authorize partial publication.

## 11. Effects and host intrinsics

Event append preserves multiplicity. Two equal event values are two emission occurrences; their BlueIds may be equal. Occurrence identity belongs to the hosting Contracts closure. The BEX interpreter does not deduplicate by content identity.

An intrinsic must have an exact static type ID present in the invocation's installed capability registry. Unknown IDs fail compilation. Runtime removal of a capability fails execution. Intrinsics receive copied explicit operands and the same gas meter; they must return explicit BEX values and account for bounded work. Files, network, clock, and randomness are not implicit capabilities.

## 12. Gas

Compilation consumes no semantic gas. Each admitted expression, statement, read, call, pointer operation, collection item, append, and size-dependent operation is charged by the algorithm at its specified point. A failed charge is recorded as rejected work and does not increment admitted `used` gas.

The default scalar tariffs are: expression 1; statement 1; document read 2; event/current-contract/steps/variable read 1; result-value read 2; pointer get base 1; pointer set base 3; object set base 2; append-change/event base 5; iteration item 1; function call 2. Size/path contributions are defined by the algorithms, not by wall-clock time.

A Compute step can impose a positive local cap while charging each admitted operation to a shared Contracts closure meter. A local-cap rejection is distinguished from shared-cap rejection in the trace. A cap is checked before work is admitted. Gas allowance, used gas, attempted rejected charge, and operational cancellation are different values.

The trace and tariff in the executable annex define this edition. A conforming implementation preserves the admitted charges and first rejected charge for identical inputs. Equivalence to a different BEX release or another tariff is a separate interoperability claim, not an additional unstated rule.

## 13. Blue output boundary

`blue_value` converts runtime values into a JSON-compatible, null-free proposal. It is not semantic admission and does not return a BlueId. Authoring aliases are resolved in an explicit authoring/preparation stage before this proposal enters the runtime output boundary. Runtime type slots MUST contain exact Blue references. The host admits the proposal through Language Exact admission and uses the resulting validated exact value; it MUST NOT resolve aliases, replay Source list construction, or reinterpret a generated string as an installed type at this stage. A BEX program may compute arbitrary Text, but a Text in a runtime type slot is not thereby a type reference. A host accepting raw data-encoded programs with unresolved literal type aliases must reject the resulting effect, not silently reinterpret it.

The corrected boundary does not collapse null to `{}`. A whole null event or null patch value fails. Undefined object members may disappear, but required fields must still satisfy the host effect schema. Effect structural validation precedes mutation, so a later malformed effect cannot cause an earlier effect to be published.

## 14. Errors and determinism

Compilation error, runtime error, invalid Blue output, gas exhaustion, and portable-resource exhaustion are distinct failure families. A caller may not turn an unavailable required Language definition or provider proof into a successful computation. A runtime exception never means "no changes" success.

Determinism requires identical admitted inputs, program and definitions, installed capabilities, matcher behavior, selected document projection, and gas schedule. Python hash seed, input-map insertion order, cached parsing, and unrelated documents must not affect the semantic result. Stateful or nondeterministic intrinsics violate this requirement unless their observations are explicit frozen inputs.

## 15. Executable inventory and conformance

`OPERATOR_REFERENCE.md` lists every installed expression and statement operator. The complete annex supplies their compilation, evaluation, value and gas definitions. Each marked module is extracted without modification. The common release verifier checks the annex against `src/blue_bex/` and the pinned Language dependency.

Conformance preserves successful results, ordered proposals, short-circuit behavior, static errors, runtime errors, output-boundary errors and gas observations. Required cases include Boolean/Integer distinction; undefined/null/empty-object distinctions; exact arithmetic; type-pattern matching; every operator family; function scope; side-effect order; Unicode ordering and size; output rejection; and local/shared gas limits. Passing a finite corpus is evidence, not a proof for all programs or capabilities.

## 16. External capability boundary

The standard algorithms require no arbitrary external I/O. A host supplies explicit document projections, a Language-backed matcher, and any selected intrinsic registry. A missing required capability or exact definition cannot be converted to successful evaluation. Intrinsics are trusted, explicitly installed code with their own semantics and bounded work; an unknown intrinsic ID is rejected.

This edition defines no production network acquisition service, operating-system sandbox, universal intrinsic package or Java diagnostic mapping. An independent implementation conforms to this edition by preserving its specified results, not by reproducing an undocumented behavior of another runtime. Host memory protection and process isolation remain operational obligations; they cannot change the semantic outcome of an admitted computation.

## 17. Composition with Language and Contracts

User-binding declarations are constants, functions, function arguments, local `$let` slots (both forms), and collection/loop item, key, index and accumulator slots. All reject the reserved names listed by `compiler.RESERVED`, including `$previousItems`. Ordinary literal object keys and host-provided read bindings are not user-binding declarations. `$previousItems` is a reserved Language name in BEX user-binding containers. It is not a BEX instruction and cannot manufacture Language list inheritance at runtime. `$previous` and other Source-only controls likewise do not replace Exact admission of effects.

An unevaluated object containing dynamic expression fields is not an instance of its eventual result type. A repository can author that value through ordinary BEX `$objectFromEntries` construction with exact type references. Resulting events and patch values are admitted only after evaluation. Rewriting a program changes its identity and may change its gas; this does not weaken Language validation.

The Contracts invocation supplies the selected executing document as the BEX document. BEX receives no ambient enclosing process or independently advancing public head. Contracts owns mutation boundaries, internal event occurrence identities, initialization, termination, checkpoint settlement, graph finalization and publication. BEX returns proposed effects and never advances those states itself.

The reference uses the Contracts contextual business-value document projection for both `canonical` and `resolved` BEX read modes. This is an explicit Contracts binding, not a redefinition of the Language serialization APIs. Configured program data is distinct from effective business values: inherited specification prose must not be inserted into a literal program or effect.

## 18. Release and identity

The complete specification comprises this text, the executable annex, operator reference and dependency bindings in that order. Its BlueId names that exact Text. The publication manifest records its identity outside the Text, avoiding a self-reference. A normative change creates a new exact specification identity. Test reports, implementation-only packaging, tutorials and provenance notes do not silently amend this edition.
