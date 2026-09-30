# IGRIS — REAL TASK EXECUTION & REALITY VERIFICATION PLAN v1.0

> Maqsad: IGRIS agent'ning haqiqiy task execution va reality verification tizimini yaratish
> Prinsip: "Menimcha bajardim" emas — "Talab → bajarildi → real natija mavjud → natija tekshirildi → barcha talablar PASS"
> Sana: 2026-09-16
> Holat: REJA — boshlanmagan

---

## 0. ASOSIY ACCEPTANCE MODELI

Har bir task quyidagi lifecycle orqali o'tishi shart:

```text
USER REQUEST
    ↓
REQUIREMENTS
    ↓
GOAL PIN
    ↓
TASK PLAN
    ↓
EXECUTION
    ↓
OBSERVATION
    ↓
RESULT
    ↓
REALITY VERIFICATION
    ↓
REQUIREMENT VERIFICATION
    ↓
COMPLETION
```

### Vazifalar
- [ ] Task faqat LLM "done" degani bilan tugamasligini ta'minlash
- [ ] Tool `ok=true` natijasi task completion emasligini ta'minlash
- [ ] Real-world evidence mavjud bo'lmasa `COMPLETE` berilmasligini ta'minlash
- [ ] User requirement'lari bajarilmaguncha task tugamasligini ta'minlash
- [ ] Har bir completed task uchun verification evidence saqlash

### Implementation
1. Task lifecycle state machine yaratish
2. COMPLETE status faqat verification'dan keyin beriladi
3. Evidence mandatory: file content, process output, etc.

---

## 1. REAL TASK TEST ENVIRONMENT

### Vazifalar
- [ ] Alohida test workspace yaratish
- [ ] Test workspace ichida real fayllar yaratish
- [ ] Agentga real filesystem access berish
- [ ] Agentning workspace chegarasini tekshirish
- [ ] Task boshlanishidan oldin initial state snapshot olish
- [ ] Task tugagandan keyin final state snapshot olish
- [ ] Before/after state comparison yaratish
- [ ] Tashqi side-effectlarni qayd qilish

### Implementation
1. `test_workspace/` papka yaratish
2. Initial state: fayllar ro'yxati, hajmi, content hash
3. Final state: xuddi shu ma'lumotlar
4. Diff: qaysi fayllar o'zgargan, qaysilari yangi, qaysilari o'chgan

---

## 2. TASK REQUIREMENT EXTRACTION

```text
USER REQUEST
    ↓
REQUIREMENTS
    ├── mandatory
    ├── optional
    ├── constraints
    ├── output
    └── success criteria
```

### Vazifalar
- [ ] User request'dan explicit requirements ajratish
- [ ] Implicit requirements'ni ajratish
- [ ] Mandatory requirement'larni belgilash
- [ ] Optional requirement'larni belgilash
- [ ] Constraint'larni belgilash
- [ ] Expected output'ni belgilash
- [ ] Success criteria yaratish
- [ ] Requirement'larni immutable snapshot sifatida saqlash
- [ ] Task davomida requirement'lar yo'qolmasligini tekshirish
- [ ] Agent o'zicha requirement qo'shib yubormasligini tekshirish

### Implementation
1. Requirements JSON schema yaratish
2. Requirements task start'da immutable snapshot
3. Task davomida requirement'lar o'zgarmaydi

---

## 3. GOAL PIN INTEGRITY

### Vazifalar
- [ ] Original user goal'ni task ID bilan bog'lash
- [ ] Goal immutable ekanini test qilish
- [ ] Planner goalni o'zgartira olmasligini test qilish
- [ ] Executor goalni o'zgartira olmasligini test qilish
- [ ] Recovery goalni o'zgartira olmasligini test qilish
- [ ] Brain restart'dan keyin goal tiklanishini test qilish
- [ ] Resume'dan keyin aynan original goal ishlatilishini test qilish

### Implementation
1. Goal: immutable reference (task_id + original_text)
2. Goal ni hech qanday module o'zgartira olmaydi
3. Recovery: faqat original goal'dan qayta boshlaydi

---

## 4. REAL TASK DECOMPOSITION

### Vazifalar
- [ ] Oddiy taskni decomposition qilish
- [ ] Multi-step taskni decomposition qilish
- [ ] Dependency'larni aniqlash
- [ ] Task order'ni aniqlash
- [ ] Har bir subtask uchun success criteria yaratish
- [ ] Parent task va child task bog'lanishini tekshirish
- [ ] Child task completion parent completion emasligini tekshirish
- [ ] Barcha mandatory child tasklar tugamaguncha parent task complete bo'lmasligini test qilish

