FROM python:3.12-slim AS builder
WORKDIR /build
COPY . .
RUN pip install --no-cache-dir build && python -m build --wheel

FROM python:3.12-slim
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl
ENTRYPOINT ["cx"]
CMD ["--help"]
