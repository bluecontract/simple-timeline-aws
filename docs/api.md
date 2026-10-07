# Reading and verifying timelines

The full contract is the vendored [Coordination specification](../vendor/packages/blue-coordination/spec/coordination.md).
The deployed provider uses the same exact type identities. JSON below uses readable
aliases for explanation; actual wire requests use `type: {"blueId":"…"}`. Obtain
those identifiers from `GET /types` or the package archive.

## Hello, then Hello 2

The owner console submits the original content, for example the text `Hello`.
The provider retains an exact entry equivalent to:

```yaml
type: Coordination/Timeline Entry
timeline: { blueId: "<timeline BlueId>" }
timestamp: 1791240000000000
actor:
  type: Coordination/Principal Actor
  displayName: Owner
message: Hello
```

The second entry contains `message: Hello 2`, a strictly greater microsecond
timestamp, and `prevEntry: {blueId: "<first entry BlueId>"}`. There can be only one
entry in a given microsecond on a timeline. A timestamp is never backfilled before
a previously committed completeness bound. Original messages are preserved.

POST this request to `<provider.endpoint>/timelines/read` to fetch both:

```yaml
type: Coordination/Read Timeline Request
timeline: { blueId: "<timeline BlueId>" }
limit: 50
```

For a private timeline, put that entire typed request inline in:

```yaml
type: Coordination/Signed Reader Request
request: <the complete typed request above>
publicKey: <64 lowercase hex characters>
signature: <128 lowercase hex characters>
```

The Ed25519 signature is over UTF-8 bytes of
`blue.coordination.reader-request\n` followed by the **request’s exact BlueId**,
with no trailing newline. The public key must currently be granted this timeline
by a Timeline Access document. There is no nonce, expiry or protocol-version field.
Replay of this exact read is allowed while the key retains permission.

A successful response is a `Provider Attestation` with its typed
`Timeline Read Response` inline. The response includes:

- `request`: the exact request BlueId;
- `checkpoint`: a signed guarantee with `completeBefore` and `lastEntry`;
- `page`: entries in ascending timestamp order, `hasMore`, and `nextCursor` only
  when another page is needed.

The checkpoint’s `completeBefore` is exclusive. Once committed, no entry may ever
appear with a timestamp below that bound. `hasMore: false` says the page has
reached that checkpoint’s head; later entries can still appear at or after the
bound. A Boolean alone is not a completeness proof.

To fetch after the first entry, add `afterEntry: {blueId: "<first entry BlueId>"}`.
Alternatively use `afterTimestamp: 1791240000000000`. Each is exclusive. To follow
a paginated snapshot, send the returned cursor inline in a new read request using
`cursor`, and sign that new request. Do not combine these three selectors. The
cursor keeps the original checkpoint even if another entry arrives between pages.

`limit: 0` asks for a completeness checkpoint only. The implementation’s maximum
page size is 50; owner appends are limited to 32 KiB of content. Requests are limited
to 128 KiB, and a response exceeding the transport budget fails rather than claiming
an incomplete page is complete.

## Public access documents

The owner asks the provider to publish a document equivalent to:

```yaml
type: Coordination/Timeline Access
allowedTimelines:
  - { blueId: "<private timeline BlueId>" }
allowedKeys:
  - <reader Ed25519 public key>
contracts:
  provider:
    type: Coordination/Public Timeline Channel
    provider:
      type: <the provider subtype, obtainable from /types>
      publicKey: <provider verification key>
    url: https://example.execute-api.us-east-1.amazonaws.com/timelines/access
  update:
    type: Coordination/Update Timeline Access
```

The provider subtype supplies `endpoint`. This is an actual executable Blue
Contracts document. An edit publishes `Contracts/Operation Request` targeting its
initial BlueId, channel `provider`, operation `update`, with a
`Coordination/Timeline Access Update` containing both new lists. The provider
executes this public history before adopting the resulting permissions.

To fetch the public access history, obtain the signed descriptor from `GET /provider`,
then send a bare `Read Timeline Request` for its `controlTimeline` to
`POST /timelines/read`. No key, login or signature is required. Continue using
`nextCursor` until `hasMore` is false and verify the checkpoint and chain. Public
access history remains fetchable after the grant is revoked.

## Runnable verified reader

Copy the provider BlueId from the console. The reader checks that adopted identity;
an untrusted discovery response alone must not select a replacement provider.

```sh
.venv/bin/python scripts/read_timeline.py https://YOUR-ENDPOINT \
  --provider EXPECTED_PROVIDER_BLUE_ID --public-access --show-exchanges
```

For a private timeline, copy its exact JSON from **Timeline object** into a file:

```sh
.venv/bin/python scripts/read_timeline.py https://YOUR-ENDPOINT \
  --provider EXPECTED_PROVIDER_BLUE_ID --timeline-file timeline.json \
  --key-file reader-seed.txt --show-exchanges
```

`reader-seed.txt` is the reader’s private 32-byte seed in hex, retained on the
reader’s computer. Only its derived public key belongs in a Timeline Access grant.
The tool signs requests, verifies response signatures, order and completeness, and automatically follows pages. It stages received Blue references without falsely claiming that every referenced application document has already been semantically admitted. A feeder must separately resolve, validate and execute application documents before using their state.
Use `--after-entry-file entry.json`, `--after-timestamp N`, or `--limit 0` as needed.

The owner console can inspect every stored object. Public `/timelines/content`
requests can resolve only objects reachable from a public timeline. A private
object cannot be read merely by knowing its BlueId or asking through an unrelated
public timeline.

## Wire compatibility and deployment

All application protocol exports resolve package and native Blue types in
`type`, `itemType`, `keyType`, and `valueType` to exact Blue references. Ordinary
text values remain unchanged. This boundary conversion preserves document
identities and signatures and does not require a snapshot or package migration.

Code-only updates through `scripts/deploy.py` retain the stack's existing
`AdminPassword`, even from a fresh checkout without a local password file. Use
`--rotate-password` only for an intentional rotation; the generated password is
saved in `.local/console-password.txt` and existing owner sessions are invalidated.
