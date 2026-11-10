FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py datos.py calculos.py serializar.py ./
COPY static ./static
COPY templates ./templates
RUN useradd --uid 10001 --no-create-home dash
USER dash
ENV DATA_PATH=/datos/BD_Dashboard_Globant.xlsx
EXPOSE 8050
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8050", "--access-logfile", "-", "app:app"]
