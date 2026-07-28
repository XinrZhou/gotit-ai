# Design — resume-driven drill

## Approach

三件事并行推进：①简历上传→解析→应用（项目库由简历产生）②深挖资料 CRUD ③模拟面试 session（简历级，可选聚焦项目，分轮次/方向）。文本提取与结构化解析在 `core/resume/`（framework-free），结构化解析复用 **Compass（海绵宝宝）人格**。Sage（桑迪）改造为消费简历+资料+轮次的面试官。REST 与 MCP 共享 `core` + `db.ops`，保持 Iron Law #4。

### 解析分层（沿用原方案）

```
上传文件 (multipart / 文件路径)
  ↓
core/resume/extract.py   — 文本提取（pypdf / python-docx / 直读）→ 纯文本
  ↓
core/resume/parse.py     — Compass 扩展（海绵宝宝人格）→ ResumeDocument{basics, projects[]}
  ↓
预览编辑（前端可改）
  ↓
db.ops.apply_resume()    — 按名称智能合并项目 + 每项目一条 note（默认不 ingest）
```

**为什么两阶段**：文本提取是确定性 IO（库），结构化是概率性推理（LLM）。分开后可独立测试：提取层用 fixture 单测，解析层用 LLM bypass stub 测。

**为什么三阶段交互**：LLM 解析有误差，必须让用户确认/编辑再落库，避免脏数据进 Project 表。

**为什么 Compass 兼任**：Compass（海绵宝宝）的职责是「把资料变成考点」，简历解析也是「把简历变成项目」，同一职责的两种输入形态。复用 Compass 人格避免新增第五个 agent，保持四角稳定。解析 prompt 在 `prompts/resume.md`。

## 数据模型

### `core/models.py` 新增

```python
class ResumeBasics(BaseModel):
    name: str | None = None
    target_role: str | None = None

class ResumeProject(BaseModel):
    name: str
    role: str | None = None
    goal: str | None = None
    tech_stack: list[str] = []
    description: str               # 存进 note.body

class ResumeDocument(BaseModel):
    basics: ResumeBasics
    projects: list[ResumeProject]

class ResumeRecord(BaseModel):
    """落库的简历记录（全局一份）。"""
    id: UUID
    upload_id: UUID
    file_path: str
    document: ResumeDocument
    created_at: datetime

class ResumeParseOutput(BaseModel):
    upload_id: UUID
    document: ResumeDocument

class DrillMaterial(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: str
    title: str
    body: str
    created_at: datetime
    updated_at: datetime

class DrillRound(StrEnum):
    TECH_1 = "tech_1"   # 技术一面：基础 + 项目梳理，偏广度
    TECH_2 = "tech_2"   # 技术二面：深度追问 + 系统设计
    TECH_3 = "tech_3"   # 技术三面：架构 / 跨项目
    TECH_4 = "tech_4"   # 技术四面：资深 / 终面技术
    HR = "hr"           # HR 面：行为面 / 职业规划

class DrillSession(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: str
    resume_id: UUID
    round: DrillRound
    direction: str | None = None     # 自由文本，如「偏架构」
    project_id: UUID | None = None   # 可选聚焦某项目；None = 简历级
    status: str = "active"            # active | done
    started_at: datetime
    ended_at: datetime | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)  # [{role, text}]

class SageVerdict(BaseModel):   # 扩展现有
    done: bool
    depth_reached: int = 0
    gaps: list[str] = Field(default_factory=list)
    follow_up: str | None = None
    round: DrillRound | None = None   # 新增：回显轮次，便于前端展示
```

### Postgres 新表（Alembic 0004）

```sql
-- resumes：全局一份（user_id 唯一约束 → 再上传覆盖）
CREATE TABLE resumes (
  id UUID PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL UNIQUE,
  upload_id UUID NOT NULL,
  file_path TEXT NOT NULL,
  document JSONB NOT NULL,          -- ResumeDocument
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- drill_materials：全局多份深挖资料
CREATE TABLE drill_materials (
  id UUID PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL,
  title VARCHAR(500) NOT NULL,
  body TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_drill_materials_user ON drill_materials(user_id);

-- drill_sessions：模拟面试 session
CREATE TABLE drill_sessions (
  id UUID PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL,
  resume_id UUID NOT NULL REFERENCES resumes(id),
  round VARCHAR(16) NOT NULL,
  direction TEXT,
  project_id UUID REFERENCES projects(id),
  status VARCHAR(16) NOT NULL DEFAULT 'active',
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at TIMESTAMPTZ,
  messages JSONB NOT NULL DEFAULT '[]'
);
CREATE INDEX ix_drill_sessions_user ON drill_sessions(user_id);
```

