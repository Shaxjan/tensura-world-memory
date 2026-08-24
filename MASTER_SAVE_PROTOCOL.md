# Tensura World Memory — Authoritative Runtime v1.0.10 Protocol

Цель: живую симуляцию ведёт проверяемый движок; мастер описывает только причинно доступный результат. v1.0.10 сохраняет Living Scene, Character Core, shared-scheduler Character Autonomy, safe intent grounding, causal named-character memory, finite visible local approach и чистый session read-model, а также вводит первый ограниченный authoritative NPC-response policy для простого прямого приветствия.

## 1. Источник истины

### `runtime/runtime_state.json`
Главный LIVE-pointer. Нормальный режим: `mode = engine_authoritative`.

Для v1.0.10:
- `engine_version = 1.0.10`;
- `base_checkpoint` — текущий compact base;
- `journal_base_seq` — уже включённый в base sequence;
- `journal_seq` — последний подтверждённый event;
- `head_state_hash` — hash после replay;
- `session_state = runtime/session_state.json` — быстрый read-model текущей игровой сессии.

### `runtime/session_state.json`
Компактный неавторитетный read-model, построенный только из авторитетного runtime.

Он содержит время, текущую локацию, деньги при Арлекино, личные деньги Арлекино вне кошелька, итог последнего **игрового** хода и текущую living scene.

Технический system-event активации новой версии не должен подменять `last_turn` последнего игрового хода.

`last_turn.pending_resolutions` в текущем session state является проекцией **текущих** authoritative rows со `status='pending'`, а не архивным снимком старых pending. Repaired/cancelled/resolved historical rows остаются в БД/journal для аудита, но не показываются как текущие pending.

Построение session read-model является read-only. Оно не должно создавать GM telemetry, увеличивать metrics или менять authoritative hash только из-за чтения.

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

`Время: T+131 ~08:18 | Место: малый боевой/тренировочный двор | При мне: 26g 05s 92c | Мои деньги вне кошелька: у Верна — остаток UNKNOWN (из переданных 50s)`

Семейная касса, project funds, promo funds, earmarked gifts/expenses и payables не являются личными деньгами Арлекино.

Если точный остаток личных денег у другого держателя неизвестен, показывать `UNKNOWN`, а не исходную переданную сумму как текущий баланс.

## 5. Чистая игровая наррация

В нормальной игре не показывать `engine_authoritative`, `journal_seq`, hashes, migration diagnostics, скрытые Character Core/plan/autonomy/memory records и внутренние resolver-данные.

Сначала HUD, затем обычная сцена. Технические данные показывать только при ошибке, recovery или прямом запросе пользователя.

Если NPC-response уже разрешён движком, мастер может передать только engine-provided observable semantics/реплику. Скрытая причина решения, Character Plan, scheduler state и private memory не раскрываются.

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

Новая структура не является разрешением выдумывать биографию. Если черта характера, страх, романтическое отношение, память, имущество или иная личная деталь не подтверждены источником/событием, поле остаётся пустым либо `not_yet_authored` / `not_yet_modeled`.

Character Core имеет authority `NON_CANON_MECHANICAL_PROSPECTIVE` и управляет будущей симуляцией от момента materialization; он не переписывает невидимое прошлое.

## 8. Persistent character plan

Для Борги v1.0.4 использует один persistent deterministic daily role plan.

Пока модель ограничена:
- `role_duty` — работа на одной из трёх калиброванных тренировочных площадок;
- `local_travel` — конечное окно перехода, без выдуманной геометрии;
- `unresolved_personal_time` — точное место `UNKNOWN`;
- `unresolved_region_activity` — точное место `UNKNOWN`.

Точный hidden place разрешён только в grounded `role_duty` block. План скрыт от игрока/рассказчика до causal observation/testimony.

## 9. Character Autonomy v1

v1.0.5 подключает Character Core Борги к существующему `autonomy_runtime`.

Главный принцип: **один персонаж — одна шкала времени — одна очередь автономности**.

Существующий `task:borga` сохраняет scheduler state; меняется только handler на `character_task_v105`. Work tick допускается только при grounded `role_duty`; иначе работа deferred. Work tick не означает completion.

Autonomy decision скрыт и становится знанием только через наблюдение/свидетельство/отчёт.

## 10. Intent Grounding v1

v1.0.6 исправляет ложное связывание именованных NPC по подстрокам.

Именованный target требует explicit token/допустимую форму имени. Случайная последовательность символов внутри другого слова не является упоминанием NPC.

Наблюдавшийся дефект `рен` внутри `тренировочный` закрыт append-only repair event; старый malformed journal не редактировался.

Known-local travel допускает ограниченную typo repair только там, где destination уже grounded alias/causal lead. Typo tolerance не разрешает угадывать неизвестные места или NPC.

## 11. Causal Encounter Memory v1

v1.0.7 добавляет первую долговременную память persistent named character, калиброванную на Борге.

### Reciprocal-awareness rule

`Арлекино увидел Боргу` **не означает** `Борга заметил/запомнил Арлекино`.

