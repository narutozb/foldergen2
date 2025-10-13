# 1) 相对路径树（默认），展示目录+文件，保持模板顺序
foldergen tree --template ./examples/template_basic.json --vars ./examples/vars_basic.json --base D:\temp

# 2) 限制深度，只看前两层
foldergen tree --template ./examples/template_basic.json --vars ./examples/vars_basic.json --base D:\temp --depth 2

# 3) 只看目录，不显示文件
foldergen tree --template ./examples/template_basic.json --vars ./examples/vars_basic.json --base D:\temp --no-show-files

# 4) 按名称字母序排序
foldergen tree --template ./examples/template_basic.json --vars ./examples/vars_basic.json --base D:\temp --sort alpha

# 5) 显示为绝对路径视角（根名 <root>）
foldergen tree --template ./examples/template_basic.json --vars ./examples/vars_basic.json --base D:\temp --absolute


#
# 相对路径 + JSON
foldergen plan --template ./examples/template_basic.json --vars ./examples/vars_basic.json --base D:\temp --export-manifest ./out/plan.json

# 绝对路径 + JSON Lines
foldergen plan --template ./examples/template_basic.json --vars ./examples/vars_basic.json --base D:\temp --absolute --export-manifest ./out/plan.jsonl --manifest-format jsonl


# 终端 ASCII（默认）
foldergen tree --template ./examples/template_basic.json --vars ./examples/vars_basic.json --base D:\temp --depth 2

# 导出 JSON
foldergen tree --template ./examples/template_basic.json --vars ./examples/vars_basic.json --base D:\temp --format json --out ./out/tree.json

# 导出 YAML（若系统未装 PyYAML，将使用简单降级文本）
foldergen tree --template ./examples/template_basic.json --vars ./examples/vars_basic.json --base D:\temp --format yaml --out ./out/tree.yaml

# 导出 Graphviz DOT
foldergen tree --template ./examples/template_basic.json --vars ./examples/vars_basic.json --base D:\temp --format dot --out ./out/tree.dot
# 渲染为 PNG（本地安装 graphviz 后）
# dot -Tpng ./out/tree.dot -o ./out/tree.png


foldergen tree --template ./examples/template_basic.json --vars ./examples/vars_basic.json --base D:\temp --status --relative --format tree --depth 3 --portable windows


# JSON（相对路径）
foldergen plan --template ./examples/template_basic.json --vars ./examples/vars_basic.json --base D:\temp --with-status --export-manifest ./out/plan_with_status.json

# JSONL（绝对路径）
foldergen plan --template ./examples/template_basic.json --vars ./examples/vars_basic.json --base D:\temp --absolute --with-status --manifest-format jsonl --export-manifest ./out/plan_abs.jsonl
