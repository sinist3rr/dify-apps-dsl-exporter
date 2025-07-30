################################
# Stage 1: Builder
################################

FROM python:3.12-slim AS builder

WORKDIR /app

ARG POETRY_VERSION=2.1.3
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false

RUN --mount=type=cache,target=/root/.cache/pypoetry \
    poetry install --no-root

COPY . .

################################
# Stage 2: Production
################################

FROM python:3.12-slim AS production

WORKDIR /app

# Copy installed dependencies and source from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app /app
                                                                
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["entrypoint.sh"]
CMD ["export"]