### Implementation
1. Task graph: parent → child → action
2. Dependency order: topological sort
3. Parent completion: ALL mandatory children PASS

---

## 5. REAL EXECUTION TESTS

### 5.1 File Creation

Task: `"test_workspace ichida report.txt yarat va ichiga IGRIS REAL TASK TEST yoz."`

- [ ] Agent fayl yaratadi
- [ ] Fayl haqiqatan mavjudligini tekshiradi
- [ ] Fayl nomini tekshiradi
- [ ] Fayl path'ini tekshiradi
- [ ] Fayl content'ini tekshiradi
- [ ] Content exact requirement bilan solishtiriladi
- [ ] Verification evidence saqlanadi
- [ ] Faqat shundan keyin COMPLETE

### 5.2 File Modification

Task: `"report.txt ichidagi TEST so'zini VERIFIED so'ziga almashtir."`

- [ ] Original file state olinadi
- [ ] Correct file tanlanadi
- [ ] Modification bajariladi
- [ ] File mavjudligi tekshiriladi
- [ ] Expected content mavjudligi tekshiriladi
- [ ] Eski content yo'qolganligi tekshiriladi
- [ ] Unrelated content o'zgarmaganligi tekshiriladi

### 5.3 Folder Organization

Task: `"test_workspace ichidagi .txt fayllarni txt_files papkasiga joylashtir."`

- [ ] Fayllar discovery qilinadi
- [ ] Target folder yaratiladi
- [ ] Files move qilinadi
- [ ] Source directory tekshiriladi
- [ ] Destination directory tekshiriladi
- [ ] Fayllar soni oldingi state bilan solishtiriladi
- [ ] Noto'g'ri fayllar ko'chirilmaganini tekshirish
- [ ] Duplicate paydo bo'lmaganini tekshirish

---

## 6. CODE EXECUTION TEST

Task: `"Python script yarat, uni ishga tushir va natijani result.txt ga yoz."`

- [ ] Script yaratiladi
- [ ] Syntax validation
- [ ] Script execution
- [ ] Process exit code tekshiriladi
- [ ] stdout tekshiriladi
- [ ] stderr tekshiriladi
- [ ] result.txt mavjudligi tekshiriladi
- [ ] result.txt content'i tekshiriladi
- [ ] Expected output bilan comparison
- [ ] Script haqiqatan ishlaganiga evidence saqlash

---

## 7. MULTI-STEP REAL TASK

Task: `"CSV faylni o'qi, jami qiymatni hisobla, natijani summary.txt ga yoz va faylni tekshir."`

- [ ] Input file topildi
- [ ] Input structure tekshirildi
- [ ] Data o'qildi
- [ ] Calculation bajarildi
- [ ] Calculation verification
- [ ] summary.txt yaratildi
- [ ] Content verification
- [ ] Expected result comparison
- [ ] Final state verification
- [ ] Task completion

---

## 8. BRAIN / PROCESS INTERRUPTION TEST

### 8.1 Brain kill

Task: `"10 bosqichli taskni bajar."`

- [ ] Task start qilinsin
- [ ] Checkpoint yaratilishi tekshirilsin
- [ ] Task o'rtasida brain/process majburiy to'xtatilsin
- [ ] Process kill qilinsin
- [ ] Runtime state diskda saqlanganini tekshirish
- [ ] Goal saqlanganini tekshirish
- [ ] Completed subtasks saqlanganini tekshirish
- [ ] Current subtask saqlanganini tekshirish
- [ ] Verification history saqlanganini tekshirish
- [ ] Recovery event saqlanganini tekshirish
- [ ] Agent qayta ishga tushirilsin
- [ ] State restore qilinsin
- [ ] Goal restore qilinsin
- [ ] Task resume qilinsin
- [ ] Oldingi completed action'lar qayta bajarilmasligini tekshirish
- [ ] Task qolgan qismdan davom etishini tekshirish
- [ ] Final result verification
- [ ] COMPLETE

---

## 9. RANDOM INTERRUPTION TEST

