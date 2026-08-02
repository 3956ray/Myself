# Myself — Agent-native Personal OS

> 一个以证据、实验和本人决策为核心的人生规划框架。可以作为 Obsidian vault 使用，也可以让 Codex、Claude Code、Cursor 或其他能够读写本地 Markdown 的 Agent 协助运行。

Myself 不是替你生成一份看起来完整的“五年计划”。它把人生规划设计成一个可迭代系统：先认识现实与自己，再形成方向，用低成本实验验证，最后根据证据调整。

## 它解决什么问题

- 把“当前事实”“感受”“解释”“假设”“决定”分开，避免愿望被误写成现实。
- 把模糊的人生目标转化为可验证的情景和阶段实验。
- 让 AI 能够参与整理、反证、复盘和规划，但不能替用户决定价值观。
- 保留每次重要变更的来源、批准、备份和结果，避免对话结束后失去上下文。
- 所有核心内容都是本地 Markdown；Obsidian 是推荐界面，不是运行前提。

## 核心调用链

```mermaid
flowchart LR
    A["Capture<br/>原始输入"] --> B["Normalize<br/>分类、时间、隐私"]
    B --> C["Evidence<br/>证据与当前状态"]
    C --> D["Route<br/>选择工作流"]
    D --> E["Analyze<br/>分析与反证"]
    E --> F["Proposal<br/>明确页面差异"]
    F --> G["Verify<br/>规则与独立验证"]
    G --> H{"Human Gate<br/>本人决定"}
    H -->|批准| I["Checkpoint<br/>可恢复快照"]
    I --> J["Commit<br/>单写者更新"]
    J --> K["Trace & Review<br/>结果回流"]
    K --> C
    H -->|修正或拒绝| D
```

详细说明见 [系统架构](docs/architecture.md) 与 [Agent 协作协议](docs/agent-protocol.md)。

## 5 分钟开始

需要 Python 3.9+，不依赖第三方包。

```bash
git clone https://github.com/3956ray/Myself.git
cd Myself
python3 scripts/init_vault.py ~/My-Personal-OS
```

然后：

1. 用 Obsidian 打开 `~/My-Personal-OS`；或直接用任意 Markdown 编辑器。
2. 让 Agent 在该目录工作，并发送：

   ```text
   请先阅读 AGENTS.md 和 99 系统/首次设置.md。
   只进行首次访谈和候选整理，不要把推断直接写成我的正式状态。
   ```

3. 按顺序完成：当前状态 → 人生罗盘 → 三年情景 → 当前季度 → 第一次周复盘。
4. 运行结构检查：

   ```bash
   python3 "99 系统/scripts/validate_vault.py"
   ```

更完整的流程见 [快速开始](docs/getting-started.md)。

## 目标发现模型

框架不会从“你五年后想做什么”直接开始，而是依次处理：

1. **现实盘点**：资源、约束、责任、风险与当前节奏。
2. **投入信号**：哪些经历让你持续投入，哪些让你消耗或逃避。
3. **反目标**：哪些人生状态明确不能接受。
4. **价值冲突**：健康、关系、自由、成长、财富冲突时如何排序。
5. **可能自我**：建立多个三年情景，不急着宣称唯一答案。
6. **现实实验**：用 2–12 周实验获取真实反馈。
7. **证据更新**：复盘后继续、停止或调整，而不是维护旧叙事。

## 仓库结构

```text
.
├── docs/                 # 架构、决策模型、Agent 与 Obsidian 指南
├── scripts/              # 初始化器与只读校验器
├── tests/                # 标准库测试
└── vault-template/       # 不含个人数据的 Personal OS 模板
    ├── 00 收件箱/         # 未验证输入
    ├── 01 基础/           # 罗盘、当前状态、人生维度
    ├── 02 战略/           # 年度主题、三年情景
    ├── 03 季度/           # 当前季度计划与入口
    ├── 04 复盘/           # 日、周、月、季、年回顾
    ├── 05 日志/           # 证据、决策、变更、运行记录
    ├── 06 实验/           # 可证伪的现实实验
    ├── 90 模板/           # 可复制的记录模板
    └── 99 系统/           # 数据契约、调用链和安全规则
```

## 设计边界

- AI 是分析者和协作者，不是人生价值的最终裁判。
- 分数、矩阵和模型只用于暴露假设，不制造“客观最优人生”。
- 财务、医疗、法律和其他高风险问题必须使用权威来源或专业人士。
- 不要在 vault 中保存密码、私钥、助记词、完整证件号码或第三方敏感信息。
- 本项目不是医疗、法律、投资或心理治疗服务。

## 开发与验证

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_vault.py --vault vault-template --template-mode
```

项目采用 [MIT License](LICENSE)。当前版本为早期可用版本，欢迎通过 Issue 提交使用反馈。

