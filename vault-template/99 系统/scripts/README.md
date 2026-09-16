# Vault 校验器

`validate_vault.py` 是只读结构检查，不创建、修改或删除 vault 内容，也不依赖第三方 Python 包。

在 vault 根目录运行：

```bash
python3 "99 系统/scripts/validate_vault.py"
```

检查范围包括核心页面、frontmatter、状态词汇、ID 唯一性、日期格式与起止顺序、复查日期别名一致性、实际启动与 as_of 的顺序、Wiki-link、敏感信息模式和复盘实例。Error 会返回非零状态；Warning 必须解释但不会阻断。

