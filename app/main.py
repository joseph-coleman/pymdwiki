from starlette.applications import Starlette
from starlette.responses import HTMLResponse, RedirectResponse, FileResponse
from starlette.exceptions import HTTPException
from starlette.routing import Route

# from jinja2 import Template
from jinja2 import Environment, FileSystemLoader

# import json
from urllib.parse import unquote
from pathlib import Path
import os

FILE_PATH = os.getenv("DATA_DIR", "wiki")
os.makedirs(FILE_PATH, exist_ok=True)

import markdown

# from markdown.extensions import Extension
# from markdown.preprocessors import Preprocessor
# from markdown.blockprocessors import BlockProcessor
# from markdown.inlinepatterns import InlineProcessor
# import xml.etree.ElementTree as etree
# import re

from src.markdown_extensions import (
    LaTeXExtension,
    StrikeThroughExtension,
    HighLightExtension,
    ImageEmbedExtension,
)

MD_EXTENSIONS = [
    LaTeXExtension(),
    # LaTeXBlockExtension(),
    # BoxExtension(),
    StrikeThroughExtension(),
    HighLightExtension(),
    "extra",
    "codehilite",
    "admonition",
    "legacy_attrs",
    # "legacy_em", not good, turn _my_word_ into <em>my</em>word_  instead of <em>my_word</em>
    "meta",
    "nl2br",
    "sane_lists",
    "smarty",
    "toc",
    "wikilinks",
    ImageEmbedExtension(),
    #
]
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
        "tables": {
            "use_align_attribute": False
        },  # True to use "align" instead of style attribute
        "md_in_html": {},  # markdown in html has no configs
    },
    "codehilite": {
        "linenums": True,  # True, False, None (auto), alieas for linenos
        "guess_lang": True,
        "css_class": "codehilite",
        "pygments_formatter": "html",
        # "noclasses": False,
        # "pygments_style": "default",
        "use_pygments": True,
    },
    "legacy_attrs": {},  # todo
    "meta": {},  #
    "nl2br": {},  # no config, treat new lines as hard breaks
    "smarty": {
        "smart_dashes": True,
        "smart_quotes": True,
        "smart_angled_quotes": True,  # default False
        "smart_ellipses": True,
        "substitutions": {
            "left-single-quote": "&lsquo;",  # sb is not a typo!
            "right-single-quote": "&rsquo;",
            "left-double-quote": "&ldquo;",
            "right-double-quote": "&rdquo;",
            # "left-single-quote": "&sbquo;",  # sb is not a typo!
            # "right-single-quote": "&lsquo;",
            # "left-double-quote": "&bdquo;",
            # "right-double-quote": "&ldquo;",
        },
    },
    "toc": {
        "marker": "[TOC]",
        "title": None,  # title to insert in the toc <div>
        "title_class": "toctitle",
        "toc_class": "toc",
        "anchorlink": False,  # True headers link to themselves,
        "anchorlink_class": "toclink",
        "permalink": False,  # True or string to generate links at end of each header.  True uses &para;
        "permalink_class": "headerlink",
        "permalink_title": "Permanent link",
        "permalink_leading": False,  # True if permanant links should be generated
        "baselevel": 1,  # adjust header size allowed, 2 makds #5 = #6, 3 makes #4=#5=#6,
        # "slugify": callable to generate anchors
        "separator": "-",  # replaces white space in id
        "toc_depth": 6,  # bottom depth of header to include.
    },
    "wikilinks": {
        "base_url": "/wiki/",
        "end_url": "/",
        "html_class": "wikilink",
        # "build_url": callable which formats the URL from its parts, probalby need this for distinguishing urls that don't exist yet.
    },
}

# various pygment styles for code.
# need to figure out how to automatically switch between light and dark mode.
STYLE = "abap"
# STYLE = "gruvbox-dark"


