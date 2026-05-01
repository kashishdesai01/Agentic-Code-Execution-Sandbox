FROM python:3.11-slim

RUN groupadd -r sandbox && useradd -r -g sandbox -d /sandbox -s /sbin/nologin sandbox

WORKDIR /sandbox

COPY sitecustomize.py /usr/local/lib/python3.11/sitecustomize.py

RUN chown sandbox:sandbox /sandbox

USER sandbox

CMD ["python", "/sandbox/task.py"]
