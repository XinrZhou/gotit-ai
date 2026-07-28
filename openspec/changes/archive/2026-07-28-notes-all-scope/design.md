# Design — notes-all-scope

## 数据

`DayNoteView` 加 `day: date`，`_note_view` 从 `note.learning_day.day` 填充（list_notes 已有 learning_day 关系；list_all_notes 需 join/select learning_day）。

## 后端

### list_all_notes

```python
select(DayNoteRow).join(LearningDayRow).where(
    LearningDayRow.user_id == user_id
).order_by(DayNoteRow.created_at.desc())
```
每条用 `_note_view` 返回（带 day）。需要 `_note_view` 能取到 day：通过 relationship `note.learning_day.day`。

### 路由

`GET /v1/notes` → `list_all_notes(user_id)`，返回 `list[DayNoteView]`。

## 前端

- store：
  - `noteScope: "today" | "all"`，`setNoteScope`
  - `allNotes: DayNote[]`，scope=all 时 `refresh` 也拉 `/v1/notes`
  - 暴露的 `notes` 不变（侧栏/考我用同一个 `notes`），但内部根据 scope 切换数据源：today→今日 notes，all→allNotes
- 侧栏：
  - 资料区标题行加「今日 / 全部」小切换（segmented）
  - all 模式下每条 noteTitle 前加日期小字（如 `7.25`）
- 考我页：用 store 的 `notes`（已 scope 感知），无需改

## Risks

- 全部模式下笔记多 → 暂不分页，个人用量可接受，后续加搜索
- day 字段加到 DTO → 旧消费方兼容（新字段，可选无影响）
