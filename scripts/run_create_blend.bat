@echo off
:: Corre create_base_blend.py con el ejecutable de Blender (no con Python del venv).
:: bpy pip NO puede guardar .blend validos — necesita el Blender real.

SET BLENDER=""
FOR %%V IN (4.4 4.3 4.2 4.1 4.0 3.6) DO (
    IF EXIST "C:\Program Files\Blender Foundation\Blender %%V\blender.exe" (
        SET BLENDER="C:\Program Files\Blender Foundation\Blender %%V\blender.exe"
        GOTO found
    )
)

echo No se encontro Blender en Program Files.
echo Edita este script y pone el path correcto a tu blender.exe en la variable BLENDER.
pause
EXIT /B 1

:found
echo Usando: %BLENDER%
echo.
%BLENDER% --background --python "%~dp0create_base_blend.py"
echo.
echo Listo. Revisa scripts\output\front-leg-default.blend
pause
