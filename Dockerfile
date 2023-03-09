FROM python:latest

RUN apt-get update && apt upgrade -y
RUN cd /
COPY . /chstockbot/
RUN cd chstockbot
WORKDIR /chstockbot
RUN pip install -r requirements.txt
CMD [ "python", "edge.py" ,"-c","/conf"]