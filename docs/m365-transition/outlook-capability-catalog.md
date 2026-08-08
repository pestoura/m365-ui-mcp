# Outlook UI Capability Catalog

Status: **TARGET PRODUCT SCOPE / DISCOVERY-DRIVEN / NOT A SUPPORT CLAIM**

## 1. Objective

The Outlook module must aim for maximum practical semantic coverage of the Outlook Web capabilities available to the authenticated professional Microsoft 365 account.

This catalog records product intent. A capability becomes supported only after:

```text
tenant/account availability
-> UI surface observed
-> UIContract fragment attested
-> semantic read validated
-> mutation validated when applicable
-> policy/governance decision
-> publication
```

Absence from Microsoft Graph is irrelevant. Presence in documentation is not evidence that the capability exists in the target tenant.

## 2. Capability-discovery tool

The Outlook module shall expose a sanitized discovery/status operation conceptually equivalent to:

```text
outlook_capabilities
```

It reports support state by application surface and scope, for example:

```text
primary mailbox
shared mailbox A
calendar
people
todo
settings
```

It must distinguish:

```text
UNVERIFIED_LIVE
DISCOVERED
READ_SUPPORTED
MUTATION_SUPPORTED
DEGRADED
BLOCKED
OUT_OF_SCOPE
```

## 3. Public-tool strategy

Do not publish one MCP tool per Outlook button.

Target:

```text
large internal capability/operation catalog
              ↓
coherent semantic public tools
              ↓
DIRECT / BATCH / DAG / RUNBOOK composition
```

Grouped tools use closed operation enums and typed schemas. A grouped tool is not a generic browser escape hatch.

---

# A. Mail — discovery, reading and search

## A1. Mailbox/message listing

Target capabilities:

- list messages;
- list unread;
- list read;
- list flagged;
- list pinned;
- list with attachments;
- list by category;
- list by sender;
- list by recipient;
- list by date/range;
- list by folder;
- list Focused/Other where applicable;
- list drafts;
- list scheduled messages;
- list sent items;
- list archive;
- list deleted items;
- list junk;
- pagination/cursors;
- bounded projections/metadata-only reads.

Candidate semantic surface:

```text
outlook_mail_list
outlook_mail_get
```

## A2. Search

Target capabilities:

- free-text search;
- sender/recipient filters;
- subject terms;
- attachment presence;
- date ranges;
- unread/read;
- flagged;
- categories;
- folder scope;
- advanced query syntax where supported by the UI;
- people/files search surfaces where integrated;
- top-N/result shaping;
- count-only / existence query.

Candidate:

```text
outlook_mail_search
```

## A3. Conversations/threads

- read conversation;
- list messages within conversation;
- conversation metadata;
- conversation-level read/unread where available;
- ignore conversation where available;
- conversation move/archive/delete where available.

Candidate:

```text
outlook_conversation_get
outlook_conversation_manage
```

## A4. Attachments

- list attachments;
- attachment metadata;
- download attachment into explicit controlled artifact boundary;
- remove attachment from draft;
- add local/controlled file to draft;
- cloud attachment/reference when safely supported;
- inline image handling where needed.

Candidate:

```text
outlook_attachment_list
outlook_attachment_get
outlook_draft_attachment_manage
```

Attachment content is sensitive and must not be persisted by default.

---

# B. Message state and organization

## B1. Read/unread

- mark read;
- mark unread;
- bulk mark read/unread;
- folder mark all read where supported.

Candidate grouped operation:

```text
outlook_message_state_manage
```

Typical policy: `SAFE_WRITE`.

## B2. Categories

Full target:

- list categories;
- category details/color;
- create category;
- delete category;
- rename through safe semantic replacement if UI has no direct rename;
- change color;
- apply one category;
- apply multiple categories;
- remove category;
- remove all categories;
- bulk apply/remove;
- category favorites where available;
- query messages by category;
- use categories on events and contacts through their own domain operations.

Candidate:

```text
outlook_categories_manage
```

Internal operations remain explicit:

