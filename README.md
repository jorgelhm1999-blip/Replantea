# Replantea

Aplicación local de replanteo de ejes en DWG/DXF para Windows de 64 bits.

## Descargar el programa

1. Abra **Actions → Compilar Replantea para Windows**.
2. Entre en la última ejecución terminada correctamente.
3. En **Artifacts**, descargue **Replantea-Windows-x64**.
4. Descomprima el ZIP y abra **Replantea.exe**.

El ejecutable lleva Python y sus dependencias integrados. El usuario final no necesita instalar Python ni ejecutar los `.cmd` del prototipo anterior.

## Compilación automática

El workflow usa Windows 2022 y Python 3.12 x64. Ejecuta pruebas geométricas, comprueba lectura DXF/DWG y arranque de la interfaz, compila con PyInstaller y ejecuta las mismas comprobaciones desde el binario congelado. Solo publica el artefacto de descarga si las comprobaciones terminan correctamente.

Se activa al actualizar el código en `main` o manualmente con **Run workflow**. No requiere tokens ni secretos adicionales. Los artefactos duran 30 días; puede regenerarlos ejecutando de nuevo el workflow.

## Uso

Seleccione una fila para resaltar el eje en el mapa. Ordene los ejes con **Mayús + ↑ / ↓** o los botones Subir/Bajar, o arrastre filas hasta la línea naranja de inserción. La flecha del eje resaltado muestra el sentido creciente. La numeración sigue el orden de las filas y el sentido del eje, incluidos los encuentros interiores. Los puntos compartidos conservan su primer número. Cambiar el orden reinicia las posiciones de etiquetas recolocadas.

Seleccione **1:1000** o **1:2000** en la interfaz. Los perfiles fijan alturas y marcas de 3 m. Los PK se rotulan cada 100 m en ambas escalas y todos los textos generados usan ARIAL; consulte `LEEME_USO.txt`. Los radios se exportan como DIMENSION radiales editables. Los rótulos de centro quedan próximos al centro, sin directriz. En cada cambio recta/curva se dibuja una marca perpendicular con RECTA y R=XXX.XXX a ambos lados, alineados con ella, y el PK exacto en el extremo. Los brazos de 3,5 m y 32,646 m se pueden ajustar en la interfaz. Las anotaciones usan ACI 9 y RGB 192,192,192; los vértices usan ARIAL y RGB 0,0,250.

Configure nombre y PK inicial, revise el sentido y calcule. Puede mover etiquetas y exportar un DXF nuevo con puntos, tangencias, centros, radios, PK y cuadros X/Y. Incluye CSV de coordenadas, curvas y elementos e informe de incidencias. Las tablas son entidades LINE/TEXT editables.

**Glorietas (0.4.0):** seleccione uno o varios ejes y pulse **Marcar glorieta** o **Quitar glorieta**. También puede alternar la columna **Glorieta** con doble clic. La clasificación es manual; puede aplicarse a varios arcos independientes de una misma glorieta. Recalcula sin cambiar el encuadre. Los ejes marcados no generan V (incluidos PI y encuentros), ni líneas auxiliares hacia la intersección de tangentes; conservan centros, tangencias, radios y PK. Un acceso sin marcar conserva sus propios V en los encuentros. `Ejes.json` documenta la clasificación; no es un archivo de sesión reimportable.

**Tablas:** ARIAL de altura 2; columnas de 10 / 19,2289 / 19,2289 y todas las filas de altura 4, en unidades de modelo, para ambas escalas. X/Y tienen justificación medio centro y su punto de alineación queda 9,1366 a la derecha y 2,0211 abajo desde la esquina superior izquierda de cada celda de datos. Identificadores V/C/TE/TS azules (RGB 0,0,255); coordenadas, cabeceras, títulos subrayados y rejilla negros (RGB 0,0,0). Cabecera escalonada con X/Y, sin celda vacía sobre el identificador. Vértices a la izquierda, centros a la derecha y tangentes debajo de centros. No se inventan bases BR ni cotas Z.

**Anotaciones de curvas (0.5.0):** cada centro tiene círculo de radio 1 y MTEXT ARIAL de altura 1,75, ambos azules RGB 0,0,250. El MTEXT tiene fondo RGB 250,250,250, factor de borde 1,0001 y no lleva directriz. Además del radio, las curvas con PI finito y sin marcar como glorieta llevan una DIMENSION del ángulo interior entre PI–TE y PI–TS, en grados centesimales con cuatro decimales: flechas oblicuo grueso ARCHTICK de 0,75, extensión 1,25 y desfase 0,625. Las dos tangentes se rotulan con MULTILEADER nativas `TE=…` y `TS=…` (longitud de cada segmento, dos decimales) apuntando a sus puntos medios: recta, sin extremo de cota, conexión horizontal y separación de 0,5, extensión de directriz activada, ARIAL 1,5, enlaces izquierdo/derecho «subrayar línea superior» y sin marco. Ángulo y directrices negros. La colocación se calcula automáticamente y es editable en CAD. El DXF de salida es al menos 2013 para conservar la propiedad de extensión de directriz; el archivo de entrada conserva su versión y geometría. Las glorietas mantienen centros y radios, sin ángulos ni directrices hacia PI.

El archivo original conserva su geometría. No se ajustan radios ni se cierran o agrupan ejes automáticamente. La numeración es provisional hasta revisarla. El cálculo es en XY; no se generan cotas Z ni bases topográficas no aportadas. Consulte `LEEME_USO.txt` para formatos admitidos y limitaciones.

## Desarrollo y pruebas

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\python -m unittest discover -s . -p "test_*.py" -v
.venv\Scripts\python launcher.py --self-test --gui-test --report source-selftest.json
.venv\Scripts\python -m PyInstaller --noconfirm --clean Replantea.spec
```

El repositorio contiene exclusivamente código y un DWG sintético de prueba. No contiene planos reales ni coordenadas de proyectos.

## Interfaz e inicio (0.6.0)

Introducción aprobada de 12,5 segundos al iniciar, con Abrir ahora o Escape para acceder directamente. Interfaz con cabecera azul marino, acciones en azul petróleo y filas alternas. Se retira la línea informativa de alturas; las incidencias se conservan en un panel oculto que se abre con Mostrar incidencias. Icono propio de eje bajo una lupa en el ejecutable Windows, título, barra de tareas y cabecera superior derecha.
