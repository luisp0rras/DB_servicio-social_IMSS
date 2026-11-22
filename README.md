# SIGEM — Sistema Integral de Gestión de Equipo Médico

**SIGEM** es una aplicación web desarrollada durante mi Servicio Social en Ingeniería Biomédica para llevar el control del inventario de equipo médico hospitalario en unidades médicas del IMSS en Chihuahua.

La idea principal del sistema es dejar atrás el manejo disperso de hojas de cálculo y concentrar en un solo lugar los hospitales, censos de inventario, equipos médicos, transferencias entre unidades, mantenimientos, proveedores y documentos técnicos. Además, está pensada para funcionar **sin conexión a internet** dentro de redes hospitalarias locales.

> ¿Quieres instalarlo o ver cómo se usa paso a paso? Revisa la **[Guía de Instalación y Uso](GUIA_INSTALACION_Y_USO.md)**.

---

## ¿Qué hace el sistema?

### Panel de Control y Navegación
- **Interfaz basada en recuadros:** Menú lateral colapsable en Verde IMSS, buscador global en la parte superior para localizar equipos por nombre, `NNI` o `SN` desde cualquier pantalla y barra de accesos rápidos.
- **Indicadores ejecutivos (6 recuadros KPI):** Total de equipos, porcentaje de disponibilidad operativa con aro visual, equipos fuera de servicio, garantías próximas/vencidas (30 días), mantenimientos programados/atrasados y unidades médicas activas. Cada recuadro filtra o lleva directo al módulo correspondiente.
- **Estado por Unidad Médica y Agenda de Alertas:** Tarjetas por hospital con barra de operatividad y lista de pendientes ordenada por urgencia, además de las tablas completas de detalle y un botón de actualización rápida.

### Equipos Médicos y Expediente Unificado
- **Catálogo Maestro con filtros en vivo:** Búsqueda y filtrado combinado por texto, inventario, hospital actual, proveedor, área, marca, garantía y estatus funcional, en una tabla con encabezados fijos y barra horizontal cómoda para ratón.
- **Expediente Unificado del Equipo (4 pestañas):** Al hacer clic en el nombre de cualquier equipo se abre su ficha completa con:
  1. **General:** Datos técnicos, ubicación, proveedor, estatus de garantía y observaciones.
  2. **Mantenimientos:** Historial de intervenciones preventivas y correctivas del equipo.
  3. **Transferencias:** Bitácora histórica de cambios entre unidades médicas (origen, destino, fecha, motivo u oficio y responsable).
  4. **Documentos:** Archivos PDF o imágenes vinculados directamente a ese equipo.
- **Manejo flexible de `NNI` y `SN`:** Si un equipo no cuenta con `NNI` ni `SN` (como camillas o mobiliario clínico básico), se puede registrar dejando ambos campos vacíos sin generar errores. Cuando sí tienen código, el sistema valida que no se dupliquen y prioriza el `NNI` (o muestra el `SN` como respaldo) en alertas y correos.
- **Alta Individual:** Registro rápido de nuevas adquisiciones directamente en un hospital mediante ventana emergente.

### Inventarios e Importación Masiva
- **Vista de Tarjetas y Lista:** Alternancia entre recuadros por levantamiento (con conteo de equipos censados y estado `EN PROCESO` o `FINALIZADO`) y vista de tabla.
- **Pantalla dedicada de captura:** Al abrir o crear un inventario, la vista se enfoca únicamente en ese censo, con botón para volver al listado y tabla completa que incluye proveedor, garantía y observaciones.
- **Importación desde Excel / CSV con *Drag & Drop*:** Plantilla descargable, zona interactiva de arrastrar y soltar, soporte para equipos sin `NNI`/`SN` y **protección anti-duplicados con huella SHA-256** que impide subir dos veces el mismo archivo CSV por accidente.
- **Exportación a Excel (`.xlsx`):** Reportes con formato institucional IMSS tanto de un inventario completo como de cualquier filtro aplicado en el catálogo, incluyendo proveedor, garantía y observaciones.

### Mantenimientos, Proveedores y Documentos
- **Mantenimientos con búsqueda inteligente:** Al registrar una intervención en la ventana emergente, primero se elige el hospital y se busca el equipo por `NNI`, `SN` o nombre, mostrando una vista previa con marca, modelo y ubicación antes de guardar.
- **Directorio de Proveedores:** Vista en tarjetas o tabla con enlaces directos para llamar o enviar correo, además de alta, edición y baja segura (sin borrar el historial de equipos o mantenimientos).
- **Repositorio Documental inteligente:** Subida de PDFs e imágenes con zona *Drag & Drop*. Al asociar un documento a un **Inventario**, **Mantenimiento** o **Equipo**, aparecen filtros específicos (hospital, fecha, proveedor, `NNI`/`SN`) y una tarjeta de vista previa para confirmar que se vincula al registro correcto.

