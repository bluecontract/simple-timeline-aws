# MyOS protocol compatibility

This optional integration check uses the actual MyOS Java protocol verifier,
Contracts engine and Activation functions. The regular Python test suite does
not require a MyOS checkout.

Requirements: JDK 21, the Python project environment, and a local
`bluecontract/myos-aws-test` checkout containing the access-events runtime and
`examples/independent-processes/packages.json`. The check was developed against
MyOS revision `65cd6d0`, with Coordination package
`4gmSjwn3DCYBVeDieXxuXgsPvvz2dU6ovFXnnuyv2RjA` and Activation package
`DD2GfxSnspBZYVb2SxnzpXdekBYzriSKeWuG5UNgZsKA`.

```sh
.venv/bin/python tests/compatibility/run.py --myos ../myos-aws-test
```

The script builds the required Java classes in that checkout, then writes
disposable fixtures and helper classes to a temporary directory. It creates no
AWS resources and makes no requests to a running provider or MyOS account.

The Python provider creates a private timeline and a separate public access
history, grants access, adds a reader, repeats the same lists with a new request,
and revokes the readers. Java verifies the provider signatures, access binding,
linked history and completeness evidence, executes the published update program,
and compares the exact resulting document IDs with the Python provider.
The resulting states are also checked by MyOS's real
`Activation/Activation Functions.validateAccessDocument`.

`SignedAccessReplay.java` supplies the signed-history channel adapter for this
isolated native-engine test. It is based on MyOS `ProviderAccessExecution` at the
revision above, with receipt generations compared by numeric value rather than
Java object equality. The original helper compares a decoded JSON `Number` with
a boxed `long`; in this local runtime that incorrectly rejects the authenticated
recipient. The fixture corrects that transport comparison without changing
Contracts, BEX, package definitions or signatures. It is not a fix to, or a test
of, the hosted MyOS importer/provider.

Creating access publishes the original document, then a genuine update operation
with the initial permission lists, in one durable transaction. Executing that
operation produces the provider-channel checkpoint required by Activation. The
initial-phase check replays both signed entries before validation; neither engine
fabricates a checkpoint. Subsequent updates continue on the same public history.

`test_protocol.py` separately checks the committed update-event occurrences,
including unchanged-list updates, rejected duplicate keys, retries and replay
after restart. `test_access.py` verifies that grants retain separate public
histories and that revocation cannot leak into another grant.

These checks do not exercise the hosted MyOS importer, party-admission automation,
or either application's browser UI.
