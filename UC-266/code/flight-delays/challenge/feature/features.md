| Campo     | Descripción                               | Ejemplo             | Uso en Predicción           |
| --------- | ----------------------------------------- | ------------------- | --------------------------- |
| Fecha-I   | Fecha/Hora programada salida (Itinerario) | 2017-01-01 23:30:00 | Base para DIA, MES, HORA    |
| Vlo-I     | Número de vuelo (Itinerario)              | 226                 | Identificador único         |
| Ori-I     | Origen (Itinerario) - Código IATA         | SCEL (Santiago)     | Aeropuerto origen           |
| Des-I     | Destino (Itinerario) - Código IATA        | KMIA (Miami)        | Aeropuerto destino          |
| Emp-I     | Aerolínea (Itinerario) - Código IATA      | AAL                 | Compañía aérea              |
| Fecha-O   | Fecha/Hora real salida (Operación)        | 2017-01-01 23:33:00 | RETRASO = real - programada |
| Vlo-O     | Número de vuelo (Operación)               | 226                 | Identificador único         |
| Ori-O     | Origen (Operación)                        | SCEL                | Aeropuerto origen           |
| Des-O     | Destino (Operación)                       | KMIA                | Aeropuerto destino          |
| Emp-O     | Aerolínea (Operación)                     | AAL                 | Compañía aérea              |
| DIA       | Día del mes (1-31)                        | 1                   | Patrones estacionales       |
| MES       | Mes (1-12)                                | 1                   | Temporadas altas/bajas      |
| AÑO       | Año                                       | 2017                | Tendencias anuales          |
| DIANOM    | Día de la semana                          | Domingo             | Congestión por día          |
| TIPOVUELO | Tipo de vuelo                             | I (Internacional)   | I=Int, N=Nacional           |
| OPERA     | Nombre aerolínea                          | American Airlines   | Performance por compañía    |
| SIGLAORI  | Origen - Nombre aeropuerto                | Santiago            | Condiciones locales         |
| SIGLADES  | Destino - Nombre aeropuerto               | Miami               | Condiciones destino         |

```
2017-01-01 23:30:00,226,SCEL,KMIA,AAL,2017-01-01 23:33:00,226,SCEL,KMIA,AAL,1,1,2017,Domingo,I,American Airlines,Santiago,Miami
```
↳ Vuelo 226 American Airlines
↳ Santiago (SCEL) → Miami (KMIA) 
↳ Programado: 23:30 → Real: 23:33 **(3 min retraso)**
↳ Domingo 1/Enero/2017 - Internacional