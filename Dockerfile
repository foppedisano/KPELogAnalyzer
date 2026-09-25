FROM python:3.12-slim
WORKDIR /app
COPY app /app/app
RUN useradd --uid 10001 --create-home analyzer && mkdir /data && chown analyzer:analyzer /data
USER analyzer
ENV KPE_DATA_DIR=/data KPE_HOST=0.0.0.0 KPE_PORT=8080 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2)"
CMD ["python", "-m", "app.server"]
