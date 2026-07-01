FROM public.ecr.aws/lambda/python:3.12

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e "."

CMD ["src.main.handler"]
