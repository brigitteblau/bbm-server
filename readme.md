
probar el bpy y correrlo el paso 2

 8dc2193d-351e-4377-8b88-3f7c959ac3ff


 to do: 
mejorar

# BBM Server (Hunda)

API para generación de prótesis caninas 3D-printables.

## Correr local
python3 -m venv venv
source venv/bin/activate   # mac
pip install -r requirements.txt
uvicorn app.main:app --reload


venv\Scripts\Activate.ps1

## Tests
python -m pytest tests/ -v

{
  "user_id": "eec346a3-8425-4e56-b077-48f733cf59e1",
  "dog_name": "Copito",
  "dog_weight_kg": 18,
  "dog_breed": "Caniche",
  "dog_size": "mediano",
  "limb_position": "delantera",
  "limb_side": "derecha",
  "stump_length_cm": 9,
  "proximal_circumference_cm": 18,
  "distal_circumference_cm": 13
}


lo proximo es 

Tu próximo paso, escrito
Objetivo de la sesión Blender: que el generate devuelva "generator_used": "blender-gn-v1" con "fallback_reason": null, y que el STL abierto en el visor sea un cono hueco correcto.
1. Python 3.11 en tu Mac (bpy no existe para tu 3.13):
bashbrew install python@3.11
2. Venv paralelo con 3.11 (el actual no lo toques, es tu entorno estable):
bashcd ~/Desktop/bbm-server
python3.11 -m venv venv311
source venv311/bin/activate
pip install -r requirements.txt
pip install bpy
El pip install bpy baja ~300 MB, paciencia. Si falla, copiame el error exacto — suele ser cuestión de versión.
3. Verificar que bpy vive:
bashpython -c "import bpy; print(bpy.app.version_string)"
Anotá la versión que imprime (importa para el paso 4).
4. El fix del export que ya sabemos que está roto (tu log lo dijo: "Converting py args to operator properties"). En blender_gn.py, en bpy.ops.wm.stl_export, cambiá use_selection=True por export_selected_objects=True. Si la versión del paso 3 es 3.x en vez de 4.x, el operador es otro (bpy.ops.export_mesh.stl con use_selection) — por eso anotaste la versión.
5. Probar:
bashBLENDER_ENABLED=true uvicorn app.main:app --reload
Generá desde /docs con la misma request de Copito. Buscás: "generator_used": "blender-gn-v1", "fallback_reason": null.
6. Verificación visual: bajá el STL del download_url, abrilo con barra espaciadora en Finder. Tiene que ser un cono hueco de ~9 cm de alto, más ancho arriba (radio ~2.9 cm) que abajo (~2.1 cm), abierto arriba, cerrado abajo con un anillo. Si en vez de eso ves un cilindro sólido, caras faltantes o un engendro, sacale screenshot y lo depuramos juntos.
7. Confirmar el fallback sigue vivo: matá la env var, generá de nuevo, verificá que vuelve a trimesh-scale-v1. Commit final: feat: generador Blender GN funcionando local.
8. (Solo si todo lo anterior anduvo, y es opcional hoy): medí la RAM del proceso uvicorn durante una generación con Blender (Activity Monitor → Memory). Ese número decide la estrategia de deploy, que es la sesión siguiente.
El único paso con riesgo real de trabarse es el 2 (la instalación de bpy) — si pasa, error completo y lo resolvemos. Todo lo demás es terreno conocido. ¡Dale!




primer paso de aca ---paso 1 front