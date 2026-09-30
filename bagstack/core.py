"""背包堆叠：堆叠上限、拆分守恒、溢出记账、按物品索引。

- 每个槽位最多 stack_max 个，满了开新槽，槽位用完的余量计入 overflow，
  不允许静默丢弃。
- 每个物品维护槽位索引、未满槽位索引和槽位总数，加入、拆分、取出与查询
  都按物品索引定位，单次操作摊还 O(1)，scanned 只随操作次数增长，
  不随槽位总数线性增长。
- 任何槽位数量恒在 [1, stack_max]；清空的槽位用末尾槽位交换填补，
  相同操作序列永远得到相同结果。
"""


class BagError(ValueError):
    """背包操作不合法。"""


class Bag:
    """一个固定槽位数的背包。"""

    def __init__(self, slot_count, stack_max):
        if slot_count < 0:
            raise BagError("槽位数不能为负：%r" % (slot_count,))
        if stack_max < 1:
            raise BagError("堆叠上限至少为 1：%r" % (stack_max,))
        self.slot_count = slot_count
        self.stack_max = stack_max
        self.slots = []
        self.overflow = {}
        self.scanned = 0
        self._index = {}
        self._partial = {}
        self._totals = {}

    def _index_add(self, item, idx):
        self._index.setdefault(item, {})[idx] = None

    def _index_discard(self, item, idx):
        found = self._index.get(item)
        if found is not None:
            found.pop(idx, None)
            if not found:
                del self._index[item]

    def _partial_add(self, item, idx):
        self._partial.setdefault(item, {})[idx] = None

    def _partial_discard(self, item, idx):
        found = self._partial.get(item)
        if found is not None:
            found.pop(idx, None)
            if not found:
                del self._partial[item]

    def _remove_slot(self, idx):
        """删掉空槽：用末尾槽位交换填补，保持槽位列表紧凑。"""
        last = len(self.slots) - 1
        name, _ = self.slots[idx]
        moved_name, moved_count = self.slots[last]
        self.slots.pop()
        self._index_discard(name, idx)
        self._partial_discard(name, idx)
        if idx != last:
            self.slots[idx] = (moved_name, moved_count)
            self._index_discard(moved_name, last)
            self._index_add(moved_name, idx)
            self._partial_discard(moved_name, last)
            if moved_count < self.stack_max:
                self._partial_add(moved_name, idx)

    def find_slot(self, item):
        """找某个物品最早出现的槽位，没有返回 -1。按物品索引 O(1)。"""
        self.scanned += 1
        found = self._index.get(item)
        if found:
            return next(iter(found))
        return -1

    def total(self, item):
        """背包里（不含溢出）的总数。按物品索引 O(1)，不扫槽位。"""
        return self._totals.get(item, 0)

    def overflow_of(self, item):
        """溢出的数量。"""
        return self.overflow.get(item, 0)

    def scanned_count(self):
        return self.scanned

    def add(self, item, count):
        """加入物品：先补未满槽，再开新槽，槽位用尽的余量计入 overflow。"""
        if count < 1:
            raise BagError("加入数量必须为正：%r" % (count,))
        self.scanned += 1
        remaining = count
        partial = self._partial.get(item)
        if partial:
            for idx in list(partial):
                self.scanned += 1
                name, have = self.slots[idx]
                put = min(self.stack_max - have, remaining)
                if put <= 0:
                    continue
                have += put
                self.slots[idx] = (name, have)
                self._totals[item] = self._totals.get(item, 0) + put
                remaining -= put
                if have >= self.stack_max:
                    self._partial_discard(item, idx)
                if remaining == 0:
                    break
        while remaining > 0 and len(self.slots) < self.slot_count:
            put = min(self.stack_max, remaining)
            idx = len(self.slots)
            self.slots.append((item, put))
            self._index_add(item, idx)
            if put < self.stack_max:
                self._partial_add(item, idx)
            self._totals[item] = self._totals.get(item, 0) + put
            remaining -= put
        if remaining > 0:
            self.overflow[item] = self.overflow.get(item, 0) + remaining

    def split(self, item, count):
        """把 count 个拆到新槽。

        拆分前后 total(item) 与 overflow_of(item) 都不变；原槽与新槽数量
        都在 [1, stack_max]。从最早出现、且数量大于 count 的槽位拆。
        """
        if count < 1:
            raise BagError("拆分数量必须为正：%r" % (count,))
        self.scanned += 1
        found = self._index.get(item)
        if not found:
            raise BagError("没有这种物品：%s" % item)
        source = -1
        for idx in found:
            self.scanned += 1
            if self.slots[idx][1] > count:
                source = idx
                break
        if source < 0:
            raise BagError("没有足够大的堆叠可拆：%s" % item)
        if len(self.slots) >= self.slot_count:
            raise BagError("没有空槽位可拆")
        have = self.slots[source][1]
        self.slots[source] = (item, have - count)
        self._partial_add(item, source)
        idx = len(self.slots)
        self.slots.append((item, count))
        self._index_add(item, idx)
        if count < self.stack_max:
            self._partial_add(item, idx)
        return True

    def remove(self, item, count):
        """取出物品：先取槽位，槽位不够再取溢出。

        total(item) + overflow_of(item) 恰好好减少 count；持有不足时报错。
        """
        if count < 1:
            raise BagError("取出数量必须为正：%r" % (count,))
        self.scanned += 1
        if count > self._totals.get(item, 0) + self.overflow.get(item, 0):
            raise BagError("取出数量超过持有：%s" % item)
        remaining = count
        while remaining > 0:
            found = self._index.get(item)
            if not found:
                break
            idx = next(iter(found))
            self.scanned += 1
            name, have = self.slots[idx]
            take = min(have, remaining)
            remaining -= take
            self._totals[item] -= take
            if take == have:
                self._remove_slot(idx)
            else:
                self.slots[idx] = (name, have - take)
                self._partial_add(item, idx)
        if remaining > 0:
            left = self.overflow[item] - remaining
            if left > 0:
                self.overflow[item] = left
            else:
                del self.overflow[item]
        return True
