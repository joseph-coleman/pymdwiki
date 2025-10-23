""" """

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from markdown.blockprocessors import BlockProcessor
from markdown.inlinepatterns import InlineProcessor
import xml.etree.ElementTree as etree
import re

# from ..main import parse_url_path, markdown_file_exists


def normalize_page_name(page_name: str) -> str:
    """Convert spaces to underscores, but preserve slashes for subdirectories."""
    parts = page_name.split("/")
    return "/".join(p.strip().replace(" ", "_") for p in parts if p.strip())


def normalize_anchor(anchor: str) -> str:
    """Normalize anchor like the Python Markdown TOC extension."""
    anchor = anchor.lower()
    # Replace spaces with dash
    anchor = re.sub(r"\s+", "-", anchor)
    # Remove all punctuation except letters, numbers, dash
    anchor = re.sub(r"[^a-z0-9\-]", "", anchor)
    # Collapse multiple dashes
    anchor = re.sub(r"-+", "-", anchor)
    return anchor.strip("-")


class WikiLinkInlineProcessor(InlineProcessor):
    def __init__(self, pattern: str, config):
        super().__init__(pattern)
        self.base_url = config["base_url"].rstrip("/")
        self.current_path = config["current_path"]  # e.g. "docs/Install_Guide"
        self.page_exists_callback = config["page_exists_callback"]

    def resolve_page_name(self, page_name: str) -> str:
        """Resolve page names with relative/absolute rules."""
        page_name = page_name.strip()

        if page_name.startswith("/"):
            # Absolute path (from wiki root)
            resolved = page_name.lstrip("/")
        elif self.current_path:
            resolved = "/".join([self.current_path, page_name])
        else:
            resolved = page_name
        return resolved

    def default_link_text(self, page_name: str, resolved_name: str) -> str:
        """Choose a default display text if user didn't specify one."""
        if "#" in page_name:
            page_name = page_name.split("#", 1)[0]  # drop anchor
        if "/" in page_name or page_name.startswith("."):
            return page_name.split("/")[-1]
        return page_name

    def handleMatch(self, m, data):
        raw_text = m.group(1).strip()

        # Pipe syntax [[Page|Text]]
        if "|" in raw_text:
            page_part, link_text = [p.strip() for p in raw_text.split("|", 1)]
        else:
            page_part, link_text = raw_text, None

        # remove anchor if present
        if "#" in page_part:
            page_name, anchor = page_part.split("#", 1)
            normalized_anchor = normalize_anchor(anchor)
        else:
            page_name, anchor = page_part, None
            normalized_anchor = None

        resolved_name = self.resolve_page_name(page_name)
        normalized_name = normalize_page_name(resolved_name)

        url = f"{self.base_url}/{normalized_name}"
        if anchor:
            url += f"#{normalized_anchor}"

        # Default link text
        if link_text is None:
            link_text = self.default_link_text(page_part, resolved_name)

        el = etree.Element("a")
        el.set("href", url)
        el.text = link_text
        el.set("class", "wikilink")

        if anchor:
            el.set("title", f"{anchor}")

        # Missing-page check
        if self.page_exists_callback is not None:
            if not self.page_exists_callback(resolved_name):
                el.set("class", "missing")

        return el, m.start(0), m.end(0)


class WikiLinkExtension(Extension):
    def __init__(self, **kwargs):
        # specify defaults first.
        self.config = {
            "base_url": ["/wiki", "Base URL for wiki links"],
            "current_path": [
                "/",
                "Current page path, for relative resolution",
            ],
            "page_exists_callback": [
                lambda x: True,
                "Function to check if a page exists",
            ],
        }
        # this super sets the config parameters and overwrites the defaults.
        super().__init__(**kwargs)

    def extendMarkdown(self, md):

        WIKI_LINK_RE = r"\[\[([^\]]+)\]\]"  # matches [[Page Name]]
        md.inlinePatterns.register(
            WikiLinkInlineProcessor(
                WIKI_LINK_RE,
                config=self.getConfigs(),
            ),
            "wikilink",
            175,
        )


class ImageEmbedInlineProcessor(InlineProcessor):
    def handleMatch(self, m, data):
        src = m.group(1)
        img = etree.Element("img")
        img.set("src", src)
        img.set("alt", "")
        return img, m.start(0), m.end(0)