### Alertas, Seguridad y Modo Offline
- **Operación 100 % Offline en la interfaz:** Bootstrap 5, Bootstrap Icons, tipografías del sistema, aros SVG y avatares por defecto con iniciales se generan y cargan localmente sin depender de internet.
- **Campanita de notificaciones y correo único por hitos:** La campanita muestra vencimientos en los próximos 30 días. En segundo plano, el servidor revisa las fechas y envía un correo natural y consolidado a los administradores únicamente en dos momentos: cuando faltan **7 días o menos** y cuando un registro **vence**, usando banderas en PostgreSQL para no repetir correos todos los días. *(El envío de correo solo opera si el equipo tiene conexión a internet y SMTP configurado; si está sin red, la aplicación sigue trabajando normalmente).*
- **Roles y acceso seguro:** Roles `ADMIN`, `EMPLEADO` e `INACTIVO`, contraseñas cifradas con `bcrypt` y recuperación de acceso mediante código temporal de 6 dígitos por correo.

---

## Tecnologías Utilizadas

- **Backend:** Python 3.10+, FastAPI, Uvicorn, SQLAlchemy, Pydantic v2, Bcrypt, Openpyxl.
- **Base de Datos:** PostgreSQL (administrable con pgAdmin 4).
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla), Bootstrap 5 y Bootstrap Icons (archivos locales en `frontend/vendor/`).

---

## Base de Datos (10 tablas en PostgreSQL)

El script `sql/01_tablas.sql` crea la estructura relacional completa:

1. `hospital` — Unidades médicas (nombre, ciudad, estado).
2. `proveedor` — Empresas de soporte biomédico y datos de contacto.
3. `usuarios` — Cuentas, contraseñas cifradas, perfil y rol (`ADMIN`, `EMPLEADO`, `INACTIVO`).
4. `equipos` — Catálogo maestro de activos, garantías, estatus y banderas de alerta.
5. `inventarios` — Levantamientos por unidad médica y fecha (`EN_PROCESO` / `FINALIZADO`).
6. `mantenimientos` — Intervenciones (`PREVENTIVO`, `CORRECTIVO`, `OTRO`), próximas fechas y banderas de alerta.
7. `documentos` — Registro y ruta física de archivos vinculados a un inventario, equipo o mantenimiento.
8. `inventario_equipo` — Relación N:M entre inventarios y equipos censados.
9. `inventario_usuario` — Relación N:M de usuarios participantes en cada inventario.
10. `transferencias_equipo` — Historial de movimientos de equipos entre hospitales.

---

## Estructura del Proyecto

```text
├── app/
│   ├── __init__.py
│   ├── database.py               # Conexión a PostgreSQL y sesiones SQLAlchemy
│   ├── main.py                   # API REST, exportación Excel, control SHA-256 y motor de alertas
│   ├── models.py                 # Modelos ORM de las 10 tablas
│   └── schemas.py                # Validaciones de entrada y salida (Pydantic v2)
├── frontend/
│   ├── css/
│   │   └── styles.css            # Estilos institucionales CMMS, tarjetas, modales y dropzones
│   ├── vendor/                   # Bootstrap 5 y Bootstrap Icons locales (modo offline)
│   ├── dashboard.html            # Interfaz principal con los 8 módulos y expediente de equipos
│   ├── favicon.svg               # Ícono local de la aplicación
│   └── login.html                # Inicio de sesión, registro y recuperación de contraseña
├── sql/
│   └── 01_tablas.sql             # Script DDL de tablas, restricciones e índices
├── archivos_subidos/             # PDFs, imágenes, avatares y control de CSV (ignorado en Git)
├── .env                          # Variables de entorno locales (ignorado en Git)
├── .gitignore
├── GUIA_INSTALACION_Y_USO.md     # Guía paso a paso de instalación y manual de usuario
├── README.md
└── requirements.txt
```

---

## Inicio Rápido

```bash
git clone <URL_DEL_REPOSITORIO>
cd <CARPETA_DEL_PROYECTO>
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abre en tu navegador: `http://127.0.0.1:8000` (o la documentación interactiva en `http://127.0.0.1:8000/docs`).

Para ver la configuración completa de PostgreSQL, el archivo `.env`, cómo crear tu primer administrador y cómo usar cada pantalla, consulta la **[Guía de Instalación y Uso](GUIA_INSTALACION_Y_USO.md)**.