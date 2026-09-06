# Eurazania T+138 — formal concert recovery

Status: `PARTIALLY_RECOVERED / RETCON-AWARE`

Purpose: preserve only the T+138 concert facts that survive the correction chain. This file deliberately separates venue capacity, observed attendance, completed performances, stale checkpoints, and unresolved material.

## Event identity

- Day: **T+138**
- Place: **Eurazania capital**
- Event type: **formal large concert**
- Scheduled start: approximately **20:00**
- Safe site cap: **18,000**
- Final attendance: **UNKNOWN**
- Final revenue: **UNKNOWN**
- Complete final setlist: **NOT YET RECOVERED**

## Capacity is not attendance

Planning source:
- commit `cca399c50cfe187084741ad85fc31e05d4560220`
- establishes a safe event cap of **18,000**.

Pre-show source:
- commit `413905798491d01299b940d6f40ac715ef57bd9b`
- around the pre-show window, a visual estimate was approximately **12,000–14,000**;
- arrivals were still continuing.

Canon rule:

`18,000 = SAFE CAPACITY`

not

`18,000 = CONFIRMED ATTENDANCE`.

Until a later direct count is recovered, final attendance remains `UNKNOWN`.

## Early confirmed completed sequence

The surviving checkpoint chain confirms these performances before the later correction point:

1. **«Та, что»**
2. **«Созвездие Ангела»**
3. adapted **La Serenata** for Rena — guitar + violin, with Runa context

Relevant checkpoints include:
- `runtime/fast_play_checkpoints/fp_t138_1956_concert_prestart_crowd_split.json`
- `runtime/fast_play_checkpoints/fp_t138_2003_after_ta_chto.json`
- `runtime/fast_play_checkpoints/fp_t138_2005_after_sozvezdie_angela.json`
- `runtime/fast_play_checkpoints/fp_t138_2012_after_serenade_runa.json`

## «Полегче» — stale checkpoint / unresolved final performance status

A file named:
- `runtime/fast_play_checkpoints/fp_t138_2021_after_palehche.json`

exists in repository history, but it is **not sufficient proof of final canon**.

Later correction:
- commit `89432cf1781cb83a5aea090aa8a696ecd217f25f`
- rewinds the scene to the moment immediately after Serenade and before «Полегче»;
- therefore the earlier `after_palehche` checkpoint is stale/overridden for continuity purposes.

The song archive entry `song_archive/palehche_canonical_v2.json` proves that the song artifact exists. It does **not** prove that the T+138 performance survived the rewind.

No later direct replay/completion source has yet been recovered.

Status:

`ПОЛЕГЧЕ_T138 = PERFORMANCE_COMPLETION_UNRESOLVED`

Do not include it in a definitive completed setlist unless a later valid source is found.

## Later confirmed concert material

### «Музыка для секса»

Confirmed concert context:
- archive commit `1971f33540566399852ed7967d97341ea32d193b`
- metadata commit `08325aeb7b88bc8fdfef25742640ac695d7e372d`
- metadata explicitly places it in the **Eurazania capital concert, T+138**.

Status: `CONFIRMED T+138 CONCERT PERFORMANCE`.

### «Конфета»

Confirmed concert context:
- metadata commit `789de3bc9fc11c7f79713ab4a07dd9232c31ac2`
- explicit **Eurazania capital concert, T+138** context.

Status: `CONFIRMED T+138 CONCERT PERFORMANCE`.

### «Любовь»

Correction chain:
- `d4e5d948b21e5e0b046f93dc46aab80c077487f9`
- final correction scope `37a2e23ed0418ee164e47c6a3ba198cb5f5840e0`

At the correction point, the performance had been held after the first four lines. That intermediate state must not be mistaken for a permanently abandoned number.

Later canonical evidence resolves the issue:
- description commit for **«Я так соскучился»**: `bb44f93ff78d762433165572617bfa3d7caee677`
- it explicitly places «Я так соскучился» immediately after **«Любовь»** and describes the completed subsequent performance context.

Therefore the safe final interpretation is:

`ЛЮБОВЬ_T138 = COMPLETED BEFORE Я ТАК СОСКУЧИЛСЯ`

The intermediate hold remains part of correction history but does not make the final song incomplete.

### «Я так соскучился»

Confirmed by:
- `bb44f93ff78d762433165572617bfa3d7caee677`

Status: `CONFIRMED COMPLETED`.

### «Я создан для тебя»

Confirmed by:
- `bfa3debef7e2dea440dc25a302a1fcf0b0759bf5`
- source places it after the preceding song.

Status: `CONFIRMED COMPLETED`.

## Recovered later chain

The retcon-aware later material confidently includes:

- «Музыка для секса»
- «Конфета»
- «Любовь»
- «Я так соскучился»
- «Я создан для тебя»

This is a confirmed relative chain among these recovered items. It must **not** yet be presented as the complete remainder of the concert.

## What is still unresolved

1. whether «Полегче» was replayed and completed after the rewind;
2. whether any still-unrecovered number belongs between Serenade and the later recovered chain;
3. exact adjacency of the first later numbers relative to any replayed «Полегче»;
4. every number after «Я создан для тебя»;
5. final concert attendance;
6. final gross/net revenue;
7. exact end time / closing sequence.

## Canon-use rules

For future simulation or summaries:
- **18,000 is capacity, not attendance**;
- observed pre-show crowd was approximately **12,000–14,000 with arrivals continuing**;
- do not use the stale `after_palehche` checkpoint as higher authority than the later rewind;
- do not treat an archived song text as proof of a completed stage performance;
- count «Любовь» as completed because later canonical continuity explicitly proceeds from it into «Я так соскучился»;
- do not call this a fully recovered setlist;
- preserve final attendance and finances as `UNKNOWN` until direct later evidence is recovered.
