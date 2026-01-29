# HarborPilot

HarborPilot һס**PM 滮  Director ִ  QA У  Dashboard ӻ**ԶűĿ  
Ĭ **PM  Codex****Director ñ Ollamaʡɱ**ֶ֧ profile ʾģ廯

---

## 1. һ

- **PM Loopɣ**
  - ȡ requirements / plan /  / ֽ
  - ṹ `PM_TASKS.json`
  - ¼Ի¼handoff
- **Director Loopִ QA**
  -  PM   Planner ƻ  ִб  QA 
  -  `DIRECTOR_RESULT.json``QA_RESPONSE.md`
  - ѡ Gap Review ɨ `docs/` 
- **Memory䣩**
  - `last_state.json`գժҪ/һ
  - ֧ **LanceDB** ־ü䣨Ĭ `--memory-backend lancedb`
- **Dialogue˻Ի**
  - JSONL ¼֧˳/ȥ/طţ
  - UI ۵鿴 phase / task_id 
- **Dashboardӻ壩**
  - ֻչʾ־Ի״̬ļ
  - һ/ֹͣ PM  Director
- **Prompt ģ廯**
  - ʾ JSON ģ + profile л
  - Ĭ demo`demo_ming_armada`

---

## 2. ĬϺģ

- **PMCodex CLI**
  - Ĭ `--pm-backend codex`
  - ڸ
- **DirectorOllama CLI**
  - Ĭģͣ`modelscope.cn/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:latest`
  - ִк QA

---

## 3. Ŀ¼ṹ

```
harborpilot/
  loops/
    loop-pm.py
    loop-director.py
  modules/harborpilot-loop/
    io_utils.py          # · / IO /  / Dialogue / ߼
    prompts.py           # Prompt װļȡ
    prompt_loader.py     # JSON ģȾ
    decision.py          # PM/Director ѡ߼
    ports.py             # ˿ڼ
    codex_utils.py       # Codex CLI 
    ollama_utils.py      # Ollama CLI 
    shared.py            # ߣıȣ
  ui/
    pm-dashboard.py
  prompts/
    demo_ming_armada.json
    generic.json
  state/ollama/
    # Ĭвд workspace
```

---

## 4. Workspace 

HarborPilot  **workspace  `docs/`**

### ĬΪ
- **Dashboard**ӵǰĿ¼ϲ `docs/`ΪĬ workspace
- **CLI**ͬϲ `docs/`Ҳᱨ˳

### Ϊʲô docs/
PM/Director ʾĬ `docs/`Gap Review Ҳɨ `docs/` ɴ١

---

## 5. зʽDashboard + CLI

### DashboardƼ
```
python ui/pm-dashboard.py
```
ڽã
- Workspace
- PM Backendcodex/ollama
- ModelOllama ã
- Prompt profile
- ೬ʱ/ˢ¼

### CLI ʾ
```
# PMĬ Codex
python loops/loop-pm.py --workspace <REPO>

# PM  Ollamaʡɱ
python loops/loop-pm.py --workspace <REPO> --pm-backend ollama

# DirectorĬ Ollama
python loops/loop-director.py --workspace <REPO> --iterations 1
```

---

## 6. вĬ·

д workspace µ `state/ollama/`

- `PLAN.md`ƻݰ
- `PM_TASKS.json`PM Լ
- `PM_REPORT.md`PM ־
- `DIRECTOR_RESULT.json`Director 
- `QA_RESPONSE.md`QA ˽
- `REVIEW_RESPONSE.md`Reviewer 
- `DIALOGUE.jsonl`Ի¼
- `events.jsonl`?Action/Observation ???
- `memory/last_state.json`
- `GAP_REPORT.md`Gap Review 

---

## 7. Prompt ģ profile л

ʾģ `prompts/`Ĭ profile Ϊ `demo_ming_armada`

```
python loops/loop-pm.py --workspace <REPO> --prompt-profile generic
python loops/loop-director.py --workspace <REPO> --prompt-profile generic
```

```
set HARBORPILOT_PROMPT_PROFILE=generic
```

---

## 8. PM Loop ؼ

1. ȡrequirements / plan / gap / QA /  / memory  
2. `PM_TASKS.json`  
3. дԻ¼handoff  
4. ѡ Director ִ  

