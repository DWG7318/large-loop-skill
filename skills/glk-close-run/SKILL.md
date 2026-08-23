---
name: glk-close-run
description: Use when an active Graph Loop Skill (GLK) Run is ready to start Fusion, perform final D2, repair a failed final composition, or archive completed members.
---

# Close a GLK Run

> **使用边界：** 本Skill是Graph Loop Skill（GLK）的子Skill，不可脱离当前GLK Run单独使用。

## Fusion

Fusion是普通GO，也是正常Graph的最后一个GO。它由预建的专属Checker和Worker按固定最新SLK施工，并在新的独立worktree中从Run基线开始。

Fusion只接收自己的直接前置GO候选、输出接口、功能意图和必要数据；不读取无关历史候选。它负责代码重叠、实现冲突和接口适配，完成真实集成施工与集成测试，不把任何前置worktree当默认主线，也不是机械Git merge。

Fusion内部的D0、D1和普通返工完全按SLK进行。D1失败时继续使用原Checker和Worker，不启动D2 Repair GO。

## 最终D2

Fusion D1通过后，Checker用Run目标、Graph完成事实、直接输入、最终候选、端到端入口和必要客观环境激活Supervisor。Supervisor在隔离输入下使用本Run允许的最高能力模型执行最终D2。

最终D2集中检查Graph是否完整、依赖和输出接口是否真实组合、Fusion是否形成完整系统、是否遗漏或重复能力，以及豁免和Run风险；不逐项重复普通CELL D1。

## D2 Repair GO

最终D2失败时才启动预建的D2 Repair GO。它的输入是D2缺陷包与Fusion候选，输出是修正后的最终候选和修复证据。

D2 Repair GO由自己的专属Checker和Worker按SLK施工；其D1返工继续使用同一组成员，不再创建另一个D2 Repair GO。完成后返回同一最终D2边界重新检查。

若第一次最终D2通过，未使用的D2 Repair GO成员直接进入归档；它不算失败、豁免或空GO。

## 记录、归档与Owner结论

最终D2通过后，Supervisor在共享Run记录汇总GO数量、D0/D1/D2、豁免、是否运行D2 Repair、最终候选和证据位置。随后按每组先Worker后Checker归档全部成员，保留Supervisor供Owner查询。

Owner只收到一个简洁结论和`GLK-RUN-<RUN-ID>.md`位置，不需要再次确认方法过程。
