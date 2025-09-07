from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Route

from pathlib import Path
import os

FILE_PATH = "wiki"

import markdown


MD_EXTENSIONS = ["extra", "codehilite"]
MD_EXTENSION_CONFIG = {
    "extra": {
        "abbr": {},  # glossary: A dictionary where the ky is the abbreviation and the value is the definition.
        "attr_list": {},  # no config options
        "def_list": {},  # no config options
        "fenced_code": {},  # lang_prefix  The prefix prepended to the langauge class assigned to the HTML <code> tag.  default `language-`
        "footnotes": {
            "PLACE_MARKER": "///Footnotes Go Here///",
            "UNIQUE_IDS": False,
            "BACKLINK_TEXT": "&#8617;",
            "SUPERSCRIPT_TEXT": "{}",
            "BACKLINK_TITLE": "Jump back to footnote {} in the text",
            "SEPARATOR": ":",
            "USE_DEFINITION_ORDER": False,
        },
    },
    "codehilite": {
        "linenums": True,  # True, False, None (auto), alieas for linenos
        "guess_lang": True,
        "css_class": "codehilite",
        "pygments_formatter": "html",
    },
}

STYLE = "abap"
# STYLE = "autumn"
# STYLE = "borland"
# STYLE = "bw"
# STYLE = "coffee"
# STYLE = "colorful"
# STYLE = "default"
# STYLE = "dracula"
# STYLE = "emacs"
# STYLE = "github-dark"
# STYLE = "lightbulb"
# STYLE = "lovelace"
# STYLE = "monokai"
# STYLE = "murphy"
# STYLE = "native"
# STYLE = "nord-darker"
# STYLE = "nord"
# STYLE = "paraiso-light"
# STYLE = "pastie"
# STYLE = "perldoc"
# STYLE = "rrt"
# STYLE = "sas"
# STYLE = "solarized-dark"
# STYLE = "solarized-light"
# STYLE = "staroffice"
# STYLE = "tango"
# STYLE = "vs"
# STYLE = "xcode"
# STYLE = "zenburn"  # dark background


# Define the catch-all endpoint
async def catch_all(request):
    # Extract the path from the request
    path = request.url.path
    query = request.url.query
    method = request.method

    # Custom logic based on the path and HTTP method
    if path == "/":
        return RedirectResponse("/wiki/")

    elif path.startswith("/wiki/"):
        # print(dir(request.url))

        path = path.replace("/wiki/", "", count=1)
        while ".." in path:
            path = path.replace("..", "")
        if path.endswith(".md"):
            path = path[:-3]

        page_name = path.split("/")[-1]

        style_path = os.path.join("template", "style", STYLE) + ".css"
        with open(style_path, "r") as style_file:
            style = style_file.read()

        file_path = os.path.join(FILE_PATH, path) + ".md"
        if Path(file_path).exists():
            md = markdown.Markdown(
                extensions=MD_EXTENSIONS,
                extension_configs=MD_EXTENSION_CONFIG,
                output_format="html",
            )
            with open(file_path, "r") as file:
                html = file.read()
            html = md.convert(html)

            response_content = f"""
                <html>
                    <head>
                    <style>{style}</style>
                    <script>
                    MathJax = {{
                    tex: {{
                        inlineMath: {{'[+]': [['$', '$']]}}
                    }}
                    }};
                    </script>
                    <script id="MathJax-script" async defer src="https://cdn.jsdelivr.net/npm/mathjax@4/tex-mml-chtml.js"></script>
                    </head><body>{html}</body></html>"""
            return HTMLResponse(response_content)
        else:
            # edit page
            response_content = f"<h1>Edit: {page_name}</h1><p>Method: {method}</p>"
            return HTMLResponse(response_content)

        response_content = f"<h1>Path: {path}</h1><p>Method: {method}</p>"
        if method == "GET":
            return HTMLResponse(response_content)
        elif method in ["POST", "PUT", "DELETE"]:
            return HTMLResponse(response_content, status_code=201)
        else:
            # Handle other methods (e.g., HEAD, PATCH) as needed
            return HTMLResponse(status_code=405)  # Method Not Allowed
    else:
        return RedirectResponse("/wiki/")


routes = [
    Route("/{path:path}", catch_all),
]


app = Starlette(debug=True, routes=routes)
