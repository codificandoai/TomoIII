locust:     sirve para hacer pruebas de carga y rendimiento de APIs o servicios, simulando muchos usuarios concurrentes para ver latencia, errores y capacidad del sistema.
            Con locust puedes simular 1000 usuarios concurrentes accediendo a tu API.

coverage:   mide la cobertura de código en las pruebas, indicando qué porcentaje del código está siendo probado.

pytest:     framework para escribir y ejecutar pruebas unitarias en Python, con soporte para fixtures, parametrización y fixtures.
            Usas pytest para verificar que tu función de limpieza devuelve el formato correcto, los casos extremos,casos de error, casos de edge.

pytest-cov: extensión de pytest que integra la medición de cobertura de código con las pruebas.
            Con pytest-cov ves que solo cubriste 70% del código.

mockito:    librería para crear mocks y stubs en Python, útil para simular dependencias en las pruebas unitarias.
            Usas mockito para simular la base de datos o APIs externas durante las pruebas.

matplotlib: librería para crear visualizaciones estáticas, gráficos y diagramas en Python.

seaborn:    librería de visualización estadística basada en matplotlib, que ofrece una interfaz de alto nivel para crear gráficos más atractivos y estadísticamente informativos.
            Con seaborn graficas la distribución de errores del modelo


Por que librerias
-----------------
En un pipeline típico de IA, pytest y mockito validan que el preprocesamiento, inferencia y API funcionen bien; coverage y pytest-cov te dicen si realmente estás probando las rutas críticas del código. locust te permite comprobar si tu servicio aguanta tráfico real, algo clave cuando expones un modelo como API. matplotlib y seaborn te sirven para analizar datos, comparar métricas de entrenamiento y explicar resultados a negocio o al equipo técnico.


Para un modelo de desarrollo: 
- pytest + mockito para pruebas unitarias
- matplotlib/seaborn para visualizaciones

Para un modelo de IA en producción, una combinación muy común es: pytest + pytest-cov + mockito para calidad del código, locust para rendimiento, y matplotlib/seaborn para análisis y reportes. 