# Blue Coordination — event integration edition

Revision: 2026-09-21-event-integration-1.

This edition integrates the supplied Blue Contracts `2026-09-21-event-1` release.
It supersedes the earlier Plan/Envelope/Grant integration. Exact earlier releases
and workspaces remain under their original identities; importing an old workspace
as this release is an error. Language and the corrective BEX selection are unchanged.

## Layer boundary

Contracts processes `document, event, eventTimestamp`. Coordination selects and
verifies the next event, then calls that interface. A decision's recipient preview,
provider proofs, authorization audit and completeness inventory are Coordination
records, never additional Contracts arguments. Contracts independently selects
channels, operations and reactions and owns atomic state, lifecycle, checkpoints,
managed graph identity, gas and public event occurrence order.

Each managed public root has an independent snapshot and history. Processing an
entry for A does not advance another public root B, even if both subscribe to the
same Timeline. Incoming observers do not enlarge the selected rooted graph.
Embedded documents reachable from a selected root are processed by Contracts as
part of that root's invocation; cycles are finite managed graphs, not recursive
copies. Historical exact attachments retain their selected archived view.

## Immutable data and provider binding

Catalogue roles are Timeline, Actor, Source, Timeline Entry, Authority, Mandate
Authority, Operation Mandate and Mandate Approval. Their exact identities include
this specification. Role availability alone does not install executable behavior.
The concrete local provider uses the separately identified Ed25519 full-prefix
binding. A generic Timeline does not automatically select that verifier.

An Actor has nonempty Text `actorId`. A concrete Timeline has nonempty Text
`timelineId` and lowercase 32-byte Ed25519 `publicKey` in hexadecimal. A Timeline
Entry contains exact `timeline`, `actor`, `message`, a safe integer `timestamp`,
and optional exact `prevEntry`, `onBehalfOf` and `source`. Its type is the exact
selected catalogue type. Additional fields are rejected except the recognition
field described below. Referenced content is structurally verified and admitted.

When `message` is a typed Contracts Operation Request, the original Entry MUST
also contain immediate `operation` equal to that exact message. Otherwise the
Entry MUST NOT contain `operation`. Both fields are committed before signing.
The processor receives this complete original Entry; adapters MUST NOT unwrap
`message`, construct an alternative cause, or add `operation` after signing.
Checkpoints and receipts therefore retain the exact original signed Entry ID.

## Verified complete prefixes

A provider owns its append ACL. Merely reading or discovering a channel MUST NOT
create a provider, acquire a private key, or authorize an actor to append.
The local authoring UI may explicitly create a new Timeline and grant its chosen
local actors append authority, showing the resulting authored Source.

A verified prefix proves all entries on a selected Timeline with timestamp less
than `completeBefore`. The bound is exclusive. Each entry must belong to that
Timeline, link to its actual predecessor and have strictly increasing timestamps.
Duplicates, omissions, malformed links and invalid signatures are errors.
A later provider assertion cannot contradict an already verified prefix.
An unavailable provider, missing record or insufficient boundary is not an empty
prefix and must not be interpreted as completeness.

The local provider timestamps an appended entry at the maximum of requested time,
its promised completeness bound and one more than its last entry's timestamp.
Thus it never inserts an entry behind an earlier completeness promise. An optional
request ID makes append idempotent; reusing it with different input is rejected.

## Explicit Timeline Channel runtime

A host installs the exact `Coordination/Timeline Channel` definition and its exact
runtime binding. This is an extension of Contracts Channel, not a primitive
Contracts type. Headers contain exact Timeline and Actor definitions. The
acceptance function compares those definitions to the original Entry's actual
fields, requires the supplied processing timestamp to equal the Entry timestamp,
and accepts only timestamps greater than this channel's previous checkpoint.
Every candidate comparison first charges `coordinationTimeline/accept = 1`.
Immutable definition resolution failures propagate as resource errors, never false
matches. The binding selects only direct actor attribution. It conveys no append
permission and does not itself verify provider signatures.

Composite External Channels and All External Channels use the selected Contracts
union algebra over these primitive channels. A Coordination root containing an
unbound generic external channel is rejected explicitly rather than guessing a
Timeline or a completeness source.

## Selection and progress

For every active document reachable from the selected root, discover the complete
current set of subscribed Timeline/Actor pairs, including members of unions.
Acquire verified prefixes for every required Timeline before deciding the next
input. Verify checkpoint subjects against retained signed history, including
subjects outside the current bounded prefix. Timestamp and exact Entry identity
must agree. Missing evidence blocks progress.

At the selected common exclusive completeness bound, order candidates by
`(timestamp, exact Timeline ID, exact Entry ID)`. Select the first candidate with
at least one fresh accepting channel in the rooted graph. The processor receives
only that original Entry and its timestamp. Do not skip an earlier invalid or
unavailable candidate to process a later one.

After a committed transition, rediscover the rooted graph and required sources.
Do not use a global root watermark to suppress older inputs newly exposed by an
attached historical document. Its own channel checkpoints determine progress.
A newly attached later state already contains the checkpoints it reached; an
emitted event missed while detached is not replayed merely by reattaching it.

`IDLE_THROUGH` means no eligible input exists below the verified bound, not that
nothing can ever happen. `WAITING` identifies unavailable or incomplete evidence.
`BLOCKED` identifies invalid input or failed processing. `UNSUPPORTED` identifies
an explicitly unsupported verifier or channel/authority protocol. No such result
manufactures checkpoints, events or an advanced public root.

## Atomic recovery and replay

The trusted local store atomically publishes the updated state head, input and
provider audit, processor receipt and ordered public outbox. Compare-and-swap
prevents committing against the wrong prior state. Request reuse is idempotent
only for the same bound transition. Failed attempts publish no state or outbox.
An acknowledged outbox occurrence is identified by occurrence ID, not event body.

Portable replay retains exact input content, selected archived views, gas policy,
installed runtime binding definitions and the original complete event. Runtime
implementations are installed separately by exact binding. A cold replay must
match normative processor observations and receipt; matching only the final
counter is insufficient. Private provider keys belong only to the local trusted
workspace and are not public tutorial downloads.

## Capability boundaries

This event-integration profile implements direct provider append ACLs, signed
completeness, independent roots, exact checkpoints, embedded and cyclic graph
processing, atomic local persistence and replay. The removed Contracts Operation
Port/Grant protocol has no compatibility substitute. A legacy delegated Mandate
input is explicitly unsupported; no owner permission is invented. The historical
Mandate specification and implementation are retained in provenance for a future
separately reviewed event-based authority profile.

The reference provider limits a prefix to 4096 entries and discovery to 256
Timelines. Contracts' selected limits remain authoritative, including 128 managed
documents per invocation and its gas limit. Performance work must not silently
raise those limits or change logical gas, exact identities, event ordering or
rollback. Reference-code extraction and implementation-equivalence checks are
separate checks.
