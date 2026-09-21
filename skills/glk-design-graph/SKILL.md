---
name: glk-design-graph
description: Use when an active Graph Loop Skill (GLK) Run needs its Node DAG, interfaces, roster, and SLK groups designed before construction starts.
---

# Design a GLK Graph

> **使用边界：** 本Skill是Graph Loop Skill（GLK）的子Skill，不可脱离当前GLK Run单独使用。

## 当前目标

由Supervisor把大型Run设计成可靠的多起点Node DAG，并在成员施工前完成静态自检和三个权威文件。

## 设计Node

1. 检查并绑定当前最新GLK与最新SLK版本；本Run开工后固定这两个方法基线。
2. 从Run目标和真实工程基线写出必要成果，再将每个成果命名为`Node001`、`Node002`直至需要的更高编号。编号只表示身份，不表示启动顺序。
3. 每个Node说明结果、开工前提、全部直接前置Node、输入、输出接口、组内SLK清单、直接后继和完成事实。
4. 每个组内SLK调用`$small-loop-skill`形成线性CELL施工方案，并调用`$slk-select-models`选择三角色能力；初始化时登记`source_kind=glk`与`source_project_name=<GLK项目名>`，Owner指定仍有效。
5. 为并行SLK安排独立worktree，以及需要隔离的端口、数据库、缓存、进程、测试路径和临时资源。文件重叠本身不是依赖。
6. 预留一个有真实目标的Fusion Node，以及一个只在最终D2失败后启动的D2 Repair Node；二者也分别包含一个或多个SLK Runs。

## Graph静态自检

Supervisor在冻结前逐项确认：

1. 有两个或以上能够独立开工的零入度Node；
2. Graph是有向无环结构，Node编号唯一且不复用；
3. 每个普通Node都有必要且非空的成果，并至少包含一个SLK；
4. 每个非起点Node都有明确开工前提和直接前置Node；
5. 每个生产方输出接口与每个消费方输入接口逐项对应；
6. 每个普通Node都从某个起点可达，也都能到达Fusion；
7. 每个汇合都使用ALL语义，不依赖无关Node；
8. 正常路径只有唯一Fusion Node作为最后节点；
9. 并行施工空间和共享资源具备可行隔离；
10. Node编号、组内SLK及其记录指针与花名册一致；
11. 从所有起点做静态依赖遍历后没有孤儿或死路；
12. D2 Repair Node唯一开工条件是最终D2失败。

任何不通过项都在设计阶段修正，不用试施工替代Graph设计。

## 建立权威文件

从`assets/GLK-GRAPH.template.md`、`assets/GLK-ROSTER.template.md`和`assets/GLK-RUN.template.md`在项目根目录创建`GLK-GRAPH.md`、`GLK-ROSTER.md`和`GLK-RUN-<RUN-ID>.md`。Supervisor冻结Graph版本和初始成员清单。

Owner查看逻辑图是建议，不是开工门禁。提供时只展示Node编号、一句话成果、依赖箭头、起点、Fusion和条件D2 Repair，不展示CELL、模型或成员细节。

## 完成后

调用`$glk-run-graph`创建全部已知SLK Runs、完成各自通讯测试并启动所有起点Node。
