"""堆叠上限、溢出记账、拆分守恒、查询代价，以及与朴素参考实现的随机对照。"""

import io
import random
import unittest
from contextlib import redirect_stdout

from bagstack import cli
from bagstack.core import Bag, BagError


class StackLimitTest(unittest.TestCase):
    def test_fill_slots_up_to_stack_max(self):
        bag = Bag(10, 3)
        bag.add("ore", 7)
        self.assertEqual([count for _, count in bag.slots], [3, 3, 1])
        self.assertEqual(len(bag.slots), 3)
        self.assertEqual(bag.total("ore"), 7)

    def test_topping_up_full_stack_opens_new_slot(self):
        bag = Bag(10, 3)
        bag.add("ore", 2)
        bag.add("ore", 3)
        self.assertEqual([count for _, count in bag.slots], [3, 2])
        self.assertEqual(bag.total("ore"), 5)

    def test_stack_max_one_uses_one_slot_each(self):
        bag = Bag(3, 1)
        bag.add("ore", 3)
        self.assertEqual([count for _, count in bag.slots], [1, 1, 1])

    def test_slot_counts_stay_in_invariant_range(self):
        bag = Bag(10, 3)
        for _ in range(20):
            bag.add("ore", 2)
        for _, count in bag.slots:
            self.assertGreaterEqual(count, 1)
            self.assertLessEqual(count, 3)


class OverflowTest(unittest.TestCase):
    def test_overflow_is_accounted_not_dropped(self):
        bag = Bag(2, 3)
        bag.add("ore", 10)
        self.assertEqual(bag.total("ore"), 6)
        self.assertEqual(bag.overflow_of("ore"), 4)
        self.assertEqual(bag.total("ore") + bag.overflow_of("ore"), 10)

    def test_overflow_only_when_slots_exhausted(self):
        bag = Bag(3, 3)
        bag.add("a", 7)
        bag.add("b", 5)
        self.assertEqual(bag.overflow_of("a"), 0)
        self.assertEqual(bag.overflow_of("b"), 5)
        self.assertEqual(bag.total("a") + bag.total("b") + 5, 12)

    def test_later_additions_keep_overflowing(self):
        bag = Bag(1, 2)
        bag.add("ore", 3)
        bag.add("ore", 4)
        self.assertEqual(bag.total("ore"), 2)
        self.assertEqual(bag.overflow_of("ore"), 5)


class SplitConservationTest(unittest.TestCase):
    def test_split_preserves_total_and_overflow(self):
        bag = Bag(6, 3)
        bag.add("ore", 3)
        bag.add("ore", 10)
        before_total = bag.total("ore")
        before_overflow = bag.overflow_of("ore")
        bag.split("ore", 1)
        self.assertEqual(bag.total("ore"), before_total)
        self.assertEqual(bag.overflow_of("ore"), before_overflow)
        self.assertEqual([count for _, count in bag.slots], [2, 3, 3, 3, 1, 1])

    def test_split_piles_stay_within_stack_max(self):
        bag = Bag(5, 4)
        bag.add("ore", 4)
        bag.split("ore", 2)
        for _, count in bag.slots:
            self.assertGreaterEqual(count, 1)
            self.assertLessEqual(count, 4)

    def test_split_more_than_stack_holds_raises(self):
        bag = Bag(5, 3)
        bag.add("ore", 3)
        with self.assertRaises(BagError):
            bag.split("ore", 3)

    def test_split_without_free_slot_raises(self):
        bag = Bag(2, 3)
        bag.add("ore", 6)
        with self.assertRaises(BagError):
            bag.split("ore", 1)


class TotalConservationTest(unittest.TestCase):
    def test_add_minus_remove_equals_total_plus_overflow(self):
        bag = Bag(3, 2)
        bag.add("ore", 10)
        bag.remove("ore", 4)
        self.assertEqual(bag.total("ore") + bag.overflow_of("ore"), 6)
        bag.add("ore", 3)
        self.assertEqual(bag.total("ore") + bag.overflow_of("ore"), 9)
        bag.remove("ore", 9)
        self.assertEqual(bag.total("ore") + bag.overflow_of("ore"), 0)

    def test_remove_overdrawn_raises(self):
        bag = Bag(3, 2)
        bag.add("ore", 3)
        with self.assertRaises(BagError):
            bag.remove("ore", 4)

    def test_same_sequence_is_deterministic(self):
        def run():
            bag = Bag(6, 3)
            bag.add("ore", 8)
            bag.add("gem", 5)
            bag.split("ore", 1)
            bag.remove("ore", 4)
            bag.add("ore", 2)
            return list(bag.slots), bag.overflow.copy()
        self.assertEqual(run(), run())


class QueryCostTest(unittest.TestCase):
    def test_scanned_is_bounded_by_4000(self):
        bag = Bag(100000, 99)
        for index in range(2000):
            bag.add("item-%d" % index, 1)
        for _ in range(2000):
            bag.total("item-1999")
        self.assertLessEqual(bag.scanned_count(), 4000)

    def test_scanned_does_not_grow_with_total_slots(self):
        values = []
        for item_count in (100, 1000, 2000):
            bag = Bag(100000, 99)
            for index in range(item_count):
                bag.add("item-%d" % index, 1)
            before = bag.scanned_count()
            for _ in range(100):
                bag.total("item-1")
            values.append(bag.scanned_count() - before)
        self.assertEqual(values, [100, 100, 100])


