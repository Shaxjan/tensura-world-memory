# Living World Simulation v1

Status: ACTIVE RUNTIME RULE.

## Purpose

Bind world autonomy, canon progression, information propagation, persistent character behavior, and material realism into one operational rule for ordinary play.

The world must not freeze around Arlequino. Player attention determines what is narrated, not what is allowed to exist.

Core principle:

`WORLD TIME ADVANCES -> WORLD SYSTEMS ADVANCE -> CONSEQUENCES EXIST -> ONLY CAUSALLY VISIBLE CONSEQUENCES REACH THE PLAYER`

This rule works together with:
- `runtime/world_state/WORLD_PROCESS_REGISTRY_v1.md`
- `runtime/world_state/active_processes.json`
- `runtime/world_state/information_frontier.json`
- `runtime/rules/CANON_TIMELINE_SYNC_v1.md`
- `runtime/rules/NEWS_RUMOR_PROPAGATION_v1.md`
- `memory/characters/CHARACTER_SYSTEM_v1.md`
- `memory/creative_exposure/CREATIVE_EXPOSURE_PROTOCOL_v1.md`
- `runtime/current_scene.json`
- `PROJECT_VISION.md`

The rule file defines behavior; the world-state registry stores what is actually in motion right now. Normal play must consult both.

## 1. When autonomous world advancement must be considered

Do not run a giant simulation after every sentence. Run meaningful world advancement whenever enough world time or causal opportunity has passed for something to change, especially during:

- sleep;
- travel;
- long work, rehearsal, shopping, recovery, waiting, study, or crafting;
- scene cuts;
- appointments and deadlines;
- multi-hour or multi-day gaps;
- major canonical event windows;
- ongoing NPC assignments;
- wars, evacuations, markets, festivals, guild operations, transport disruption, or other systems with their own clocks.

Short conversational exchanges usually inherit the existing world state unless an independent event is already due or physically nearby.

## 2. Active-process check before simulation

Before inventing new background activity, read `runtime/world_state/active_processes.json` and `runtime/world_state/information_frontier.json`.

The registry answers:
- who already has an assignment or obligation;
- which project is already running;
- which canon/world aftermath is active;
- what dependencies or delays exist;
- what information is already moving;
- what Arlequino and important NPCs do or do not know.

Do not restart an existing task as if newly assigned. Do not make a registered task disappear because the player changed scenes. Do not autocomplete a task without enough elapsed time/opportunity.

When a new durable task/process appears, register it. When a process materially advances, update it. When it resolves, persist the result to the appropriate event/memory layer before removing or archiving it.

## 3. World-side advancement order

When the world advances, consider these layers in order:

1. **Locked or currently active canon events**
   - Apply `CANON_TIMELINE_SYNC_v1.md`.
   - Canonical actors continue pursuing their goals without waiting for Arlequino.
   - Do not postpone a canonical event merely to protect the player's concert, romance, travel, sleep, or project.
   - A causally sufficient player/world intervention may create a real divergence; canon is a baseline, not an invulnerable railroad.

2. **Registered active processes**
   - Review each relevant entry in `active_processes.json` against elapsed time, actor availability, dependencies and current circumstances.
   - Preserve explicit blocking reasons.
   - Advance partial progress where justified instead of forcing binary success/failure.

3. **Autonomous NPC plans and obligations**
   - Named persistent NPCs may work, travel, refuse, negotiate, investigate, spend resources, meet others, change plans, fail, succeed, misunderstand, or initiate contact when justified by their goals, duties, relationships, knowledge, resources, location, and time.
   - NPCs do not wait in suspended animation until the player asks what they did.
   - Off-screen action must remain consistent with the character record and causal constraints.

4. **Institutions and material systems**
   - Governments, guilds, guards, shops, schools, organizers, roads, lodging, transport, prices, queues, military movement, evacuation, supply, and similar systems continue operating independently.
   - Changes may occur before the player learns why.

5. **News and rumor propagation**
   - Apply `NEWS_RUMOR_PROPAGATION_v1.md` and update `information_frontier.json`.
   - Events inject facts/claims into plausible transmission channels only after they occur.
   - Travel/process delay, source quality, distortion, contradiction, and local relevance matter.
   - Public knowledge is not universal knowledge.

6. **Player-visible exposure**
   - Surface only what Arlequino can causally notice, hear, receive, infer from material consequences, or be told.
   - Do not reveal hidden GM knowledge, future canon, secret motives, or private NPC thoughts unless causally exposed.

## 4. NPC autonomy standard

A recurring NPC must not behave as a player-serving utility.

Before giving an NPC a meaningful action, check:
- What do they want right now?
- What obligations are competing for their time?
- What do they actually know?
- Where are they physically?
- What resources and authority do they have?
- What would their established character make them likely to do?
- What can go wrong?

Valid autonomous behavior includes:
- initiating a conversation or task;
- saying no;
- delaying something;
- choosing a different method than the player expected;
- making a mistake;
- withholding something for a believable reason;
- disagreeing with another NPC;
- pursuing a personal objective while the player is elsewhere;
- changing an opinion after new evidence;
- contacting Arlequino because an event affects an existing agreement or relationship.

Autonomy must not be random chaos. It must be explainable from character + knowledge + circumstances.

## 5. Character realism

