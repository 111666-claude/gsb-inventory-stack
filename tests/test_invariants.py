"""不变量与对照测试：堆叠上限、溢出记账、拆分守恒、总量守恒、查询代价。"""

import contextlib
import io
import random
import unittest

from bagstack.cli import main as cli_main
from bagstack.core import Bag, BagError


class ReferenceBag:
    """参考实现：按物品索引 + 分堆填槽 + 溢出记账。

    与 bagstack.core.Bag 同一套槽位策略，但只用最直白的列表写法，
    用来交叉验证带索引优化的实现。
    """

    def __init__(self, slot_count, stack_max):
        self.slot_count = slot_count
        self.stack_max = stack_max
        self.slots = []
        self.overflow = {}
        self.order = {}
        self.partial = {}

    def _discard_from(self, table, item, idx):
        found = table.get(item)
        if found is not None and idx in found:
            found.remove(idx)
            if not found:
                del table[item]

    def _discard_slot(self, idx):
        name, _ = self.slots[idx]
        last = len(self.slots) - 1
        moved_name, moved_count = self.slots[last]
        self.slots.pop()
        self._discard_from(self.order, name, idx)
        self._discard_from(self.partial, name, idx)
        if idx != last:
            self.slots[idx] = (moved_name, moved_count)
            self._discard_from(self.order, moved_name, last)
            self.order.setdefault(moved_name, []).append(idx)
            self._discard_from(self.partial, moved_name, last)
            if moved_count < self.stack_max:
                self.partial.setdefault(moved_name, []).append(idx)

    def add(self, item, count):
        if count < 1:
            raise BagError("加入数量必须为正：%r" % (count,))
        remaining = count
        for idx in list(self.partial.get(item, ())):
            name, have = self.slots[idx]
            put = min(self.stack_max - have, remaining)
            if put <= 0:
                continue
            have += put
            self.slots[idx] = (name, have)
            remaining -= put
            if have >= self.stack_max:
                self._discard_from(self.partial, item, idx)
            if remaining == 0:
                break
        while remaining > 0 and len(self.slots) < self.slot_count:
            put = min(self.stack_max, remaining)
            self.slots.append((item, put))
            idx = len(self.slots) - 1
            self.order.setdefault(item, []).append(idx)
            if put < self.stack_max:
                self.partial.setdefault(item, []).append(idx)
            remaining -= put
        if remaining > 0:
            self.overflow[item] = self.overflow.get(item, 0) + remaining

    def split(self, item, count):
        if count < 1:
            raise BagError("拆分数量必须为正：%r" % (count,))
        if item not in self.order:
            raise BagError("没有这种物品：%s" % item)
        source = -1
        for idx in self.order[item]:
            if self.slots[idx][1] > count:
                source = idx
                break
        if source < 0:
            raise BagError("没有足够大的堆叠可拆：%s" % item)
        if len(self.slots) >= self.slot_count:
            raise BagError("没有空槽位可拆")
        name, have = self.slots[source]
        self.slots[source] = (name, have - count)
        if source not in self.partial.get(item, ()):
            self.partial.setdefault(item, []).append(source)
        self.slots.append((item, count))
        idx = len(self.slots) - 1
        self.order.setdefault(item, []).append(idx)
        if count < self.stack_max:
            self.partial.setdefault(item, []).append(idx)
        return True

    def remove(self, item, count):
        if count < 1:
            raise BagError("取出数量必须为正：%r" % (count,))
        in_slots = sum(have for name, have in self.slots if name == item)
        if count > in_slots + self.overflow.get(item, 0):
            raise BagError("取出数量超过持有：%s" % item)
        remaining = count
        while remaining > 0 and item in self.order:
            idx = self.order[item][0]
            name, have = self.slots[idx]
            take = min(have, remaining)
            remaining -= take
            if take == have:
                self._discard_slot(idx)
            else:
                self.slots[idx] = (name, have - take)
                if idx not in self.partial.get(item, ()):
                    self.partial.setdefault(item, []).append(idx)
        if remaining > 0:
            left = self.overflow[item] - remaining
            if left > 0:
                self.overflow[item] = left
            else:
                del self.overflow[item]
        return True

    def total(self, item):
        return sum(have for name, have in self.slots if name == item)

    def overflow_of(self, item):
        return self.overflow.get(item, 0)


