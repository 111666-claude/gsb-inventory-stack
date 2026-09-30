# inventory-stack

背包堆叠：堆叠上限、拆分守恒、溢出记账、按物品索引，只用 Python 标准库。

```
python3 -m bagstack.cli --sample stack
python3 -m bagstack.cli --sample overflow
python3 -m bagstack.cli --sample split
python3 -m unittest discover -s tests -v
```

## 口径（README 为准）

- **堆叠上限**：每个槽位最多 `stack_max` 个；一个槽位满了要开新槽，
  槽位用完时多出来的部分计入该物品的 `overflow`，不许静默丢弃。
- **拆分守恒**：`split(item, count)` 把 `count` 个拆到新槽，拆分前后
  `total(item)` 与 `overflow_of(item)` 都不许变化，两块都不许超过 `stack_max`。
- **总量守恒**：`total(item) + overflow_of(item)` 等于累计加入数减去累计取出数。
- **查询代价**：加入与查询都按物品索引定位，`scanned_count()` 不随槽位数线性增长。
- **规模**：5000 个槽位、每秒 10 万次加入与查询，单次操作摊还 O(1)，内存 O(槽位数)。

## 输出契约（不改格式）

```
slots=3 total=7
total=6 overflow=4
total=3
scanned<=4000
```

## 目录

```
bagstack/core.py   堆叠、拆分与溢出
bagstack/cli.py    命令行入口
tests/             unittest 用例
```
