from starlette.applications import Starlette
from starlette.responses import HTMLResponse, RedirectResponse, FileResponse
from starlette.exceptions import HTTPException
from starlette.routing import Route

from html import escape
import datetime

# from jinja2 import Template
from jinja2 import Environment, FileSystemLoader

import json
from urllib.parse import unquote
from pathlib import Path
import os
from pathlib import PurePosixPath

import markdown

from config import DEFAULT_WIKI_PAGE, TEMPLATE

# these aren't configurable
RESERVED_PATHS = ["wiki", "edit", "save", "delete"]
FILE_PATH = "wiki"

os.makedirs(FILE_PATH, exist_ok=True)

from src.markdown_extensions import (
    LaTeXExtension,
    StrikeThroughExtension,
    HighLightExtension,
    ImageEmbedExtension,
    WikiLinkExtension,
)

MD_EXTENSIONS = [
    LaTeXExtension(),
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
    ImageEmbedExtension(),
    # WikiLinkExtension(), specified below with parameters
    #
]
# these configs are only for builtin extensions,
# config passing for custom extensions needs to occur when instatiating
# the object
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
        "anchorlink": False,  # True, headers link to themselves,
        "anchorlink_class": "toclink",
        "permalink": False,  # True or string to generate links at end of each header.  True uses &para;
        "permalink_class": "headerlink",
        "permalink_title": "Permanent link",
        "permalink_leading": False,  # True if permanant links should be generated
        "baselevel": 1,  # adjust header size allowed, 2 makes #5 = #6, 3 makes #4=#5=#6,
        # "slugify": callable to generate anchors
        "separator": "-",  # replaces white space in id
        "toc_depth": 6,  # bottom depth of header to include.
    },
}


def parse_url_path(path):
    """helper to break url into some commonly used components"""
    path = unquote(path)
    while ".." in path:
        path = path.replace("..", "")
    while "//" in path:
        path = path.replace("//", "/")
    path_split = path.split("/")
    path_split = [each for each in path_split if each]

    if path_split and path_split[0] in RESERVED_PATHS:
        path_split.pop(0)

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
        file_name = DEFAULT_WIKI_PAGE
        file_ext = ""
        file_name_no_ext = DEFAULT_WIKI_PAGE

    response = {
        "path": "/".join(path_split),
        "path_list": path_split,
        "file_name": file_name,
        "file_ext": file_ext,
        "file_name_no_ext": file_name_no_ext,
    }
    return response


def markdown_page_name(url_pieces):
    """helper for cleaner urls to file.md files"""
    path = url_pieces["path"]
    path_list = url_pieces["path_list"]
    file_name = url_pieces["file_name"]
    file_ext = url_pieces["file_ext"]
    file_name_base = url_pieces["file_name_no_ext"]

    if file_ext == "":
        page_name = file_name_base
    elif file_ext == "md":
        page_name = file_name_base
    else:
        page_name = file_name

    return page_name


def wikilink_page_check(resolved_name):
    """check if a wiki link points to an actual documenbt"""

    path = PurePosixPath(resolved_name)
    parts = []
    for part in path.parts:
        if part == "..":
            if parts and parts[-1] != "..":
                parts.pop()
            else:
                parts.append(part)
        elif part != ".":
            parts.append(part)
    resolved_path = "/" + "/".join(parts)

    # resolved_path = path.resolve()
    url_pieces = parse_url_path(resolved_path)
    file_exists = markdown_file_exists(url_pieces)

    if not file_exists:
        return False
    return True


def markdown_file_exists(url_pieces):
    """Determines if a markdown url exists as a file"""

    path = url_pieces["path"]
    path_list = url_pieces["path_list"]
    file_name = url_pieces["file_name"]
    file_ext = url_pieces["file_ext"]
    file_name_base = url_pieces["file_name_no_ext"]

    file_path = ""

    if file_ext == "":
        file_path = os.path.join(FILE_PATH, *path_list, file_name) + ".md"
    elif file_ext == "md":
        file_path = os.path.join(FILE_PATH, *path_list, file_name)

    if len(file_path) > 0 and Path(file_path).exists():
        return file_path
    else:
        return False


# Define the catch-all endpoint
async def catch_all(request):

    # here we catch anything not with an explicit prefix.
    # Do we assume /document should be /wiki/document
    # Do we want to redirect to /wiki/document if
    # it exists, or to /edit/document if it doesn't?

    url_pieces = parse_url_path(request.url.path)
    path = url_pieces["path"]
    path_list = url_pieces["path_list"]
    file_name = url_pieces["file_name"]
    file_ext = url_pieces["file_ext"]

    # kind of annoying that browsers always request this file.
    if file_name == "favicon.ico":
        file_path = os.path.join(os.getcwd(), file_name)
        if Path(file_path).exists():
            return FileResponse(file_path, filename=file_name)
        raise HTTPException(status_code=404, detail="File not found.")

    # resources in the template folder.
    # anything like /template/default/page_header.jpg would get served here
    # but forced under the current template, i.e. no sharing of resources
    # So, really f"/template/{TEMPLATE}/page_header.jpg" would be served
    if path_list[0] == "template":
        path_list.pop(0)
        path_list.pop(0)
        template_path = os.path.join("template", TEMPLATE)
        if file_ext in ["css", "js", "png", "jpg", "jpeg", "gif"]:
            file_path = os.path.join(os.getcwd(), template_path, *path_list, file_name)
            if Path(file_path).exists():
                return FileResponse(file_path, filename=file_name)

    # should config a default start page
    return RedirectResponse(f"/wiki/{DEFAULT_WIKI_PAGE}")


