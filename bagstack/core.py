"""背包堆叠：堆叠上限、拆分守恒、溢出记账、按物品索引。

缺陷：堆叠上限不生效、拆分不守恒、溢出直接丢且不记账、每次加入都全扫所有槽位。
"""


class BagError(ValueError):
    """背包操作不合法。"""


class Bag:
    """一个固定槽位数的背包。"""

    def __init__(self, slot_count, stack_max):
        self.slot_count = slot_count
        self.stack_max = stack_max
        self.slots = []
        self.overflow = {}
        self.scanned = 0

    def find_slot(self, item):
        """找某个物品所在的槽位。缺陷：线性扫描全部槽位。"""
        for index, (name, _) in enumerate(self.slots):
            self.scanned += 1
            if name == item:
                return index
        return -1

    def add(self, item, count):
        """加入物品。缺陷：不看堆叠上限，槽位满了也不记账地丢掉。"""
        index = self.find_slot(item)
        if index >= 0:
            name, have = self.slots[index]
            self.slots[index] = (name, have + count)
            return
        self.slots.append((item, count))

    def split(self, item, count):
        """从堆叠里拆出 count 个。缺陷：拆完之后总量不守恒。"""
        index = self.find_slot(item)
        if index < 0:
            raise BagError("没有这种物品：%s" % item)
        name, have = self.slots[index]
        self.slots[index] = (name, count)
        self.slots.append((name, have))
        return True

    def total(self, item):
        """背包里的总数。缺陷：每次全扫槽位。"""
        total = 0
        for name, count in self.slots:
            self.scanned += 1
            if name == item:
                total += count
        return total

    def overflow_of(self, item):
        """溢出的数量。缺陷：从来没被写过。"""
        return self.overflow.get(item, 0)

    def scanned_count(self):
        return self.scanned
