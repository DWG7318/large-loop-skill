---
name: graph-loop-skill
description: Use when one large engineering Run needs multiple outcome-dependent GOs to start and unlock through a directed acyclic graph before final Fusion.
---

# Graph Loop Skill

## 方法身份

GLK是基于Graph逻辑的Loop Engineering施工技术，适合用一个大型Run覆盖完整工程。一个Graph就是一个Run，每个节点是一个GO。

Graph是有向无环DAG：它可以有多个起点、分叉和ALL汇合；GO在全部直接前提满足后立即开工，不等待无关GO。正常路径最后只有一个Fusion GO。

## 与SLK的关系

每个GO都进入本Run固定的最新SLK，通过`$small-loop-skill`完成线性CELL施工。Checker和Worker只按SLK工作，不需要理解整个Graph；GLK不复制SLK的规划、派工、D0、D1、返工、通讯、记录或模型规则。

一个GO独占一组Checker和Worker。普通GO由SLK形成可用交付后回到Supervisor，不增加GO级D2；Fusion完成后才有整个Graph的一次最终D2。

## Supervisor

一个GLK Run只有一个Supervisor。它负责设计和维护Graph、建立成员、接收GO交付、按依赖转发、启动Fusion、执行最终D2与必要的D2 Repair，并在收尾时归档Checker和Worker。

Supervisor不承担普通CELL派工或D1，也不重新检查普通GO内容。消息激活它完成一次路由或边界工作后，它结束当前活动，不使用`wait_threads`观察成员施工。

## 三个权威文件

- `GLK-GRAPH.md`：Supervisor创建和修改的Graph与GO合同权威，所有成员可读。
- `GLK-ROSTER.md`：Supervisor创建和修改的成员花名册，所有成员可读。
- `GLK-RUN-<RUN-ID>.md`：Supervisor创建的唯一共享Run记录，每个成员追加自己的工作事实。

GLK不为每个GO再建一份方法记录。GO内详细工作仍写入同一共享Run记录的对应分区。

## 按当前情境选择指导

- 设计、自检并冻结Graph：`$glk-design-graph`
- 建立成员、启动GO、转发交付与维护未启动区域：`$glk-run-graph`
- 启动Fusion、执行最终D2、D2 Repair与归档：`$glk-close-run`

## Owner边界

原对话与Owner确定Run目标和GLK选择，创建Supervisor并交接后退出工程工作。Supervisor可以建议Owner查看简化逻辑图；Owner不想查看时不阻塞施工。最终只向Owner提供一个简洁结论和共享Run记录位置。