**为什么 resumes 用 user_id UNIQUE**：全局一份，再上传覆盖（apply 时新简历替换旧记录；旧项目按名称合并，已有 claim/笔记的 project_id 不变）。

**为什么 messages 用 JSONB 不拆表**：M0 单机、消息量小（一个 session 几十轮），JSONB 简单且读写一次到位；后续若要跨 session 分析再拆 `drill_messages` 表。

## 简历应用：清空重建

`db.ops.apply_resume(session, document, *, ingest=False, user_id)`：

```
# 1. 清空旧项目库 + 旧简历笔记
old_projects = list_projects(user_id, include_archived=True)
# 删除 tags 含 "resume" 的笔记（简历派生，非用户手写）
delete_notes(tags_contains="resume")
# 用户手写笔记/claim/计划项的 project_id 置空（脱离已删项目，保留学习数据）
detach_project_refs(old_project_ids=old_projects)
# 删除所有旧项目
delete_projects(old_projects)
# 2. 重建
upsert_resume(user_id, upload_id, file_path, document)   # 覆盖全局简历记录
for pp in document.projects:
    p = create_project(name=pp.name, role=pp.role, goal=pp.goal, tech_stack=pp.tech_stack)
    note = add_note(day=today, body=pp.description, title=pp.name, project_id=p.id, tags=["resume"])
    if ingest: ingest_note(note.id, claims=None)
```

**为什么清空重建而非合并**：用户明确选择再上传即清空重建——简历版本切换时项目库完全跟随新简历，避免旧项目残留造成混乱。用户手写笔记/claim 是学习数据（Iron Law #1），不删除，仅置空 `project_id` 脱离已删项目；后续用户可重新关联到新项目。

**为什么删简历笔记而非归档**：简历笔记（`tags` 含 `resume`）是解析派生数据，非用户手写，随项目库一起重建；保留会造成重复。

## Sage（桑迪）改造

`core/agents/sage.py` 的 `build_prompt` 改为消费简历 + 资料 + 轮次 + 方向：

```python
def build_prompt(
    *,
    resume: ResumeDocument,            # 简历（项目库 + basics）
    materials: list[DrillMaterial],     # 深挖资料
    project: Project | None,            # 可选聚焦
    round_: DrillRound,
    direction: str | None,
    history: list[dict[str, str]],
    answer: str | None,
    memory: list[MemoryEntry],
) -> str:
    ...
```

`run_sage` 签名相应调整，新增 `resume / materials / round_ / direction` 参数。`prompts/sage.md` 加轮次分档：

- **技术轮（tech_1~4）**：沿用 drill ladder（tech choice → why → scale 100x → failure mode → metrics），轮次越高追问越深、越偏架构/跨项目
  - tech_1：偏广度，先把项目讲清楚
  - tech_2：深度追问 + 系统设计
  - tech_3：架构 / 跨项目权衡
  - tech_4：资深终面，偏技术领导力 / 取舍
- **HR 轮（hr）**：行为面（STAR）+ 职业规划 + 软技能，不追问技术细节
- **direction**：作为额外 hint 注入（如「偏架构」→ 多问架构取舍）

无 `LLM_API_KEY` 时 stub bypass：首轮返回开场白（按轮次生成），有 answer 时返回 done=true + 占位 gaps。

## REST ↔ MCP parity

| REST | MCP | 说明 |
|------|-----|------|
| `POST /v1/resumes/upload`（multipart） | `gotit_upload_resume(file_path: str)` | MCP 接受文件路径（或 `content_b64`+`content_type`），复用 extract + parse |
| `POST /v1/resumes/apply` | `gotit_apply_resume(upload_id, document, ingest=false)` | 完全对等 |
| `GET /v1/resumes` | `gotit_get_resume` | 取当前简历 |
| `GET /v1/drill/materials` | `gotit_list_drill_materials` | 列资料 |
| `POST /v1/drill/materials` | `gotit_upsert_drill_material(id?, title, body)` | 新建/更新（有 id 更新） |
| `PATCH /v1/drill/materials/{id}` | （同 upsert） | 更新 |
| `DELETE /v1/drill/materials/{id}` | `gotit_delete_drill_material(id)` | 删除 |
| `POST /v1/drill/sessions` | `gotit_start_drill_session(round, direction?, project_id?)` | 开 session，返回 session + 首轮 verdict |
| `POST /v1/drill/sessions/{id}` | `gotit_continue_drill_session(session_id, answer)` | 继续追问 |
| `GET /v1/drill/sessions` | `gotit_list_drill_sessions` | session 列表 |
| `GET /v1/drill/sessions/{id}` | `gotit_get_drill_session(id)` | 含消息 |

