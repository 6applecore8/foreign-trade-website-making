# 简历项目描述（Hermes Agent）
> 正文采用用户明确提供的项目背景，个人贡献只收录有 Git 证据的表述。复制前请查看后面的背景校验；不要把审计信息与待确认清单粘贴到简历。

## 可直接粘贴的项目条目

### site-workflow-mvp — AI Agent / LLM 应用

**参与时间**：2026.08 — 2026.08

**个人角色**：项目初始化与核心功能开发

**技术栈**：Python · JavaScript · Vue · PostgreSQL · npm/yarn/pnpm · Vite · pip · Docker Compose

**项目简介**：本地静态网站生成工作流 MVP：通过主 Agent 调度多个 Subagent，完成需求分析、元数据、内容生成、网站实现和验证，面向需要快速生成并验证本地网站的开发场景；面向AI Agent / LLM 应用场景的多环节协同需求，项目聚焦数据统计与报表流程衔接。基于 Vue、PostgreSQL 构建AI Agent / LLM 应用核心链路，采用适配器模式，组织核心模块与扩展边界。

1. 工程化建设：针对多环境协作中依赖、构建与配置入口需要保持一致的工程要求，完善项目工程化建设，落地create local multi-agent website workflow MVP并统一依赖、构建与配置入口；形成可复用的环境准备与交付路径，减少重复配置和协作维护成本。

## 证据映射（不要粘贴到简历）

### 项目简介上下文

- 证据：用户提供背景：本地静态网站生成工作流 MVP：通过主 Agent 调度多个 Subagent，完成需求分析、元数据、内容生成、网站实现和验证，面向需要快速生成并验证本地网站的开发场景。
- 证据：README: README.md
- 证据：领域关键词命中：agent, rag
- 证据：业务流程（仓库语义推断）：数据统计与报表
- 证据：架构/设计模式：适配器模式
- 证据：依赖文件：intake\package.json、rag\requirements.txt、rag\docker-compose.yml → Python · JavaScript · Vue · PostgreSQL · npm/yarn/pnpm · Vite · pip · Docker Compose

### 用户提供背景与仓库校验

- **声明**：项目性质/使用场景：本地静态网站生成工作流 MVP：通过主 Agent 调度多个 Subagent，完成需求分析、元数据、内容生成、网站实现和验证，面向需要快速生成并验证本地网站的开发场景。
  - 来源：用户提供
  - 风险等级：`needs_confirmation`
  - 分析：按用户明确提供的背景写入项目简介；项目是否真实上线、内部使用、开源或课程实践通常无法仅凭代码仓库独立核验。
  - 校验证据：用户明确提供的项目背景


### 1. 工程化建设：针对多环境协作中依赖、构建与配置入口需要保持一致的工程要求，完善项目工程化建设，落地create local multi-agent website workflow MVP并统一依赖、构建与配置入口；形成可复用的环境准备与交付路径，减少重复配置和协作维护成本。

- 风险等级：`safe`
- 证据：commit 845bec9 [ci] feat: create local multi-agent website workflow MVP；文件：.gitignore、INDEX.md、README.md、archive/INDEX.md


## 待本人确认后补强

- [ ] 确认个人角色与团队边界：团队人数、本人负责范围，以及是否可使用“主导/主要负责”。
- [ ] 补充真实规模：用户量、数据量、QPS、运行时长或 star；没有可靠数据就不要填写。

## 目标岗位适配

- 仓库技术栈与「AI Agent/后端开发工程师」的典型要求匹配度有限；应如实呈现现有技术，不包装不存在的经验。

## 可补充的真实指标

以下指标已按当前贡献主题优先排序，只有在本人能提供 benchmark、监控、测试报告或其他可靠来源时才能加入正文：

- 工程效率：环境初始化耗时、构建耗时、部署成功率或新模块接入耗时
- 接口响应时间 / P95 / P99（需压测或监控数据）
- 吞吐量、QPS 或批处理耗时（需压测记录）
- 故障率、超时率或缺陷数量变化
- 测试覆盖率与自动化用例数量
- 真实用户量、数据量级与线上运行时长
