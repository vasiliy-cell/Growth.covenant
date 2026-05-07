import os

BASE_LOG_DIR = "logs"


def get_log_files():
    if not os.path.exists(BASE_LOG_DIR):
        return []

    files = [
        f for f in os.listdir(BASE_LOG_DIR)
        if f.endswith(".jsonl")
    ]

    return sorted(files)


def choose_files():
    files = get_log_files()

    if not files:
        print("No logs found")
        return []

    total = len(files)

    print(f"\nFound {total} log files")

    print("\nSelect mode:")
    print("1 - All logs")
    print("2 - Last log only")
    print("3 - Last N logs")
    print("4 - First N logs")
    print("5 - Exact range")

    choice = input("Enter choice: ").strip()

    # ---------------------------------------------------
    # ALL
    # ---------------------------------------------------
    if choice == "1":
        return files

    # ---------------------------------------------------
    # LAST ONE
    # ---------------------------------------------------
    elif choice == "2":

        print(f"\nSelected:\n{files[-1]}")

        return [files[-1]]

    # ---------------------------------------------------
    # LAST N
    # ---------------------------------------------------
    elif choice == "3":

        try:
            n = int(input("Last N logs: "))

            selected = files[-n:]

            print(f"\nSelected last {len(selected)} logs")

            return selected

        except:
            print("Invalid input")
            return []

    # ---------------------------------------------------
    # FIRST N
    # ---------------------------------------------------
    elif choice == "4":

        try:
            n = int(input("First N logs: "))

            selected = files[:n]

            print(f"\nSelected first {len(selected)} logs")

            return selected

        except:
            print("Invalid input")
            return []

    # ---------------------------------------------------
    # RANGE
    # ---------------------------------------------------
    elif choice == "5":

        try:
            print(f"\nAvailable indexes: 0 .. {total - 1}")

            start = int(input("Start index: "))
            end = int(input("End index: "))

            selected = files[start:end + 1]

            print(f"\nSelected {len(selected)} logs")

            return selected

        except:
            print("Invalid input")
            return []

    else:
        print("Unknown choice")
        return []