ò
- `--pm-backend codex|ollama`
- `--requirements-path docs/product/requirements.md`
- `--run-director`Զ Director

䣺
- `PM_TASKS` ɰ `required_evidence`ǿ Director ȶָļ/Χ/ţʺʧܾƫ

---

## 9. Director Loop ؼ

1. ȡ `PM_TASKS.json`
2. Tool Planner ȡ֤repo_* λƬ
3. Patch Planner ִмƻ
4. ִиĶ  д `OLLAMA_RESPONSE.md`
5. Reviewer 󣨿ѡ д `REVIEW_RESPONSE.md`
6. QA   д `QA_RESPONSE.md`
7.  `DIRECTOR_RESULT.json`
8.  `memory/last_state.json`

ò
- `--model <ollama-model>`
- `--memory-backend lancedb|file|none`
- `--gap-review / --no-gap-review`
- `--gap-write-plan / --no-gap-write-plan`

---

## 10. Dialogue ¼ṹ

ÿ¼¼д `state/ollama/DIALOGUE.jsonl`ֶΣ
- `timestamp` / `ts_epoch`
- `seq`
- `event_id`uuid
- `speaker`PM / Director / QA / System
- `type`handoff / receipt / say / done ȣ
- `refs.task_id` / `refs.phase`

Dashboard ȡʾⲢ

---

## 10.1 Events ¼

ڡAction/Observation׼¼¼ߵáдQA/Reviewer ִʵ
- ·`state/ollama/events.jsonl`
- ÿ¼ `kind`action/observation`actor``name``refs`run/task/phase
- Observation  `ok/output/truncation/duration_ms`

;طš⡢ѹtrajectory 

---

## 11. ɫЭ˵Director ࣩ

Director Ƕ̡Э**ʾģɫӽ**  
ɫ `prompts/*.json` ģ壺
- `demo_ming_armada.json`Creative Director / ProducerGame DesignerUI DesignerGame Engineer
- `generic.json`ͨýɫ

ģ滻ΪԼŶӽṹƷ//ǰ/ԣ

---

## 12. ϵͳ˵

- `memory/last_state.json`  ****ֻӦժҪ/һ  
  **** ǻ۸ PM ͬĿꡣ  
- `--memory-backend lancedb` Ὣڼд LanceDB

---

## 13. 

裺
- Python 3.10+
- **Codex CLI**PM Ĭϣ
- **Ollama CLI**Director Ĭϣ

ѡ
- `flet`Dashboard
- `psutil`˿ڼ׼ȷ
- `lancedb`ڼ䣩

---

## 14. 

**Q: Ҳ docs/**  
A: CLI ֱӱ˳ȷ workspace Ŀ¼ `docs/`

**Q: PM ̫ȫ Ollama **  
A: ԣֱӼ `--pm-backend ollama`

**Q: Director Ҫģͣ**  
A: `--model <ollama-model>` ɸĬģ͡

---

## 15. Ʊ߽磨Ҫ

- ****PM ԼPM_TASKS
- **ִ**Director ϸִкԼ
- **չʾ**Dashboard ֻ

ñ߽ȷϵͳȶά

---

## 16. PM п״̬ļ䣩

- **ѭ**`--loop``--interval``--max-iterations`
- **/ֹͣ**`--stop-on-failure``--max-failures``--max-blocked``--max-same-task`
- **ֹͣ**PM  `state/ollama/PM_STOP.flag` Dashboard ťֶֹͣѭ
- **״̬¼**`PM_STATE.json`  `consecutive_failures` / `consecutive_blocked` / `same_task_count` / `force_switch`
- **־**`PM_LOG.jsonl``PM_TASK_HISTORY.jsonl``PM_LAST_RESPONSE.md`Codex
- **PM  Director**`--run-director` + `--director-*` + `--director-result-timeout`

---

## 17. Director ߼䣩

- ****`--iterations` / `--forever` / `--delay-seconds`
- **Auto Repair**`--auto-repair` + `--repair-rounds`QA ʧܻᰴԶ
  - `--max-repair-attempts` Ϊ `--repair-rounds` ı
- **ݴ**`--continue-on-error`ȱ brief / file list ʱжѭ
- **NPM ִ**`--run-npm` / `--npm-timeout`
  - ִֻ `npm ...` ᱻˣ
