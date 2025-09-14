# Command line 
To start,  `uvicorn main:app` or `uvicorn main:app --reload`

# Docker

Build image
docker build -t pymdwiki .

Run the container
`docker run -p 8000:8000 pymdwiki`
docker run -it --rm -p 8000:8000 -e DATA_DIR=/mnt/data -v $(pwd):/app -v $(pwd)/wiki:/mnt/data  pymdwiki
docker run -it --rm -p 8000:8000 -e DATA_DIR=/mnt/data  -v "d:/code/pymdwiki/app/wiki":/app/app/wiki pymdwiki
docker run -it --rm -p 8000:8000 -e DATA_DIR=/mnt/data -v "d:/code/pymdwiki/app":/app/app -v "d:/code/pymdwiki/app/wiki":/mnt/data pymdwiki


docker run -it --rm -p 8000:8000 -e DATA_DIR=/mnt/data -v "d:/code/pymdwiki/app":/app/app  pymdwiki

this prints  
/app/app
['template', 'main.py', 'wiki']
docker run -it --rm -p 8000:8000 -e DATA_DIR=/mnt/data  pymdwiki


Or, 
`docker compose up --build`

or 
`docker compose up` when it's already built.

# pip or not to pip

<!-- 
pip, python:3.13-slim,          155.39 MB size
uv, python3.13-bookworm-slim,   215.91 MB
uv, python3.13-alpine,          140.45 MB
pip, python:3.13-alpine,         82.86 MB
uv, multi, 3.13 bookwormslim,   136.52 MB
uv, multi, 3.13 alphine          61.07 MB -->