from starlette.applications import Starlette
from starlette.responses import (
    HTMLResponse,
    RedirectResponse,
    FileResponse,
    JSONResponse,
)
from starlette.exceptions import HTTPException
from starlette.routing import Route

from starlette.requests import Request

from starlette.websockets import WebSocket
from starlette.routing import WebSocketRoute

from html import escape
import datetime

# from jinja2 import Template
from jinja2 import Environment, FileSystemLoader

import httpx

import json
from urllib.parse import unquote
from pathlib import Path
import os
from pathlib import PurePosixPath
import glob

import markdown

from config import (
    DEFAULT_WIKI_PAGE,
    TEMPLATE,
    DIRECTORY_AS_MD_FILE_LINK,
    HIDE_DOT_DIRECTORY,
    DEFAULT_ENCODING,
)

# these aren't configurable
RESERVED_PATHS = ["wiki", "edit", "save", "delete", "index"]
FILE_PATH = "wiki"

os.makedirs(FILE_PATH, exist_ok=True)

from src.markdown_extensions import (
    LaTeXExtension,
    StrikeThroughExtension,
    HighLightExtension,
    AutoLinkExtension,
    ImageEmbedExtension,
    WikiLinkExtension,
)

from src.jupyter_extension import JupyterCellExtension


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
    AutoLinkExtension(),
    # WikiLinkExtension(), specified below with parameters
    #
    JupyterCellExtension(),
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
    while "\\" in path:
        path = path.replace("\\", "/")
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
            if file_name_parts[0]:
                file_ext = file_name_parts.pop()
                file_name_no_ext = file_name[: -1 - len(file_ext)]
            else:
                # could be .hidden.md  ['', 'hidden', 'md']
                # or .hidden  ['', 'hidden']
                if len(file_name_parts) == 2:
                    file_ext = ""
                    file_name_no_ext = file_name
                else:
                    file_ext = file_name_parts.pop()
                    file_name_no_ext = ".".join(file_name_parts)
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
    file_exists = markdown_file_exists(url_pieces, any_type=True)

    if not file_exists:
        return False
    return True


def markdown_file_exists(url_pieces, any_type=False):
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
    elif any_type:
        # check other extensions?
        # should we explicitly check from a subset of supported filename extensions?
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
        if path_list:
            path_list.pop(0)
        template_path = os.path.join("template", TEMPLATE)
        if file_ext in ["css", "js", "png", "jpg", "jpeg", "gif"]:
            file_path = os.path.join(os.getcwd(), template_path, *path_list, file_name)
            print(file_path)
            if Path(file_path).exists():
                return FileResponse(file_path, filename=file_name)
            else:
                print("file doesn't exist")

    # should config a default start page
    return RedirectResponse(f"/wiki/{DEFAULT_WIKI_PAGE}")


