# News and rumor propagation v1 — activated at T+151

Status: ACTIVE RUNTIME RULE.

## Defect being fixed
The previous simulation correctly enforced causal knowledge (`SOURCE -> TRANSMISSION -> TIME -> RECIPIENT`) but applied it too narrowly. The result was an unrealistically silent world: unless Arlequino explicitly asked a specific NPC about a specific event, large-scale news and ordinary rumors often never reached him.

That behavior is corrected from T+151 onward.

## Core principle
Causal knowledge remains mandatory, but information itself now travels autonomously through the world.

The world must continuously generate and propagate information through plausible channels even when the player does not ask for it.

`WORLD EVENT -> SOURCE/WITNESS -> TRANSMISSION CHANNEL -> TRAVEL/PROCESSING DELAY -> LOCAL INFORMATION POOL -> PLAYER/NPC EXPOSURE`

No omniscience is introduced. Instead, the transmission network is simulated.

## Information channels
Depending on region and event, information may move through:

- royal/government announcements;
- military orders and visible mobilization;
- Free Guild / adventurer-guild notices;
- merchant guilds, caravans and traders;
- inns, taverns, markets, bathhouses and street conversation;
- travelers, refugees and pilgrims;
- performers, students and craftsmen moving between cities;
- messengers, letters and courier services;
- guards, gate staff and road checkpoints;
- diplomats and visiting delegations;
- sailors/river traffic where relevant;
- direct magical communication only where canonically/locally established and available;
- eyewitnesses to spectacular events.

## Information classes
Every propagated item should internally belong to one of these classes:

1. OFFICIAL — public decree, guild notice, military order, diplomatic statement. High source identity; may still contain propaganda or incomplete facts.
2. DIRECT WITNESS — someone claims to have personally seen the event. Useful but fallible.
3. RELIABLE SECONDARY — merchant/guild/courier network with identifiable origin.
4. RUMOR — ordinary repeated talk with uncertain origin.
5. WILD RUMOR — sensational, contradictory or low-confidence claim.
6. SECRET/RESTRICTED — does not enter public circulation unless leaked through a causal event.

The GM must not narrate rumor as objective truth. Language should expose uncertainty naturally: `говорят`, `караванщики утверждают`, `в гильдии висит сообщение`, `два независимых торговца повторяют`, etc.

## Propagation speed
Information has travel time.

- Same building/street after a visible incident: minutes to hours.
- Same city, ordinary public event: hours; major spectacular event can spread citywide very quickly.
- Same kingdom via roads/markets/guilds: typically hours to days depending on distance and channel.
- Neighboring kingdoms: days unless a faster established channel exists.
- Distant states: longer and more distorted unless official/magical courier routes are established.

Do not invent exact magical instant-news networks merely to deliver plot exposition.

## Passive player exposure
Arlequino does NOT need to ask `what are the news?` to hear anything.

When he spends meaningful time in populated/public environments, interacts with mobile people, receives visitors, works with organizers, attends a guild/market/tavern, passes gates, travels, or is present during a major local event, the scene may naturally surface relevant information.

Examples of valid passive exposure:
- two merchants arguing about a road closure while Arlequino passes;
- a tavern crowd discussing a rumor from Tempest;
- Meira mentioning a new official restriction because it affects festival logistics;
- a guild notice appearing on a board;
- arriving travelers describing unusual troop movement;
- a messenger seeking Maestro Arlequino or Maestro Rena because their project is affected;
- price/traffic/lodging changes becoming noticeable before anyone explains the political reason.

Passive exposure must remain proportional. Do not turn every RP turn into a news bulletin.

## Relevance / salience
The chance and speed of exposure rises with:

- geographic proximity;
- event magnitude;
- number of witnesses;
- public consequences;
- relevance to Arlequino's current projects/status;
- Arlequino's fame and social connectivity;
- repetition across independent sources.

A capital-destroying threat cannot remain invisible to a famous resident coordinating a giant festival in that same capital once authorities/roads/people are visibly reacting.

## Local information pool
Each populated region conceptually maintains a rolling local information pool:

- newly arrived facts/claims;
- current public concerns;
- older rumors decaying in relevance;
- contradictions between sources;
- official corrections;
- visible material consequences.

NPCs draw only from information they plausibly encountered. They are not automatically synchronized with the whole local pool.

## Major-event escalation rule
For major events, exposure escalates naturally:

1. faint/contradictory signs;
2. multiple independent rumors;
3. visible institutional reaction;
4. direct local consequences;
5. official confirmation / eyewitness certainty where applicable.

Do not force every stage if the event is directly visible. Example: Milim appearing over the Eurazania capital is itself direct observation for people who can see/hear it; it does not need to arrive as tavern gossip first.

## Backlog repair at T+151
Because previous gameplay under-surfaced ambient news, do NOT retcon Arlequino as having secretly known specific facts all along.

Instead:
- keep his established player knowledge unchanged;
- from T+151 forward, allow a plausible backlog of already-circulating non-secret information to reach him naturally through current contacts/environment;
- do not fabricate exact past conversations that were never played;
- old public events may be learned late with appropriate wording (`ты впервые слышишь`, `похоже, об этом уже несколько дней говорят`, etc.) if causally plausible.

## Canon integration
Canonical world events occur on the schedule in `runtime/rules/CANON_TIMELINE_SYNC_v1.md` and automatically inject information into appropriate transmission networks.

This does NOT reveal future canon to the player. Only events that have happened in world-time may begin propagating.

## NPC knowledge remains causal
This rule does not weaken the existing knowledge-chain requirement. It repairs the missing TRANSMISSION layer.

For any important NPC knowledge claim, the model should be able to answer conceptually:
`Where could they have heard/seen this, and was there enough time?`
If no plausible answer exists, the NPC does not know.

## Presentation rule
News should primarily appear inside ordinary living scenes rather than as detached encyclopedic dumps. A short explicit news/rumor digest is appropriate only when Arlequino deliberately checks a guild board, asks for news, reads reports, or receives a compiled briefing.

## Player prominence
Arlequino's fame increases incoming social information but does not make him omniscient. People may approach him with gossip, invitations, warnings, requests, rumors or opportunistic claims because he is famous and connected. Some of those claims may be wrong.

Effective immediately at T+151. No game time is advanced by activating this rule.