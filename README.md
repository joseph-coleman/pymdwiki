
# what is this?

This is a simple wiki app built with python where files are saved as markdown.  This can work as a simple web interface to an Obsidian vault as an example.  

This is designed to run on your local computer for personal note taking. 

# Docker

First, edit `docker-compose.yml` with a plain text editor. 

You'll need to edit the paths in the `volumes` key, 

Assuming you've cloned the repo to `d:/code/pymdwiki/` (this is a windows path), you'll need to map the `app` directory to `/app/app` in the docker image.  This first mapping is for development purposes, so any edits anything in `app/` get reloaded by `uvicorn`.  It's nice, but not needed. 

The second line is a mapping of where you want your wiki markdown files to be stored on your computer.  Here in this example, the host path is `d:/code/pymdwiki/app/wiki` and that gets mapped to `/mnt/data` inside the container.  You only need to configure the paths of the host files. Leave `/app/app` and `/mnt/data` as is.

The location of your wiki data can be a path to an Obsidian vault, since those files are markdown.

```
    volumes:
      - d:/code/pymdwiki/app:/app/app
      - d:/code/pymdwiki/app/wiki:/mnt/data 
```

## Once the config is done

Easiest way is to run, assuming you have Docker desktop installed. Go do that first if you don't have it. 

`docker compose up --build`


docker run -it --rm -p 8000:8000 -e DATA_DIR=/mnt/data -v "d:/code/pymdwiki/app":/app/app -v "d:/code/pymdwiki/app/wiki":/mnt/data pymdwiki

You can use `docker compose up` when it's already built.


# to pip or not to pip

Started off using `uv` to manage packages, but when it came time to having a working docker container, the idea of creating a Dockerfile that installs `uv` just to install a very small set of python packages felt like too much.  With `uv` I already had a simple environment that worked, so putting those packages into a requirements.txt was trivial.  The Dockerfile was also trivial.  

But I did some testing. 

Turns out astral has some images with `uv` already installed, so why not try them?  Unfortunately they're much more bloated than justs using `pip`.  And I don't need that application bloat in my life.  Luckily astral had some other more convoluted docker scripts on their github pages.  Only the multi stage worked for me. It reduced my container image size from 155 MB with pip to just 61MB with uv. Not bad.  The downside is that in the build process there are actually two base containers used, one with `uv` installed that is used to install packages, those packages are copied over to another container that does not have `uv`, and the initial container gets discarded.

In terms of final size, the winner is the multi-stage docker build process with alpine.  I'm sure docker has cached the images somwhere on my computer to speed up subsequent builds if a new python package needs to be installed, so the savings in disk space is probably a wash. 

tool | distribution               | size
-----|----------------------------|-------------
pip  | python:3.13-slim,          | 155.39 MB 
uv   | python3.13-bookworm-slim,  | 215.91 MB
uv   | multi, 3.13 bookworm-slim, | 136.52 MB
pip  | python:3.13-alpine,        |  82.86 MB
uv   | python3.13-alpine,         | 140.45 MB
uv   | multi, 3.13 alphine        |  61.07 MB 