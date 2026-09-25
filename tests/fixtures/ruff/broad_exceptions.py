"""Broad-exception rule fixtures."""


def broad_handler_without_raise() -> None:
    try:
        print("work")
    except Exception as error:
        print(error)


def bare_handler_without_raise() -> None:
    try:
        print("work")
    except:
        print("failed")


def base_exception_handler_without_raise() -> None:
    try:
        print("work")
    except BaseException:
        print("failed")


def broad_handler_with_raise() -> None:
    try:
        print("work")
    except Exception:
        raise


def broad_handler_with_typed_raise() -> None:
    try:
        print("work")
    except Exception as error:
        raise RuntimeError from error


def narrow_handler_without_raise() -> None:
    try:
        print("work")
    except ValueError as error:
        print(error)
