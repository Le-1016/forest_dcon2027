FROM python:3.12-slim
WORKDIR /app
COPY ml/forest_ml ./forest_ml
RUN useradd --uid 10001 --create-home forest && mkdir /state && chown forest:forest /state
USER forest
EXPOSE 8090
CMD ["python", "-m", "forest_ml.server", "--host", "0.0.0.0", "--state", "/state"]
