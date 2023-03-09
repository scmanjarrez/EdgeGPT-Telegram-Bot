FROM python:latest

RUN apt-get update && apt upgrade -y
RUN cd /
COPY . /edgebot/
RUN cd edgebot
WORKDIR /edgebot
RUN pip install -r requirements.txt
CMD [ "python", "edge.py" ,"-c","/conf"]