- **Ĭ QA **`--default-tools` / `--no-default-tools`
  - Ĭãruff  mypy  pytest Patch Planner δ tool_commands ʱ
- **Reviewer 󣨿ѡ**`--reviewer` / `--no-reviewer`
  - `--reviewer-rounds` ޴
  - `--reviewer-response-path` ָļ
- **ع**`--rollback-on-fail` / `--no-rollback-on-fail`
  - QA ʧܻǰԶعֻߣ⡰ԽԽá
- ****Զ¼ `DIRECTOR_RESULT.json`  `patch_risk`
- **ſ**`--risk-block-threshold`
  -  `patch_risk.score >= threshold` ʱֱִֹУ0 ʾرգ
- **ȡ֤**`--evidence-verbosity summary|full`
- **RAG **`--rag-topk`
- ** PM ʱԶѡĿ**`--auto-pick-target`
  -  `PLAN.md`  `Backlog A/B` ѯѡȡ
- **Gap Review չ**
  - `--gap-review` / `--gap-max-headings` / `--gap-max-files`
  - ɽժҪд `PLAN.md` `<!-- GAP_REPORT:BEGIN -->` ڣ
- **·Զ**`--pm-task-path` / `--dialogue-path` / `--planner-response-path` 
  - ¼`--events-path`Ĭ `state/ollama/events.jsonl`

---

## 17.1 Director Policy

Ĭ policy ļ·
`state/ollama/director_policy.json`

 CLI ǣ
`--policy-path <path>`

ֿṩһʼģ壨ͬ·ֱ޸ģ

֧񼶸ǣPM_TASKS.json
```
{
  "policy_overrides": {
    "repair": {"max_attempts": 2},
    "risk": {"block_threshold": 6}
  }
}
```
ҲԷھ task ڣ
  ```
  {"tasks":[{"policy_overrides": {...}}]}
  ```

  memory ãpolicy  `memory`ʾ
  ```
  {
    "memory": {
      "enabled": true,
      "backend": "lancedb",
      "store_enabled": true,
      "store_every": 1,
      "store_on_accept": false
    }
  }
  ```
  - `backend`: `lancedb|file|both|none`
  - `store_every`: N дһΣڽƵд룩
  - `store_on_accept`:  QA ͨʱд

ȼӸߵͣ
1) CLI   
2) PM_TASKS.json.policy_overrides  
3) policy ļ  
4)   
5) Ĭֵ

DIRECTOR_RESULT.json ¼
- `policy_effective`ϲ policy
- `policy_sources`ÿֶεԴ

---

## 18. ˿ڲ밲ȫ䣩

- ض˿ڣ`3180/3181/3182/3183/6379`
- `--port-policy auto|switch|none`
  - auto/switch ᳢Խ˿
  -  Physics ˿ڻ `PHYSICS_PORT` / `VITE_PHYSICS_WS` 
- `--kill-on-port-conflict`ҪʱԶռö˿ڽ
- ʾлע˿״̬ժҪظ

---

## 19. ־鵵䣩

- Director ļ
  - `PLANNER_RESPONSE.md` / `OLLAMA_RESPONSE.md` / `REVIEW_RESPONSE.md` / `RUNLOG.md`
- PM ÿֹ鵵
  - `state/ollama/runs/pm-00001/` Զ鵵
- ȡ֤
  - `state/ollama/evidence/EVIDENCE_<task_id>_<iter>.json`ToolPlanner ȡ֤ժҪ
- Dashboard ֶ֧Իȡ־תʱԶͷָ

---

## 20. Prompt Ⱦϸڣ䣩

- JSON ģ֧ `{{placeholder}}` 滻
- `plan_template`  `PLAN.md` ʱԶ

---

## 21. 嵥Ѱװ

 `嵥.rm`а ruff/pytest/coverage/mypy/pydantic/jsonschema/tree_sitter/tree_sitter_languages/rich ;뽨顣

## 22. Tools CLI

 `tools.py`ṩͳһڣ Director/ã
