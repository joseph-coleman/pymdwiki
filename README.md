# Command line 
To start,  `uvicorn main:app` or `uvicorn main:app --reload`

# Docker

Build container
`docker build -t my-uvicorn-app .`

Run the container
`docker run -p 8000:8000 my-uvicorn-app`


Or, 
`docker compose up --build`