- [ ] Taskning turli bosqichlarida process kill qilish
- [ ] PLAN vaqtida kill
- [ ] EXECUTE vaqtida kill
- [ ] Tool call vaqtida kill
- [ ] OBSERVE vaqtida kill
- [ ] VERIFY vaqtida kill
- [ ] Recovery vaqtida kill
- [ ] Har bir holatdan resume qilish
- [ ] Duplicate side-effect'larni tekshirish
- [ ] Lost state'ni tekshirish
- [ ] Corrupted checkpoint'ni tekshirish

---

## 10. CHECKPOINT INTEGRITY

Har checkpoint quyidagilarni o'z ichiga olishi kerak:

```text
task_id
goal
requirements
current_state
completed_tasks
pending_tasks
current_task
current_action
world_state
verification_log
errors
recovery_events
memory_reference
timestamp
checkpoint_version
```

### Vazifalar
- [ ] Barcha critical state checkpoint'da mavjud
- [ ] Checkpoint atomic write qilinadi
- [ ] Partial checkpoint corruption protection
- [ ] Checkpoint versioning
- [ ] Latest valid checkpoint recovery
- [ ] Corrupted checkpoint detection
- [ ] Old checkpoint fallback
- [ ] Resume consistency test

---

## 11. DUPLICATE ACTION PROTECTION

Brain restart'dan keyin:

- [ ] File creation duplicate bo'lmasligi
- [ ] File move duplicate bo'lmasligi
- [ ] Command duplicate execution xavfi aniqlanishi
- [ ] API/action duplicate xavfi aniqlanishi
- [ ] Tool action ID ishlatilishi
- [ ] Idempotency imkon qadar ta'minlanishi
- [ ] Already-completed action detection
- [ ] Side-effecting action uchun pre-check

---

## 12. REALITY VERIFICATION

Agent quyidagini farqlashi shart:

```text
INTENTION    → "I will create the file"
ACTION       → "write_file() called"
TOOL RESULT  → "ok=true"
REALITY      → "file exists with expected content"
VERIFIED     → "requirements satisfied"
```

### Vazifalar
- [ ] Intention ≠ result
- [ ] Tool result ≠ reality
- [ ] Reality ≠ requirement satisfaction
- [ ] Requirement satisfaction ≠ full task completion agar boshqa requirementlar qolgan bo'lsa

---

## 13. FILE REALITY VERIFICATION

Har file operation uchun:

- [ ] Path exists
- [ ] Correct filename
- [ ] Correct extension
- [ ] Correct file type
- [ ] Correct size
- [ ] Correct content
- [ ] Correct encoding
- [ ] Expected structure
- [ ] No corruption
- [ ] No unexpected files
- [ ] No missing files

---

## 14. CODE REALITY VERIFICATION

Code task uchun:

- [ ] File exists
- [ ] Syntax valid
- [ ] Imports valid
- [ ] Program executes
- [ ] Exit code valid
- [ ] Expected output produced
- [ ] Error output absent yoki expected
- [ ] Output artifact exists
- [ ] Artifact content valid
- [ ] Requirements satisfied

---

## 15. RESEARCH TASK REALITY VERIFICATION

Task: `"3 ta manba top, ularni tahlil qil va summary.md yarat."`

- [ ] Sources actually accessed
- [ ] Source identity recorded
- [ ] Source content actually retrieved
- [ ] Claims linked to evidence
- [ ] Required number of sources mavjud
- [ ] Summary file exists
- [ ] Summary contains required sections
- [ ] No invented sources
- [ ] No unsupported claims
- [ ] Final document checked against requirements

---

## 16. DOCUMENT TASK REALITY VERIFICATION

Task: `"Word document yarat va 5 ta section qo'sh."`

- [ ] Document exists
- [ ] Correct format
- [ ] Correct filename
- [ ] Correct location
- [ ] 5 sections exist
- [ ] Section titles correct
- [ ] Content exists
- [ ] Formatting requirements satisfied
- [ ] Document opens successfully
- [ ] No corruption
- [ ] Final document re-read by verifier

---

## 17. REQUIREMENT-TO-RESULT VERIFICATION MATRIX

Har task oxirida:

```text
Requirement       Expected       Actual       Evidence       Status
-------------------------------------------------------------------
R1                ...            ...          ...             PASS
R2                ...            ...          ...             PASS
R3                ...            ...          ...             FAIL
```

### Vazifalar
- [ ] Har requirement uchun verification
- [ ] PASS/FAIL/UNKNOWN status
- [ ] Evidence reference
- [ ] Failed requirement COMPLETE'ni bloklashi
- [ ] UNKNOWN requirement COMPLETE'ni bloklashi
- [ ] Barcha mandatory requirements PASS bo'lmaguncha COMPLETE yo'q

