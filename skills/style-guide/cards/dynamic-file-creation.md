# Dynamic File / Config Creation from Code

> **Style card `DYNAMIC-FILE-CREATION`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: Code that writes a file (config, script, data file) by assembling content from raw strings, shell heredocs, or inline byte buffers — making the content invisible to review, diff, and static analysis.

```python
# BAD: writing config from a string literal in code
config_content = f"""
[server]
host = {host}
port = {port}
timeout = {timeout}
"""
Path("/etc/app/config.ini").write_text(config_content)

# BAD: generating a JSON config from a dict that was constructed ad-hoc
# (same problem — no independent file to review)
```

## Preferred construction: Commit a static version of the file as a tracked artifact.
Read or copy it at runtime.
If dynamic content is genuinely required (not for config — for user data), use a real templating engine (Jinja2, Mustache, etc.) with a template file that IS the reviewed artifact.

```python
# ## Preferred construction: tracked static file, read at runtime
config = configparser.ConfigParser()
config.read("/etc/app/config.ini")  # file is committed, reviewed, diffable

# When dynamic content IS genuinely needed: real template engine
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader("templates"))
rendered = env.get_template("report.html").render(data=data)
Path("/tmp/report.html").write_text(rendered)
```

## Use this pattern when:
- The generated file is a config, script, or static data file the app owns.
- The content is assembled from string literals, f-strings, template literals, or shell heredocs inline in code.
- The file would be more reviewable, diffable, and auditable as a static committed artifact.

## Choose a different pattern when:
- The app's express purpose IS file generation (template parser, code generator, build tool).
- The content comes from genuine user data, not from strings embedded in the app's own code.
