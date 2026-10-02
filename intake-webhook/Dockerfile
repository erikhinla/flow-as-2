FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn pydantic
COPY intake-webhook/app.py ./app.py
COPY shared/intake_envelope.py ./intake_envelope.py
COPY intake-webhook/arva_handoff.py ./arva_handoff.py
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
