"""背包堆叠：堆叠上限、拆分守恒、溢出记账、按物品索引。

实现要点：
- 每个物品用字典索引它占用的槽位，加入与查询都按物品定位，
  不随槽位总数线性扫描。
- 每个物品维护一个未满槽位的最小堆（惰性删除），加入时先填满
  下标最小的未满槽位，再开新槽，最后计入 overflow，摊还 O(1)。
"""


from heapq import heappop, heappush


class BagError(ValueError):
    """背包操作不合法。"""


class Bag:
    """一个固定槽位数的背包。"""

    def __init__(self, slot_count, stack_max):
        if slot_count < 0:
            raise BagError("槽位数不能为负")
        if stack_max < 1:
            raise BagError("堆叠上限至少为 1")
        self.slot_count = slot_count
        self.stack_max = stack_max
        self.slots = []
        self.overflow = {}
        self.scanned = 0
        self._index = {}
        self._partials = {}

    def _partial_heap(self, item):
        return self._partials.setdefault(item, [])

    def _is_partial(self, item, slot_index):
        return (
            slot_index < len(self.slots)
            and self.slots[slot_index][0] == item
            and self.slots[slot_index][1] < self.stack_max
        )

    def _drop_slot(self, slot_index):
        """删掉一个空槽位：用末尾槽位补上，保持 slots 紧凑。"""
        last_index = len(self.slots) - 1
        name, _ = self.slots[slot_index]
        named_slots = self._index[name]
        del named_slots[slot_index]
        if slot_index != last_index:
            moved_name, moved_count = self.slots[last_index]
            self.slots[slot_index] = (moved_name, moved_count)
            moved_slots = self._index[moved_name]
            del moved_slots[last_index]
            moved_slots[slot_index] = None
            if moved_count < self.stack_max:
                heappush(self._partial_heap(moved_name), slot_index)
        self.slots.pop()
        if not named_slots:
            del self._index[name]

    def find_slot(self, item):
        """找某个物品下标最小的槽位，没有返回 -1。"""
        slot_indexes = self._index.get(item)
        if not slot_indexes:
            return -1
        return min(slot_indexes)

    def add(self, item, count):
        """加入物品：先填满已有的未满槽位，再开新槽，余量计入 overflow。"""
        if count < 1:
            raise BagError("加入数量必须为正")
        heap = self._partial_heap(item)
        while count > 0 and heap:
            slot_index = heap[0]
            if not self._is_partial(item, slot_index):
                heappop(heap)
                continue
            name, have = self.slots[slot_index]
            self.scanned += 1
            move = min(self.stack_max - have, count)
            have += move
            count -= move
            self.slots[slot_index] = (name, have)
            if have == self.stack_max:
                heappop(heap)
        while count > 0 and len(self.slots) < self.slot_count:
            move = min(count, self.stack_max)
            slot_index = len(self.slots)
            self.slots.append((item, move))
            self._index.setdefault(item, {})[slot_index] = None
            if move < self.stack_max:
                heappush(heap, slot_index)
            count -= move
        if count > 0:
            self.overflow[item] = self.overflow.get(item, 0) + count

    def split(self, item, count):
        """把 count 个拆到新槽，拆分前后 total 与 overflow 都不变。"""
        if count < 1:
            raise BagError("拆分数量必须为正")
        slot_indexes = self._index.get(item)
        if not slot_indexes:
            raise BagError("没有这种物品：%s" % item)
        if len(self.slots) >= self.slot_count:
            raise BagError("没有空槽位可以拆分")
        source = -1
        for slot_index in sorted(slot_indexes):
            if self.slots[slot_index][1] > count:
                source = slot_index
                break
        if source < 0:
            raise BagError("拆不出 %d 个：%s" % (count, item))
        name, have = self.slots[source]
        self.slots[source] = (name, have - count)
        new_index = len(self.slots)
        self.slots.append((name, count))
        self._index[name][new_index] = None
        heappush(self._partial_heap(name), source)
        heappush(self._partial_heap(name), new_index)
        return True

    def remove(self, item, count):
        """取出 count 个：先扣槽位（下标从大到小），不够再扣 overflow。"""
        if count < 1:
            raise BagError("取出数量必须为正")
        available = self.total(item) + self.overflow_of(item)
        if count > available:
            raise BagError("取出超过持有：%s" % item)
        slot_indexes = self._index.get(item)
        if slot_indexes:
            for slot_index in sorted(slot_indexes, reverse=True):
                if count == 0:
                    break
                name, have = self.slots[slot_index]
                take = min(have, count)
                have -= take
                count -= take
                if have == 0:
                    self._drop_slot(slot_index)
                else:
                    self.slots[slot_index] = (name, have)
                    heappush(self._partial_heap(name), slot_index)
        if count > 0:
            self.overflow[item] = self.overflow.get(item, 0) - count
        return True

    def take(self, item, count):
        """remove 的别名。"""
        return self.remove(item, count)

    def total(self, item):
        """背包里该物品的总数（不含 overflow），按物品索引定位。"""
        total = 0
        for slot_index in self._index.get(item, ()):
            self.scanned += 1
            total += self.slots[slot_index][1]
        return total

    def overflow_of(self, item):
        """该物品计入溢出的数量。"""
        return self.overflow.get(item, 0)

    def scanned_count(self):
        return self.scanned
