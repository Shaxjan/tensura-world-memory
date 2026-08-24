# Tensura World Memory — Authoritative Runtime v1.0.5 Protocol

Цель: живую симуляцию ведёт проверяемый движок; мастер описывает только причинно доступный результат. v1.0.5 подключает первый постоянный Character Core к общей очереди автономности мира, не создавая второй NPC-clock и не превращая скрытые решения персонажа в знание игрока или рассказчика.

## 1. Источник истины

### `runtime/runtime_state.json`
Главный LIVE-pointer. Нормальный режим: `mode = engine_authoritative`.

Для v1.0.5:
- `engine_version = 1.0.5`;
- `base_checkpoint` — текущий compact base;
- `journal_base_seq` — уже включённый в base sequence;
- `journal_seq` — последний подтверждённый event;
- `head_state_hash` — hash после replay;
- `session_state = runtime/session_state.json` — быстрый read-model текущей игровой сессии.

### `runtime/session_state.json`
Компактный неавторитетный read-model, построенный только из авторитетного runtime.

Он содержит время, текущую локацию, деньги при Арлекино, личные деньги Арлекино вне кошелька, итог последнего **игрового** хода и текущую living scene.

Технический system-event активации новой версии не должен подменять `last_turn` последнего игрового хода.

Если `session_state.journal_seq` совпадает с pointer, в уже синхронизированном чате мастер использует его напрямую. При новом чате, конфликте seq/hash или ошибке нужен full replay.

### Остальные файлы
- `runtime/checkpoints/` — immutable portable snapshots;
- `runtime/journal/jNNNNNN.json` — append-only авторитетные переходы;
- `runtime/requests/rNNNNNN.json` — входящие пользовательские команды;
- `live_state.json` — замороженный legacy v159 / rollback-anchor;
- `world_save.json`, `live_v*/`, `memory/` — история и аудит, они не перекрывают runtime.

## 2. Старт нового чата

1. Прочитать `MASTER_SAVE_PROTOCOL.md`.
2. Прочитать `runtime/runtime_state.json`.
3. Прочитать `runtime/session_state.json`, если его seq совпадает с pointer.
4. Один раз проверить full replay: base checkpoint + journal после `journal_base_seq` до `journal_seq` -> `head_state_hash`.
5. После успешной проверки держать session state в контексте.
6. Не перечитывать весь архив на каждом сообщении.
7. Старый pending не использовать повторно, если он уже закрыт runtime event.

`UNKNOWN` не заменять догадкой.

## 3. Быстрый игровой ход

Для каждого нового действия пользователя:

1. Проверить свежий `runtime/runtime_state.json`.
2. Если pointer seq совпадает с локально известным — full replay не нужен.
3. Создать ровно один `runtime/requests/rNNNNNN.json`, где `seq = journal_seq + 1`, а `raw_text` — дословный текст пользователя.
4. Workflow `Tensura Runtime Turn` выбирает request processor по `engine_version`, восстанавливает state, выполняет engine, создаёт новый journal event, обновляет pointer и `runtime/session_state.json`.
5. Дождаться подтверждённого нового session state.
6. Для обычного ответа читать session state; journal нужен только для подробного результата/аудита.
7. При stale seq/hash сначала синхронизироваться и не повторять эффект вслепую.

Нельзя выдавать игровой исход до подтверждённого runtime event.

## 4. Обязательный HUD в КАЖДОМ игровом ответе

Каждый обычный игровой ответ явно показывает:
- `Время`;
- `Место`;
- `При мне`;
- `Мои деньги вне кошелька`.

Рекомендуемый формат:

`Время: T+131 ~08:00 | Место: большой тренировочный двор Борги | При мне: 26g 05s 92c | Мои деньги вне кошелька: у Верна — остаток UNKNOWN (из переданных 50s)`

Семейная касса, project funds, promo funds, earmarked gifts/expenses и payables не являются личными деньгами Арлекино.

Если точный остаток личных денег у другого держателя неизвестен, показывать `UNKNOWN`, а не исходную переданную сумму как текущий баланс.

## 5. Чистая игровая наррация

В нормальной игре не показывать `engine_authoritative`, `journal_seq`, hashes, migration diagnostics, скрытые Character Core/plan/autonomy decisions и внутренние resolver-данные.

Сначала HUD, затем обычная сцена. Технические данные показывать только при ошибке, recovery или прямом запросе пользователя.

## 6. Living Scene Runtime

