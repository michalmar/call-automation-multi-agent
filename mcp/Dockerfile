FROM python:3.11-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY server.py transcription.py ./

EXPOSE 8000

CMD ["uv", "run", "python", "server.py"]