Память создаётся только для нового принятого хода, если:
- Борга уже causally visible в той же локальной сцене;
- Арлекино явно адресует/упоминает Боргу через safe intent grounding;
- ход содержит реально наблюдаемое обращение/interaction/handoff/performance component.

Простой поиск/обнаружение Борги память Борги не создаёт.

### Storage rule

Production `actors` пока содержит generic actor-state только там, где все обязательные поля grounded. Нельзя материализовать Боргу как generic actor с фиктивными `cash=0`, stats или status только ради старого FK `memories` table.

Поэтому v1.0.7 хранит causal named-character memory в существующем authoritative `facts` store с ключом `v107:character_memory:borga:<turn_key>`, а `Character Core.memories` хранит ссылку на этот fact.

### Memory content

Можно сохранять:
- кто наблюдал/кого;
- время и место;
- source turn;
- дословно наблюдаемый player text;
- тип наблюдаемого компонента;
- causal basis/confidence.

Нельзя автоматически выводить из memory:
- эмоцию/approval/disapproval;
- изменение отношений;
- ответ Борги;
- consent/acceptance;
- истинность сказанного Арлекино.

Memory fact приватен для character state и не становится знанием рассказчика/других NPC автоматически.

## 11A. Causal NPC Response v1

v1.0.10 добавляет первый bounded authoritative response resolver для persistent named character.

Первая калибровка ограничена случаем **Борга + простое прямое приветствие**. Ответ разрешён только для нового хода после activation, если одновременно выполнены условия:
- Борга прямо видим игроку в текущей living scene;
- Борга явно назван через safe intent grounding;
- ход содержит `speech_or_request`;
- для этого же нового хода уже создана causal encounter memory Борги;
- текущий Character Plan подтверждает точное присутствие Борги в том же месте в `role_duty` block;
- фраза является только приветствием, а не вопросом, просьбой, предложением или иным содержательным social action.

Разрешённый результат первой калибровки: `minimal_reciprocal_greeting` / `return_greeting`, 0 полных world minutes. Canonical surface может зеркально вернуть распознанное приветствие, например `Доброе утро.`.

Response policy внутри Character Core является скрытой prospective механикой, а не чертой характера. Нельзя выводить из ответа эмоцию, tone, approval/disapproval, симпатию, доверие, consent, willingness to continue conversation или relationship delta.

Наблюдаемый игроком ответ хранится отдельно как `v110:player_observed_response:borga:<turn_key>` и может стать player knowledge. Скрытый план/decision basis в этот observable fact не записывается.

Всё вне этой узкой калибровки остаётся unresolved до отдельной поддерживаемой response-механики.

## 12. Version continuity / activation

Каждая смена semantics сначала compact-ит подтверждённый предыдущий LIVE head в новый immutable base checkpoint, затем добавляет новый activation journal event.

Activation v1.0.7:
- не является действием Арлекино;
- 0 игровых минут;
- не меняет деньги/регион/место;
- сохраняет `last_turn`;
- не импортирует память из предыдущего one-way поиска `r000009`;
- не materializes Боргу как generic `actors` row;
- только подключает memory model к существующему Character Core.

Activation v1.0.8:
- 0 игровых минут;
- append-only отменяет только известные ложные `local_navigation` pending r11/r12;
- не объявляет их движение успешным задним числом;
- не меняет память/отношения/деньги/место.

Activation v1.0.9:
- 0 игровых минут;
- не меняет gameplay DB state, память, отношения, деньги или место;
- сохраняет последний игровой ход;
- пересобирает session read-model так, чтобы `last_turn.pending_resolutions` содержал только реально текущие authoritative pending.

Activation v1.0.10:
- 0 игровых минут;
- не является действием Арлекино или Борги;
- materializes только prospective response policy в Character Core;
- не меняет personality, relationships, existing memories, деньги, регион или место;
- не создаёт NPC-response задним числом;
- прежнее приветствие `r000013` остаётся исторически без подтверждённой реакции;
- первый authoritative NPC-response возможен только на новом player turn после activation.

## 13. Именованные NPC и локальный поиск

Именованный NPC не появляется потому, что так удобнее сцене.

Для позиции требуется сохранённая позиция, допустимый hidden prospective plan/routine, прямое наблюдение либо причинное свидетельство.

Поиск Борги на известной площадке — конечное действие: 6 игровых минут; за это время работает autonomy; результат — `found`, `lead` или `not_found_no_lead`.

`lead` — свидетельство, а не всеведение. Во время `local_travel` / unresolved block скрытая точная позиция Борги остаётся `UNKNOWN`.

## 14. Локальное перемещение

Известная точка текущего города — конечное действие. Движок двигает clock, запускает autonomy, фиксирует прибытие и living scene. Повтор команды в уже достигнутую точку не списывает время повторно.

Локальное перемещение не даёт скрытое знание Character Core/plan/memory.

v1.0.8 отдельно разрешает **явный подход к прямо видимому именованному NPC в той же living scene** как конечное same-scene действие. Требуются explicit approach language + ровно один safe-grounded named target + текущий `visible` observation.

