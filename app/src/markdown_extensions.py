from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from markdown.blockprocessors import BlockProcessor
from markdown.inlinepatterns import InlineProcessor
import xml.etree.ElementTree as etree
import re


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

        return text.split("\n")


class LaTeXExtension(Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(UnifiedMathPreprocessor(md), "unified-math", 25)