```text
categories.list
categories.create
categories.delete
categories.rename
categories.set_color
message.categories.apply
message.categories.remove
```

## B3. Flags / follow-up

- flag message;
- clear flag;
- mark complete;
- today/tomorrow/this week/custom follow-up where UI exposes it;
- due date;
- reminder;
- importance/To Do relationship where available;
- list flagged messages.

Candidate:

```text
outlook_followup_manage
```

## B4. Pin

- pin;
- unpin;
- list pinned.

Candidate may be part of `outlook_message_state_manage`.

## B5. Snooze

- snooze until explicit timestamp;
- snooze using supported presets;
- unsnooze/restore when possible;
- list snoozed where surfaced.

Candidate:

```text
outlook_snooze_manage
```

## B6. Archive

- archive;
- bulk archive;
- restore/move back;
- online archive/archive mailbox surfaces where tenant supports them;
- retention/archive-policy discovery where exposed.

## B7. Focused Inbox

- move to Focused;
- move to Other;
- always Focused from sender;
- always Other from sender;
- discover whether Focused Inbox is enabled.

Candidate:

```text
outlook_focused_inbox_manage
```

---

# C. Folders and favorites

Target:

- list folders;
- get folder metadata;
- create folder;
- create subfolder;
- rename folder;
- move folder where UI permits;
- delete folder;
- empty folder where permitted;
- add/remove favorite;
- mark all read;
- move message;
- copy message where supported;
- bulk move/copy;
- retention/archive policy association where available;
- folder permissions for shared folders when exposed;
- Search Folder discovery/management where supported by Outlook Web/new Outlook.

Candidate:

```text
outlook_folder_manage
outlook_message_move
```

Deletion/empty-folder operations require stronger policy than ordinary move.

---

# D. Sweep / Varrer

Target capability discovery:

- move/delete all from sender;
- apply future behavior;
- keep latest where supported;
- remove older messages according to the options exposed;
- inspect existing Sweep behavior when the UI exposes it.

Candidate:

```text
outlook_sweep_manage
```

Sweep modifies future mailbox behavior and should normally be `GOVERNED_WRITE`.

---

# E. Inbox rules

Maximum target:

- list rules;
- read rule details;
- create rule;
- update rule;
- delete rule;
- enable/disable;
- change priority/order;
- stop processing more rules;
- multiple conditions;
- multiple actions;
- exceptions;
- move/copy actions;
- category actions;
- mark/read/importance actions;
- forward/redirect actions where tenant permits;
- delete actions;
- rule execution/application when exposed;
- detect unsupported/tenant-disabled conditions/actions.

Candidate:

```text
outlook_rule_manage
```

Rule schemas must be closed typed structures. No arbitrary expression field.

Rules that forward externally, delete messages or affect security posture require stronger policy/approval.

---

# F. Quick Steps

Target:

- list Quick Steps;
- read details;
- create;
- update;
- delete;
- reorder where supported;
- execute against selected message(s);
- validate all embedded actions before execution.

Candidate:

```text
outlook_quickstep_manage
outlook_quickstep_execute
```

A Quick Step must not bypass per-action policy. Before executing a discovered Quick Step, the platform must know/attest its material effects or classify execution conservatively.

---

# G. Conditional formatting

Target:

- list formatting rules;
- create;
- update;
- delete;
- enable/disable;
- reorder;
- conditions based on sender/recipient/subject and other UI-supported fields;
- presentation options surfaced by Outlook.

Candidate:

```text
outlook_conditional_format_manage
```

Verification reads rule definitions, not rendered pixel colors.

---

# H. Drafts and compose

## H1. Draft lifecycle

- create draft;
- open/get draft;
- update draft;
- save draft;
- discard/delete draft;
- clone/resend-like draft workflows where needed.

Candidate:

```text
outlook_draft_manage
```

## H2. Recipients and sender identity

- From;
- To;
- CC;
- BCC;
- recipient resolution/autocomplete;
- alternate From identities where authorized;
- shared mailbox send-as/send-on-behalf where available.

Ambiguous recipient resolution fails closed.

