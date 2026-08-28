# Reglas de git
# ######################
# main branch protection
Bloquear pushes directos a main y permitir cambios solo vía pull request.
- Para main, debes crear una regla que bloquee pushes directos, evite borrado y force push, y obligue a que los cambios entren solo por Pull Request con checks aprobados
- Add classic branch protection rule si quieres proteger específicamente main de forma simple y directa. 
- GitHub indica que las reglas clásicas sirven para bloquear force push, evitar borrado de la rama y exigir pull requests o checks antes de fusionar, main solo acepta pull requests.
    Branch name pattern: main.
    Activa Require a pull request before merging.
    Activa Require status checks to pass before merging.
    Desactiva Allow force pushes.
    Desactiva Allow deletions.
    Si aparece, activa Require linear history para mantener historial limpio

# auditory
Exigir al menos una o más aprobaciones antes de combinar, según el tamaño y criticidad del equipo.
Requerir que pasen los checks de CI/CD antes de permitir el merge, por ejemplo tests, lint, build y security scans.
Activar “require linear history” si quieres evitar merges desordenados y mantener un historial limpio.
Deshabilitar force push y borrado de la rama main.
Proteger también los workflows sensibles en GitHub Actions, fijando acciones de terceros por SHA y limitando permisos del token

# CDCI
Cada PR debe pasar CI.
Al menos un reviewer debe aprobar.
Nadie puede hacer push directo ni force push.
El merge se hace solo si el release está validado en staging o preproducción.

# retain history
- mantener la historia (do not delete your development branches).
    Abre Branches o Rulesets, según lo que te muestre tu repo.
    Crea una regla para tus ramas de desarrollo, por ejemplo:
    develop
    feature/*
    release/*
    Activa estas opciones:
        Prevent branch deletion o Do not allow deletions.
        Prevent force pushes o Do not allow force pushes.
        Si aplica, Require pull request before merging.

# patrones
vamos a manejar para ML el patrón: feature/* → develop o release/* → main. Cuando la rama release/* está estabilizada, se fusiona a main y se etiqueta la versión para producción, reduciendo el riegos que entren cambios incompletos a la rama principal.

# recomendation
para “solo releases listas para producción”, configura main como rama de producción inmutable, y usa una rama release para el endurecimiento final antes del merge. Eso te da trazabilidad, control de calidad y un historial limpio de entregas.