`UNKNOWN` местонахождения именованного NPC не означает пустую локацию.

Известная локальная точка может иметь persistent prospective ambient population: анонимные роли, группы и текущие занятия, допустимые для места и времени.

Ambient entities — `NON_CANON_MECHANICAL_PROSPECTIVE`: они существуют с момента materialization, но не являются ретроактивными утверждениями о прошлом.

Нельзя автоматически превращать фонового человека в старого знакомого, важного именованного NPC или носителя приватной информации.

## 7. Character Core v1

v1.0.4 вводит первый постоянный Character Core для Борги.

Core хранит:
- стабильную идентичность;
- autonomy tier;
- текущие source-grounded цели/обязанности;
- personality container;
- relationships;
- memories;
- causal knowledge policy;
- placeholders для будущих needs/resources;
- ссылку на текущий план.

### Главное правило заполнения
Новая структура не является разрешением выдумывать биографию.

Если черта характера, страх, романтическое отношение, память, имущество или иная личная деталь не подтверждены источником/событием, поле остаётся пустым либо `not_yet_authored` / `not_yet_modeled`.

Character Core имеет authority `NON_CANON_MECHANICAL_PROSPECTIVE` и управляет будущей симуляцией от момента materialization; он не переписывает невидимое прошлое.

## 8. Persistent character plan

Для Борги v1.0.4 заменяет независимый почасовой location roll одним persistent deterministic daily role plan.

Пока модель намеренно ограничена:
- `role_duty` — работа на одной из трёх уже калиброванных тренировочных площадок;
- `local_travel` — конечное окно перехода между рабочими точками, но без выдуманной геометрии;
- `unresolved_personal_time` — точное место `UNKNOWN`;
- `unresolved_region_activity` — точное место `UNKNOWN`.

Точный hidden place разрешён только в grounded `role_duty` block.

План является скрытым состоянием движка. Рассказчик и игрок не знают его автоматически.

Правильная цепочка:

`hidden character plan -> observation/testimony/transmission -> player knowledge`

## 9. Character Autonomy v1

v1.0.5 подключает первый Character Core к уже существующему `autonomy_runtime`.

Главный принцип: **один персонаж — одна шкала времени — одна очередь автономности**.

Для Борги не создаётся новый таймер и не дублируется поручение. Сохраняется уже авторитетный `task:borga`; меняется только его runtime-handler с generic `task_progress` на `character_task_v105`.

При активации обязаны сохраниться без сброса:
- `next_due_at`;
- `cadence_minutes`;
- `tick_count`;
- `status`.

Character Autonomy state извлекает рабочие направления только из уже сохранённого поручения Борги: combat rules, admissions, judges, testing, tournament operations. Новые обязанности из самой структуры не возникают.

На каждом due tick движок сначала сверяет persistent Character Plan:
- в `role_duty` block с точной grounded training-site допускается реальный hidden work tick по одной существующей обязанности;
- в `local_travel`, `unresolved_personal_time` или `unresolved_region_activity` работа откладывается как `character_work_deferred`; точное место не выдумывается.

Work tick означает подтверждённое усилие, но **не завершение** задачи. Автоматическое completion по количеству тиков запрещено до появления grounded completion condition/deliverable mechanic.

Autonomy decision — скрытое состояние движка. Арлекино, рассказчик, ambient NPC и другие персонажи не узнают его автоматически. Нужен причинный канал: наблюдение, свидетельство, отчёт или иная передача.

Все остальные commitments продолжают использовать существующие handlers общей очереди, если отдельная character-specific semantics для них ещё не калибрована.

## 10. v1.0.4 -> v1.0.5 continuity

Перед сменой semantics подтверждённый v1.0.4 head compact-ится неизменённым в новый v1.0.5 base checkpoint.

Activation оформляется новым append-only `character_autonomy_activation` journal event.

Activation:
- не является новым действием Арлекино;
- не двигает мировое время;
- не меняет деньги или регион игрока;
- не редактирует старые события;
- сохраняет последний игровой `last_turn`;
- не сбрасывает уже накопленный scheduler state Борги;
- только materializes Character Autonomy state и переназначает handler существующего `task:borga`.

Предыдущая v1.0.3 -> v1.0.4 причинная непрерывность сохраняется: current-day Borga plan по-прежнему использует допустимый migration anchor, а hidden plan не является знанием игрока.

## 11. Именованные NPC и локальный поиск

Именованный NPC не появляется потому, что так удобнее сцене.