Use `memory/characters/CHARACTER_SYSTEM_v1.md`.

Requirements:
- do not flatten groups into one reaction;
- do not turn affection, marriage, friendship, employment, rank, or gratitude into obedience;
- do not invent stable traits from one convenient scene;
- allow contradictions inside a developed personality;
- preserve boundaries and competing goals;
- allow moods to change without rewriting core personality;
- maintain individual speech/initiative patterns only where actually established;
- update durable character memory only when a scene reveals something stable or consequential.

Named characters should accumulate history. Repeated exposure should change what later behavior can plausibly mean.

## 6. Information and rumor realism

Every important knowledge claim should be defensible as:

`SOURCE -> TRANSMISSION -> DELAY -> RECIPIENT`

Rumors may:
- lose detail;
- gain exaggeration;
- merge with another story;
- contradict official statements;
- be true in core but wrong in numbers;
- be deliberately manipulated;
- die locally if nobody has reason to repeat them.

Major events spread faster because more witnesses and institutions are involved. Secret information does not become public merely because it is important to the plot.

Repeated independent sources increase credibility but do not automatically produce omniscience.

For important moving information, use `runtime/world_state/information_frontier.json` so a new chat can distinguish world truth, regional circulation and individual exposure.

## 7. Material realism

Narration and state changes must respect:
- elapsed time;
- travel distance and transport;
- opening hours / availability where relevant;
- money, prices, payment and ownership;
- inventory and physical possession;
- housing and access;
- fatigue, sleep, injury and recovery;
- weather and local conditions when material;
- administrative authority and bureaucracy;
- crowd size and venue capacity;
- supply, labor and preparation time;
- consequences of war, evacuation, road closures, shortages, fear, fame, crime, and public events.

Do not create instant logistics because the player requested an outcome. NPCs can try immediately; completion still takes the time the world requires.

## 8. Canon progression and divergence

Canon actors are autonomous world actors.

Rules:
- canonical events continue on their synchronized schedule unless a real prior divergence changes them;
- the player is allowed to interfere if he causally learns enough and acts in time;
- success is not guaranteed;
- the GM must not secretly force canon by making affected NPCs irrational;
- the GM must not secretly protect the player by freezing canon;
- once a true divergence occurs, persist it as this world's history and propagate its consequences forward.

When a locked canon event becomes due and occurs, persist the world-side event and register any continuing aftermath that materially matters to future play.

## 9. Off-screen events and persistence

Not every off-screen action deserves a stored event. Persist events that materially affect future causality, including:
- completed assignments;
- changed agreements;
- major decisions;
- travel/location changes of important NPCs;
- deaths, injuries, arrests, promotions, breakups, marriages, betrayals, alliances;
- substantial money/property changes;
- public announcements and major rumors;
- important creative exposure;
- canon divergence;
- any fact a later scene will need in order not to reset continuity.

Use the appropriate runtime journal/significant-event, character-memory, exposure, clarification, correction or world-state layer rather than stuffing everything into the current scene.

Active unfinished work belongs in `runtime/world_state/active_processes.json`. Information in transit or unevenly distributed belongs in `runtime/world_state/information_frontier.json`.

## 10. Scene presentation realism

The player should experience a living world mostly through ordinary scenes:
- someone arrives late because roads are crowded;
- a shop has changed prices;
- a student already discussed something with another student;
- an organizer has made progress without being prompted again;
- a rumor reaches the room indirectly;
- a guard changes procedure after an official order;
- a friend is busy, tired, annoyed, excited, or pursuing their own plan;
- a major crisis changes transport, lodging, crowds, work, and conversation before the player receives a full explanation.

Do not convert the game into a detached simulation report unless the player explicitly asks for one.

## 11. Anti-freeze rule

The following are continuity errors:
- canon waiting for the player to finish a personal project;
- NPC assignments producing no movement simply because the player did not ask again;
- a registered active process vanishing between scenes without resolution;
- a city remaining socially unchanged during a major local crisis;
- rumors never moving unless Arlequino asks for news;
- recurring NPCs forgetting established personality or prior interactions;
- every NPC being available whenever the player wants them;
- instant travel, logistics, construction, investigation, or institutional action without sufficient time/resources;
- hidden facts appearing in dialogue without a causal knowledge path.

## 12. Anti-oversimulation rule

Living-world autonomy is not permission to invent large unseen outcomes without evidence.

When an off-screen result is not yet determined by stored rules, known character goals, time, resources, active-process state or direct simulation, keep the exact outcome unresolved until it is causally resolved.

Prefer:
- `task is in progress`
- `likely arrival window`
- `several plausible outcomes remain`
- `exact result UNKNOWN`

over fabricating a convenient success/failure.

## 13. Operational check before every substantial scene transition

Ask internally:
1. How much world time passed?
2. What entries in `active_processes.json` must be reviewed?
3. Did any canon anchor become due?
4. What important NPC plans could have advanced?
5. What institutions/material conditions could have changed?
6. What items in `information_frontier.json` had enough time to travel?
7. What can Arlequino actually perceive or know now?
8. Does the new scene preserve character, money, location, agreements and prior exposure?
9. What durable consequence must be persisted?

If nothing causally changed, inherit the previous state. If something did, advance it without waiting for the player to request permission for the world to exist.