# /wiki/*
async def view_document(request):

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

    file_path = markdown_file_exists(url_pieces)

    if file_path:

        page_name = markdown_page_name(url_pieces)

        # custom extensions need to be configured on creation,
        # and this one needs the current path
        all_extensions = MD_EXTENSIONS + [
            WikiLinkExtension(
                base_url="/wiki",
                current_path=path,
                page_exists_callback=wikilink_page_check,
            )
        ]

        md = markdown.Markdown(
            extensions=all_extensions,
            extension_configs=MD_EXTENSION_CONFIG,
            output_format="html",
        )
        with open(file_path, "r") as file:
            html = file.read()
        html = md.convert(html)

        doc_data["title"] = file_name_base
        doc_data["page_name"] = page_name
        doc_data["page_path"] = path
        doc_data["toc"] = md.toc

        # this here allows for including it only on the document page.
        # and only if LaTeX was in the markdown and got processed.
        if md.pymdwiki_has_latex:
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
        if file_ext in ["png", "jpg", "jpeg", "gif"]:
            file_path = os.path.join(FILE_PATH, *path_list, file_name)
            if Path(file_path).exists():
                return FileResponse(file_path, filename=file_name)
            else:
                raise HTTPException(status_code=404, detail="File not found.")

        # response_content = f"<h1>Edit: {file_name}</h1><p>Method: {method}</p>"
        # return HTMLResponse(response_content)
        return RedirectResponse("/".join(["/edit", *path_list, file_name]))


# /edit/
async def edit_document(request):

    template_path = os.path.join("template", TEMPLATE)
    jinja_env = Environment(loader=FileSystemLoader(template_path))
    doc_template = jinja_env.get_template("edit.html")

    doc_data = {}

    url_pieces = parse_url_path(request.url.path)

    path = url_pieces["path"]
    path_list = url_pieces["path_list"]
    file_name = url_pieces["file_name"]
    file_ext = url_pieces["file_ext"]
    file_name_base = url_pieces["file_name_no_ext"]

    file_path = ""

    # doc_data["css"] = f"<style>{style}</style>"

    if file_ext == "":
        file_path = os.path.join(FILE_PATH, *path_list, file_name) + ".md"
        page_name = file_name_base
    elif file_ext == "md":
        file_path = os.path.join(FILE_PATH, *path_list, file_name)
        page_name = file_name_base
    else:
        # what happens when the file isn't markdown? yikes!
        page_name = file_name

    if len(file_path) > 0 and Path(file_path).exists():
        with open(file_path, "r") as file:
            raw_markdown = file.read()
        page_title = f"Editing {file_name}"
        doc_data["document_mode"] = "edit"
    else:
        # file doesn't exist,
        raw_markdown = f"""Title: {file_name}\nSummary:\nAuthors: \nDate: {datetime.datetime.now(datetime.timezone.utc)}\nKeywords: \n\n# Header \n Edit your document {file_name}"""
        page_title = f"Creating {file_name}"
        doc_data["document_mode"] = "create"

    doc_data["title"] = file_name_base
    doc_data["page_name"] = page_name
    doc_data["page_path"] = path

    # doc_data[
    #     "scripts"
    # ] = """
    #         <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.css" integrity="sha384-5TcZemv2l/9On385z///+d7MSYlvIEw9FuZTIdZ14vJLqWphw7e7ZPuOiCHJcFCP" crossorigin="anonymous">
    #         <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.js" integrity="sha384-cMkvdD8LoxVzGF/RPUKAcvmm49FQ0oxwDF3BGKtDXcEc+T1b2N+teh/OJfpU0jr6" crossorigin="anonymous"></script>
    #         <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/contrib/auto-render.min.js" integrity="sha384-hCXGrW6PitJEwbkoStFjeJxv+fSOOQKOPbJxSfM6G5sWZjAyWhXiTIIAmQqnlLlh" crossorigin="anonymous"></script>
    #         <script>
    #             document.addEventListener("DOMContentLoaded", function() {
    #                 renderMathInElement(document.body, {
    #                 delimiters: [
    #                     {left: '\\\\(', right: '\\\\)', display: false},
    #                     {left: '\\\\[', right: '\\\\]', display: true}
    #                 ],
    #                 throwOnError : false
    #                 });
    #             });
    #         </script>"""

    doc_data["scripts"] = ""

    doc_data["document"] = escape(raw_markdown)
    doc_data["file_path"] = escape(file_path)

    response_content = doc_template.render(doc_data)

    return HTMLResponse(response_content)


# /save/ process documenbt saves
async def save_document(request):
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

        os.makedirs(os.path.join(FILE_PATH, *path_list), exist_ok=True)

        with open(file_path, "w") as file:
            file.write(updated_markdown)
        # do we want to catch case when we write an empty file?

    return RedirectResponse(f"/wiki/{path}/{file_name_base}")


# /delete/
async def delete_document(request):
    ## TODO: See comments in /save/
    ## probably makes sense to have dedicated endpoint for deletion
    ## Not implemented yet.

    print("DELETE DOCUMENT")

    url_pieces = parse_url_path(request.url.path)
    path = url_pieces["path"]
    path_list = url_pieces["path_list"]
    file_name = url_pieces["file_name"]
    file_ext = url_pieces["file_ext"]
    file_name_base = url_pieces["file_name_no_ext"]

    return RedirectResponse(f"/edit/{path}/{file_name_base}")


routes = [
    Route("/delete/{path:path}", endpoint=delete_document, methods=["GET", "POST"]),
    Route("/save/{path:path}", endpoint=save_document, methods=["GET", "POST"]),
    Route("/edit/{path:path}", endpoint=edit_document, methods=["GET", "POST"]),
    Route("/wiki/{path:path}", endpoint=view_document, methods=["GET", "POST"]),
    Route("/{path:path}", endpoint=catch_all, methods=["GET", "POST"]),
]

app = Starlette(debug=True, routes=routes)