Для позиции требуется сохранённая позиция, допустимый hidden prospective plan/routine, прямое наблюдение либо причинное свидетельство.

Поиск Борги на известной площадке остаётся конечным действием: 6 игровых минут; за это время работает autonomy; результат — `found`, `lead` или `not_found_no_lead`.

`lead` — свидетельство, а не всеведение. Оно не гарантирует, что Борга останется там до прихода игрока.

Во время `local_travel` / unresolved block скрытая точная позиция Борги остаётся `UNKNOWN`.

Для некалиброванного именованного NPC exact position остаётся guarded `UNKNOWN`.

## 12. Локальное перемещение

Известная точка текущего города — конечное действие.

Движок двигает мировой clock, запускает автономность, фиксирует прибытие и living scene. Повтор команды в уже достигнутую точку не списывает время повторно.

Локальное перемещение игрока не даёт ему скрытое знание Character Core/plan.

## 13. Pending

Pending нужен только там, где исход нельзя безопасно разрешить текущей механикой. Narration не превращает pending в факт.

System resume допускается только для уже явно выбранного пользователем действия.

Generic resolver нельзя использовать для обхода денег, боя, магии/лечения, рынка, силы или межрегионального travel.

## 14. Деньги

- 100c = 1s; 100s = 1g.
- Личная касса отдельно от family/project/promo.
- После реально завершённого публичного выступления: income / expense / net / new personal cash.
- Неизвестный entrusted float остаётся `UNKNOWN` до причинного отчёта/расхода/возврата.
- У Верна переданный principal 50s не равен текущему остатку: текущий остаток `UNKNOWN`.
- Не создавать деньги из реакции толпы.
- Character Core/Autonomy activation не меняет деньги.

## 15. Контроль Арлекино и знания

- Арлекино/Маэстро полностью контролирует пользователь.
- Не придумывать его реплики, чувства, решения и значимые действия.
- NPC и мир автономны.
- Знание NPC требует `SOURCE -> TRANSMISSION -> TIME -> RECIPIENT`.
- Скрытый character plan и hidden autonomy decisions не являются знанием NPC вокруг него автоматически.
- Не передавать NPC приватные сведения без канала.
- Только Рена говорит «павлин».
- Jura — регион; JTF ещё нет.
- Falmuth, не Farmenas.
- Поручение Верна в Дваргон не связано с Ореном.
- Гарет и Верн знают точную гостиницу в мире; GM не знает её названия и не придумывает его.

## 16. Retcon / repair

Прямая коррекция пользователя отменяет противоречащую старую запись. После cutover repair оформляется новым runtime transition. Старый journal event не редактировать.

## 17. Checkpoint / compaction

При смене engine semantics или периодически:
1. replay текущего base + journal до head;
2. проверить hash;
3. экспортировать новый portable checkpoint в новый файл;
4. проверить roundtrip;
5. обновить pointer и `journal_base_seq`;
6. старые checkpoint/journal не удалять.

Новая версия engine не должна replay старых событий под изменившейся семантикой, если это меняет их результат. Сначала compact старый подтверждённый head, затем новые события новой версии.

## 18. Rollback

`legacy_rollback` хранит точную pre-cutover v159 точку.

Emergency rollback: остановить runtime writes; проверить anchor/blob SHA; сохранить текущий runtime head; восстановить ровно legacy pointer; не переносить частично новые runtime events в legacy автоматически.

Каждая новая engine activation должна оставлять предыдущий checkpoint/journal доступными для аудита.

## 19. Песни

- Одна песня = один полный UTF-8 файл, когда текст реально полный и проверен.
- `FULL_CANONICAL` только после обратного чтения полного файла.
- Потерянный/обрезанный текст не восстанавливать по оригиналу или памяти.

## 20. Нельзя

- считать legacy `live_state.json` текущим SAVE;
- редактировать подтверждённый journal event;
- обновлять pointer раньше успешного event;
- придумывать `UNKNOWN`;
- трактовать отсутствие именованного NPC как отсутствие всех людей;
- смешивать личные, семейные и проектные деньги;
- решать за Арлекино;
- давать NPC невозможные знания;
- раскрывать hidden Character Core/plan/autonomy decision как будто игрок это знает;
- создавать для одного commitment второй автономный таймер/очередь;
- заполнять новый Core выдуманными чертами, памятью, отношениями или имуществом;
- превращать causal testimony в абсолютную истину;
- показывать техничку вместо игровой сцены без необходимости;
- пропускать обязательный HUD.