# /wiki/*
async def view_document(request):

    template_path = style_path = os.path.join("template", TEMPLATE)
    jinja_env = Environment(loader=FileSystemLoader(template_path))
    doc_template = jinja_env.get_template("document.html")

    doc_data = {}
    doc_data["default_wiki_page"] = DEFAULT_WIKI_PAGE

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

    file_path = markdown_file_exists(url_pieces, any_type=False)

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
        with open(file_path, "r", newline="", encoding=DEFAULT_ENCODING) as file:
            html = file.read()
        html = md.convert(html)

        doc_data["title"] = file_name_base
        doc_data["page_name"] = page_name
        doc_data["page_path"] = path
        doc_data["toc"] = md.toc  # pylint: disable=no-member
        doc_data["scripts"] = ""

        # this here allows for including it only on the document page.
        # and only if LaTeX was in the markdown and got processed.

        if md.pymdwiki_has_latex:  # pylint: disable=no-member
            doc_data[
                "scripts"
            ] += """
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

        if md.pymdwiki_has_jupyter:  # pylint: disable=no-member
            doc_data["is_jupyter"] = True
            doc_data["scripts"] += """<script src="/template/jupyter.js"></script>"""

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
    doc_data["default_wiki_page"] = DEFAULT_WIKI_PAGE

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
        with open(file_path, "r", newline="", encoding=DEFAULT_ENCODING) as file:
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
        return await delete_document(request)

    if not document_name:
        return RedirectResponse(f"/wiki/{DEFAULT_WIKI_PAGE}")

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

        with open(
            file_path,
            "w",
            newline="\n",
            encoding=DEFAULT_ENCODING,
            errors="xmlcharrefreplace",
        ) as file:
            file.write(updated_markdown)
        # do we want to catch case when we write an empty file?

    return RedirectResponse("/".join(["/wiki", *path_list, file_name_base]))


# /delete/
async def delete_document(request):
    """Deletes a file.  Does not delete directories."""
    method = request.method

    if method == "POST":

        form = await request.form()
        document_name = form["document_name"]

        if not document_name:
            return RedirectResponse(f"/wiki/{DEFAULT_WIKI_PAGE}")

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
                os.remove(file_path)
    elif method == "GET":
        ...

    return RedirectResponse("/index/")
    # return RedirectResponse("/".join(["/edit", *path_list, file_name_base]))


def find_last_match_index(A, B):
    """Given two lists, find the index of last match"""
    min_len = min(len(A), len(B))
    if min_len == 0:
        return -1  # or would raise error be better?
    for n in range(min_len):
        if A[n] != B[n]:
            return n - 1
    return min_len - 1


def parse_file_path(path, remove_reserved=True):
    """helper to break path into some commonly used components"""
    path = unquote(path)
    while ".." in path:
        path = path.replace("..", "")
    while "\\" in path:
        path = path.replace("\\", "/")
    while "//" in path:
        path = path.replace("//", "/")
    path_split = path.split("/")
    path_split = [each for each in path_split if each]
    is_md = False

    if remove_reserved and path_split and path_split[0] in RESERVED_PATHS:
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

        if file_ext == "md":
            is_md = True
            path_split.append(file_name_no_ext)

        if not path_split[0]:
            path_split.pop(0)
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
        "is_md": is_md,
    }
    return response


# /index/
async def index_document(request):

    template_path = os.path.join("template", TEMPLATE)
    jinja_env = Environment(loader=FileSystemLoader(template_path))
    doc_template = jinja_env.get_template("document.html")

    doc_data = {}
    doc_data["default_wiki_page"] = DEFAULT_WIKI_PAGE

    url_pieces = parse_url_path(request.url.path)

    path = url_pieces["path"]
    path_list = url_pieces["path_list"]
    file_name = url_pieces["file_name"]
    file_ext = url_pieces["file_ext"]
    file_name_base = url_pieces["file_name_no_ext"]

    file_path = ""

    # file_path = os.path.join(".", FILE_PATH)
    file_path = os.path.join(FILE_PATH)
    # specify the file extension you want to search for
    extension = "*.md"
    # use the glob module to find all files with the specified extension in the directory and its subdirectories

    file_list = []
    for extension in ["*.md", "*.png", "*.jpg", "*.jpeg", "*.pdf", "*.canvas"]:

        file_list = file_list + glob.glob(
            f"{file_path}/**/{extension}",
            recursive=True,
            include_hidden=not HIDE_DOT_DIRECTORY,
        )

    md_list = ""
    last_list_depth = 0
    current_list_depth = 0

    last_path_list = []
    last_path = ""
    file_list = [f if f[-3:] != ".md" else f[:-3] for f in file_list]
    file_list = list(set(file_list))
    file_list.sort(key=str.lower)

    for each in file_list:
        d = parse_file_path(each)

        if not d["path"]:
            current_list_depth = 0
        else:
            current_list_depth = len(d["path_list"])

            # # ignore any hidden folders, anything that begins with .
            # if any(
            #     [
            #         True if directory_name[0] == "." else False
            #         for directory_name in d["path_list"]
            #     ]
            # ):
            #     if HIDE_DOT_DIRECTORY:
            #         continue

        if not (last_path_list == d["path_list"]):
            # path has changed.
            branch_index = find_last_match_index(last_path_list, d["path_list"])
            if branch_index == -1:
                # branch_index = 0  # just starting
                ...

            # up_depth = last_list_depth - branch_index
            down_depth = current_list_depth - branch_index

            if branch_index == -1:
                # correction
                down_depth = down_depth - 1

            for depth in range(branch_index + 1, current_list_depth):

                if depth == (current_list_depth - 1):
                    if d["is_md"]:
                        md_list += (
                            f"{depth * '    '}* [["
                            + "/".join(d["path_list"])
                            + "]]\n"
                            + f"{{: .list_file .file_{d['file_ext']} }}\n"
                        )
                        break

                if DIRECTORY_AS_MD_FILE_LINK:
                    md_list += (
                        f"{depth * '    '}* [["
                        + "/".join(d["path_list"][: depth + 1])
                        + "]] \n"
                        + "{: .list_dir_link }\n"
                    )
                else:
                    md_list += (
                        f"{depth * '    '}* "
                        + d["path_list"][depth]
                        + "\n"
                        + "{: .list_dir }\n"
                    )
        else:
            ...

        if not d["is_md"]:
            md_list += (
                f"{current_list_depth * '    '}* [["
                + "/".join([*d["path_list"], d["file_name"]])
                + "]]\n"
                + f"{{: .list_file .file_{d['file_ext']} }}\n"
            )
        # else:
        #     md_list += (
        #         f"{current_list_depth * '    '}* <<[["
        #         + "/".join(d["path_list"])
        #         + "]]>>\n"
        #         # + f"{{: .list_file .file_{d['file_ext']} }}\n"
        #     )

        # md_list += (
        #     f"{current_list_depth * '    '}* <<[["
        #     + "/".join(d["path_list"])
        #     + "/"
        #     + d["file_name_no_ext"]
        #     + "]]>>\n"
        #     # + f"{{: .list_file .file_{d['file_ext']} }}\n"
        # )

        # current becomes last on next iteration.
        last_list_depth = current_list_depth
        last_path_list = d["path_list"].copy()
        last_path = d["path"]

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
    html = md.convert(md_list)

    doc_data["scripts"] = ""
    doc_data["unlinked_title"] = "Index"
    # doc_data["document"] = "<pre>" + md_list + "</pre><pre>" + debug_text + "</pre>"
    doc_data["document"] = html

    response_content = doc_template.render(doc_data)

    return HTMLResponse(response_content)


from src.jupyter_client import jupyter_manager
from src.tasks import kernel_reaper_loop

import asyncio
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    # --- Startup ---
    print("Starting Kernel Reaper...")
    # Create the background task
    reaper_task = asyncio.create_task(kernel_reaper_loop())

    yield

    # --- Shutdown ---
    print("Stopping Kernel Reaper...")
    reaper_task.cancel()
    try:
        await reaper_task
    except asyncio.CancelledError:
        pass


async def jupyter_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        # 1. Wait for the frontend to send the configuration
        data = await websocket.receive_json()
        page_id = data.get("page_id")
        code = data.get("code")

        if not page_id or not code:
            await websocket.send_text("Error: Missing page_id or code")
            await websocket.close()
            return

        # 2. Get/Create Kernel
        # Note: Add error handling here if Jupyter is down
        kernel_id = await jupyter_manager.get_or_create_kernel(page_id)

        # 3. Stream the output
        async for output_chunk in jupyter_manager.execute_code_stream(kernel_id, code):
            # Send chunk to browser immediately
            await websocket.send_text(output_chunk)

    except Exception as e:
        print("web socket exception")
        await websocket.send_text(f"\nSystem Error: {str(e)}")

    finally:
        await websocket.close()


async def manage_jupyter(request):
    # /manage/jupyter
    k_list = jupyter_manager.list_kernels()
    k_list_response = await k_list

    qp = request.query_params
    if kernel_to_delete := qp.get("delete"):
        await jupyter_manager.delete_kernel_by_id(kernel_to_delete)
        return RedirectResponse(f"/manage/jupyter")

    raw_markdown = ""
    if isinstance(k_list_response, list) and len(k_list_response) > 0:
        raw_markdown = """Action    | Name  | State | Idle | Connections | Pages\n----- | ----- | ----- | ----- | ----- | -----\n"""
        for each_k in k_list_response:
            raw_markdown += f"""[❌](/manage/jupyter?delete={each_k['id']} ) | {each_k['name']} | {each_k['execution_state']} | {each_k['idle']} | {str(each_k['connections'])} | {str(each_k['pages'])} | \n"""
    else:
        raw_markdown = "No kernels."

    ###################################################
    template_path = os.path.join("template", TEMPLATE)
    jinja_env = Environment(loader=FileSystemLoader(template_path))
    doc_template = jinja_env.get_template("document.html")
    doc_data = {}
    doc_data["is_jupyter"] = True
    doc_data["unlinked_title"] = "Kernel Management"
    md = markdown.Markdown(
        extensions=MD_EXTENSIONS,
        extension_configs=MD_EXTENSION_CONFIG,
        output_format="html",
    )
    html = md.convert(raw_markdown)
    doc_data["document"] = html
    response_content = doc_template.render(doc_data)
    return HTMLResponse(response_content)


async def markdown_convert_code(request):
    # This takes as input some python code and
    # converts it to snippet of markdown
    form = await request.form()
    code_snippet = form["code"]
    raw_markdown = f"```python\n{code_snippet}\n```\n"
    md = markdown.Markdown(
        extensions=MD_EXTENSIONS,
        extension_configs=MD_EXTENSION_CONFIG,
        output_format="html",
    )
    html = md.convert(raw_markdown)
    return HTMLResponse(html)


routes = [
    WebSocketRoute("/ws/run_jupyter", jupyter_websocket_endpoint),
    Route("/manage/{path:path}", endpoint=manage_jupyter, methods=["GET", "POST"]),
    Route("/api/markdown/code/", endpoint=markdown_convert_code, methods=["POST"]),
    Route("/index/{path:path}", endpoint=index_document, methods=["GET", "POST"]),
    Route("/delete/{path:path}", endpoint=delete_document, methods=["GET", "POST"]),
    Route("/save/{path:path}", endpoint=save_document, methods=["GET", "POST"]),
    Route("/edit/{path:path}", endpoint=edit_document, methods=["GET", "POST"]),
    Route("/wiki/{path:path}", endpoint=view_document, methods=["GET", "POST"]),
    Route("/{path:path}", endpoint=catch_all, methods=["GET", "POST"]),
]

app = Starlette(debug=True, routes=routes, lifespan=lifespan)


@app.on_event("shutdown")
async def on_shutdown():
    await jupyter_manager.prune_stale_kernels(-1)
