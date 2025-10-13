# 📦 FolderGen CLI 使用说明

> **FolderGen** 是一个基于模板字符串生成、校验、导出文件夹结构的 Python 工具。  
> 适用于构建工程模板、素材目录、发行版本、剧集/镜头批量结构等自动化需求。

---

## 目录

- [安装与运行环境](#安装与运行环境)
- [命令总览](#命令总览)
- [`plan`——生成计划与导出 Manifest](#plan生成计划与导出-manifest)
- [`simulate`——模拟生成（不写盘）](#simulate模拟生成不写盘)
- [`build`——实际生成结构](#build实际生成结构)
- [`check`——校验现有文件系统](#check校验现有文件系统)
- [`tree`——以树形方式展示结构](#tree以树形方式展示结构)
- [Template 与 Vars 配置说明](#template-与-vars-配置说明)
- [模板字符串语法](#模板字符串语法)
  - [单花括号变量 `{var}` 与过滤器](#单花括号变量-var-与过滤器)
  - [双花括号生成器 `{{...}}`](#双花括号生成器-)
- [常见问题 & 提示](#常见问题--提示)

---

## 安装与运行环境

- Python 3.9+
- 安装（源码根目录）：
  ```bash
  pip install -e .
  ```
- 命令行可用性：安装后将提供 `foldergen` 命令。

---

## 命令总览

| 命令 | 功能简介 |
|------|----------|
| `foldergen plan` | 解析模板并输出“生成计划”，或导出 manifest（JSON/JSONL） |
| `foldergen simulate` | 模拟生成（只打印，不写入磁盘） |
| `foldergen build` | 按模板真正创建目录与文件 |
| `foldergen check` | 对比模板与磁盘现状，输出缺失/冲突/多余/命名问题等 |
| `foldergen tree` | 以树形方式（ASCII/JSON/YAML）展示结构，可选状态着色 |

> **术语说明**
> - **模板（template）**：描述目录/文件结构的 JSON。支持变量占位与批量生成器语法。
> - **变量（vars）**：提供模板中 `{var}` 所需的键值对（JSON）。
> - **根路径（base）**：所有生成/校验的根目录。

---

## `plan`——生成计划与导出 Manifest

解析模板 (`template.json`) 与变量 (`vars.json`)，生成所有应创建的目录/文件列表。支持导出为 **manifest**（便于其他应用消费）。

**语法**

```bash
foldergen plan --template <模板文件> --vars <变量文件> --base <根目录>
               [--relative/--absolute]
               [--with-status]
               [--export-manifest <文件路径>]
               [--manifest-format json|jsonl]
               [--portable auto|windows|posix|mac|all|none]
               [--max-path-len N] [--follow-symlinks]
```

**常用参数**

| 参数 | 说明 |
|------|------|
| `--template` | 模板文件（JSON） |
| `--vars` | 变量文件（JSON） |
| `--base` | 根路径 |
| `--relative/--absolute` | manifest 中的 `path` 输出相对/绝对路径（默认相对） |
| `--with-status` | 附带 `check` 的结果（`existing/missing/conflict/planned`）与 `issues` |
| `--export-manifest` | 输出到文件（默认打印到终端） |
| `--manifest-format` | `json` 或 `jsonl`（逐行 JSON） |
| `--portable` | 名称合法性规则：`auto/windows/posix/mac/all/none` |
| `--max-path-len` | 路径长度提示阈值（默认 240） |

**示例**

```bash
# 1) 生成计划（终端显示，路径相对 base）
foldergen plan --template ./examples/template_basic.json --vars ./examples/vars_basic.json --base D:\temp

# 2) 导出相对路径清单
foldergen plan --template ./examples/template_basic.json --vars ./examples/vars_basic.json \
  --base D:\temp --export-manifest ./out/plan.json

# 3) 导出绝对路径清单 + 附带状态
foldergen plan --template ./examples/template_basic.json --vars ./examples/vars_basic.json \
  --base D:\temp --absolute --with-status --export-manifest ./out/plan_abs.json
```

**manifest 输出示例**（`--with-status` 时）：
```json
[
  {"type":"dir","path":"DemoProject/Release_202501","status":"existing"},
  {"type":"file","path":"DemoProject/README.md","status":"planned"}
]
```

---

## `simulate`——模拟生成（不写盘）

打印将要创建的目录/文件，**不**进行任何写入。

```bash
foldergen simulate --template ./examples/template_basic.json \
                   --vars ./examples/vars_basic.json \
                   --base D:\temp
```

输出示例：
```
[dir ] D:\temp\DemoProject
[dir ] D:\temp\DemoProject\Release_202501
[file] D:\temp\DemoProject\README.md
...
```

---

## `build`——实际生成结构

根据计划**真正创建**目录/文件。建议先跑一次 `simulate`。

```bash
foldergen build --template ./examples/template_basic.json \
                --vars ./examples/vars_basic.json \
                --base D:\temp
```

---

## `check`——校验现有文件系统

对比“模板计划”与“磁盘现状”，输出分类报告。支持 JSON 或表格输出，适合 CI。

**语法**
```bash
foldergen check --template <模板> --vars <变量> --base <根目录>
                [--format json|table]
                [--portable auto|windows|posix|mac|all|none]
                [--max-path-len N]
                [--follow-symlinks]
                [--strict]
```

**报告包含**

- **Missing**（缺失）：模板要求但磁盘不存在
- **Existing**（已存在）：与模板一致的目录/文件
- **Conflict**（类型冲突）：模板是目录/文件，但磁盘为相反类型
- **Extras**（多余）：磁盘存在但模板未定义（已排除根目录本身）
- **Name Issues**：非法字符、保留名、路径过长、大小写冲突（可配置）
- **Permission Issues**：访问/写入权限不足
- **Outside Base**：路径逃逸到 `--base` 之外（安全保护）

**示例**
```bash
# 表格输出 + Windows 名称规则
foldergen check --template ./examples/template_basic.json --vars ./examples/vars_basic.json \
                --base D:\temp --format table --portable windows

# 作为 CI 步骤（发现问题返回非零码）
foldergen check --template ./examples/template_basic.json --vars ./examples/vars_basic.json \
                --base D:\temp --strict
```

---

## `tree`——以树形方式展示结构

可视化展示结果（ASCII），或导出为 JSON/YAML 的树对象。`--status` 可注入 `check` 结果并着色。

**语法**
```bash
foldergen tree --template <模板> --vars <变量> --base <根目录>
               [--relative/--absolute]
               [--format tree|json|yaml]
               [--depth N]
               [--show-files/--no-show-files]
               [--status]
               [--portable ...] [--max-path-len N] [--follow-symlinks]
               [--out <文件路径>]
```

**示例**

```bash
# 1) 纯模板树（ASCII）
foldergen tree --template ./examples/template_basic.json --vars ./examples/vars_basic.json \
               --base D:\temp --depth 2

# 2) 带状态彩色树（existing=绿 / missing=红 / conflict=黄）
foldergen tree --template ./examples/template_basic.json --vars ./examples/vars_basic.json \
               --base D:\temp --status

# 3) 导出 JSON / YAML
foldergen tree --template ./examples/template_basic.json --vars ./examples/vars_basic.json \
               --base D:\temp --format json --out ./out/tree.json
foldergen tree --template ./examples/template_basic.json --vars ./examples/vars_basic.json \
               --base D:\temp --format yaml --out ./out/tree.yaml
```

ASCII 输出示例：
```
DemoProject
└─ Release_202501
   ├─ Char_A [missing]
   └─ Char_B
```

---

## Template 与 Vars 配置说明

### 模板（template.json）

- 使用嵌套结构描述目录与文件：
  - `name`：节点名（可含占位符/生成器）
  - `dirs`：子目录列表（数组）
  - `files`：当前目录下的文件名列表（数组）
- 支持**单花括号变量** `{var}` 与**双花括号生成器** `{{...}}` 的**组合**。

**示例**

```json
{
  "name": "DemoProject",
  "dirs": [
    {
      "name": "Release_{{date: start=2025-01-01; stop=2025-03-01; step=1m; fmt=%Y%m}}",
      "dirs": [
        {
          "name": "Char_{{alpha: start=A; stop=B}}",
          "dirs": [
            { "name": "LOD_{{int: start=0; stop=2; pad=2}}" }
          ]
        }
      ]
    }
  ],
  "files": [
    "README.md",
    "{project|slug}.py",
    "{episode|pad(3)}_intro.txt"
  ]
}
```

### 变量（vars.json）

为 `{var}` 提供值：

```json
{
  "project": "My Cool Project",
  "episode": 7
}
```

---

## 模板字符串语法

> **处理顺序**：先对 `{{...}}` 生成器做**笛卡尔积展开**，再对 `{var|filter}` 做变量替换与过滤。

### 单花括号变量 `{var}` 与过滤器

- 形式：`{key}` 或 `{key|filter(args)|filter2}`（可串联）
- 变量值来自 `vars.json` 的同名键
- **内置过滤器**：
  - `pad(n)`：将数字左侧补零到 n 位（如 `{episode|pad(3)}` → `007`）
  - `slug`：将字符串小写、空格替换为 `_`（如 `{project|slug}` → `my_cool_project`）
- 变量缺失会在计划阶段报错（`Missing variables in context`）。

**示例**
```
"{project|slug}_{episode|pad(2)}"  →  "my_cool_project_07"
```

### 双花括号生成器 `{{...}}`

在**同一个名字**内，可以放**一个或多个**生成器；系统会做**笛卡尔积**。

#### 1) 整数生成器 `{{int: ...}}`

| 参数 | 说明 | 示例 |
|------|------|------|
| `start` | 起始整数（含） | `0` |
| `stop` | 结束整数（含） | `2` |
| `step` | 步长（默认 `1`，可负） | `2` |
| `pad` | 左侧补零位数 | `2` |

**例**：`LOD_{{int: start=0; stop=2; pad=2}}` → `LOD_00`, `LOD_01`, `LOD_02`

#### 2) 字母生成器 `{{alpha: ...}}`

| 参数 | 说明 |
|------|------|
| `start` | 起始字母（单个字符） |
| `stop` | 结束字母（单个字符，含） |
| `step` | 步长（默认 `1`，可负） |

**例**：`Char_{{alpha: start=A; stop=C}}` → `Char_A`, `Char_B`, `Char_C`

#### 3) 日期生成器 `{{date: ...}}`

| 参数 | 说明 | 示例 |
|------|------|------|
| `start` | 起始日期（含，`YYYY-MM-DD`） | `2025-01-01` |
| `stop` | 结束日期（含，`YYYY-MM-DD`） | `2025-03-01` |
| `step` | 步长，`Xd`=天，`Xm`=月，`Xy`=年（`X` 可负） | `1m` |
| `fmt` | 输出格式（`strftime`） | `%Y%m`, `%Y%m%d` |

**例**：`Release_{{date: start=2025-01-01; stop=2025-03-01; step=1m; fmt=%Y%m}}`  
→ `Release_202501`, `Release_202502`, `Release_202503`

> 说明：生成器是**闭区间**（包含 `start` 与 `stop`）；多个生成器并存时做笛卡尔积展开。

---

## 常见问题 & 提示

- **为什么我的 `{{...}}` 被当成缺失变量？**  
  请确认你已使用最新版本的校验器：它会**忽略**双花括号生成器，仅检查单花括号 `{var}`。

- **Extras 中为什么不再显示根目录？**  
  我们已在检查逻辑中**排除了 `--base` 自身**，只报告真正“多余”的路径。

- **Windows 盘符被判为非法字符？**  
  已修正：名称检查在 Windows 下会**跳过盘符组件**，仅检查目录/文件名本身。

- **跨平台协作建议**：  
  - 在 CI 中启用最严格：`--portable all`；路径长度阈值建议 240~260。  
  - 需要仅关注某平台时使用 `--portable windows|posix|mac`。

- **安全提醒**：  
  - 工具会检查路径是否**逃逸**到 `--base` 之外。  
  - 在将 manifest/zip 交给其他系统时，也应在目标侧重新做一次越界检查。

---

© FolderGen — Template-driven Folder Structure Generator
