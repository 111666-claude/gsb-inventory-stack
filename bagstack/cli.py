"""命令行入口：跑背包堆叠样例。"""

import argparse

from .core import Bag


def build_parser():
    parser = argparse.ArgumentParser(prog="inventory-stack", description="背包堆叠")
    parser.add_argument("--sample", default="stack", help="stack / overflow / split / scan")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.sample == "stack":
        bag = Bag(10, 3)
        bag.add("ore", 7)
        print("slots=%d total=%d" % (len(bag.slots), bag.total("ore")))
    elif args.sample == "overflow":
        bag = Bag(2, 3)
        bag.add("ore", 10)
        print("total=%d overflow=%d" % (bag.total("ore"), bag.overflow_of("ore")))
    elif args.sample == "split":
        bag = Bag(5, 3)
        bag.add("ore", 3)
        bag.split("ore", 1)
        print("total=%d" % bag.total("ore"))
    elif args.sample == "scan":
        bag = Bag(100000, 99)
        for index in range(2000):
            bag.add("item-%d" % index, 1)
        for _ in range(2000):
            bag.total("item-1999")
        print("scanned=%d" % bag.scanned_count())
    else:
        raise SystemExit("需要 --sample stack|overflow|split|scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
