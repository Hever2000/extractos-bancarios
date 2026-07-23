# Roadmap de Deploy — Extractos Bancarios

## Auditoría de Funcionalidades

### ✅ Lo que funciona hoy

#### Pipeline de extracción ✅

#### Servicios AWS 
| Funcionalidad | Estado | Notas |
|---|---|---|
| SHA-256 hash para detección de duplicados | ✅ Listo | `hash_service.py` |
| Upload a S3 | ✅ Listo | `s3_service.py` — ruta `extractos/{YYYY}/{MM}/{uuid}.pdf` |
| Persistencia en SQL Server | ✅ Listo | `upload_repository.py` via pymssql |
| Response builder (éxito/duplicado/error) | ✅ Listo | `response_builder.py` |
| Orchestrator (coordina pipeline + servicios) | ✅ Listo | `orchestrator.py` |
| Lambda handler (API Gateway POST) | ✅ Listo | `main.py` — base64 body |

#### Infraestructura
| Funcionalidad | Estado | Notas |
|---|---|---|
| Dockerfile (Lambda Python 3.12) | ✅ Listo | Incluye freetds-devel para pymssql |
| docker-compose.yml (lambda + test + lint + typecheck) | ✅ Listo | |
| Makefile (comandos de desarrollo) | ✅ Listo | |
| CI (GitHub Actions — verify en push/PR) | ✅ Listo | Python 3.12 + 3.13, ruff, mypy, pytest |
| CD (GitHub Actions — deploy en tags v*) | ✅ Listo | Build ECR + update Lambda |

#### Testing
| Funcionalidad | Estado | Notas |
|---|---|---|
| Unit tests (9 stages, ~40 tests) | ✅ Listo | `tests/test_stages/` |
| Golden tests (Macro, Provincia+Nación) | ✅ Listo | `tests/test_pipeline.py` |
| Bank detection tests (10 tests) | ✅ Listo | `tests/test_detectors.py` |
| Amount normalization tests (12 tests) | ✅ Listo | `tests/test_normalizers.py` |
| Validation tests (4 tests) | ✅ Listo | `tests/test_validators.py` |
| Metadata extraction tests (40+ tests) | ✅ Listo | `tests/test_extractors.py` |
| Service layer tests (orchestrator, S3, hash, DB) | ✅ Listo | `tests/test_services/` |
| Mutation testing framework (30+ operadores) | ✅ Listo | `tests/mutations/` |
| Laboratorio de robustez | ✅ Listo | `tests/laboratorio/` |

### ❌ Lo que NO funciona / falta

#### Bugs conocidos
| Issue | Archivo | Gravedad |
|---|---|---|
| `tests/laboratorio/test_robustez.py` accede a `result.stage_confidence` que no existe en `MutatedResult` | `tests/mutations/runner.py` | ⚠️ Media — rompe laboratorio |
| `README.md` tiene marcadores de merge conflict sin resolver (líneas 107-110) | `README.md` | ⚠️ Media |

#### Funcionalidades incompletas
| Funcionalidad | Estado | Dónde |
|---|---|---|
| S3 trigger en Lambda | ❌ No implementado | `src/main.py:29` — `raise NotImplementedError` |
| `src/models/trace.py` | 🗑️ Archivo vacío (solo `from __future__ import annotations`) | Eliminar o implementar |

#### Lo que falta para producción real

##### Fase 1: Infraestructura como Código (CRÍTICO)
| Item | Por qué es necesario |
|---|---|
| **API Gateway REST/HTTP API** — No hay definición de API Gateway en ningún lado | El Lambda handler espera eventos de API Gateway pero no hay configuración (tipo, auth, CORS, payload limits) |
| **Lambda execution role IAM** — No hay definición de permisos | Necesita permisos para S3 (`PutObject`), ECR, CloudWatch Logs, y acceso a VPC para SQL Server |
| **VPC + Security Groups para SQL Server** — Lambda necesita estar en VPC para alcanzar SQL Server on-premise o RDS | Sin VPC no hay conexión a DB. VPC implica NAT Gateway (costo ~$35/mes) o VPC Endpoints |
| **S3 bucket + policy** — Definir bucket name, cifrado, políticas de acceso, lifecycle rules | Actualmente el bucket se configura por env var `S3_BUCKET` |

##### Fase 2: Seguridad y Secretos
| Item | Por qué es necesario |
|---|---|
| **AWS Secrets Manager** — Las credenciales de DB están en env vars (`DB_HOST`, `DB_USER`, `DB_PASSWORD`) | No es seguro para producción. Rotación automática, cifrado en reposo |
| **KMS encryption para S3** — Los PDFs contienen datos financieros sensibles | Deberían cifrarse en reposo con KMS. Hoy no hay config de cifrado en `s3_service.py` |
| **API Gateway auth** — No hay autenticación configurada | Podría ser API Key, IAM auth, o Lambda authorizer. Hoy cualquiera con la URL puede enviar PDFs |
| **IAM roles mínimo privilegio** — No hay definición de policies | El execution role debe tener solo los permisos necesarios |