def parse_url_path(path):
    path = unquote(path)
    while ".." in path:
        path = path.replace("..", "")
    path_split = path.split("/")
    path_split = [each for each in path_split if each]

    if path_split:
        file_name = path_split.pop()
        if len(path_split) == 0:
            path_split = [""]
        file_name_parts = file_name.split(".")
        if len(file_name_parts) > 1:
            file_ext = file_name_parts.pop()
            file_name_no_ext = file_name[: -1 - len(file_ext)]
        else:
            file_ext = ""
            file_name_no_ext = file_name
    else:
        path_split = [""]
        file_name = ""
        file_ext = ""
        file_name_no_ext = ""

    response = {
        "path": "/".join(path_split),
        "path_list": path_split,
        "file_name": file_name,
        "file_ext": file_ext,
        "file_name_no_ext": file_name_no_ext,
    }
    return response


# Define the catch-all endpoint
async def catch_all(request):

    # here we catch anything not with an explicit prefix.
    # Do we assume /document should be /wiki/document
    # Do we want to redirect to /wiki/document if
    # it exists, or to /edit/document if it doesn't?

    TEMPLATE = "default"

    url_pieces = parse_url_path(request.url.path)
    path = url_pieces["path"]
    path_list = url_pieces["path_list"]
    file_name = url_pieces["file_name"]
    file_ext = url_pieces["file_ext"]

    if file_name == "favicon.ico":
        # print("ico ico ico ico ico ico")
        file_path = os.path.join(os.getcwd(), file_name)
        # print(file_path)
        if Path(file_path).exists():
            # print("fave fave fave fave fave fave")
            return FileResponse(file_path, filename=file_name)
        raise HTTPException(status_code=404, detail="File not found.")

    # resources in the template folder.
    if path_list[0] == "template":
        path_list.pop(0)
        path_list.pop(0)
        template_path = os.path.join("template", TEMPLATE)
        if file_ext in ["css", "js", "png", "jpg", "jpeg", "gif"]:
            file_path = os.path.join(os.getcwd(), template_path, *path_list, file_name)
            if Path(file_path).exists():
                return FileResponse(file_path, filename=file_name)

    # should config a default start page
    return RedirectResponse("/wiki/main")


# /wiki/*
async def view_document(request):
    print("VIEW DOCUMENT")

    TEMPLATE = "default"
    template_path = style_path = os.path.join("template", TEMPLATE)
    jinja_env = Environment(loader=FileSystemLoader(template_path))
    doc_template = jinja_env.get_template("document.html")

    doc_data = {}

    # Extract the path from the request
    path = request.url.path
    query = request.url.query
    method = request.method

    url_pieces = parse_url_path(request.url.path)

    path = url_pieces["path"]
    path_list = url_pieces["path_list"]
    file_name = url_pieces["file_name"]
    file_ext = url_pieces["file_ext"]
    file_name_base = url_pieces["file_name_no_ext"]

    path_list.pop(0)

    file_path = ""
    style_path = os.path.join("template", "style", STYLE) + ".css"
    with open(style_path, "r") as style_file:
        style = style_file.read()

    doc_data["css"] = f"<style>{style}</style>"

    if file_ext == "":
        file_path = os.path.join(FILE_PATH, *path_list, file_name) + ".md"
        page_name = file_name_base
    elif file_ext == "md":
        file_path = os.path.join(FILE_PATH, *path_list, file_name)
        page_name = file_name_base
    else:
        page_name = file_name

    if len(file_path) > 0 and Path(file_path).exists():
        md = markdown.Markdown(
            extensions=MD_EXTENSIONS,
            extension_configs=MD_EXTENSION_CONFIG,
            output_format="html",
        )
        with open(file_path, "r") as file:
            html = file.read()
        html = md.convert(html)

        doc_data["title"] = file_name_base
        doc_data["pagename"] = page_name

        doc_data[
            "scripts"
        ] = """
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.css" integrity="sha384-5TcZemv2l/9On385z///+d7MSYlvIEw9FuZTIdZ14vJLqWphw7e7ZPuOiCHJcFCP" crossorigin="anonymous">
                <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.js" integrity="sha384-cMkvdD8LoxVzGF/RPUKAcvmm49FQ0oxwDF3BGKtDXcEc+T1b2N+teh/OJfpU0jr6" crossorigin="anonymous"></script>
                <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/contrib/auto-render.min.js" integrity="sha384-hCXGrW6PitJEwbkoStFjeJxv+fSOOQKOPbJxSfM6G5sWZjAyWhXiTIIAmQqnlLlh" crossorigin="anonymous"></script>
                <script>
                    document.addEventListener("DOMContentLoaded", function() {
                        renderMathInElement(document.body, {
                        delimiters: [
                            {left: '\\\\(', right: '\\\\)', display: false},
                            {left: '\\\\[', right: '\\\\]', display: true}
                        ],
                        throwOnError : false
                        });
                    });
                </script>"""

        doc_data["document"] = html

        response_content = doc_template.render(doc_data)

        return HTMLResponse(response_content)
    else:
        # print("EEEEEEEEEEEE")
        if file_ext in ["png", "jpg", "jpeg", "gif"]:
            # print("FFFFFFFFF")
            file_path = os.path.join(FILE_PATH, *path_list, file_name)
            # print(file_path)
            if Path(file_path).exists():
                return FileResponse(file_path, filename=file_name)
            else:
                pass
                # print("GGGGGGGG")
        # edit page
        response_content = f"<h1>Edit: {file_name}</h1><p>Method: {method}</p>"
        return HTMLResponse(response_content)


