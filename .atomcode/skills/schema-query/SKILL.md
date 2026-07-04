---
name: schema-query
description: 查询 medicare_engine.db 数据库的表结构和样本数据。开发时需要查看表结构时使用。
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash
---

查询 `medicare_engine.db` (SQLite) 的数据库结构。

## 常用查询

### 列出所有表
```bash
sqlite3 medicare_engine.db ".tables"
```

### 查看表结构
```bash
sqlite3 medicare_engine.db ".schema <table_name>"
```

### 查看样本数据
```bash
sqlite3 medicare_engine.db "SELECT * FROM <table_name> LIMIT 5;"
```

### 查看建表语句全部
```bash
cat schema.sql
```

## 项目说明

数据库文件: `medicare_engine.db` (~45MB)
建表 DDL: `schema.sql` (含详细注释)
数据来源: 医保两库规则、药品/诊疗项目/耗材目录、ICD-10/ICD-9 编码