---

## 18. INDEPENDENT VERIFIER

- [ ] Executor va verifier'ni ajratish
- [ ] Executor o'z ishini avtomatik "correct" deb belgilamasligi
- [ ] Verification mustaqil state'dan ishlashi
- [ ] Verification actual world state'dan foydalanishi
- [ ] Verification evidence talab qilishi
- [ ] Verification failure recovery'ga yuborishi
- [ ] Verifier ham xato qilishi mumkinligi uchun sanity checks

---

## 19. FALSE COMPLETION TESTS

Quyidagi holatlarda agent COMPLETE demasligi kerak:

- [ ] Tool `ok=true`, lekin file yo'q
- [ ] File mavjud, lekin content noto'g'ri
- [ ] Content to'g'ri, lekin noto'g'ri path
- [ ] Bir requirement bajarilmagan
- [ ] Verification ishlamagan
- [ ] Evidence mavjud emas
- [ ] Process timeout bo'lgan
- [ ] Brain restart bo'lgan va state noaniq
- [ ] Tool natijasi unknown
- [ ] External side-effect tasdiqlanmagan
- [ ] Expected output va actual output farq qiladi

---

## 20. FALSE FAILURE TESTS

Agent quyidagi holatlarda taskni noto'g'ri FAILED demasligi kerak:

- [ ] Temporary tool failure'dan keyin recovery mumkin
- [ ] Network retry mumkin
- [ ] Process restart'dan keyin resume mumkin
- [ ] One subtask failure boshqa independent subtasklarni bloklamaydi
- [ ] Existing artifact'dan resume qilish mumkin
- [ ] Partial progress saqlangan

---

## 21. BRAIN CRASH RECOVERY

- [ ] SIGTERM test
- [ ] SIGKILL test
- [ ] Process crash test
- [ ] Python exception test
- [ ] OOM simulation
- [ ] Tool process crash
- [ ] Ollama unavailable test
- [ ] Runtime restart test
- [ ] Machine restart simulation
- [ ] State recovery
- [ ] Goal recovery
- [ ] Task recovery
- [ ] World state recovery
- [ ] Verification recovery
- [ ] Final task verification

---

## 22. RESUME CORRECTNESS

Resume'dan keyin:

```text
OLD STATE → RESTORE → VALIDATE → RECONCILE WITH REAL WORLD → CONTINUE
```

### Vazifalar
- [ ] Checkpoint state restore
- [ ] Real filesystem bilan reconciliation
- [ ] Existing artifacts discovery
- [ ] State va reality conflict detection
- [ ] Conflict resolution
- [ ] Completed action detection
- [ ] Safe continuation
- [ ] Final verification

---

## 23. EXTERNAL REALITY RECONCILIATION

Brain o'chgan paytda tashqi dunyo o'zgarishi mumkin.

- [ ] Checkpoint state va real state solishtirish
- [ ] File o'chirilgan bo'lsa aniqlash
- [ ] File o'zgargan bo'lsa aniqlash
- [ ] Tool action tashqaridan bajarilgan bo'lsa aniqlash
- [ ] Unexpected changes aniqlash
- [ ] Stale checkpoint detection
- [ ] Re-plan zarur bo'lsa re-plan
- [ ] Goal saqlangan holda current state yangilanishi

---

## 24. LONG-RUNNING TASK

- [ ] 5+ step task
- [ ] 10+ step task
- [ ] 20+ step task
- [ ] 50+ step task
- [ ] Long task checkpoint frequency
- [ ] Memory growth
- [ ] Context growth
- [ ] State growth
- [ ] Loop stability
- [ ] Recovery
- [ ] Final verification

---

## 25. STRESS TEST

- [ ] Multiple consecutive tasks
- [ ] Long task
- [ ] Multiple tool failures
- [ ] Multiple retries
- [ ] Context pressure
- [ ] Memory pressure
- [ ] CPU pressure
- [ ] Ollama slow response
- [ ] Ollama unavailable
- [ ] Runtime restart
- [ ] Random interruption
- [ ] Recovery after interruption

---

## 26. END-TO-END ACCEPTANCE TEST

Kamida quyidagi real tasklarni boshidan oxirigacha bajarish:

