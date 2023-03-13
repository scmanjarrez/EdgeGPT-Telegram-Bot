# syntax = docker/dockerfile:1.2
FROM --platform=linux/amd64,linux/arm64/python:3.10

RUN apt-get update && apt upgrade -y
RUN cd /
COPY . /edgebot/
RUN cd edgebot
WORKDIR /edgebot
RUN pip install -r requirements.txt
CMD [ "python", "edge.py" ,"-c","/conf"]