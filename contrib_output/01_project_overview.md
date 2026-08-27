# 项目概览

- **项目名称**：site-workflow-mvp
- **仓库路径**：C:\Users\HP\.hermes\workspace\site-workflow-mvp
- **主要语言**（按文件数）：Python(32)、JavaScript(8)、HTML(6)、Vue(5)、CSS(3)
- **框架**：Vue
- **数据库**：PostgreSQL
- **中间件**：未识别
- **构建工具**：npm/yarn/pnpm、Vite、pip
- **部署方式**：Docker Compose
- **依赖证据文件**：intake\package.json、rag\requirements.txt、rag\docker-compose.yml

## 业务背景（推断为主，注意置信度）

- **推断业务领域**：AI Agent / LLM 应用（次要相关：OA/协同办公）（置信度：中）
- **项目目标**：README 描述（事实）：一个“主 Agent + Subagent”自动创建本地静态网站的最小可行工作流。
- **解决的问题**：推断：见 README 描述；具体业务痛点建议向项目负责人确认
- **目标用户**：推断：需结合业务方确认（仓库内无直接证据）
- **核心业务流程**：推断：数据统计与报表
- **证据来源**：README: README.md；领域关键词命中：agent, rag

## 用户提供背景与仓库校验

- **声明**：项目性质/使用场景：本地静态网站生成工作流 MVP：通过主 Agent 调度多个 Subagent，完成需求分析、元数据、内容生成、网站实现和验证，面向需要快速生成并验证本地网站的开发场景。
  - 来源：用户提供
  - 风险等级：`needs_confirmation`
  - 分析：按用户明确提供的背景写入项目简介；项目是否真实上线、内部使用、开源或课程实践通常无法仅凭代码仓库独立核验。
  - 校验证据：用户明确提供的项目背景

## 待确认问题（写简历/面试前建议先回答）

1. 这个项目是真实上线、内部使用，还是课程/练习项目？
2. 项目的实际用户是谁？大概什么量级？
3. 项目立项的直接原因是什么（业务痛点 / 课程要求 / 个人兴趣）？
4. 是否有线上运行数据（QPS、日活、数据量）可以补充？
5. 团队总人数和分工是怎样的？

## 目录结构要点

- 顶层目录：archive、artifacts、config、docs、intake、main-agent、orchestrator、rag、rag-data、runs、screenshots、scripts
- 关键目录：intake\src、intake\src\core
- 测试目录：intake\tests、main-agent\tests、orchestrator\tests、rag\tests
- README：README.md