# Infrastructure and guarantees

The stack contains an API Gateway HTTP API, a Python Lambda serving both the
console and protocol, a DynamoDB state/session table, private S3 buckets, Secrets
Manager, IAM roles and CloudWatch log groups. A small installation Lambda copies
the checksum-pinned release into the target account and initializes the secret.
The main service does not need access to the source release bucket after installation.

## Commit boundary

This first implementation intentionally uses one serialized provider state. Each
mutation—or read that issues a new completeness guarantee—works from a consistent
DynamoDB state pointer, writes an immutable compressed S3 snapshot, then commits
a replacement pointer with a conditional write. A conflict reloads current state,
rechecks permissions and retries. No signed success leaves the service before
that commit succeeds. This serializes appends, completeness seals and revocations.

A crash before commit can leave an unreachable snapshot but cannot publish a
partially applied state. A crash after commit but before the client receives its
response is handled by the durable idempotency record. Owner retries must reuse
the same idempotency key. Historical retries do not undo later permission changes.
Timestamps are assigned as the maximum of wall-clock microseconds, previous entry
plus one, and the previously sealed bound.

Snapshots contain Blue objects, accepted chains, durable checkpoints and
idempotency records; they contain no signing seed or owner password. S3 snapshot
hashes are checked when loading. Restored objects are rehashed with the pinned Blue implementation. Their original
admission is reused only from the provider’s own hash-checked committed snapshot;
remote request content still goes through semantic admission. The reusable admission
is bound to the exact vendored runtime and package manifest; a changed runtime
requires an explicit state migration. Noncanonical source
forms are admitted again to reproduce their canonical identities. Access updates use the actual pinned
Contracts processor, not a separately invented permission-document format.

Cold restoration reuses one Blue resolver while rehashing snapshot objects and
publishes each resolved dependency body once. Rebuilding the resolver for every
saved read response repeatedly copied the growing store and could exhaust the
29-second Lambda request budget. Per-object processing limits and the canonical
admission fallback remain in force. This changes no provider, timeline, access,
checkpoint or idempotency identity and requires no snapshot migration. It does
not remove the overall history-dependent cost of this single-snapshot design.

Source changes are not automatically deployed. After merging a restoration fix,
build and deploy the merged revision to the existing stack, retaining its
identity, signing seed, password and state resources. Check a cold `/provider`
request and a normal owner operation against the retained state; local timings
are not evidence that the deployed Lambda stays within its request budget.

## Console reads

Each committed snapshot includes the owner workspace view, produced from that
same state. Workspace, entry-list and stored-object requests read the hash-checked
snapshot directly; they do not initialize the Blue execution engine or replay
access documents. Every request checks the consistent state pointer, so a write
by another Lambda replaces the cached view on the next read. Older snapshots
gain this view in one normal, conditional state commit.

This read model is only for the authenticated console. Protocol responses,
permission decisions and mutations still use the full Blue execution path.
Refreshing the password secret updates session validation while preserving the
state cache when the provider signing seed has not changed.

## Authentication

The provider’s random Ed25519 seed and salted scrypt password hash are stored in
Secrets Manager. The owner receives a random opaque session token in a Secure,
HttpOnly, SameSite=Strict cookie. Only its hash is retained in DynamoDB. Sessions
expire after 12 hours. Mutations check Origin. Login attempts are rate-limited with
an atomic counter; source IPs are hashed. Request bodies, passwords and seeds are
not written to logs.

Change AdminPassword by updating the stack parameter. Secret values are refreshed
within 60 seconds; existing sessions are then rejected. Provider name, company,
website and endpoint are immutable creation values. The installer saves them with
the provider secret and rejects a stack update that changes any of them, before
installing code or changing the secret. The deploy command rejects changed identity
arguments before publishing assets. Runtime configuration must match the saved
values as well. Ordinary code updates preserve these values and the signing key.

ProviderName, ProviderCompany and ProviderWebsite initialize a new provider's
identity. The website is an informational claim; ENDPOINT is assigned from the
actual API Gateway resource and appears explicitly on new provider objects.
Restoration rejects an endpoint different from the one adopted in the persisted
provider. Existing providers keep their original identity and inherited fields.
The console displays those resolved details beside the exact object; inlining
a provider reference preserves its BlueId, whereas adding inherited properties
to an old provider object would change it.

## Storage, retention and scale

This is suitable for a small provider and a personal owner console. It is not yet
a high-volume banking deployment. Snapshot rewriting and full access-history
replay make cost and latency grow with history. Keep the current single commit
boundary until a partitioned storage implementation has equivalent concurrency
and crash-recovery tests. Existing MyOS services and their poller are not modified
by this stack; integrating a MyOS feeder is a subsequent step.

The API endpoint, data buckets, the DynamoDB table and the provider secret have CloudFormation
retention policies. DynamoDB point-in-time recovery and S3 versioning are enabled.
The scripted deployment also enables stack termination protection. Deleting a
stack therefore requires an explicit operational decision and does not erase its
retained records. The code release bucket is separate and publicly readable;
application data buckets block public access.

Archiving a timeline is an owner-console lifecycle change, not permission to erase
signed history. It revokes its private grants and prevents new appends. Revoking
an access document publishes empty lists. Public records cannot be made secret
retroactively. Unreachable snapshots left by failed commits may be cleaned up only
with a process that proves they are not referenced by a retained state pointer or
backup.

New Timeline Access documents each allocate a dedicated provider-owned public
timeline in the same atomic state commit as their initial publication and first
executed update. That update establishes the provider-channel checkpoint required
by MyOS Activation. If it fails, the grant and its new public history roll back. Retrying
creation reuses the recorded document and channel, including after a restart or
lost response. New requests with identical grants create independent documents.
Updates and revocations continue on the channel recorded in each document.
Within the same protocol edition, upgrades preserve older documents on their original shared timeline; no signed
document or historical entry is rewritten. The default provider descriptor remains
available for those histories. Clients reading a newer document use
`GET /provider?access=<initial-document-BlueId>` and verify its channel before
reading or executing its history.

AWS charges apply for API calls, Lambda, Secrets Manager, storage and logs. There
is no always-on server. The template uses a modest API throttle; adjust it with
observed latency and load. Monitor Lambda errors/duration and DynamoDB conditional
conflicts before raising concurrency or traffic.

## Verified release

The earlier 0.2.0-rc.2 provider was exercised on AWS with owner and anonymous requests, Ed25519
private reads, pagination, entry attestations, access updates and revocation.
A separate keyless reader verified the public access history. Local tests cover
restart recovery, compare-and-swap conflicts, lost responses, historical retries,
unique timestamps and an independent reader that has not preloaded the checkpoint
head. The owner console was also checked in a browser.

The current source selects Coordination `0.2.0-access-events.1` and Contracts
`1.0.0-final-gas.1`, matching the MyOS access-events runtime. This upgrade requires
a new stack: the admission-runtime fingerprint deliberately rejects saved states
from the previous protocol. It does not rewrite existing signatures, identities,
keys, access histories or snapshots.

Run `python -m unittest discover -s tests -v` for provider and installer checks,
and [the optional MyOS compatibility test](../tests/compatibility/README.md) for
independent signed-history verification and native execution. These local results
do not claim a hosted end-to-end run of the upgraded release.

Publishing an installer and deploying an application are separate operations.
`scripts/deploy.py --publish-only --update-readme` uploads only public code and
templates, verifies their bytes anonymously, and validates the CloudFormation
template before advertising its URL. It makes no stack changes. A source push
alone cannot update a previously published immutable installer.
