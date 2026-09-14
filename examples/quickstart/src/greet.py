"""A tiny CLI whose behavior can be checked without third-party dependencies."""

import sys


def greet(name):
    return f"Hello, {name}!"


if __name__ == "__main__":
    print(greet(sys.argv[1] if len(sys.argv) > 1 else "world"))