class StackCapTest(unittest.TestCase):
    def test_stack_cap_opens_new_slots(self):
        bag = Bag(10, 3)
        bag.add("ore", 7)
        self.assertEqual(bag.slots, [("ore", 3), ("ore", 3), ("ore", 1)])
        self.assertEqual(bag.total("ore"), 7)

    def test_every_slot_within_cap(self):
        bag = Bag(20, 4)
        bag.add("ore", 17)
        bag.add("gem", 9)
        for _, count in bag.slots:
            self.assertGreaterEqual(count, 1)
            self.assertLessEqual(count, 4)

    def test_merge_fills_partial_before_new_slot(self):
        bag = Bag(10, 3)
        bag.add("ore", 2)
        bag.add("ore", 5)
        self.assertEqual(bag.slots, [("ore", 3), ("ore", 3), ("ore", 1)])


class OverflowTest(unittest.TestCase):
    def test_slots_full_goes_to_overflow(self):
        bag = Bag(2, 3)
        bag.add("ore", 10)
        self.assertEqual(bag.total("ore"), 6)
        self.assertEqual(bag.overflow_of("ore"), 4)

    def test_overflow_not_silently_dropped(self):
        bag = Bag(1, 2)
        bag.add("ore", 5)
        self.assertEqual(bag.total("ore") + bag.overflow_of("ore"), 5)
        bag.remove("ore", 4)
        self.assertEqual(bag.total("ore") + bag.overflow_of("ore"), 1)
        self.assertEqual(bag.overflow_of("ore"), 1)

    def test_zero_slots_all_overflow(self):
        bag = Bag(0, 3)
        bag.add("ore", 4)
        self.assertEqual(bag.total("ore"), 0)
        self.assertEqual(bag.overflow_of("ore"), 4)


class SplitConservationTest(unittest.TestCase):
    def test_split_preserves_total_and_overflow(self):
        bag = Bag(5, 3)
        bag.add("ore", 8)
        before = (bag.total("ore"), bag.overflow_of("ore"))
        bag.split("ore", 1)
        self.assertEqual((bag.total("ore"), bag.overflow_of("ore")), before)

    def test_split_parts_within_cap(self):
        bag = Bag(5, 3)
        bag.add("ore", 3)
        bag.split("ore", 1)
        self.assertEqual(bag.slots, [("ore", 2), ("ore", 1)])

    def test_split_without_free_slot_raises(self):
        bag = Bag(2, 3)
        bag.add("ore", 6)
        before = (bag.slots[:], bag.total("ore"), bag.overflow_of("ore"))
        with self.assertRaises(BagError):
            bag.split("ore", 1)
        self.assertEqual((bag.slots[:], bag.total("ore"), bag.overflow_of("ore")), before)

    def test_split_whole_stack_raises(self):
        bag = Bag(5, 3)
        bag.add("ore", 3)
        with self.assertRaises(BagError):
            bag.split("ore", 3)
        self.assertEqual(bag.total("ore"), 3)


class RemoveConservationTest(unittest.TestCase):
    def test_remove_drains_slots_then_overflow(self):
        bag = Bag(1, 2)
        bag.add("ore", 5)
        bag.remove("ore", 3)
        self.assertEqual(bag.total("ore"), 0)
        self.assertEqual(bag.overflow_of("ore"), 2)

    def test_remove_compacts_slots(self):
        bag = Bag(3, 4)
        bag.add("ore", 10)
        bag.remove("ore", 5)
        self.assertEqual(bag.slots, [("ore", 2), ("ore", 3)])
        self.assertEqual(bag.total("ore"), 5)

    def test_remove_more_than_held_raises(self):
        bag = Bag(2, 3)
        bag.add("ore", 4)
        with self.assertRaises(BagError):
            bag.remove("ore", 5)
        self.assertEqual(bag.total("ore") + bag.overflow_of("ore"), 4)