```
python tools.py list
python tools.py ruff_check -- .
python tools.py ruff_format -- .
python tools.py pytest -- -q
python tools.py coverage_run
python tools.py coverage_report
python tools.py mypy -- .
python tools.py jsonschema_validate -- schema.json data.json
python tools.py pydantic_validate -- module:ModelClass data.json
python tools.py treesitter_outline -- typescript path/to/file.ts
python tools.py treesitter_find_symbol -- python path/to/file.py MyClass
python tools.py treesitter_replace_node -- python path/to/file.py MyClass.my_method "..."
python tools.py pytest_target -- tests/test_api.py::test_case
python tools.py python_run -- scripts/repro.py --arg value
python tools.py node_run -- scripts/repro.mjs --arg value
python tools.py repo_symbols_index -- . --max-files 200
python tools.py repo_import_graph -- . --max-files 200
python tools.py repo_api_surface -- . --max-files 200
python tools.py lancedb_index_code -- . --max-files 200
python tools.py lancedb_query_code -- "query text"
python tools.py policy_validate -- state/ollama/director_policy.json
```

˵ڲԶִзעṤߣṩЩߺͳһðװ
⣬Director  Planner / QA ʾѰ `tools.py` ĵøʽ˵ prompts ģ壩
ߵ÷ࣺ
- Tool Planner ׶λԶ repo_* ڶλƬȡ
- ֻ Planner/ Patch Planner ȷ `tool_commands` ʱŻִС
  -  Patch Planner δ `tool_commands`ԶִĬ QA  `--no-default-tools` رգ

## 23. Repo-IO ߣ

ڡȶλ  ƬĶĸЧϢȡ
```
python tools.py repo_tree -- . --depth 3
python tools.py repo_rg -- "pattern" -- path1 path2 --max 50
python tools.py repo_read_around -- path/to/file.py 120 80
python tools.py repo_read_slice -- path/to/file.py 980 1080
python tools.py repo_read_head -- path/to/file.py 60
python tools.py repo_read_tail -- path/to/file.py 60
python tools.py repo_diff -- --stat
```
˵кţֽ֧ض·ƣʺģ͡ٶ
Director  Tool Planner ׶Զ repo_* ߣι Patch Planner پǷ֡
Ƽ̣repo_tree  repo_rg  repo_read_around  (repo_read_head/tail)  ٶ֡

## 24. Tree-sitter ṹдߣ

ڡ﷨޸ģַģ
```
python tools.py treesitter_find_symbol -- python path/to/file.py ClassName
python tools.py treesitter_replace_node -- python path/to/file.py ClassName.method "new body..."
python tools.py treesitter_insert_method -- python path/to/file.py ClassName "def new_method(...): ..."
python tools.py treesitter_rename_symbol -- python path/to/file.py OldName NewName
```
˵ `treesitter_find_symbol` λΧٽ滻//ȶԸڴַ༭

## 25. Repo  /  RAG

ڸ춨λڡ֪ʶ⡱
```
python tools.py repo_symbols_index -- . --max-files 200
python tools.py repo_import_graph -- . --max-files 200
python tools.py repo_api_surface -- . --max-files 200
python tools.py lancedb_index_code -- . --max-files 200
python tools.py lancedb_query_code -- "where is parse_planner_payload?"
```
˵
- `repo_*` ߿ɷ// API ʺģ͡Ķ
- `lancedb_*` ǿѡı RAG  `lancedb`ڳڼ


---

## 26. ????????????Reality?Driven Architecture?

?????????????? / ???? / ????????????????????????

- ???????????????? Codex?PM ???????????????????? Ollama
- ???? / ?? / ?? / policy ????????????????????
- ???? IO?repo ???JSONL ?? flush??? tail??????????? IO ????
- ???? workspace???? Docker ????????????????
- ??????????????????????????

If a feature is rarely used, hard to reason about, or adds complexity without daily value, it does not belong here.

---

## 27. ???????????????????

?????????????????????

- **??????**?? Codex ?????????? PM/Director ?????
- **????**???????<16GB????? IO ??????
- **?????**????????/??????? CI ?????????????
- **????**??????????????????????????????
- **??????**???????/?????????? gap review ? prompt ????

---

## 28. ???????????????

??????????????????????

- ??????????? / ????? / ????
- ??????????????????????
- ??????????????????
- ??????? / ?? / policy ?????????
- ??????????PM_TASKS / DIRECTOR_RESULT / workspace?

??????????????????????????
