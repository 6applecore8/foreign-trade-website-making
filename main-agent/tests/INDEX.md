# Main Agent Tests

本目录存放 Main Agent 的只读工作流合同测试，用于在不改写项目输入、产物或活动配置的前提下验证兼容性约束。

`test_intake_compatibility_gate.py` 验证：兼容性门禁在归档门禁前以 fail-closed 方式执行；必须显式选择规范的 `intake/requests/<request_id>`；当前请求通过、旧版或 `latest` 请求被拒绝；请求与生成配置满足 JSON Schema、身份和路径一致性；同时固定工作流图、活动配置哈希、四页面及十二个实现文件限制。

只读运行命令（从项目根目录执行）：

```bash
python -m unittest discover -s main-agent/tests -p test_*.py -v
```

## Owner 边界

工作流合同 Owner 仅维护 workflow、schema、prompts、navigation 与 documentation（包括本索引）；不得修改 `intake/**`、`artifacts/**` 或活动配置 `config/site-config.json`。本目录测试也不得通过修复、迁移或补字段来改写历史请求。
