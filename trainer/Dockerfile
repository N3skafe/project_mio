FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu .
ENV PYTHONUNBUFFERED=1
ENV MAIDOPS_TRAIN_DEVICE=cpu
ENV MAIDOPS_MODEL_DIR=/models
CMD ["python", "-m", "maidops_trainer"]
