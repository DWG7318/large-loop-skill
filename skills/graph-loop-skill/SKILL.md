---
name: graph-loop-skill
description: Use when one large engineering Run needs groups of SLK Runs to start and unlock through a directed acyclic Node graph before final Fusion.
---

# Graph Loop Skill

## 方法身份

GLK是基于Graph逻辑的Loop Engineering施工技术，适合用一个大型Run覆盖完整工程。一个Graph就是一个Run，每个节点是一个Node；一个Node是一组共同形成该节点成果的SLK Runs。

Graph是有向无环的Node DAG：它可以有多个起点、分叉和ALL汇合；Node在全部直接前提满足后立即启动其中的SLK Runs，不等待无关Node。正常路径最后只有一个Fusion Node。

## 与SLK的关系

每个Node列出一个或多个本Run固定最新SLK基线的Runs；每个SLK通过`$small-loop-skill`完成线性CELL施工并拥有自己的Supervisor、Checker和Worker。SLK成员不需要理解整个Graph；GLK不复制SLK的规划、派工、D0、D1、返工、通讯、记录或模型规则。

普通Node在组内全部必需SLK形成可用交付后完成，不增加Node级检验；Fusion完成后才有整个Graph的一次最终D2。

## Supervisor

一个GLK Run只有一个GLK Supervisor。它负责设计和维护Graph、启动各Node下的SLK、接收SLK交付、按依赖转发、启动Fusion、执行最终D2与必要的D2 Repair；每个SLK仍按自身方法管理三角色与归档。

GLK Supervisor不承担普通CELL派工或D1，也不重新检查普通Node内的SLK内容。消息激活它完成一次路由或边界工作后，它结束当前活动，不使用`wait_threads`观察成员施工。

## 三个权威文件

- `GLK-GRAPH.md`：Supervisor创建和修改的Node DAG与接口合同权威，所有成员可读。
- `GLK-ROSTER.md`：Supervisor创建和修改的成员花名册，所有成员可读。
- `GLK-RUN-<RUN-ID>.md`：Supervisor创建的唯一共享Run记录，每个成员追加自己的工作事实。

GLK不为每个Node再建一份方法记录；Node只引用组内各SLK的中央记录，详细施工事实留在对应SLK。

## 按当前情境选择指导

- 设计、自检并冻结Graph：`$glk-design-graph`
- 启动Node内的SLK、转发交付与维护未启动区域：`$glk-run-graph`
- 启动Fusion、执行最终D2、D2 Repair与归档：`$glk-close-run`

## Owner边界

原对话与Owner确定Run目标和GLK选择，创建Supervisor并交接后退出工程工作。Supervisor可以建议Owner查看简化逻辑图；Owner不想查看时不阻塞施工。最终只向Owner提供一个简洁结论和共享Run记录位置。
