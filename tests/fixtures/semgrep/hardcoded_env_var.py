# POLICY.NO_HIDDEN_CONFIG: an environment variable set to a value written in
# the source. A value that the program computes is not hidden configuration.
import os
import shutil


def configure(directory: str) -> None:
    # ruleid: py-no-hardcoded-env-var
    os.environ["NODE_ENV"] = "production"
    # ruleid: py-no-hardcoded-env-var
    os.environ["API_HOST"] = 'api.example.org'

    # ok: py-no-hardcoded-env-var
    os.environ["PATH"] = directory + os.pathsep + os.environ["PATH"]
    # ok: py-no-hardcoded-env-var
    os.environ["SHELL"] = shutil.which("bash")