## H3. Message body

- plain text;
- rich text/HTML formatting through safe typed semantic operations where needed;
- links;
- lists;
- inline images;
- signature insertion/default behavior;
- template insertion;
- Loop/advanced compose components only after specific discovery and risk review.

The MCP does not expose arbitrary DOM/HTML execution. HTML body content, if supported, is content, not executable page scripting.

## H4. Message options

- importance;
- sensitivity;
- categories on draft/sent message where supported;
- read receipt;
- delivery receipt;
- encryption options;
- S/MIME options;
- schedule send;
- tenant-specific message protection controls.

---

# I. Send, reply, forward and resend

Target:

- send draft;
- compose-and-send as governed composite operation;
- reply;
- reply all;
- forward;
- resend where UI exposes it;
- send from shared mailbox;
- send on behalf;
- send-as;
- validation of resolved recipients before send;
- read-back through Drafts/Sent Items as applicable.

Candidate:

```text
outlook_mail_send
outlook_mail_reply
outlook_mail_forward
outlook_mail_resend
```

External communication is `GOVERNED_WRITE` by default and usually approval-controlled according to policy/profile.

`create draft` and `send` must remain separable so automated workflows can prepare without automatically transmitting.

---

# J. Scheduled send / delay / undo-send settings

Target:

- schedule send at explicit time;
- inspect scheduled draft;
- change schedule;
- cancel scheduled send;
- send now;
- discover/configure Undo Send delay where supported by Outlook Web settings.

Candidate:

```text
outlook_schedule_send_manage
outlook_undo_send_settings_manage
```

---

# K. Recall and sent-message management

Target:

- discover recall availability;
- initiate recall;
- read recall status/report;
- distinguish recipients/outcomes when UI safely exposes them;
- do not claim recall success merely because request was submitted.

Candidate:

```text
outlook_recall
outlook_recall_status
```

Recall is externally consequential and policy-controlled.

---

# L. Receipts and delivery tracking

Target:

- request read receipt;
- request delivery receipt;
- inspect available receipt/tracking information;
- normalize partial/unknown results;
- avoid treating absence of a receipt as proof of unread/non-delivery.

Candidate may be integrated into draft/message tracking tools.

---

# M. Message security, sensitivity and encryption

Capability discovery must determine tenant support for:

- sensitivity labels/options surfaced in Outlook;
- Microsoft Purview encryption/message protection;
- Do Not Forward-type options where exposed;
- S/MIME signing;
- S/MIME encryption;
- certificate/configuration status;
- removing/changing applicable protection before send when permitted;
- secure-message indicators during reads.

Candidate:

```text
outlook_message_security_manage
outlook_message_security_status
```

No private key/certificate secret material is exported through MCP.

---

# N. Templates and reusable content

Target both template surfaces where available:

## N1. Full mail templates

- list;
- create;
- update;
- delete;
- apply to draft;
- recipients/subject/body/formatting/images/attachments where the UI supports them.

## N2. My Templates / snippets

- list;
- create;
- update;
- delete;
- insert into draft.

Candidate:

```text
outlook_template_manage
outlook_template_apply
```

---

# O. Polls in email

Target where available:

- create poll;
- add/remove options;
- allow/disallow multiple answers;
- insert/send poll;
- inspect poll state/results;
- update/cancel where supported.

Candidate:

```text
outlook_poll_manage
```

---

# P. Junk, phishing and sender/domain trust

Target:

- report junk;
- mark not junk;
- report phishing;
- block sender;
- unblock sender;
- safe sender add/remove;
- block domain;
- unblock domain;
- safe domain add/remove;
- inspect blocked/safe lists;
- junk-mail settings surfaced by Outlook.

Candidate:

```text
outlook_junk_manage
outlook_sender_trust_manage
```

Security-sensitive list changes require appropriate governance and audit.

---

# Q. Mail forwarding and mailbox processing settings

Target discovery/management where tenant permits:

- automatic mailbox forwarding;
- keep-copy behavior;
- forwarding address;
- external forwarding restrictions/tenant blockers;
- message handling defaults;
- reply/reply-all defaults if surfaced;
- read receipt behavior;
- compose defaults.

