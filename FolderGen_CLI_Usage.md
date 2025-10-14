# 📦 FolderGen CLI 使用说明（最新版）

> **FolderGen** 是一个基于模板字符串的文件夹结构生成与验证工具，使用 JSON 模板与变量文件快速构建、校验、导出标准化目录结构。  
> 设计目标：**轻量、可视、可移植、自动化**。

---

## 🧭 命令总览

| 命令 | 功能简介 |
|------|----------|
| `foldergen plan` | 解析模板并输出生成计划（manifest），可导出 JSON/JSONL |
| `foldergen simulate` | 模拟生成结构（打印操作，不写入磁盘） |
| `foldergen build` | 按模板实际创建文件夹与文件 |
| `foldergen check` | 校验磁盘结构与模板一致性 |
| `foldergen tree` | 树形可视化模板结构或实际状态 |

---

## ⚙️ 全局参数一致性

所有命令统一支持：  
- `--template <模板文件>`、`--vars <变量文件>`、`--base <根目录>`：核心路径参数（必需）  
- `--relative/--absolute`：控制输出路径类型（默认相对）  
- `--max-expand <N>`：限制生成器展开上限（默认 50000）  
- `--portable auto|windows|posix|mac|all|none`：控制可移植性规则（部分命令有效）  
- `--max-path-len <N>`：路径长度警告阈值（默认 240）  
- `--follow-symlinks/--no-follow-symlinks`：控制符号链接跟踪（默认关闭）  

---

## 🧩 1. `plan` —— 生成计划与导出 Manifest

解析模板 (`template.json`) 与变量 (`vars.json`)，生成所有应创建的目录与文件路径，可导出为 JSON/JSONL。支持状态信息与变量警告。

### 命令
`foldergen plan --template <模板文件> --vars <变量文件> --base <根目录> [--relative/--absolute] [--with-status] [--warn-unused-vars] [--max-expand N] [--export-manifest <文件路径>] [--manifest-format json|jsonl] [--portable auto|windows|posix|mac|all|none] [--max-path-len N] [--follow-symlinks]`

### 示例
```powershell
# 基本生成计划（输出到终端）
foldergen plan --template .\examples\template_basic.json --vars .\examples\vars_basic.json --base D:\temp

# 导出 manifest 文件
foldergen plan --template .\examples\template_basic.json --vars .\examples\vars_basic.json --base D:\temp --export-manifest .\out\plan.json

# 检查变量未使用并限制生成规模
foldergen plan --template .\examples\template_basic.json --vars .\examples\vars_basic.json --base D:\temp --warn-unused-vars --max-expand 10000
```

### 新增功能
- **`--warn-unused-vars`**：检测并警告未使用的变量。  
- **`--max-expand`**：规模守门，防止生成器爆炸展开。  
- **错误定位增强**：若模板生成器错误（如 `step=0`），报错信息中会显示问题片段。

---

## 🧪 2. `simulate` —— 模拟生成（不写盘）

仅打印将要创建的目录与文件，便于验证模板输出效果。

### 命令
`foldergen simulate --template <模板文件> --vars <变量文件> --base <根目录> [--quiet] [--summary] [--max-expand N]`

### 示例
```powershell
# 打印完整操作
foldergen simulate --template .\examples\template_basic.json --vars .\examples\vars_basic.json --base D:\temp

# 仅输出汇总信息
foldergen simulate --template .\examples\template_basic.json --vars .\examples\vars_basic.json --base D:\temp --quiet

# 打印完整列表 + 汇总
foldergen simulate --template .\examples\template_basic.json --vars .\examples\vars_basic.json --base D:\temp --summary
```

### 新增功能
- **`--quiet`**：静默模式，仅输出统计。  
- **`--summary`**：显示总计目录与文件数量。

---

## 🏗️ 3. `build` —— 实际生成结构

根据模板在磁盘上创建目录与文件，默认交互确认，可跳过确认以用于自动化。

### 命令
`foldergen build --template <模板文件> --vars <变量文件> --base <根目录> [--assume-yes] [--max-expand N]`

### 示例
```powershell
# 创建文件结构（交互确认）
foldergen build --template .\examples\template_basic.json --vars .\examples\vars_basic.json --base D:\temp

# 无确认直接执行（CI 环境推荐）
foldergen build --template .\examples\template_basic.json --vars .\examples\vars_basic.json --base D:\temp --assume-yes
```

### 新增功能
- **`--assume-yes`**：跳过确认提示。  
- **`--max-expand`**：控制最大生成规模。

---

## 🧰 4. `check` —— 校验现有文件系统

检查当前目录结构是否与模板一致，输出缺失、冲突、命名问题、多余项等。支持过滤与可移植性规则。

