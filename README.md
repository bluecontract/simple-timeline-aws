# Simple Timeline on AWS

A small, self-contained Blue timeline provider with an owner console. It publishes
signed, timestamped entries and executable Timeline Access documents, using the
selected `blue-coordination` package.

<!-- DEPLOY_BUTTON -->
[![Deploy to AWS](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/create/review?stackName=simple-timeline-provider&templateURL=https%3A%2F%2Fsimple-timeline-releases-581571886327.s3.us-east-1.amazonaws.com%2Freleases%2F8293d047ca01637f50270686947130ce2f54622a605fb00dabc051e9ab396701%2Ftemplate.json)
<!-- /DEPLOY_BUTTON -->

Enter the **provider name**, **company name**, **website URL**, and a
**16–128 character console password** in CloudFormation. Company and website may
be left empty for a personal provider. Acknowledge the IAM resources and create
the stack. Open the **ConsoleUrl** stack
output and sign in with that password. You do not need to install anything locally.
The template copies its checksum-pinned code into your account and selected region.
Your records, sessions and secrets stay in your account.

New providers explicitly include `displayName`, `companyName`, `website` and
`endpoint` in their Blue provider object (omitting empty optional fields). The
endpoint is the stack's actual HTTPS API address, not the website entered in the
form. It is part of the provider's exact Blue identity and remains fixed after
initialization. The API resource is retained on stack deletion or replacement.
Name, company and website are self-declared; a familiar company name does not
prove control of its domain. Clients must use the adopted endpoint and verify
its signed provider descriptor. This starter uses an AWS-assigned endpoint;
it cannot claim an arbitrary company domain by entering it as a website.

Provider name, company, website and endpoint are set once at creation. They cannot
be edited: both the deploy command and the CloudFormation installer reject changes,
and the service checks its configuration against the saved creation values.
Different identity details require a separate provider stack; the old provider
keeps its existing timelines. The inspector resolves inherited details
for older providers without rewriting their signed objects.

## Owner console

- Create private or public timelines and browse their exact Blue definitions.
- Append text or Blue JSON. The provider assigns the timestamp, actor and predecessor.
- Browse entries and inspect/copy the exact Blue objects.
- Create Timeline Access documents selecting timelines and Ed25519 public keys.
- Edit both access lists together. The provider publishes a Contracts `update`
  operation on its public access timeline and executes the resulting document.
- Revoke an access document: publish an update clearing both lists and remove it
  from the active view. Its initial document and public history remain available.
- Archive a timeline: remove its grants and stop owner appends. Existing entries
  remain immutable. Public timelines remain public; archive is not erasure.

The public access timeline is created automatically and cannot be archived or
written to directly through the owner console. Its entries are published by the
provider when access changes. Timeline and access-document names are console metadata; they are not
extra protocol identifiers.

## Protocol

`Timeline Provider.endpoint` is the single HTTPS REST base for public and private
timelines. For example, `https://abc.execute-api.us-east-1.amazonaws.com` exposes:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/provider` | Signed provider descriptor, including the public access timeline |
| GET | `/types` | Public provider subtype definition and exact type identifiers |
| GET | `/packages/coordination.bluepkg` | The selected Coordination package and dependency closure |
| POST | `/timelines/read` | Entries and completeness, with fixed-checkpoint pagination |
| POST | `/timelines/entry` | Retrieve a particular accepted entry and its attestation |
| POST | `/timelines/content` | Resolve content reachable from an authorized timeline |
| POST | `/access/get` | Initial and current access document and publication evidence |
| POST | `/access/create`, `/access/update` | Owner requests to publish access changes |
| POST | `/timelines/create`, `/timelines/append` | Owner-only ingest extension |

Public read requests contain a bare typed request. Private reads wrap the same
request in an Ed25519 `Signed Reader Request`. Signatures cover the exact BlueId;
JSON hashing is not a substitute for Blue identity. Every private request,
including a cursor continuation, checks the current access grants. Reader keys
cannot append entries or change access. The `/owner/*` endpoints are a console
convenience API authenticated by the owner session cookie.

See [the API guide](docs/api.md), [the complete Coordination specification](vendor/packages/blue-coordination/spec/coordination.md),
and [the infrastructure notes](docs/operations.md).

## Develop, test and deploy from source

Python 3.13 is required. The exact Blue runtime and package closure are vendored
and their hashes recorded in `vendor/manifest.json`.

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
node --check static/app.js

.venv/bin/python scripts/build_release.py \
  --release-base https://YOUR-RELEASE-BUCKET.s3.us-east-1.amazonaws.com/releases
.venv/bin/python scripts/deploy.py \
  --account YOUR_AWS_ACCOUNT --release-bucket YOUR-RELEASE-BUCKET
.venv/bin/python scripts/deploy.py \
  --account YOUR_AWS_ACCOUNT --release-bucket YOUR-RELEASE-BUCKET --status
```

Use the usual AWS SDK credential chain. A local `--credentials PATH` option accepts
the legacy `access`, `secret`, optional `token` properties file. Credentials are
never bundled. The deploy command generates a console password in
`.local/console-password.txt` with owner-only permissions and never prints it.

Deployment assets in the dedicated release bucket are publicly readable so the
button works for another AWS account. The stack’s data and asset buckets are
private. Only code and the template are uploaded to the public release bucket.
The deploy command verifies the account ID before making changes.
