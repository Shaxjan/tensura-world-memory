# Eurazania — «Фестиваль Эуразании: Неделя силы» status recovery

Status: `RECOVERED STATUS / NO CONFIRMED COMPLETION`

This recovery file separates what was publicly planned and approved from what was actually completed in the surviving continuity.

## Recovered event plan

By T+131 the project existed publicly as **«Фестиваль Эуразании: Неделя силы»**.

Confirmed plan elements:
- public promotion had already begun by T+130;
- at T+131 there were **29 days remaining**, placing the intended start around **T+160**;
- planned site: south of the Eurazania capital;
- participation was open;
- winner: gold prize (exact amount still TBD in surviving planning material), the right to a real fight with **King Carrion**, plus a separate Crown reward still to be determined;
- monetary prizes were intended for the final ten;
- **Borga** was the public contact for questions;
- **Rena** and Borga both heard the public T+130 promotion;
- the collective poem about Eurazania created at the first poetry evening on T+131 was approved by those present for future festival use.

## T+153 — festival still future

A T+153 checkpoint/commit describing the plan to travel to Tempest **after the festival** is not evidence that the festival had already occurred. Its chronology means the opposite: at T+153 Arlequino still intended to remain in Eurazania until the festival was over and only then leave with Rena.

Primary checkpoint:
- commit `2686e1e5a6ae33368e274655d3c980765016bc24` — `Save T+153 post-festival Tempest travel plan and Cthulhu release policy`

Interpretation status: `CONFIRMED FUTURE PLAN AT T+153`.

## T+154 — war / evacuation disruption

By T+154 the continuity changed sharply:
- King Carrion announced that Milim had declared war on Eurazania because of Arlequino's fox attack;
- Arlequino addressed a large refugee group from the training-yard platform;
- a full wartime song was performed and followed by a real public anti-Milim declaration;
- in the subsequent mass response, **thousands of refugees** took up the refrain.

Important numeric rule:
- the surviving source explicitly leaves the exact population unspecified;
- carry only the qualitative scale **THOUSANDS OF REFUGEES**;
- do not convert this into 18,000, 100,000, or any other exact figure.

Primary checkpoints:
- `99dfa42191e8138ac0e6db27c9ca08968fea417e` — `Save T+154 evening anti-Milim war declaration`
- `12426a99190823a0ac2cd3b3ae15e59e229b2e76` — `Record T+154 mass war-song crowd response and sung refrain`
- `5b539fe73557f8ef35c4fb3434ad6e514226e9cb` — `Record T+154 war-song production package and complete concert canon`

Interpretation status: `CONFIRMED MAJOR DISRUPTION BEFORE PLANNED FESTIVAL DATE`.

## T+160 — Arlequino is in Dwargon

On the festival's approximately intended start day, direct surviving continuity places Arlequino in **Dwargon**, not at a completed Eurazania festival.

Primary checkpoint:
- `19e087535088a335710aff624cdd12b87640c842` — `T+160 01:23: recover sword, instrument and clothing storage`
- location recorded there: Dwargon / local storage
- Rena is with Arlequino

Additional T+160 Dwargon checkpoints exist later the same day, reinforcing that this is not a momentary mislabeled location.

Interpretation status: `CONFIRMED ABSENCE FROM EURAZANIA ON PLANNED START DATE`.

## Festival completion status

### What is confirmed

`PLANNED_AND_PUBLICLY_PROMOTED`

The festival was a real approved/public project, not a private idea.

### What is not confirmed

`NO_CONFIRMED_COMPLETION`

No surviving source located in the audit shows:
- opening of the Week of Strength;
- completed tournament rounds;
- final ten;
- winner;
- winner receiving gold;
- winner fighting Carrion;
- festival closing ceremony;
- festival audience count.

### Formal cancellation wording

`NOT_LOCATED`

Searches of the current repository and commit history for cancellation language did not locate a direct checkpoint saying the equivalent of “the festival is cancelled.” Therefore do **not** invent a formal cancellation order.

The safe continuity statement is:

> The Week of Strength was planned and publicly promoted, remained future at T+153, was overtaken by the T+154 war/evacuation crisis, and has no confirmed completion in surviving continuity; by its intended T+160 start window Arlequino was already in Dwargon.

Classification: `DERAILED_BY_WAR / COMPLETION_UNCONFIRMED`.

## Remembered audience figures: ~18,000 / ~100,000 / hundreds of thousands

Status: `UNSUPPORTED FOR THIS FESTIVAL`.

Repository/code/commit searches performed during recovery found no direct festival source containing:
- `18,000` as a Week of Strength audience;
- `100,000` as a Week of Strength audience;
- a confirmed “hundreds of thousands” festival crowd.

The strongest direct large-crowd Eurazania source currently recovered is the **T+154 refugee war-song response**, which says **thousands** and explicitly does not establish an exact population.

Do not migrate any remembered larger number into festival canon unless a direct historical source is later recovered.

## Canon-use rule

For future simulation:
- refer to the Week of Strength as a **planned/publicly promoted but unconfirmed/derailed event**;
- characters who heard the promotions may remember the project and intended rules;
- do not let NPCs remember a winner, completed tournament, Carrion title fight, festival crowd size, or closing ceremony unless another direct source is found;
- the T+154 wartime gathering is a **separate public event** and must not be merged into the festival.
