# jupyter_extension.py
# Python-Markdown extension to convert ```jupyter``` code fences into interactive cells


from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
import re
import html
from hashlib import sha1


RE_FENCE = re.compile(r"```jupyter\n(.*?)\n```", re.MULTILINE | re.DOTALL)


class JupyterCellPreprocessor(Preprocessor):
    """
    A block of code starting with !!!jupyter and ending with !!!
    gets processed into container div that holds some buttons,
    a textarea for editing code in the web page,
    a div for displaying pretty markdown syntax highlighted code
        which is done in a different step, this puts the code
        in a markdown block ```python ...code... ``` to be processed
        later
    and another div for holding code output.
    """

    def run(self, lines):
        text = "\n".join(lines)

        original_text = text + ""

        def repl(m):
            code = m.group(1).rstrip("\n")

            md_code = f"<div class='jupyter-formatted'>\n```python\n{code}\n```\n</div>"

            # Unique stable id for the cell (hash of content) — helps with ordering & persistence
            # Not really using cell hash,
            cell_hash = sha1(code.encode("utf-8")).hexdigest()[:12]
            safe_code = html.escape(code)

            return (
                f"""<div class="jupyter-cell" data-cell-hash="{cell_hash}">"""
                + self.md.htmlStash.store(
                    f"""<div class="jupyter-button-wrapper">
                    <button title="Run" class="jupyter-run" onclick="runJupyterCode(this)">▶️</button>
                    <button title="Clear Output" class="jupyter-clear" onclick="runJupyterClear(this)">🗑️</button>
                    <button title="Edit" class="jupyter-edit" onclick="runJupyterEdit(this)" aria-pressed="false">✏️</button>
                    </div>
                    <div class="jupyter-output" style="display:none;"></div>
                    <textarea  style="display:none;" class="jupyter-code" spellcheck="false" autocomplete="off" autocorrect="off" autocaptialize="off">{safe_code}</textarea>
                """
                )
                + md_code
                + "</div>"
            )

        new = RE_FENCE.sub(repl, text)

        if text != original_text:
            self.md.pymdwiki_has_jupyter = True
        return new.split("\n")


class JupyterCellExtension(Extension):
    def extendMarkdown(self, md):
        md.pymdwiki_has_jupyter = True
        md.registerExtension(self)  # this do anything?
        md.preprocessors.register(JupyterCellPreprocessor(md), "jupyter_cell", 26)
