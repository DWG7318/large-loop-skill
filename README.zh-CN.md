# Graph Loop Skill（GLK）3.0.0

规范仓库：https://github.com/DWG7318/large-loop-skill

GLK 用一张由可独立验证 GO 构成的有向无环执行图，治理一个边界冻结的工程 Run。

## 标准流程

```text
冻结 RUN_CONTRACT
→ 为本 Run 新建 Run Supervisor 实例
→ 冻结 GO 执行 DAG
→ 不能执行的 GO 进入 WAITING_GO 并记录原因
→ 所有条件满足的 GO 进入最大安全 ACTIVE_GO 集合
→ 各 GO 并行执行 D0、独立 D1、独立 D2
→ 跨 GO 修复时形成确认的因果追踪与最小后继失效范围
→ 新解锁的后继 GO 直接进入 ACTIVE_GO
→ 独立 Run D3
→ 当前 Run 立即进行 Owner Acceptance
→ LOOP_OWNER_ACCEPTED
→ 向 LCCoding 输出安全交接
```

## 六角色

1. Run Supervisor
2. Worker
3. Checker
4. GO Verifier
5. Run Verifier
6. Owner

每次 Run 都必须新建独立 Run Supervisor 实例，不得跨 Run 复用其身份、上下文、
可变工作区或证据目录。多个 ACTIVE_GO 使用同一角色类型的多个隔离实例，不增加
第七种角色。

## Graph 执行原则

GLK 不设置介于等待与执行之间的排队层。未完成 GO 只有在仍存在有证据的依赖、
写入冲突、资源、隔离或安全原因时才是 `WAITING_GO`；原因全部解除后必须直接进入
最大安全 `ACTIVE_GO` 集合。

GLK 必须尽可能同时激活相互独立的 GO。不得为了管理方便任意串行化，也不得伪造
依赖边。若多个安全组合包含的 GO 数量不同，必须选择能同时激活最多 GO 的组合。

## 因果恢复

每条 D2 边绑定生产者声明/输出、消费者输入/假设和消费证据。
`GO_CAUSAL_TRACE` 将一次 incident 的确认来源绑定到当前不可变候选、显式真实症状集
以及由事故证据选中的实际消费边。仅仅可达但未被证据确认的替代路径必须排除；来源
与症状仍只是注解，不是新的节点类型或状态。只有确认的选定路径才能使当前证据失效。

图修订使用带类型的候选、证据或声明/输出 seed，并拒绝无关引用。候选或声明/输出
seed 要求来源返工或隔离；仅证据 seed 可重新验证，多 seed 采用最严格来源规则。
修复后只重新投影被证明受影响的最小切片。历史 receipt 保持追加不可变，未受影响
分支继续有效；来源 GO 在等待原因清除时直接进入 `ACTIVE_GO`，新解锁的多个后继在
同一次最大基数调度中并行重激活。不增加可调度中间队列，也不全图重跑。

## 验证边界

- D0：Worker 的实现侧证据；
- D1：独立 CELL 候选验证；
- D2：独立 GO 组合验证；
- D3：独立 Run Feature 与图接缝验证。

D3 消费有效 D2 证据，不机械重跑全部下层检查。D3 PASS 后，Owner 立即验收当前
Run；项目级集中安全闭环仍归 LCCoding。

正式使用前必须完整读取 [SPEC.md](SPEC.md)。可执行模板、Schema、图模型和验证器位于
[glk](glk/) 目录。

## 3.0 权限与验证

GLK 3.0 将 Worker D0、Checker D1、Supervisor admission、GO Verifier D2、
Supervisor graph event、Run Verifier D3 与 Owner Acceptance 拆成互不混权的追加型
artifact。版本化 `CELL_MANIFEST` 与精确 `GO_CANDIDATE_CLOSURE` 阻止过早 D2；只有
完全未变化且仍 current-valid 的 CELL D1 才能复用。

`validate_glk` 验证 `REPOSITORY_DISTRIBUTION`，`validate_run` 对完整 `RUN_PACKAGE`
执行十层验证。bootstrap 只生成草稿；preflight 与 simulation 是派生门禁；liveness
失败关闭；技术权限或连续架构级错误会停止 Run。进度必须同时报告 required GO/D2
与 required CELL/D1。

方法锁固定 3.0.0、本规范仓库、commit/release、Schema、Skill、真实 Run validator
源码 bundle 与 adapter contract。2.4 formal-use freeze 只允许历史迁移诊断，绝不把
未证明的 2.4 receipt 升级为 current evidence。

GLK 只定义四操作 provenance adapter 契约。LCCoding 负责生命周期和集中安全路由；
LCagent 或其他可信执行环境负责凭据、会话、签发、replay/checkpoint、Broker 与 runtime
provenance 实现。
