# Flujo de trabajo WSL + Git + VS Code

Este repositorio está preparado para trabajar desde Ubuntu en WSL, manteniendo Python,
dependencias y archivos de desarrollo fuera de Windows.

## 1. Ubicación recomendada

Guarda los repositorios dentro del filesystem Linux:

```bash
mkdir -p ~/dev
cd ~/dev
```

Evita desarrollar dentro de `/mnt/c/...` porque suele ser más lento para proyectos con
muchos archivos, entornos virtuales y herramientas de desarrollo.

## 2. Primera vez en cada PC

```bash
cd ~/dev
git clone <URL-DEL-REPOSITORIO>
cd <NOMBRE-DEL-REPOSITORIO>
code .
```

Dentro del terminal WSL:

```bash
make setup
```

Después edita `.env` y agrega tus secretos locales.

Arranca la aplicación:

```bash
make run
```

Desde Windows abre:

```text
http://localhost:8000
```

WSL publica normalmente el puerto hacia Windows automáticamente.

## 3. Trabajo diario

Antes de empezar:

```bash
git switch main
git pull --rebase
```

Para una funcionalidad:

```bash
git switch -c feat/nombre-corto
```

Trabaja normalmente y prueba con:

```bash
make run
```

Guarda cambios:

```bash
git status
git add .
git commit -m "feat: descripción del cambio"
git push -u origin feat/nombre-corto
```

Luego integra mediante Pull Request/Merge Request, o directamente a `main` si ese es el
flujo definido por tu equipo.

## 4. Continuar en otro PC

```bash
cd ~/dev/<NOMBRE-DEL-REPOSITORIO>
git switch main
git pull --rebase
```

Si la rama ya existe en remoto:

```bash
git fetch --all --prune
git switch feat/nombre-corto
git pull --rebase
```

Cada PC mantiene su propio `.env` y `.venv`; ninguno debe subirse a Git.

## 5. Qué sí y qué no se versiona

Sí:
- `app/`
- `scripts/`
- `requirements.txt`
- `Makefile`
- `.env.example`
- `.vscode/`
- documentación

No:
- `.env`
- `.venv/`
- `research.db`
- `__pycache__/`
- claves API o credenciales

## 6. Sobre `research.db`

La V0.1 usa SQLite y `research.db` es local a cada PC. Eso está bien para desarrollo.

Cuando quieras que varias personas o varios PCs compartan el mismo historial,
migraremos esta parte a PostgreSQL alojado en un servidor o servicio corporativo.

## 7. Comandos rápidos

```bash
make setup   # crea .venv e instala dependencias
make run     # inicia el servidor de desarrollo
make health  # comprueba que la API responde
make clean   # elimina el entorno local y caches
```
