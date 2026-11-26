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

Seleccione una fila para resaltar el eje en el mapa. Ordene los ejes con **Mayús + ↑ / ↓** o los botones Subir/Bajar. La numeración sigue el orden de las filas y el sentido del eje, incluidos los encuentros interiores. Los puntos compartidos conservan su primer número. Cambiar el orden reinicia las posiciones de etiquetas recolocadas.

Seleccione **1:1000** o **1:2000** en la interfaz. Los perfiles fijan alturas, estilos, intervalo de PK y marcas de 3 m; consulte `LEEME_USO.txt`. Los radios se exportan como DIMENSION radiales editables. Las anotaciones usan ACI 9 y RGB 192,192,192; los vértices usan ARIAL y RGB 0,0,250.

Configure nombre y PK inicial, revise el sentido y calcule. Puede mover etiquetas y exportar un DXF nuevo con puntos, tangencias, centros, radios, PK y cuadros X/Y. Incluye CSV de coordenadas, curvas y elementos e informe de incidencias. Las tablas son entidades LINE/TEXT editables.

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
