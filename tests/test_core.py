import unittest

from bagstack.core import Bag, BagError


class AddTest(unittest.TestCase):
    def test_new_item_opens_slot(self):
        bag = Bag(10, 3)
        bag.add("ore", 2)
        self.assertEqual(len(bag.slots), 1)

    def test_same_item_merges(self):
        bag = Bag(10, 3)
        bag.add("ore", 1)
        bag.add("ore", 2)
        self.assertEqual(len(bag.slots), 1)
        self.assertEqual(bag.total("ore"), 3)

    def test_overflow_starts_at_zero(self):
        self.assertEqual(Bag(2, 3).overflow_of("ore"), 0)


class SplitTest(unittest.TestCase):
    def test_split_creates_new_slot(self):
        bag = Bag(5, 3)
        bag.add("ore", 3)
        bag.split("ore", 1)
        self.assertEqual(len(bag.slots), 2)

    def test_split_unknown_item_raises(self):
        with self.assertRaises(BagError):
            Bag(5, 3).split("ore", 1)


if __name__ == "__main__":
    unittest.main()