##### Fase 3: Configuración de Lambda
| Item | Por qué es necesario |
|---|---|
| **Lambda timeout** — No documentado | Procesar PDFs grandes (ej. 800 transacciones de Provincia) puede llevar >30s. El default de Lambda es 3s |
| **Lambda memory** — No documentado | pdfplumber procesa en memoria. 512MB puede ser poco para PDFs grandes |
| **Lambda ephemeral storage** — No documentado | Default 512MB. Puede necesitarse más para descompresión de PDFs |
| **Reserved concurrency** — Sin límite | Un pico de requests podría saturar la DB o S3 |

##### Fase 4: Monitoreo y Observabilidad
| Item | Por qué es necesario |
|---|---|
| **Structured logging** — `pipeline.py` usa `print()` para debug (líneas 47-48, 54-55, 68-69, 78-79, 100-104, 108-109) | En Lambda no hay stdout visible salvo por CloudWatch. Cambiar a `log.info()` |
| **CloudWatch alarms** — Sin monitoreo de errores, latencia, throttles | No saberías si el pipeline está fallando en producción |
| **Métricas de negocio** — Cantidad de PDFs procesados, tasa de error por banco, duplicados | No hay dashboards ni métricas personalizadas |
| **Dead Letter Queue (DLQ)** — Eventos fallidos se pierden | Si el pipeline falla, no hay reintento ni registro del evento |
| **X-Ray tracing** — Sin tracing distribuido | Dificulta diagnosticar cuellos de botella (S3, DB, pipeline) |

##### Fase 5: Calidad de Datos y Resiliencia
| Item | Por qué es necesario |
|---|---|
| **Graceful degradation si S3 falla** — Hoy si `upload_to_s3()` falla, retorna error y no procesa | Podría seguir procesando sin S3 y guardar solo en DB |
| **Request validation en API Gateway** — Sin validación de payload size, content-type | Un PDF corrupto o demasiado grande pasa igual hasta llegar al pipeline |
| **Idempotency tokens** — SHA-256 cubre duplicados exactos, pero no reintentos | Si el mismo PDF se envía dos veces por defecto de red, el segundo falla como duplicado. Eso está bien, pero no hay tracking de request_id |
| **Health check endpoint** — Sin endpoint `/health` | No hay forma de monitorear que el servicio está vivo |

##### Fase 6: Documentación
| Item | Por qué es necesario |
|---|---|
| **OpenAPI/Swagger spec** — La API no tiene definición formal | El bot de WhatsApp necesita saber el contrato exacto de entrada/salida |
| **Deployment runbook** — No hay guía paso a paso | Un nuevo integrante o un recovery post-fallo requiere conocimiento tácito |
| **Environment variables reference** — No hay lista completa de vars con descripción | `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `S3_BUCKET`, etc. no están documentadas en un solo lugar |
| **Database schema** — La tabla `impo_uni_archivos_upload` no tiene DDL documentado | Para crear la tabla en producción, hay que deducir el schema del código |

---

## Roadmap: Fases para Producción

### Fase 0: Bug Fixes (inmediato, ~1 día)
- [ ] Eliminar marcadores de merge conflict en `README.md`
- [ ] Eliminar archivo `src/models/trace.py` (vacío)
- [ ] Eliminar archivo `prov.txt` (debug orphan)
- [ ] Eliminar o ignorar archivo `Makefile` redundante (hay dos?)
- [ ] Revisar y corregir `stage_confidence` en `tests/mutations/runner.py` (si aplica)
- [ ] Reemplazar `print()` en `pipeline.py` por `log.info()`

### Fase 1: Infraestructura como Código (~1 semana)
- [ ] Definir API Gateway (REST o HTTP API) con:
  - Ruta `POST /process` (o la que corresponda)
  - Payload máximo 10MB (default API Gateway es 10MB)
  - Content-Type validation (`application/pdf` o `multipart/form-data`)
  - Timeout consistente con Lambda (29s para REST API)
- [ ] Crear IaC (Terraform recomendado, o SAM/CDK) con:
  - Lambda function + execution role IAM
  - API Gateway + integration con Lambda
  - S3 bucket + policies
  - ECR repository + lifecycle policy
  - VPC + subnets + security groups para SQL Server
  - VPC Endpoints para S3 y CloudWatch Logs
  - Secrets Manager para credenciales DB
- [ ] Configurar Lambda:
  - Timeout: 60s (o más según PDFs más grandes)
  - Memory: 1024MB (ajustable)
  - Ephemeral storage: 1024MB
  - Reserved concurrency: 5 (evitar saturación DB)
  - DLQ: SQS o SNS para fallos

### Fase 2: Seguridad (~2-3 días)
- [ ] Migrar credenciales DB de env vars a Secrets Manager
- [ ] Agregar KMS encryption en `s3_service.py` (opcional, depende del bucket policy)
- [ ] Configurar API Key o IAM auth en API Gateway
- [ ] Revisar IAM roles con mínimo privilegio:
  - Lambda: `s3:PutObject`, `s3:GetObject` (bucket específico)
  - Lambda: `ec2:CreateNetworkInterface`, `ec2:DescribeNetworkInterfaces` (VPC)
  - Lambda: `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
  - Lambda: `secretsmanager:GetSecretValue`