class ImageEmbedExtension(Extension):
    def extendMarkdown(self, md):
        IMAGE_EMBED_RE = r"!\[\[([^\]]+)\]\]"  # Matches ![[filename]]
        md.inlinePatterns.register(
            ImageEmbedInlineProcessor(IMAGE_EMBED_RE, md), "image_embed", 175
        )


class StrikeThroughInlineProcessor(InlineProcessor):
    def handleMatch(self, m, data):
        strike_through = etree.Element("s")
        strike_through.text = m.group(1)
        return strike_through, m.start(0), m.end(0)


class StrikeThroughExtension(Extension):
    def extendMarkdown(self, md):
        MD_RE = r"~~(.*?)~~"
        md.inlinePatterns.register(
            StrikeThroughInlineProcessor(MD_RE, md), "strikethrough", 175
        )


class HighLightInlineProcessor(InlineProcessor):
    def handleMatch(self, m, data):
        strike_through = etree.Element("mark")
        strike_through.text = m.group(1)
        return strike_through, m.start(0), m.end(0)


class HighLightExtension(Extension):
    def extendMarkdown(self, md):
        MD_RE = r"==(.*?)=="
        md.inlinePatterns.register(
            HighLightInlineProcessor(MD_RE, md), "highlightinline", 175
        )


class UnifiedMathPreprocessor(Preprocessor):
    # """
    # Handles all math delimiters via regex replacements:
    #   - $...$ (inline)
    #   - \( ... \) (inline)
    #   - \[ ... \] (inline or block depending on position)
    #   - $$ ... $$ (block)
    # """

    # Patterns
    RE_BLOCK_DOLLAR = re.compile(r"^\$\$\s*\n(.*?)\n\s*\$\$", re.MULTILINE | re.DOTALL)
    RE_BLOCK_BRACKET = re.compile(
        r"^\s*\\\[\s*\n(.*?)\n\s*\\\]\s*$", re.MULTILINE | re.DOTALL
    )
    # RE_INLINE_DOLLAR = re.compile(
    #     r"(?<!\\)(?<!\$)\$(?!\$)(.+?)(?<!\\)(?<!\$)\$(?!\$)", re.DOTALL
    # )

    RE_INLINE_DOLLAR = re.compile(
        r"(?<!\\)(?<!\$)\$(?!\$)(?!\d)(.+?)(?<!\\)(?<!\$)\$(?!\$)", re.DOTALL
    )

    RE_INLINE_DOUBLEDOLLAR = re.compile(
        r"(?<!\\)(?<!\$)\$\$(?!\$)(.+?)(?<!\\)(?<!\$)\$\$(?!\$)", re.DOTALL
    )
    RE_INLINE_PAREN = re.compile(r"(?<!\\)\\\((.+?)\\\)", re.DOTALL)
    RE_INLINE_BRACKET = re.compile(r"(?<!\\)\\\[(.+?)\\\]", re.DOTALL)

    def run(self, lines):
        text = "\n".join(lines)

        original_text = text + ""

        # Block: $$ ... $$
        text = self.RE_BLOCK_DOLLAR.sub(
            lambda m: self.md.htmlStash.store(f"\\[\n{ m.group(1).strip()}\n\\]"), text
        )

        # Block: \[ ... \] (on separate lines)
        text = self.RE_BLOCK_BRACKET.sub(
            lambda m: self.md.htmlStash.store(f"\\[\n{m.group(1).strip()}\n\\]"), text
        )

        # Inline Block: $$ ... $$
        text = self.RE_INLINE_DOUBLEDOLLAR.sub(
            lambda m: self.md.htmlStash.store(f"\\[{m.group(1).strip()}\\]"), text
        )

        # Inline: $...$
        text = self.RE_INLINE_DOLLAR.sub(
            lambda m: self.md.htmlStash.store(f"\\({m.group(1).strip()}\\)"), text
        )

        # Inline: \( ... \)
        text = self.RE_INLINE_PAREN.sub(
            lambda m: self.md.htmlStash.store(f"\\(\n{m.group(1).strip()}\n\\)"), text
        )

        # Inline: \[ ... \]
        text = self.RE_INLINE_BRACKET.sub(
            lambda m: self.md.htmlStash.store(f"\\[\n{m.group(1).strip()}\n\\]"), text
        )

        if text != original_text:
            self.md.pymdwiki_has_latex = True

        return text.split("\n")


class LaTeXExtension(Extension):
    def extendMarkdown(self, md):
        md.pymdwiki_has_latex = False
        md.preprocessors.register(UnifiedMathPreprocessor(md), "unified-math", 25)
