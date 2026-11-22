# Guía de Instalación y Uso — SIGEM

Esta guía explica paso a paso cómo descargar, configurar y arrancar **SIGEM** desde cero en una computadora con Windows, así como el flujo básico para usarlo en el día a día.

---

## Parte 1: Requisitos Previos

Antes de empezar, asegúrate de tener instalado lo siguiente:

1. **Git:** Para clonar el repositorio ([git-scm.com](https://git-scm.com/)).
2. **Python 3.10 o superior:** Al instalarlo en Windows, marca la casilla **"Add Python to PATH"** ([python.org](https://www.python.org/)).
3. **PostgreSQL (con pgAdmin 4):** Motor de base de datos ([postgresql.org](https://www.postgresql.org/)). Recuerda la contraseña que elijas para el usuario `postgres`.

Puedes comprobar que Python y Git están listos abriendo **PowerShell** y ejecutando:

```powershell
python --version
git --version
```

---

## Parte 2: Instalación Paso a Paso

### 1. Clonar el repositorio

Abre PowerShell en la carpeta donde quieras guardar el proyecto y ejecuta:

```powershell
git clone <https://github.com/luisp0rras/DB_servicio-social_IMSS>
cd <backend_>
```

### 2. Crear y activar el entorno virtual

Esto mantiene las librerías de Python aisladas del resto de tu computadora:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

> **Nota si PowerShell bloquea el script:** Ejecuta una sola vez `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, confirma con `S` y vuelve a correr `.\venv\Scripts\Activate.ps1`. Sabrás que está activo cuando veas `(venv)` al inicio de la línea.

### 3. Instalar las dependencias

Con el entorno virtual activo, instala los paquetes del proyecto:

```powershell
pip install -r requirements.txt
```

### 4. Crear la base de datos en PostgreSQL

1. Abre **pgAdmin 4** e inicia sesión con tu contraseña de `postgres`.
2. Da clic derecho en **Databases** -> **Create** -> **Database...**
3. Ponle un nombre claro, por ejemplo: `sigem_biomedica` (o el nombre que prefieras) y guarda.
4. Da clic derecho sobre la base de datos recién creada y selecciona **Query Tool**.
5. Abre el archivo `sql/01_tablas.sql` del proyecto (ícono de carpeta o copia y pega su contenido) y ejecútalo con **F5** (botón *Play*).
6. Verifica en **Schemas -> public -> Tables** que se hayan creado las **10 tablas**.

### 5. Configurar el archivo `.env`

En la carpeta raíz del proyecto (al mismo nivel que `README.md` y `requirements.txt`), crea un archivo llamado `.env` con el siguiente contenido y ajusta tus datos:

```env
# Conexión a PostgreSQL
DATABASE_URL=postgresql://postgres:TU_CONTRASENA_POSTGRES@localhost:5432/sigem_biomedica

# Configuración de correo Gmail (opcional, solo para alertas y recuperación de contraseña)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_correo@gmail.com
SMTP_PASSWORD=tu_contrasena_de_aplicacion_de_16_letras
```

> **Sobre Gmail (`SMTP_PASSWORD`):** Gmail no acepta tu contraseña normal para aplicaciones externas. Debes activar la *Verificación en dos pasos* en tu cuenta de Google, ir a **Contraseñas de aplicaciones**, generar una para "SIGEM" y pegar ese código de 16 caracteres (sin espacios) en `SMTP_PASSWORD`.
> **Modo sin internet:** Si usarás el sistema 100 % offline, puedes dejar los campos `SMTP_*` vacíos; el resto de la plataforma funcionará sin problema.

### 6. Arrancar el servidor

Con `(venv)` activo en PowerShell, ejecuta:

```powershell
uvicorn app.main:app --reload
```

Si quieres que otras computadoras conectadas a la **misma red local (Wi-Fi o Ethernet del hospital)** puedan entrar a SIGEM usando tu IP local:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Luego abre tu navegador en:
- **Aplicación web:** `http://127.0.0.1:8000`
- **Documentación API (Swagger):** `http://127.0.0.1:8000/docs`
- **Prueba rápida de conexión a BD:** `http://127.0.0.1:8000/health-db`

### 7. Crear tu primer usuario Administrador

Por seguridad, todas las cuentas nuevas creadas desde la pantalla de registro nacen con rol `EMPLEADO`. Para convertir tu primera cuenta en `ADMIN`:

1. Entra a `http://127.0.0.1:8000`, haz clic en **Crear cuenta** y regístrate con tu correo.
2. Abre **pgAdmin 4** -> **Query Tool** sobre tu base de datos y ejecuta:

```sql
UPDATE usuarios
SET rol = 'ADMIN'
WHERE correo = 'tu_correo@ejemplo.com';
```

3. Cierra sesión en la web y vuelve a iniciar sesión. Ya verás habilitados todos los botones de administración y el módulo **Usuarios** en el menú lateral. A partir de aquí podrás dar rol `ADMIN` a otras personas directo desde la interfaz.

---

## Parte 3: Guía de Uso Diario

### 1. Panel de Control
- Al entrar verás **6 recuadros KPI** clicables (equipos totales, disponibilidad operativa, fuera de servicio, garantías a 30 días, mantenimientos y unidades médicas).
- Debajo tienes **Estado por Unidad Médica** (clic en cualquier hospital para ver solo sus equipos) y la **Agenda de Alertas** ordenada por urgencia.
- En la barra superior puedes buscar cualquier equipo por nombre, `NNI` o `SN` sin importar en qué sección estés, y revisar la **campanita** de notificaciones.

### 2. Levantamiento de Inventarios e Importación CSV
1. Entra a **Inventarios** (puedes alternar entre vista de **Tarjetas** y **Lista**).
2. Haz clic en **Iniciar Nuevo Inventario**, elige el hospital (o regístralo ahí mismo si es nuevo), la fecha y los participantes.
3. Se abrirá una pantalla enfocada únicamente en ese inventario con dos formas de captura:
   - **Registro Manual:** Captura equipo por equipo. Los campos `SN` y `NNI` son opcionales si el equipo no cuenta con ellos.
   - **Importación Masiva desde Excel / CSV:**
     1. Descarga la **Plantilla CSV de Ejemplo** desde la misma pestaña.
     2. Prepara tu archivo en Excel cuidando que la fila 1 tenga exactamente los encabezados esperados (`nombre_equipo`, `area`, `subarea`, `marca`, `modelo`, `sn`, `nni`, `garantia`, `fecha_expgarantia`, `estatusfuncional`, `observaciones`).
     3. Deja las celdas vacías en lugar de escribir textos como *"Sin marca"* o *"Sin modelo"* para mantener limpios los filtros.
     4. Guarda en Excel como **CSV UTF-8 (delimitado por comas) (*.csv)**.
     5. Arrastra el archivo a la zona punteada y presiona **Importar CSV**.
     - *Seguridad:* El sistema calcula la huella `SHA-256` del archivo para evitar que se suba dos veces el mismo CSV por error, y omite automáticamente equipos cuyo `SN` o `NNI` ya exista en la base de datos.
4. Cuando termines el censo, presiona **Finalizar Inventario** para bloquear nuevas ediciones. Puedes descargar su reporte en **Exportar (.xlsx)** en cualquier momento.

### 3. Catálogo de Equipos Médicos y Expediente Unificado
- Usa los filtros superiores para combinar búsqueda por texto, inventario, hospital, proveedor, área, marca, garantía o estatus, y exporta esa selección exacta a Excel.
- Haz clic en el **nombre de cualquier equipo** (o en el ícono de expediente) para abrir su **Ficha Unificada** con 4 pestañas: *General*, *Mantenimientos*, *Transferencias* y *Documentos*, más accesos rápidos para editarlo, transferirlo o cargarle un archivo.
- Para dar de alta una adquisición nueva sin abrir un inventario, usa **+ Nuevo Equipo**.
- Para mover un equipo a otra unidad médica, usa el botón de **Transferir** (flechas encontradas); el cambio actualiza el hospital actual y guarda el registro con fecha y motivo/oficio en la bitácora.

### 4. Mantenimientos
- Al hacer clic en **Registrar Mantenimiento**, selecciona primero el **Hospital** y usa el buscador por `NNI`, `SN` o nombre para ubicar el equipo rápidamente.
- Antes de guardar, el recuadro de vista previa te confirmará el nombre, área, marca, modelo, `NNI` y `SN` del equipo elegido.
- Si capturas una **Próxima Fecha Programada**, el sistema comenzará a monitorearla automáticamente en la campanita (30 días) y enviará el aviso por correo cuando falten 7 días o si llega a vencerse.

### 5. Proveedores y Documentos
- En **Proveedores** puedes alternar entre **Tarjetas** (con enlaces rápidos a correo y teléfono) y **Lista**. Si eliminas un proveedor, los equipos y mantenimientos anteriores conservan su historial sin borrarse.
- En **Documentos**, al presionar **Subir Documento**, elige si el archivo pertenece a un **Inventario**, **Mantenimiento** o **Equipo Médico**. Usa los filtros dinámicos (hospital, fecha, proveedor o `NNI`/`SN`), revisa la tarjeta de confirmación y arrastra tu PDF o imagen a la zona punteada.

### 6. Mi Perfil y Usuarios
- En **Mi Perfil** cada usuario puede subir su foto local, cambiar su `username` y actualizar su contraseña.
- En **Usuarios** (solo `ADMIN`) se pueden cambiar roles entre `EMPLEADO` y `ADMIN`, bloquear cuentas dejándolas como `INACTIVO` o eliminar usuarios.

---

## Solución Rápida de Problemas

| Problema | Causa probable | Solución |
| :--- | :--- | :--- |
| Error al activar `venv` en PowerShell | Política de ejecución de scripts en Windows | Ejecuta `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelve a activar `.\venv\Scripts\Activate.ps1`. |
| `Error al conectar con la base de datos` en `/health-db` | Servicio de PostgreSQL detenido o datos erróneos en `.env` | Verifica que PostgreSQL esté corriendo y que usuario, contraseña, puerto (`5432`) y nombre de BD coincidan en `.env`. |
| No se ven los cambios visuales tras actualizar el código | Caché del navegador | Recarga la página con **`Ctrl + F5`** (recarga forzada). |
| No salen los correos de alertas o recuperación | Sin internet o contraseña normal de Gmail en `.env` | Verifica tu conexión y asegúrate de usar una **Contraseña de aplicación** de 16 caracteres de Google en `SMTP_PASSWORD`. |
| Error `Este archivo CSV ya fue importado` | Protección anti-duplicados `SHA-256` | Ese mismo archivo ya se cargó antes. Si cancelas/eliminas el inventario anterior, la huella se libera automáticamente. |