- [ ] Habilitar encryption at rest en S3 (SSE-S3 o SSE-KMS)

### Fase 3: Observabilidad (~2 días)
- [ ] Reemplazar `print()` por logging estructurado con JSON
- [ ] Agregar CloudWatch alarms:
  - Lambda errors > 0 en 5 min
  - Lambda throttles > 0
  - API Gateway 5xx > 0
  - Pipeline duration > p99
- [ ] Agregar métricas de negocio (CloudWatch Embedded Metric Format):
  - `ProcessedPDFs` (por banco)
  - `ProcessingDuration`
  - `DuplicateRate`
  - `ErrorRate`
- [ ] Habilitar X-Ray tracing en Lambda
- [ ] Configurar DLQ (SQS) con alarmas

### Fase 4: Resiliencia (~2 días)
- [ ] Graceful degradation: si S3 falla, procesar igual y persistir solo en DB (o viceversa)
- [ ] Implementar `request_id` tracking para correlación de logs
- [ ] Agregar validación de PDF en handler (magic bytes + size + content-type)
- [ ] Timeout específico para pipeline (separado del timeout de Lambda)
- [ ] Retry con exponential backoff en S3 upload y DB save

### Fase 5: Documentación (~1 día)
- [ ] Escribir OpenAPI/Swagger spec (`docs/openapi.yaml`)
- [ ] Escribir deployment runbook (`docs/deploy-runbook.md`)
- [ ] Escribir reference de environment variables (`docs/env-vars.md`)
- [ ] Escribir DDL de la tabla SQL Server (`docs/schema.sql`)
- [ ] Actualizar `README.md` con badges de CI, instrucciones de deploy, y enlaces a docs

### Fase 6: Post-Deploy (opcional, iterativo)
- [ ] Monitorear CloudWatch Logs por errores de parsing de bancos existentes
- [ ] Agregar soporte para nuevos bancos a pedido
- [ ] Optimizar memoria/timeout de Lambda basado en métricas reales
- [ ] Implementar S3 trigger si se necesita procesamiento por upload a bucket
- [ ] Performance tuning: cachear pdfplumber pages, profiling del pipeline

---

## Arquitectura Target (Producción)

```
WhatsApp Bot (otra Lambda)
    │
    │ POST /process (PDF bytes, filename)
    ▼
API Gateway (REST/HTTP)
    │
    ▼
Lambda (extractos-bancarios) ← Docker imagen ECR
    │
    ├── Validación (magic bytes, size)
    ├── SHA-256 → check DB (duplicado?)
    ├── Upload PDF a S3 (cifrado)
    ├── Pipeline de extracción (9 etapas)
    ├── Save resultado a SQL Server
    └── Response {exito, duplicado, mensaje, resumen}
         │
         ▼
    WhatsApp Bot → User
```

### Servicios AWS requeridos
| Servicio | Propósito |
|---|---|
| **Lambda** | Procesamiento serverless (container image) |
| **API Gateway** | Endpoint HTTP para recibir PDFs |
| **ECR** | Repositorio de imágenes Docker |
| **S3** | Almacenamiento de PDFs originales |
| **CloudWatch** | Logs, métricas, alarmas |
| **Secrets Manager** | Credenciales de DB |
| **VPC + Subnets + SG** | Acceso seguro a SQL Server |
| **SQS (opcional)** | DLQ para eventos fallidos |
| **X-Ray (opcional)** | Tracing distribuido |
| **KMS (opcional)** | Cifrado de S3 |

### Dependencias externas
| Servicio | Propósito |
|---|---|
| **SQL Server** | Persistencia de resultados (on-premise o RDS) |
| **Meta Cloud API** | Bot de WhatsApp (otra Lambda, fuera de scope) |