**移除**：`POST /v1/projects`（手动新建）、`POST /v1/projects/{id}/drill`（被 session 取代）。保留 `GET /v1/projects`、`GET/PATCH /v1/projects/{id}`、`GET /v1/projects/{id}/progress`。

## 前端改动

- **DrillPage 重设计**（`pages/DrillPage/`）：
  - 顶部：简历状态（已导入/未导入）+ 上传入口 + 资料管理入口
  - 无 session 时：简历未导入 → 引导上传；已导入 → 显示「新建 session」面板（轮次选择 5 段 + 方向输入框 + 可选项目聚焦下拉）+ 历史 session 列表
  - session 激活：ChatLog + Composer（沿用现有组件）
- **简历上传**：复用「添加资料」modal 的「文件」tab → 上传 → 解析预览（项目列表可编辑）→ 二次确认（已有简历时）→ apply
- **资料管理**：新增 modal/抽屉，列表 + 新建/编辑/删除（title + body 富文本）
- **项目库降级**：侧栏项目 chip 仍保留（active 项目），点击 = 在 DrillPage 新建 session 时预填聚焦项目；项目 chip 区移除 `+` 新建按钮
- **移除**：手动新建项目 modal
- **project_id 串联**：`onSaveNote` / `onGotItMaterial` 传 `selectedProjectId`；侧栏项目 chip 筛选 notes

## 目录结构

```
src/gotit/
  core/
    resume/
      __init__.py
      extract.py        # extract_text(content, content_type) -> str
      parse.py          # build_resume_parser + run_resume_parser + ResumeDocument（Compass 扩展）
    models.py          # 加 ResumeBasics/ResumeProject/ResumeDocument/ResumeRecord/
                       #    ResumeParseOutput/DrillMaterial/DrillRound/DrillSession；扩展 SageVerdict
    agents/
      sage.py          # build_prompt / run_sage 改签名（消费 resume+materials+round+direction）
  api/
    routes.py          # 加 resumes/* + drill/materials + drill/sessions；移除 POST /v1/projects、
                       #    POST /v1/projects/{id}/drill
  mcp/
    server.py          # 加 8 个 drill/resume MCP 工具
  db/
    models.py          # 加 ResumeRow/DrillMaterialRow/DrillSessionRow
    ops.py             # 加 apply_resume / upsert_resume / get_resume /
                       #    list_drill_materials / upsert_drill_material / delete_drill_material /
                       #    create_drill_session / continue_drill_session / list_drill_sessions / get_drill_session
alembic/versions/
  0004_resume_drill.py # resumes + drill_materials + drill_sessions
prompts/
  resume.md            # ResumeParser（海绵宝宝人格 + 简历抽取契约）
  sage.md              # 加轮次分档 + direction hint
uploads/               # gitignore
tests/
  test_resume.py       # extract + parse stub + apply（含覆盖合并）e2e
  test_drill.py        # materials CRUD + session e2e + stub bypass
  fixtures/sample.txt
web/src/
  pages/DrillPage/     # 重设计
  components/ResumeUploadModal/  # 上传+预览+确认
  components/DrillMaterialModal/ # 资料管理
  components/SessionStartPanel/  # 轮次/方向/聚焦
  store.tsx            # drill sessions / materials / resume 状态
  api.ts               # 新端点
.gitignore             # 加 uploads/
pyproject.toml         # 加 pypdf, python-docx
```

## Risks

- **LLM 解析质量**：简历格式千差万别，可能漏抽/误抽项目。缓解：三阶段交互让用户确认/编辑；prompt 给 few-shot；后续加 harness case 评估解析质量
- **覆盖上传清空重建**：再上传新简历时旧项目 + 旧简历笔记被删除，用户手写笔记/claim 的 `project_id` 置空保留（脱离已删项目）。缓解：用户手写学习数据不丢失，仅需重新关联到新项目；前端二次确认避免误操作
- **PDF 文本提取失败**：扫描版 PDF 提不出文本。缓解：明确报错提示换可复制文本的简历，M0 不接 OCR
- **文件安全**：上传文件可能含恶意内容。缓解：M0 限制大小（10MB）、限制扩展名、只读不执行、`uploads/` 不在 web 静态目录
- **MCP multipart 限制**：MCP stdio 不支持 multipart，`gotit_upload_resume` 接受文件路径或 base64，OpenClaw 侧负责下载
- **session messages JSONB 增长**：超长 session 的 messages 会变大。缓解：M0 单机可接受；后续可拆表或截断历史
- **轮次 prompt 调优**：5 个轮次的人格分档需要迭代。缓解：prompt 版本化（已有 prompt_versions 表）+ harness case 评估
- **移除手动新建的回退**：用户想加临时主题时无手动入口。缓解：可上传只含一段描述的 .txt 作为「单项目简历」
