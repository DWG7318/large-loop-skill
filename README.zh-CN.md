# Graph Loop Skill（GLK）

当前版本：**3.2.0**

GLK是面向大型工程Run的Graph型Loop Engineering方法。它把一个Run设计为多个起点、由真实成果依赖连接的有向无环DAG，并让每个GO使用本Run固定的最新SLK基线完成线性施工。

```text
多个起点GO
    -> 按依赖即时启动
    -> 一个Fusion GO
    -> 一次最终D2
    -> Run完成
```

## 核心边界

- 一个Graph就是一个Run，每个节点是一个使用`GO001`一类数字身份的必要GO。
- GO在全部直接前提存在后立即开工；所有汇合使用`ALL`，无关工作不互相等待。
- 一个Supervisor负责Graph设计、成员建立、路由、Fusion、最终D2和归档。
- 每个GO独占一组Checker/Worker并只按SLK施工。GLK不复制SLK的CELL、D0、D1、返工、通讯、记录或模型指导。
- 正常施工最后只有一个Fusion GO；预建的条件D2 Repair GO只在最终D2失败时使用。
- `$slk-select-models`是SLK、CLK和GLK唯一的模型选择权威。

## Run权威文件

- `GLK-GRAPH.md`：Supervisor创建和修改的DAG与GO合同权威，所有成员可读。
- `GLK-ROSTER.md`：Supervisor创建和修改的可见成员花名册，所有成员可读。
- `GLK-RUN-<RUN-ID>.md`：唯一共享的追加式Run记录，每个成员记录自己的事实。

## Skill集合

GLK 3.2.0由4个并列Skill目录组成：

| Skill | 用途 |
| --- | --- |
| `skills/graph-loop-skill/SKILL.md` | 方法身份、SLK组合、Supervisor边界与情境路由 |
| `skills/glk-design-graph/SKILL.md` | DAG设计、静态检查、初始SLK规划与Run文件 |
| `skills/glk-run-graph/SKILL.md` | 成员建立、GO启动、交付转发与未启动区域调整 |
| `skills/glk-close-run/SKILL.md` | Fusion、最终D2、D2 Repair、归档与Owner结论 |

本集合不再包含GLK专属Checker、Worker、模型选择、运行控制、巡检或额外检验角色Skill。

## Fusion

Fusion在自己的独立worktree中从Run基线开始，只接收直接前置GO候选，负责代码重叠、实现冲突、接口适配、真实集成施工和集成测试。机械Git merge不等于Fusion完成。

## 验证

```powershell
python scripts/validate_repository.py
python scripts/quick_validate.py skills
python -m pytest -q
```

迁移边界见[MIGRATION.md](MIGRATION.md)，当前验证证据见[VALIDATION-REPORT.md](VALIDATION-REPORT.md)。