- [ ] File creation
- [ ] File modification
- [ ] File organization
- [ ] Code generation + execution
- [ ] Multi-file task
- [ ] Data processing
- [ ] Research
- [ ] Document creation
- [ ] Long-running task
- [ ] Task cancellation
- [ ] Task resume
- [ ] Brain/process crash recovery
- [ ] Tool failure recovery
- [ ] Requirement failure detection
- [ ] False completion prevention

---

## 27. HAR BIR TEST UCHUN MAJBURIY TRACE

```text
TASK_ID
GOAL
REQUIREMENTS
INITIAL_WORLD_STATE
PLAN
STATE_TRANSITIONS
ACTIONS
TOOL_RESULTS
OBSERVATIONS
WORLD_STATE_CHANGES
VERIFICATIONS
ERRORS
RECOVERY_EVENTS
CHECKPOINTS
INTERRUPTIONS
RESUME_EVENTS
FINAL_WORLD_STATE
REQUIREMENT_MATRIX
COMPLETION_EVIDENCE
FINAL_STATUS
```

### Vazifalar
- [ ] Trace to'liq
- [ ] Timeline to'g'ri
- [ ] Har action parent task bilan bog'langan
- [ ] Har verification parent requirement bilan bog'langan
- [ ] Final status evidence bilan bog'langan

---

## 28. FINAL COMPLETION CONTRACT

Agent faqat quyidagi shartlarda `COMPLETE` qilishi mumkin:

```text
COMPLETE =
    Goal preserved
    AND All mandatory requirements PASS
    AND Real-world state verified
    AND Expected artifacts exist
    AND Expected content/state is correct
    AND No unresolved critical errors
    AND Verification evidence exists
```

Aks holda: `IN_PROGRESS | FAILED | PARTIAL | BLOCKED | UNKNOWN`

---

## 29. GOLDEN RULE

```text
THINKING        ≠  ACTION
ACTION          ≠  SUCCESS
SUCCESS         ≠  VERIFIED SUCCESS
VERIFIED SUCCESS =  REALITY + REQUIREMENTS + EVIDENCE
```

IGRIS uchun haqiqiy `COMPLETE` faqat:

**"Menimcha bajardim" emas,**

**"Talab → bajarildi → real natija mavjud → natija tekshirildi → barcha talablar PASS."**

---

## IMPLEMENTATION ORDER

### Phase 1: Foundation (1 hafta)
1. Requirement extraction system (Section 2)
2. Goal pin integrity (Section 3)
3. Task decomposition (Section 4)
4. Checkpoint system (Section 10)

### Phase 2: Reality Verification (1-2 hafta)
5. Reality verification core (Section 12)
6. File reality verification (Section 13)
7. Code reality verification (Section 14)
8. Independent verifier (Section 18)
9. Requirement-to-result matrix (Section 17)

### Phase 3: Recovery & Resume (1 hafta)
10. Crash recovery (Section 21)
11. Resume correctness (Section 22)
12. External reality reconciliation (Section 23)
13. Duplicate action protection (Section 11)

### Phase 4: Tests (1-2 hafta)
14. Real execution tests (Section 5)
15. Code execution test (Section 6)
16. Multi-step task test (Section 7)
17. Interruption tests (Section 8-9)
18. False completion tests (Section 19)
19. False failure tests (Section 20)

### Phase 5: Stress & E2E (1 hafta)
20. Long-running tasks (Section 24)
21. Stress tests (Section 25)
22. E2E acceptance tests (Section 26)
23. Trace system (Section 27)

### Phase 6: Final Audit (3 kun)
24. Final completion contract (Section 28)
25. Golden rule validation (Section 29)
26. Documentation

---

## ESTIMATED DURATION: 5-7 HAFTA

---

## KEY PRINCIPLES

1. **Evidence Mandatory**: Evidence'siz COMPLETE taqiqlanadi
2. **Independent Verifier**: Executor va verifier ajratilgan
3. **Goal Immutable**: Original goal hech qachon o'zgarmaydi
4. **Checkpoint Atomic**: Checkpoint to'liq yoki yo'q
5. **Resume Safe**: Resume real world bilan reconcile qilinadi
6. **False Completion Blocked**: Tool ok=true ≠ task complete
7. **Duplicate Protected**: Restart'dan keyin duplicate action yo'q
8. **Real World is Source of Truth**: Checkpoint emas, real state

---

*Bu reja IGRIS agent'ning real task execution va reality verification tizimini yaratish uchun asos bo'ladi.*
