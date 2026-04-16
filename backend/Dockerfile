FROM python:3.11-slim

WORKDIR /app

# Switch to Aliyun mirrors for fast downloads inside mainland China servers
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list 2>/dev/null || true

# Install system dependencies for Pillow and ReportLab
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    fonts-wqy-microhei \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Use Aliyun PyPI mirror for fast pip install in China
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
