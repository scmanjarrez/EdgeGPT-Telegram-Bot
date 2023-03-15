FROM python:3.8.10-alpine

COPY . /edgegpt
WORKDIR /edgegpt
RUN apk add build-base
RUN pip install wheel
RUN pip install -r requirements.txt
CMD ["python", "src/edge.py"]