### 命令
`foldergen check --template <模板文件> --vars <变量文件> --base <根目录> [--format json|table] [--filter status=missing,conflict] [--portable auto|windows|posix|mac|all|none] [--max-path-len N] [--follow-symlinks] [--strict]`

### 示例
```powershell
# 表格模式检查
foldergen check --template .\examples\template_basic.json --vars .\examples\vars_basic.json --base D:\temp --format table

# 仅查看缺失与冲突项
foldergen check --template .\examples\template_basic.json --vars .\examples\vars_basic.json --base D:\temp --filter missing,conflict

# 可移植性校验（Windows）
foldergen check --template .\examples\template_basic.json --vars .\examples\vars_basic.json --base D:\temp --portable windows
```

### 新增功能
- **`--filter status=...`**：筛选输出状态（如 `missing,conflict`）。  
- **`--max-expand`**：在计划阶段限制生成器规模。  
- **盘符与根目录排除**：Windows 下盘符不会被判非法，根目录不会出现在 Extras。

---

## 🌲 5. `tree` —— 树形结构展示

以 ASCII、JSON、YAML 方式展示模板结构，可附带状态标色。

### 命令
`foldergen tree --template <模板文件> --vars <变量文件> --base <根目录> [--relative/--absolute] [--format tree|json|yaml] [--depth N] [--show-files/--no-show-files] [--status] [--portable ...] [--max-path-len N] [--follow-symlinks] [--out <文件>] [--max-expand N]`

### 示例
```powershell
# 纯模板树
foldergen tree --template .\examples\template_basic.json --vars .\examples\vars_basic.json --base D:\temp --depth 2

# 带状态彩色树（existing=绿, missing=红, conflict=黄）
foldergen tree --template .\examples\template_basic.json --vars .\examples\vars_basic.json --base D:\temp --status

# 导出 JSON / YAML 树
foldergen tree --template .\examples\template_basic.json --vars .\examples\vars_basic.json --base D:\temp --format json --out .\out\tree.json
```

### 新增功能
- **`--status`**：自动注入并标色状态（existing/missing/conflict/planned）。  
- **`--max-expand`**：生成阶段规模限制。

---

## 📁 Template 与 Vars 文件配置

### Template 示例
```json
{
  "schemaVersion": 1,
  "name": "DemoProject",
  "dirs": [
    {
      "name": "Release_{{date: start=2025-01-01; stop=2025-03-01; step=1m; fmt=%Y%m}}",
      "dirs": [
        {
          "name": "Char_{{alpha: start=A; stop=B}}",
          "dirs": [
            {"name": "LOD_{{int: start=0; stop=2; pad=2}}"}
          ]
        }
      ]
    }
  ],
  "files": ["README.md", "{project|slug}.py", "{episode|pad(3)}_intro.txt"]
}
```

### Vars 示例
```json
{
  "project": "My Cool Project",
  "episode": 7
}
```

---

## 🧮 模板字符串语法

### 单花括号 `{var}` 与过滤器
| 语法 | 功能 | 示例 |
|------|------|------|
| `{var}` | 替换 vars.json 中的同名键值 | `{project}` |
| `{var|pad(n)}` | 数字左侧补零 | `{episode|pad(3)}` → `007` |
| `{var|slug}` | 字符串转小写并替换空格为 `_` | `{project|slug}` → `my_cool_project` |

### 双花括号生成器 `{{...}}`
| 类型 | 参数 | 示例 |
|------|------|------|
| `int` | `start`, `stop`, `step`, `pad` | `LOD_{{int: start=0; stop=2; pad=2}}` → `LOD_00`, `LOD_01`, `LOD_02` |
| `alpha` | `start`, `stop`, `step` | `Char_{{alpha: start=A; stop=C}}` → `Char_A`, `Char_B`, `Char_C` |
| `date` | `start`, `stop`, `step`, `fmt` | `Release_{{date: start=2025-01-01; stop=2025-03-01; step=1m; fmt=%Y%m}}` → `Release_202501`, `Release_202502`, `Release_202503` |

> 错误时会输出明确片段，如 `int step cannot be 0 [at: {{ int: start=0; stop=10; step=0 }}]`。

---

## 📘 总结

| 目标 | 推荐命令 |
|------|-----------|
| 预览模板结果 | `foldergen simulate` |
| 创建结构 | `foldergen build --assume-yes` |
| 校验结构 | `foldergen check --format table` |
| 导出清单 | `foldergen plan --export-manifest plan.json` |
| 可视化结构 | `foldergen tree --status` |

---

© 2025 FolderGen — Template-driven Folder Structure Generator
