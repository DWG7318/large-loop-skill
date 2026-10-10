---
name: glk-run-graph
description: Use when an active Graph Loop Skill (GLK) Run has a frozen Node DAG and needs child SLK Runs started or completed handoffs routed.
---

# Run a GLK Graph

> **使用边界：** 本Skill是Graph Loop Skill（GLK）的子Skill，不可脱离当前GLK Run单独使用。

## 当前目标

由GLK Supervisor保持Graph连续推进；每个Node包含一组最新SLK Runs，所有Graph复杂性留在GLK Supervisor。

## 建立成员

1. Supervisor按冻结花名册为每个Node创建已知子SLK Run。每个Run的Supervisor角色绑定引用同一个共享Supervisor Agent，不会创建新的Supervisor对话；Fusion与D2 Repair子SLK也预先登记，满足条件前保持未启动。
2. 每个子SLK独立建立Checker和Worker；每个子SLK独立完成通讯测试，并保留自己的SLK TOKEN、中央记录、独立worktree、CELL、D0、D1、子SLK D2与归档。不同子SLK的Checker或Worker之间不建立工作通道。
3. 把唯一共享Agent、各子SLK的Supervisor绑定、Run ID、Checker、Worker、SLK TOKEN、中央记录、worktree、通讯结果和状态写入`GLK-ROSTER.md`。隐藏代理或文字角色不算成员。

## 启动与路由

1. 共享Supervisor向所有起点Node中的子SLK分别发送完整交付，使它们可以并行开工。每次动作必须绑定`GLK_RUN_ID + NODE_ID + SLK_RUN_ID + CELL_ID`并重新读取目标子SLK中央记录与当前SLK TOKEN。
2. 每个子SLK只按固定SLK完成CELL、D0、D1、子SLK D2、必要返工和记录；关闭后把完整交付交给同一个共享Supervisor。
3. 共享Supervisor已经在对应子SLK作用域完成子SLK D2；进入Graph路由阶段后不再次检查交付内容、不重跑测试也不给第二个结论，只记录交付身份和Graph位置。
4. 某Node组内全部必需SLK关闭后，该Node完成；目标Node的全部直接前置Node交付到齐时，Supervisor把这些交付及目标Node合同合成一份完整交付，立即启动目标Node下的SLK，不等待其他无关Node。
5. 交付缺失或消息不可用时，目标Checker只向Supervisor报告通讯问题；Supervisor恢复通道或把同一交付原样重发。上游Checker不参与回退确认。
6. 受阻Node只让相关后继保持未启动，其他路径继续。Supervisor完成一次启动、转发或恢复后结束当前活动，不使用`wait_threads`观察成员。

## 失败关闭

发现重复Supervisor Agent、四元作用域缺失或碰撞、跨子SLK Checker/Worker派工或记录/TOKEN不匹配时，立即失败关闭；不猜ID、不跨域重发，也不创建替代Supervisor。子SLK仍分别保留可恢复证据。

## 交付接收记录

目标SLK在共享Run记录中写下收到的直接输入身份与当前Node。该记录用于确认传输闭合，不代表它已经完成，也不形成反向依赖。

## 未启动区域调整

新的工程事实可以让Supervisor在未启动区域插入、删除、合并或重画Node，但应保持Run目标、有向无环、ALL汇合、唯一Fusion和接口一致。活动或已完成Node的合同不改写，不复用Node编号；新Node使用新编号、新SLK Runs和新通讯测试。

如果某SLK因豁免而无法提供可用输出接口，它仍留在原Node的SLK恢复循环，后继不启动；不把缺失输出转移成新的Graph问题。

## 完成后

所有Fusion直接前置Node完成交付后，调用`$glk-close-run`启动Fusion与最终收口。
