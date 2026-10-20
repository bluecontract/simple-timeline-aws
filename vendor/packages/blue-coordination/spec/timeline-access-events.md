# Timeline Access update events

This specification addendum defines the access-event publication of the Timeline
Access application program. The frozen Coordination transport and admission rules
remain unchanged. This is a new exact program and package, not a reinterpretation
of an older access document.

After validating and replacing both permission lists, Update Timeline Access MUST
execute the ordinary Contracts Trigger Event step with a Timeline Access Updated
value. The event contains no copies of permissions or additional document identity.

Each successful update emits exactly one event, including unchanged-list updates.
Invalid or rolled-back updates commit neither permission changes nor an event.
Reprocessing a consumed request does not execute the update or emit again. Distinct
successful requests have distinct occurrences even if their event values match.

The event is a notification, not proof of permission. Authority comes from verified
provider history and the executed access document. Consumers use ordinary Embedded
Node Channels filtered to the exact source path and event type. Contracts installs
the completed child state before delivering application events. Initial readiness
is calculated from the installed state without replaying a prior notification.

The host must recognize the new exact access program. Prior publications retain
their original program and output behavior; changing a package alias does not
upgrade an existing document. No extra native state channel or callback is used.
