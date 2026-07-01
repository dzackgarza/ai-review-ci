def classify(value: int, flags: list[bool]) -> str:
    result = "start"
    if value > 0:
        if flags and flags[0]:
            result = "a"
        elif len(flags) > 1 and flags[1]:
            result = "b"
        elif len(flags) > 2 and flags[2]:
            result = "c"
        elif len(flags) > 3 and flags[3]:
            result = "d"
        elif len(flags) > 4 and flags[4]:
            result = "e"
        elif len(flags) > 5 and flags[5]:
            result = "f"
        elif len(flags) > 6 and flags[6]:
            result = "g"
        else:
            result = "h"
    else:
        for flag in flags:
            if flag:
                result = "negative-active"
            else:
                result = "negative-inactive"
    return result