# /edit/
async def edit_document(request):

    url_pieces = parse_url_path(request.url.path)

    path = url_pieces["path"]
    path_list = url_pieces["path_list"]
    file_name = url_pieces["file_name"]
    file_ext = url_pieces["file_ext"]
    file_name_base = url_pieces["file_name_no_ext"]

    path_list.pop(0)

    file_path = ""
    style_path = os.path.join("template", "style", STYLE) + ".css"
    with open(style_path, "r") as style_file:
        style = style_file.read()

    if file_ext == "":
        file_path = os.path.join(FILE_PATH, *path_list, file_name) + ".md"
    elif file_ext == "md":
        file_path = os.path.join(FILE_PATH, *path_list, file_name)

    if len(file_path) > 0 and Path(file_path).exists():
        with open(file_path, "r") as file:
            raw_markdown = file.read()
        page_title = f"Editing {file_name}"
    else:
        # file doesn't exist,
        raw_markdown = f"# Edit \n Edit your document {file_name}"  # template?
        page_title = f"Creating {file_name}"

    response_content = f"""<!DOCTYPE html>
        <html>
            <head>
            <style>{style}</style>
            </head><body>
            <h1>{page_title}</h1>
            <form action="/save/" method="post" name="edit_document_form">
            <textarea name="markdown" style="width:100%;" rows=50>{raw_markdown}</textarea>
            <br/>
            <input type="submit" value="Save" />
            <input type="hidden" name="document_name" value="{file_path}">
            <button name="delete_button" value="true">Delete</button>
            </form></body></html>"""

    return HTMLResponse(response_content)


# Define the catch-all endpoint
async def save_document(request):
    print("SAVE DOCUMENT")

    # do we really care if this was a POST or GET?
    method = request.method

    form = await request.form()
    updated_markdown = form["markdown"]
    document_name = form["document_name"]
    if "delete_button" in form:
        ...
        delete_document = True

    url_pieces = parse_url_path(document_name)
    path = url_pieces["path"]
    path_list = url_pieces["path_list"]
    file_name = url_pieces["file_name"]
    file_ext = url_pieces["file_ext"]
    file_name_base = url_pieces["file_name_no_ext"]

    path_list.pop(0)  # get rid of the /wiki/ prefix.

    file_path = ""
    if file_ext == "":
        file_name = file_name + ".md"
        file_ext = "md"

    file_path = os.path.join(FILE_PATH, *path_list, file_name)

    if len(file_path) > 0:
        if Path(file_path).exists():
            # any special consideratin when overwriting a file?
            # backup old file? versioning?
            ...

        with open(file_path, "w") as file:
            file.write(updated_markdown)
        # do we want to catch case when we write an empty file?

    return RedirectResponse(f"/{path}/{file_name_base}")


routes = [
    Route("/save/{path:path}", endpoint=save_document, methods=["GET", "POST"]),
    Route("/edit/{path:path}", endpoint=edit_document, methods=["GET", "POST"]),
    Route("/wiki/{path:path}", endpoint=view_document, methods=["GET", "POST"]),
    Route("/{path:path}", endpoint=catch_all, methods=["GET", "POST"]),
]


app = Starlette(debug=True, routes=routes)
