FROM python:3.11-slim

WORKDIR /app

# Install pipenv
RUN pip install --no-cache-dir pipenv

# Copy Pipfile and Pipfile.lock
COPY Pipfile Pipfile.lock ./

# Install dependencies from Pipfile.lock into system Python
RUN pipenv install --deploy --system

# Copy application
COPY ./app .

# Create data directory
RUN mkdir -p ./archive

EXPOSE 8000
# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]