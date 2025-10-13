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
