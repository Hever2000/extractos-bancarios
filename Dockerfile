FROM public.ecr.aws/lambda/python:3.12

RUN yum install -y freetds-devel gcc && yum clean all

COPY pyproject.toml ./
RUN pip install --no-cache-dir "pdfplumber>=0.11.0" "boto3>=1.34" "pymssql>=2.2"

COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps -e "."

CMD ["src.main.handler"]