Candidate:

```text
outlook_mail_settings_manage
```

External automatic forwarding is high-risk and should default to governed/approval-required or deny depending on policy.

---

# R. Calendar — core events

## R1. Reads

- list calendars;
- list events;
- search events;
- get event details;
- date range/window;
- category filters;
- organizer/attendee filters where UI supports them;
- availability view;
- calendar overlay/select views where relevant to extraction.

Candidate:

```text
outlook_calendar_list
outlook_calendar_event_get
outlook_calendar_search
```

## R2. Event lifecycle

- create appointment;
- create meeting;
- update;
- cancel/delete;
- duplicate/copy where available;
- recurring series;
- occurrence vs series distinction;
- edit one occurrence;
- edit series;
- end recurrence;
- all-day event;
- private event;
- show-as/free/busy/tentative/working elsewhere where exposed;
- reminder;
- category;
- body/notes;
- location;
- online meeting/Teams meeting.

Candidate:

```text
outlook_calendar_event_manage
```

## R3. Attendees

- required attendees;
- optional attendees;
- resources/rooms;
- add/remove attendee;
- recipient resolution;
- response tracking where available.

Sending invitations is `GOVERNED_WRITE`.

---

# S. Scheduling Assistant / availability

Target:

- inspect attendee availability;
- find free/busy ranges;
- find common slot;
- constrain working hours/day ranges;
- room/resource availability;
- suggested times surfaced by Outlook;
- return bounded options rather than large calendar dumps.

Candidate:

```text
outlook_find_availability
outlook_find_common_slot
outlook_find_room
```

This is an excellent deterministic composite-read domain and should avoid LLM involvement when constraints are structured.

---

# T. Scheduling Poll

Where available:

- create poll;
- participants;
- candidate slots;
- options/settings;
- send/update/cancel;
- read results;
- choose/schedule winner where supported;
- read-back created meeting.

Candidate:

```text
outlook_scheduling_poll_manage
```

---

# U. Meeting invitations and responses

Target:

- accept;
- accept with response;
- tentative;
- tentative with response;
- decline;
- decline with response;
- propose new time;
- forward meeting;
- organizer response status;
- cancel meeting;
- update meeting and notify attendees according to UI behavior;
- distinguish event state from invitation message state.

Candidate:

```text
outlook_meeting_response
outlook_meeting_manage
```

---

# V. Shared calendars and delegation

Target:

- add shared calendar;
- remove shared calendar;
- share calendar;
- unshare;
- list permissions;
- set/remove permission;
- free/busy-only access;
- titles/locations access;
- full-details access;
- edit permission;
- delegate permission;
- publish/unpublish calendar where tenant allows;
- calendar group management where surfaced;
- distinguish organizational policy blockers.

Candidate:

```text
outlook_calendar_sharing_manage
```

Access changes are high-risk governed operations.

---

# W. Calendar settings

Target discovery/management:

- working hours;
- work week;
- time zone;
- first day of week;
- default reminder;
- meeting shortening/default duration where surfaced;
- work location/hybrid location features when available;
- birthday calendar toggle where relevant;
- automatic event-processing settings where UI exposes them.

Candidate:

```text
outlook_calendar_settings_manage
```

---

# X. People / Contacts

## X1. Contact reads/search

- search personal contacts;
- directory/organizational search;
- get contact;
- recent interaction context where safely exposed;
- organization/manager/org-chart metadata where available;
- favorites.

Candidate:

```text
outlook_people_search
outlook_contact_get
```

## X2. Contact lifecycle

- create;
- update;
- delete;
- favorite/unfavorite;
- categories;
- notes/fields surfaced by UI;
- contact photo handling only if safe and required.

Candidate:

```text
outlook_contact_manage
```

## X3. Contact lists/groups

- create contact list;
- update/rename;
- delete;
- list members;
- add/remove members;
- use list as recipient where UI supports it.

Candidate:

```text
outlook_contact_list_manage
```

