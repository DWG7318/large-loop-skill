---
name: glk-run-graph
description: Use when an active Graph Loop Skill (GLK) Run has a frozen DAG and needs visible GO pairs created, startable GOs activated, or completed handoffs routed.
---

# Run a GLK Graph

> **使用边界：** 本Skill是Graph Loop Skill（GLK）的子Skill，不可脱离当前GLK Run单独使用。

## 当前目标

由Supervisor保持Graph连续推进；每个GO独占一组最新SLK成员，例如`GO012-Checker`和`GO012-Worker`，所有Graph复杂性留在Supervisor。

## 建立成员

1. Supervisor按冻结花名册创建所有已知GO的Checker；每个Checker再按`$small-loop-skill`创建自己的Worker。Fusion与D2 Repair成员也在开工前建好，之后保持非活动。
2. 完成`Supervisor ↔ 每个Checker`双向通讯测试，再由每组完成`每个Checker ↔ 自己的Worker`双向通讯测试。Checker之间不建立工作通道。
3. 把可见对话ID、专属worktree、通讯结果和成员状态写入`GLK-ROSTER.md`。隐藏代理或文字角色不算成员。

## 启动与路由

1. Supervisor向所有起点GO的Checker分别发送完整SLK交付，使它们可以并行开工。
2. Checker与Worker只按固定SLK完成GO的CELL、D0、D1、必要返工和记录。Checker在GO交付可用后把完整交付发送给Supervisor。
3. Supervisor不检查交付内容、不重跑测试也不给第二个结论；它记录交付身份和Graph位置。
4. 某GO的全部直接前置GO交付都到齐后，Supervisor把这些交付及目标GO合同合成一份完整交付，立即启动目标Checker，不等待其他无关GO。
5. 交付缺失或消息不可用时，目标Checker只向Supervisor报告通讯问题；Supervisor恢复通道或把同一交付原样重发。上游Checker不参与回退确认。
6. 受阻GO只让相关后继保持未启动，其他路径继续。Supervisor完成一次启动、转发或恢复后结束当前活动，不使用`wait_threads`观察成员。

## 交付接收记录

目标Checker在共享Run记录中写下收到的直接输入身份与当前GO。该记录用于确认传输闭合，不代表它已经完成D1，也不形成反向依赖。

## 未启动区域调整

新的工程事实可以让Supervisor在未启动区域插入、删除、合并或重画GO，但应保持Run目标、有向无环、ALL汇合、唯一Fusion和接口一致。活动或已完成GO的合同不改写，不复用GO编号；新GO使用新编号、新Checker/Worker和新通讯测试。

如果某GO因豁免而无法提供可用输出接口，它仍留在原GO的SLK恢复循环，后继不启动；不把缺失输出转移成新的Graph问题。

## 完成后

所有Fusion直接前置GO完成交付后，调用`$glk-close-run`启动Fusion与最终收口。