class CliSampleTest(unittest.TestCase):
    def run_sample(self, sample):
        output = io.StringIO()
        with redirect_stdout(output):
            cli.main(["--sample", sample])
        return output.getvalue().strip()

    def test_samples_match_contract(self):
        self.assertEqual(self.run_sample("stack"), "slots=3 total=7")
        self.assertEqual(self.run_sample("overflow"), "total=6 overflow=4")
        self.assertEqual(self.run_sample("split"), "total=3")
        self.assertEqual(self.run_sample("scan"), "scanned=2000")


class ReferenceBag:
    """朴素参考实现：按物品索引（顺序扫槽）+ 分堆填槽 + 溢出记账。

    与 Bag 采用同一套确定的口径：
    - add 先按下标从小到大填满该物品的未满槽，再开新槽，余量记 overflow；
    - split 从下标最小且持有量 > count 的槽拆，新槽追加到末尾；
    - remove 按下标从大到小扣槽位，空槽用末尾槽位补上，再扣 overflow。
    """

    def __init__(self, slot_count, stack_max):
        self.slot_count = slot_count
        self.stack_max = stack_max
        self.slots = []
        self.overflow = {}

    def add(self, item, count):
        for index, (name, have) in enumerate(self.slots):
            if count == 0:
                break
            if name != item or have >= self.stack_max:
                continue
            move = min(self.stack_max - have, count)
            self.slots[index] = (name, have + move)
            count -= move
        while count > 0 and len(self.slots) < self.slot_count:
            move = min(count, self.stack_max)
            self.slots.append((item, move))
            count -= move
        if count > 0:
            self.overflow[item] = self.overflow.get(item, 0) + count

    def split(self, item, count):
        if not any(name == item for name, _ in self.slots):
            raise BagError("没有这种物品：%s" % item)
        if len(self.slots) >= self.slot_count:
            raise BagError("没有空槽位可以拆分")
        for index in range(len(self.slots)):
            name, have = self.slots[index]
            if name == item and have > count:
                self.slots[index] = (name, have - count)
                self.slots.append((name, count))
                return True
        raise BagError("拆不出 %d 个：%s" % (count, item))

    def remove(self, item, count):
        available = self.total(item) + self.overflow.get(item, 0)
        if count > available:
            raise BagError("取出超过持有：%s" % item)
        index = len(self.slots) - 1
        while count > 0 and index >= 0:
            name, have = self.slots[index]
            if name != item:
                index -= 1
                continue
            take = min(have, count)
            have -= take
            count -= take
            if have == 0:
                self.slots[index] = self.slots[-1]
                self.slots.pop()
                if index >= len(self.slots):
                    index = len(self.slots) - 1
            else:
                self.slots[index] = (name, have)
                index -= 1
        if count > 0:
            self.overflow[item] -= count
        return True

    def total(self, item):
        return sum(c for name, c in self.slots if name == item)

    def overflow_of(self, item):
        return self.overflow.get(item, 0)


class RandomizedConformanceTest(unittest.TestCase):
    def test_200_random_sequences_match_reference(self):
        rng = random.Random(20260930)
        items = ["a", "b", "c", "d"]
        for _ in range(200):
            slot_count = rng.randint(1, 12)
            stack_max = rng.randint(1, 5)
            bag = Bag(slot_count, stack_max)
            ref = ReferenceBag(slot_count, stack_max)
            added = {}
            removed = {}
            operations = []
            for _ in range(60):
                item = rng.choice(items)
                choice = rng.random()
                if choice < 0.5:
                    count = rng.randint(1, 8)
                    bag.add(item, count)
                    ref.add(item, count)
                    added[item] = added.get(item, 0) + count
                    operations.append(("add", item, count))
                elif choice < 0.75:
                    count = rng.randint(1, 6)
                    operations.append(("split", item, count))
                    bag_error = ref_error = None
                    try:
                        bag.split(item, count)
                    except BagError as exc:
                        bag_error = exc
                    try:
                        ref.split(item, count)
                    except BagError as exc:
                        ref_error = exc
                    self.assertEqual(
                        bag_error is None, ref_error is None, operations
                    )
                else:
                    count = rng.randint(1, 8)
                    operations.append(("remove", item, count))
                    bag_error = ref_error = None
                    try:
                        bag.remove(item, count)
                    except BagError as exc:
                        bag_error = exc
                    try:
                        ref.remove(item, count)
                    except BagError as exc:
                        ref_error = exc
                    if bag_error is None:
                        removed[item] = removed.get(item, 0) + count
                    self.assertEqual(
                        bag_error is None, ref_error is None, operations
                    )

                self.assertEqual(bag.slots, ref.slots, operations)
                for name in items:
                    self.assertEqual(
                        bag.total(name), ref.total(name), operations
                    )
                    self.assertEqual(
                        bag.overflow_of(name),
                        ref.overflow_of(name),
                        operations,
                    )
                    self.assertEqual(
                        bag.total(name) + bag.overflow_of(name),
                        added.get(name, 0) - removed.get(name, 0),
                        operations,
                    )
                for _, slot_count_in_slot in bag.slots:
                    self.assertGreaterEqual(slot_count_in_slot, 1)
                    self.assertLessEqual(
                        slot_count_in_slot, stack_max, operations
                    )


if __name__ == "__main__":
    unittest.main()