---

# Y. Shared mailboxes

Shared mailboxes require scope-aware capability discovery; do not assume parity with primary mailbox.

Target:

- list known/accessible shared mailboxes where UI provides discovery;
- open shared mailbox;
- search/read messages;
- folders;
- categories;
- flags;
- rules;
- automatic replies;
- notifications/settings where supported;
- compose/reply;
- send-as;
- send-on-behalf;
- shared calendar access;
- capability differences from primary mailbox explicitly surfaced.

Candidate surface may reuse ordinary tools with `mailbox_scope` plus dedicated high-risk tools for send-as/delegation.

Never silently fall back from a shared mailbox operation to the user's primary mailbox.

---

# Z. Automatic replies / Out of Office

Target:

- read current configuration;
- enable/disable;
- set start/end period;
- internal message;
- external message;
- external replies contacts-only/all according to UI;
- block calendar for absence;
- automatically decline new invitations where supported;
- cancel/decline existing meetings during period where supported;
- verify resulting configuration.

Candidate:

```text
outlook_auto_reply_manage
```

Calendar cancellations caused by OOO settings are externally visible and require appropriate policy.

---

# AA. Signatures

Target:

- list/discover signatures;
- create;
- update;
- delete;
- default for new mail;
- default for replies/forwards;
- account/from-identity-specific behavior where UI supports it;
- ensure body generation does not duplicate signatures unintentionally.

Candidate:

```text
outlook_signature_manage
```

---

# AB. Microsoft To Do / My Day inside Outlook

## AB1. Task reads

- lists;
- My Day;
- Important;
- Planned;
- All;
- Completed;
- Assigned to me where available;
- Flagged Email;
- Due Today;
- task get/search/filter.

Candidate:

```text
outlook_todo_list
outlook_todo_get
```

## AB2. Task lifecycle

- create;
- update;
- complete/reopen;
- delete;
- due date;
- reminder;
- recurrence;
- important;
- add/remove My Day;
- notes;
- attachments where supported;
- task steps/subtasks/checklist items.

Candidate:

```text
outlook_todo_manage
```

## AB3. Flagged email integration

- observe message-to-To-Do linkage where available;
- flag email and verify task appearance when capability exists;
- convert/drag email to task where UI provides deterministic operation;
- preserve source reference;
- report shared-mailbox limitations rather than pretending parity.

Candidate composite operation:

```text
outlook_email_to_task
```

---

# AC. Views and presentation settings

Target discovery/management where useful:

- Focused Inbox on/off;
- conversation mode;
- conversation newest/top behavior where exposed;
- density;
- reading pane location/off;
- sort;
- filter;
- message-list layout;
- sender image/grouping settings where exposed;
- favorites visibility;
- theme/presentation generally low priority unless needed for deterministic UI stability.

Candidate:

```text
outlook_view_settings_manage
```

Presentation settings must not become critical dependencies for semantic reads where avoidable.

---

# AD. Notifications and mail settings

Target:

- notification preferences;
- desktop/browser notification settings where surfaced;
- sound/banner settings when meaningful;
- read receipt policy;
- compose/reply defaults;
- spelling/editor options only if operationally useful;
- attachment reminder or related safe settings where exposed.

Candidate:

```text
outlook_notification_settings_manage
outlook_mail_settings_manage
```

---

# AE. Retention, archive and compliance-visible controls

Discovery-driven, tenant-policy-sensitive target:

- online archive availability;
- retention labels/policies surfaced to end user;
- move to archive;
- assign/remove allowed retention policy where UI permits;
- compliance/sensitivity labels visible in message UI;
- report policy-blocked actions cleanly.

The MCP must never attempt to bypass Purview/retention/compliance policy.

---

# AF. Microsoft 365 Groups inside Outlook

Discovery target where the account uses group surfaces:

- list groups;
- group conversations/mail;
- group calendar;
- membership visibility;
- follow/unfollow behavior;
- group files/related surfaces only if they remain within a clearly defined Outlook/M365 semantic boundary;
- membership changes classified as access-control mutations.

