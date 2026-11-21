FROM python:3.13-slim-bookworm AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 libffi8 shared-mime-info fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY api/requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt
COPY . /app
RUN sed -i 's/\r$//' /app/api/entrypoint.sh && useradd --create-home api
USER api
CMD ["sh", "/app/api/entrypoint.sh"]

# Legacy service tests are a development-only regression oracle, never a runtime dependency.
FROM runtime AS regression
USER root
RUN pip install --no-cache-dir Django==5.2.19
USER api