class ScanCostTest(unittest.TestCase):
    def test_scanned_not_linear_in_slots(self):
        bag = Bag(100000, 99)
        for index in range(2000):
            bag.add("item-%d" % index, 1)
        for _ in range(2000):
            bag.total("item-1999")
        self.assertLessEqual(bag.scanned_count(), 4000)

    def test_scanned_grows_with_ops_not_slots(self):
        bag = Bag(5000, 99)
        for index in range(2000):
            bag.add("item-%d" % index, 1)
        base = bag.scanned_count()
        for round_index in range(1000):
            bag.add("item-%d" % (round_index % 2000), 1)
            bag.total("item-0")
        self.assertLessEqual(bag.scanned_count() - base, 3 * 1000)


class DeterminismTest(unittest.TestCase):
    def test_same_sequence_same_result(self):
        def run():
            rng = random.Random(7)
            bag = Bag(6, 4)
            for _ in range(300):
                op = rng.choice(("add", "split", "remove"))
                item = "item-%d" % rng.randint(0, 2)
                count = rng.randint(1, 6)
                try:
                    getattr(bag, op)(item, count)
                except BagError:
                    pass
            return bag

        first, second = run(), run()
        self.assertEqual(first.slots, second.slots)
        self.assertEqual(first.overflow, second.overflow)


class RandomizedDiffTest(unittest.TestCase):
    """随机序列与参考实现逐步比对：槽位、total、overflow 差异必须为 0。"""

    def _apply(self, bag, ref, op, item, count):
        bag_error = ref_error = None
        try:
            getattr(bag, op)(item, count)
        except BagError as exc:
            bag_error = exc
        try:
            getattr(ref, op)(item, count)
        except BagError as exc:
            ref_error = exc
        self.assertEqual(bag_error is None, ref_error is None,
                         "%s(%s, %d) 一边报错一边没报" % (op, item, count))
        return bag_error is None

    def _assert_same_state(self, bag, ref, items, added, removed):
        self.assertEqual(bag.slots, ref.slots)
        self.assertEqual(bag.overflow, ref.overflow)
        for item in items:
            self.assertEqual(bag.total(item), ref.total(item))
            self.assertEqual(bag.overflow_of(item), ref.overflow_of(item))
            self.assertEqual(
                bag.total(item) + bag.overflow_of(item),
                added.get(item, 0) - removed.get(item, 0),
            )
        for _, count in bag.slots:
            self.assertGreaterEqual(count, 1)
            self.assertLessEqual(count, bag.stack_max)

    def test_200_random_sequences_match_reference(self):
        rng = random.Random(20260930)
        for _ in range(200):
            slot_count = rng.randint(0, 12)
            stack_max = rng.randint(1, 6)
            items = ["item-%d" % i for i in range(rng.randint(1, 4))]
            bag = Bag(slot_count, stack_max)
            ref = ReferenceBag(slot_count, stack_max)
            added, removed = {}, {}
            for _ in range(rng.randint(1, 120)):
                op = rng.choice(("add", "add", "split", "remove", "remove"))
                item = rng.choice(items)
                count = rng.randint(1, 2 * stack_max + 1)
                if self._apply(bag, ref, op, item, count):
                    ledger = added if op == "add" else removed if op == "remove" else None
                    if ledger is not None:
                        ledger[item] = ledger.get(item, 0) + count
                self._assert_same_state(bag, ref, items, added, removed)


class CliContractTest(unittest.TestCase):
    def _run(self, sample):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli_main(["--sample", sample])
        return buf.getvalue().strip()

    def test_stack_sample(self):
        self.assertEqual(self._run("stack"), "slots=3 total=7")

    def test_overflow_sample(self):
        self.assertEqual(self._run("overflow"), "total=6 overflow=4")

    def test_split_sample(self):
        self.assertEqual(self._run("split"), "total=3")

    def test_scan_sample(self):
        output = self._run("scan")
        self.assertTrue(output.startswith("scanned="))
        self.assertLessEqual(int(output.split("=")[1]), 4000)


if __name__ == "__main__":
    unittest.main()