This area is intentionally later-phase and requires separate capability/security review.

---

# AG. Add-ins / apps / advanced Outlook extensions

The product may discover add-in/app surfaces but must not expose generic add-in automation.

A specific add-in may become a typed capability only after:

- purpose is explicitly in product scope;
- UI behavior is deterministic;
- security review completed;
- data-flow/privacy impact understood;
- dedicated contract and policy exist.

No arbitrary Office add-in invocation tool.

---

# AH. Composite Outlook operations

The following are higher-level semantic operations intended to reduce round-trips and LLM context.

## AH1. Inbox digest

Concept:

```text
outlook_inbox_digest
```

Possible structured inputs:

```text
since
unread_only
include_flagged
include_categories
include_attachments_metadata
max_items
fields
```

The MCP gathers/aggregates deterministically; summarization by an LLM is optional and outside the raw UI execution requirement.

## AH2. Mail triage

Concept:

```text
outlook_mail_triage
```

Closed requested actions may include:

```text
category
flag/follow-up
mark_read
move_folder
pin
```

Every child action retains its policy/read-back semantics.

## AH3. Person context

Concept:

```text
outlook_person_context
```

May deterministically aggregate:

```text
recent email metadata
upcoming calendar events
contact/directory record
tasks/flagged items where explicitly requested
```

Result shaping is mandatory to prevent context explosion.

## AH4. Daily/weekly operational view

Possible deterministic aggregation across:

- unread/flagged mail;
- calendar;
- To Do;
- optionally Planner through M365 BATCH/DAG.

The operation gathers structured facts. Any narrative summary is a separate reasoning layer.

---

# AI. Cross-application M365 operations

After Planner + Outlook are both stable:

## AI1. M365 batch

```text
m365_batch_execute
```

Example:

```text
search Outlook mail
+ read calendar range
+ read Planner tasks
```

One MCP request, independent policy per node.

## AI2. M365 DAG

Example:

```text
find email -> extract project reference -> query Planner -> return joined result
```

Bindings are typed and deterministic.

## AI3. Runbooks

Potential future runbooks:

```text
m365-daily-work-context-v1
outlook-inbox-triage-v1
meeting-preparation-v1
project-mail-followup-v1
shared-mailbox-health-v1
```

---

# AJ. Policy baseline for Outlook

Indicative default, subject to final governance:

| Operation type | Typical class |
|---|---|
| search/read/list | READ / T1 when mailbox content |
| mark read/unread | SAFE_WRITE |
| category apply/remove | SAFE_WRITE |
| flag/pin/snooze | SAFE_WRITE |
| create/update draft | SAFE_WRITE or GOVERNED depending content/scope |
| move message | SAFE_WRITE / governed for sensitive scope |
| change rules/Sweep | GOVERNED_WRITE |
| create Quick Step | GOVERNED_WRITE |
| execute attested low-risk Quick Step | depends on embedded actions |
| send/reply/forward | GOVERNED_WRITE |
| send-as/on-behalf | GOVERNED_WRITE / higher tier |
| create meeting with attendees | GOVERNED_WRITE |
| accept/tentative meeting | SAFE/GOVERNED according to policy |
| decline/cancel meeting | GOVERNED/DESTRUCTIVE |
| recall message | GOVERNED_WRITE |
| permanent delete | DESTRUCTIVE |
| change delegation/permissions | DESTRUCTIVE or highest governed tier |
| automatic external forwarding | high-risk governed or DENY by policy |

The registry, not this table, becomes the runtime authority.

---

# AK. Capability acceptance rule

For every capability above, implementation is not complete until there is:

1. semantic schema;
2. registry entry;
3. policy/risk class;
4. UIContract fragment;
5. mock fixture;
6. unit/integration test;
7. live UI observation;
8. attestation evidence;
9. read or mutation acceptance;
10. read-back strategy for mutations;
11. sanitized error mapping;
12. observability instrumentation;
13. documentation and traceability;
14. explicit support-state promotion.

No feature is advertised as supported merely because Playwright code for it exists.
