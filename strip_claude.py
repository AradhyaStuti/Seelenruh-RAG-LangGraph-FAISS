import sys
for line in sys.stdin:
    if "Co-Authored-By: Claude" not in line:
        print(line, end="")
