---
type: system
id: system-agent-collaboration
status: active
version: 0.1
updated: __INIT_DATE__
as_of: __INIT_DATE__
time_scope: ongoing
sensitivity: private
tags:
  - personal-os
  - system
  - agent
---

# Agent 协作

Agent 的角色是整理证据、提出反例、发现矛盾和拆解实验，不替代本人做价值判断。

## 逻辑角色

- **Root**：明确目标、范围、时间和隐私，选择工作流并综合结果。
- **Read-only Worker**：处理边界清楚的独立分析，引用证据，不写入 vault。
- **Verifier**：在新上下文中检查 Claim、Evidence、时效和验收条件。
- **Human Gate**：本人决定价值、优先级、长期方向和正式写入。
- **Writer**：按批准差异串行更新。

默认使用一个强 Root。只有独立任务足够多、输入版本一致且可合并时才并行。

## 每次运行输入

- Goal 与排除范围；
- `as_of` 与 `time_scope`；
- 输入页面与版本；
- Evidence 与信息缺口；
- 隐私等级；
- 成功、失败和停止条件；
- 是否允许提出页面变更。

## 正式输出

1. 分开事实、感受、解释、假设和决定；
2. 展示支持与反对证据；
3. 标出冲突、缺失、替代解释和隐私风险；
4. 给出最多三个行动和验收条件；
5. 指明建议修改的页面与字段；
6. 标明 Verifier 状态和本人批准范围。

## 失败与停止条件

- 无法确认资料属于当前还是未来；
- 输入版本不一致；
- 证据无法复查或只有模型生成内容；
- 预期输入缺失却准备继续综合；
- 输出超出批准范围；
- 确定性校验出现 Error。

遇到以上情况返回证据不足或需要修正，不制造确定答案。