Такой подход:
- занимает 0 полных world minutes при текущей минутной гранулярности;
- не выдумывает точную дистанцию/геометрию;
- не означает NPC reply, attention, emotion, consent, relationship change или reciprocal memory.

Bare `Подхожу` без явного target не привязывается к Борге автоматически.

## 15. Pending

Pending нужен только там, где исход нельзя безопасно разрешить текущей механикой. Narration не превращает pending в факт.

System resume допускается только для уже явно выбранного действия. Generic resolver нельзя использовать для обхода денег, боя, магии/лечения, рынка, силы или межрегионального travel.

Факт того, что Борга услышал принятую явную реплику, сам по себе не разрешает произвольный ответ. v1.0.10 снимает неопределённость только в своей узкой simple-greeting калибровке; вопросы, просьбы, предложения и прочие содержательные реакции остаются pending/unresolved согласно поддерживаемой механике.

Текущий session read-model обязан проверять authoritative `scene_pending_resolution.status`. Старый pending после `repaired/cancelled/resolved` не может оставаться в `last_turn.pending_resolutions` как будто он всё ещё активен.

## 16. Деньги

- 100c = 1s; 100s = 1g.
- Личная касса отдельно от family/project/promo.
- После реально завершённого публичного выступления: income / expense / net / new personal cash.
- Неизвестный entrusted float остаётся `UNKNOWN` до причинного отчёта/расхода/возврата.
- У Верна переданный principal 50s не равен текущему остатку: текущий остаток `UNKNOWN`.
- Не создавать деньги из реакции толпы.
- Engine activation не меняет деньги.

## 17. Контроль Арлекино и знания

- Арлекино/Маэстро полностью контролирует пользователь.
- Не придумывать его реплики, чувства, решения и значимые действия.
- NPC и мир автономны.
- Знание NPC требует `SOURCE -> TRANSMISSION -> TIME -> RECIPIENT`.
- Скрытый plan/autonomy/memory другого персонажа не является знанием автоматически.
- Не передавать NPC приватные сведения без канала.
- Только Рена говорит «павлин».
- Jura — регион; JTF ещё нет.
- Falmuth, не Farmenas.
- Поручение Верна в Дваргон не связано с Ореном.
- Гарет и Верн знают точную гостиницу в мире; GM не знает её названия и не придумывает его.

## 18. Retcon / repair

Прямая коррекция пользователя отменяет противоречащую старую запись. Repair оформляется новым runtime transition. Старый journal event не редактировать.

## 19. Checkpoint / compaction

При смене engine semantics или периодически:
1. replay текущего base + journal до head;
2. проверить hash;
3. экспортировать новый portable checkpoint в новый файл;
4. проверить roundtrip;
5. обновить pointer и `journal_base_seq`;
6. старые checkpoint/journal не удалять.

Новая версия engine не должна replay старых событий под изменившейся семантикой, если это меняет их результат. Сначала compact старый подтверждённый head, затем новые события новой версии.

## 20. Rollback

`legacy_rollback` хранит точную pre-cutover v159 точку.

Emergency rollback: остановить runtime writes; проверить anchor/blob SHA; сохранить текущий runtime head; восстановить ровно legacy pointer; не переносить частично новые runtime events в legacy автоматически.

Каждая новая engine activation должна оставлять предыдущий checkpoint/journal доступными для аудита.

## 21. Песни

- Одна песня = один полный UTF-8 файл, когда текст реально полный и проверен.
- `FULL_CANONICAL` только после обратного чтения полного файла.
- Потерянный/обрезанный текст не восстанавливать по оригиналу или памяти.

## 22. Нельзя

- считать legacy `live_state.json` текущим SAVE;
- редактировать подтверждённый journal event;
- обновлять pointer раньше успешного event;
- придумывать `UNKNOWN`;
- трактовать отсутствие именованного NPC как отсутствие всех людей;
- смешивать личные, семейные и проектные деньги;
- решать за Арлекино;
- давать NPC невозможные знания;
- раскрывать hidden Character Core/plan/autonomy/private memory как будто игрок это знает;
- создавать для одного commitment второй автономный таймер/очередь;
- заполнять Core выдуманными чертами, памятью, отношениями или имуществом;
- создавать NPC memory только потому, что игрок увидел NPC;
- превращать causal memory в эмоцию, consent, reply или relationship delta без отдельного основания;
- materialize named character как generic actor с фиктивными обязательными полями ради удобства схемы;
- auto-bind bare same-scene movement к видимому NPC без явного target;
- показывать repaired/cancelled historical pending как текущий pending в session read-model;
- строить session read-model через side-effecting GM telemetry path;
- генерировать произвольную NPC-реплику без authoritative response semantics;
- трактовать minimal reciprocal greeting как эмоцию, отношение, согласие или готовность продолжать разговор;
- ретроактивно разрешать старые NPC-response после установки новой response policy;
- превращать causal testimony в абсолютную истину;
- показывать техничку вместо игровой сцены без необходимости;
- пропускать обязательный HUD.
