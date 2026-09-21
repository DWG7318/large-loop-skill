# Graph Loop Skill（GLK）

当前版本：**4.0.0**

GLK是面向大型工程Run的Graph型Loop Engineering方法。它把一个Run设计为多个起点、由真实成果依赖连接的Node DAG；每个Node是一组使用本Run固定最新SLK基线的完整SLK Runs。

```text
多个起点Node
    -> 按依赖即时启动Node内的SLK Runs
    -> 一个Fusion Node
    -> 一次最终D2
    -> Run完成
```

## 核心边界

- 一个Graph就是一个Run，每个节点使用`Node001`一类数字身份，并包含一个或多个SLK Runs。
- Node在全部直接前提存在后启动；所有汇合使用`ALL`，无关工作不互相等待。
- 一个GLK Supervisor负责Graph设计、Node路由、Fusion和最终D2；每个SLK仍有自己的Supervisor、Checker与Worker。
- GLK不复制SLK的CELL、D0、D1、D2、返工、通讯、记录或模型指导。
- 正常施工最后只有一个Fusion Node；预建的条件D2 Repair Node只在最终D2失败时使用。
- `$slk-select-models`是SLK、CLK和GLK唯一的模型选择权威。

## Run权威文件

- `GLK-GRAPH.md`：Supervisor创建和修改的Node DAG与接口合同权威，所有成员可读。
- `GLK-ROSTER.md`：Supervisor创建和修改的Node/SLK花名册，所有成员可读。
- `GLK-RUN-<RUN-ID>.md`：唯一共享的追加式Run记录，每个成员记录自己的事实。

## Skill集合

GLK 4.0.0由4个并列Skill目录组成：

| Skill | 用途 |
| --- | --- |
| `skills/graph-loop-skill/SKILL.md` | 方法身份、SLK组合、Supervisor边界与情境路由 |
| `skills/glk-design-graph/SKILL.md` | DAG设计、静态检查、初始SLK规划与Run文件 |
| `skills/glk-run-graph/SKILL.md` | SLK建立、Node启动、交付转发与未启动区域调整 |
| `skills/glk-close-run/SKILL.md` | Fusion、最终D2、D2 Repair、归档与Owner结论 |

本集合不再包含GLK专属Checker、Worker、模型选择、运行控制、巡检或额外检验角色Skill。

## Fusion

Fusion Node在独立worktree中从Run基线开始，只接收直接前置Node候选，由组内SLK负责代码重叠、实现冲突、接口适配、真实集成施工和集成测试。机械Git merge不等于Fusion完成。各SLK登记GLK项目来源；LE BI只展示SLK本身，不展示Node、Fusion或DAG结构。

## 验证

```powershell
python scripts/validate_repository.py
python scripts/quick_validate.py skills
python -m pytest -q
```

迁移边界见[MIGRATION.md](MIGRATION.md)，当前验证证据见[VALIDATION-REPORT.md](VALIDATION-REPORT.md)。
