#!/bin/bash
# Abre el menú de sesiones de Claude Code
# Doble-click para ejecutar — te muestra todas tus conversaciones anteriores
# y puedes elegir cuál continuar (o presionar Esc para empezar una nueva).

cd "$HOME"
exec claude --resume
