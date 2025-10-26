#
# If a page doesn't exist in some location, or is not specified,
# use the following page name.
#
DEFAULT_WIKI_PAGE = "Main"

#
# Name of the directory in app/src/template/ that contains files,
# document.html and edit.html, which are Jinja templates
#
TEMPLATE = "default"

#
# Show directory as en editable link in /index view.
# The turns /path/location/ into /path/location.md link
#
DIRECTORY_AS_MD_FILE_LINK = True

#
# If a directory begins with a dot, such as .path,
# then ignore all of it's contents on the /index/ page
# Currently still accessable from /wiki/
#
HIDE_DOT_DIRECTORY = False
