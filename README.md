# Agente de Abastecimiento — MVP V0.2 (WSL-first)

> Flujo recomendado: Ubuntu en WSL + Git + VS Code Remote/WSL.
> No necesitas instalar Python, pip ni dependencias del proyecto directamente en Windows.

## Arranque rápido en WSL

```bash
cd ~/dev
git clone <URL-DEL-REPOSITORIO>
cd <NOMBRE-DEL-REPOSITORIO>
code .
make setup
```

Edita `.env` y después:

```bash
make run
```

Abre desde Windows:

```text
http://localhost:8000
```

Consulta `WORKFLOW_WSL.md` para el flujo entre varios PCs.

---

MVP para investigar y recomendar proveedores reales a partir de una necesidad de compra en lenguaje natural.

## Qué hace hoy

- Recibe una solicitud como: “Necesito 500 kg de papa negra R-12 para Bucaramanga”.
- Usa búsqueda web desde la API de OpenAI para investigar proveedores actuales.
- Separa información **confirmada**, **estimada** y **por confirmar**.
- Extrae precio, crédito, entrega, certificaciones/estándares, capacidad y contactos cuando hay evidencia.
- Muestra fuentes web clicables.
- Calcula un ranking transparente:
  - Precio: 35%
  - Crédito: 25%
  - Entrega: 20%
  - Certificaciones: 15%
  - Calidad de evidencia: 5%
- Guarda el historial localmente en SQLite.

## Requisitos

- Python 3.11 o 3.12
- Una clave de OpenAI API con acceso a Responses API y web search.

> La suscripción de ChatGPT y la API son productos separados. El uso de la API puede generar consumo facturable.

## Ejecutar en Windows / macOS / Linux

```bash
python -m venv .venv
```

Activa el entorno virtual.

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Instala dependencias:

```bash
pip install -r requirements.txt
```

Crea `.env` a partir de `.env.example` y agrega tu clave:

```env
OPENAI_API_KEY=sk-...
OPENAI_RESEARCH_MODEL=gpt-5.6-terra
OPENAI_EXTRACT_MODEL=gpt-5.6-luna
```

Inicia:

```bash
uvicorn app.main:app --reload
```

Abre:

```text
http://127.0.0.1:8000
```

## Ejecutar con Docker

```bash
docker build -t abastecimiento-ai .
docker run --rm -p 8000:8000 --env-file .env abastecimiento-ai
```

## Importante sobre confiabilidad

La aplicación está diseñada para NO rellenar vacíos inventando información.

- `Confirmado`: la investigación encontró evidencia explícita.
- `Estimado`: es una inferencia razonable y debe verificarse antes de comprar.
- `Por confirmar`: no se encontró evidencia suficiente.

El resultado es una herramienta de apoyo a compras, no una orden automática de adjudicación.

## Próximos pasos recomendados

1. Afinar prompts con 10–20 solicitudes reales de la empresa.
2. Agregar reglas de homologación de proveedores.
3. Añadir lista interna de proveedores cuando aparezca el archivo/ERP.
4. Añadir impuestos, flete y normalización robusta de unidades.
5. Incorporar autenticación y roles.
6. Desplegar en una nube corporativa.
7. Más adelante: preparar/enviar RFQ y capturar respuestas.

## Gestión de dependencias

Este proyecto usa `uv` y `pyproject.toml`. Ejecuta `uv sync` después de cada `git pull` si cambiaron dependencias.
