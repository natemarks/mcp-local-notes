FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY src ./src
RUN pip install --no-cache-dir --no-deps .

ENV NOTES_DIR=/notes
ENV MCP_HOST=0.0.0.0
VOLUME ["/notes"]
EXPOSE 8000

CMD ["mcp-local-notes-server"]
