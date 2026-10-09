# Criterio de Buchón

Buchón avisa en Discord, con una mención a todo el canal, cuando un organismo publica algo que obliga a modificar la localización argentina de Eynes (`l10n_ar_eynes` y sus complementos). Solo publica lo urgente y lo semiurgente. Este archivo dice qué cubre la localización, qué vale un aviso, con qué urgencia y cómo se escribe.

## Qué hace la localización

**ARCA**
- Factura electrónica por web service: WSAA (autenticación y certificados), WSFE, WSFEX (exportación) y WSFECRED (factura de crédito electrónica MiPyME, incluida la nómina de grandes empresas).
- Padrón: `ws_sr_constancia_inscripcion` para traer datos del contribuyente.
- Libro IVA Digital: archivos de comprobantes y alícuotas de ventas y compras, y alícuotas de importación. Ancho fijo.
- SICORE: retenciones y percepciones de IVA y Ganancias. Ancho fijo, 145 caracteres.
- Cálculo de retenciones de Ganancias e IVA en órdenes de pago: conceptos, escalas, mínimos no sujetos, códigos de régimen.
- Tablas que vienen cargadas: tipos de comprobante, tipos de documento, condiciones frente al IVA, códigos de moneda, conceptos de retención y percepción.
- Remitos con CAI y despachos de importación.

**ARBA**
- Archivos de percepciones (71 caracteres) y retenciones (67 caracteres), por quincena o mes, comprimidos.
- Régimen A-122R: declaración jurada y servicio web.
- Padrón de alícuotas por sujeto.
- COT (Código de Operación de Traslado).

**AGIP**
- e-ARCIBA: archivo de retenciones y percepciones (226 caracteres) y de notas de crédito (119 caracteres).
- Padrones de alícuotas.

**Comisión Arbitral (COMARB)**
- SIFERE: archivos de percepciones, retenciones y percepciones aduaneras, con sus 24 jurisdicciones.
- SIRCAR: percepciones y retenciones.
- No tiene exportador para SIRTAC, SIRCREB, SIRCUPA, SIRPEI ni SIRCIP, pero se vigilan: si uno pasa a ser obligatorio para agentes de retención o percepción comunes (SIRCIP es el más probable), va a hacer falta. Avisar con impacto bajo o medio según la fecha.
- Padrón Federal y nomenclador de actividades NAES: afectan los datos del contribuyente y los códigos de actividad.

**Provincias con exportador propio**
- Tucumán (SIRETPER e informe de IIBB), Salta (SIPOT y padrón de gasoil), Misiones (IIBB).

**Resto de las provincias**
- La localización calcula retenciones y percepciones de Ingresos Brutos de las 24 jurisdicciones con alícuotas configuradas, sin exportador propio. No se vigila cada provincia: la Gaceta Tributaria Provincial de COMARB trae una vez por mes el resumen de normas de todas. Cuando aparezca una gaceta nueva hay que leerla y avisar lo que toque regímenes de retención o percepción de Ingresos Brutos.

**Otros**
- Exportadores bancarios de pago a proveedores (Banco Nación, BBVA) y cheques, incluidos los electrónicos.
- Cotizaciones del Banco Nación.
- Ajuste por inflación contable (índices para RECPAM).

## Qué novedades importan

Una novedad importa si hace al menos una de estas cosas:

1. Cambia el **diseño de registro** o el formato de un archivo que la localización genera: campos, largos, códigos, separadores, nombre del archivo.
2. Cambia un **web service** que la localización consume: versión nueva del manual, métodos o campos nuevos u obligatorios, validaciones, fecha de baja de una versión, cambios de certificados o de TLS.
3. Cambia el **cálculo**: alícuotas, escalas, mínimos no sujetos a retención, montos a partir de los cuales rige una obligación (por ejemplo los topes de FCE MiPyME), conceptos o códigos de régimen.
4. Crea, reemplaza o deroga un **régimen** de retención, percepción o información de los que la localización cubre, o crea uno que previsiblemente haya que cubrir.
5. Cambia **tablas de códigos**: tipos de comprobante, de documento, condiciones frente al IVA, monedas, actividades, jurisdicciones.
6. Cambia datos que el **comprobante impreso o electrónico** debe llevar (leyendas, QR, discriminación de impuestos).
7. Cambia un **padrón** o su forma de consulta o descarga.

Que una novedad importe no alcanza para publicarla: la urgencia se decide más abajo.

## Qué no importa

- Prórrogas de vencimientos y plazos de presentación de declaraciones juradas.
- Planes de facilidades de pago, moratorias, intereses.
- Aduana y comercio exterior (clasificaciones arancelarias, regímenes aduaneros, depositarios), salvo que cambie el despacho de importación en el Libro IVA o WSFEX.
- Designaciones y renuncias de funcionarios, estructura interna de los organismos, licitaciones.
- Impuestos que la localización no liquida: Bienes Personales, Ganancias de personas humanas, monotributo en lo que hace al contribuyente, seguridad social y sueldos.
- Noticias institucionales, campañas, recordatorios de vencimientos de patentes o inmobiliario.
- En las páginas vigiladas: cambios de menú, de redacción o de enlaces que no apuntan a documentación técnica.
- Padrones que se renuevan todos los meses (AGIP, ARBA, Salta): que aparezca el archivo del mes nuevo no es novedad. Sí lo es que cambie el diseño, el nombre o la forma de descarga.
- Calendarios de vencimientos de SIFERE, SIRCAR, SIRTAC y similares, y sus prórrogas.
- Altas y bajas de agentes de retención o percepción con nombre y apellido (lo que publica Tucumán casi todas las semanas), salvo que la norma cambie el régimen.
- Casos concretos y resoluciones interpretativas sobre atribución de ingresos entre jurisdicciones.

## Avisos de mantenimiento

Algunas fuentes son listados de un año (resoluciones 2026 de ARBA, AGIP, COMARB, Tucumán y Misiones) y al lado se vigila su índice de años. Si en un índice aparece un año nuevo, las normas de ese año no se ven hasta que alguien sume la fuente. Eso no es un aviso de localización y no lleva mención a todos: se publica como mensaje simple con

`python buchon.py decir "buchón necesita mantenimiento: apareció el año <año> en <fuente>, hay que sumar <dirección> a fuentes.json"`

## Una misma norma en dos fuentes

Hay normas que llegan por dos caminos: las de AGIP por su listado y por el Boletín Oficial de la Ciudad; las de ARBA por su índice y por el buscador de normas de la provincia; las de ARCA por la Biblioteca y por el Boletín Oficial; las de COMARB por su sitio y por el Boletín Oficial. Se publica un solo aviso por norma. Antes de avisar, mirar `estado/avisados.json`, que guarda los últimos avisos publicados: si la norma ya está ahí, no se avisa de nuevo. Ese archivo sirve solo para no repetir: no es antecedente de qué urgencia corresponde. Que una norma parecida figure ahí no sube ni baja el impacto de una nueva, que se decide siempre con la sección de urgencia.

## Urgencia: qué se publica y qué no

Cada aviso publicado lleva una mención a todo el canal (`@everyone`), así que solo se publica cuando **hay que modificar algo** en la localización o en la configuración de los clientes. Lo demás se clasifica igual, pero no llega al canal.

- **alto (rojo, urgente)**: hay que modificar código o configuración y no hay margen. La vigencia ya empezó o empieza dentro de los próximos 30 días, o algo que hoy funciona va a dejar de funcionar: un diseño de registro que cambia, un campo que pasa a ser obligatorio, un web service o una versión que se da de baja, un régimen nuevo que hay que informar.
- **medio (amarillo, semiurgente)**: hay que modificar algo, pero hay más de 30 días o el cambio no rompe lo que hoy funciona. También va acá un documento técnico reemplazado (un manual, un diseño de registro) cuando se lo leyó y no se pudo determinar qué cambió: alguien tiene que mirarlo.
- **bajo (verde)**: informativo. No hay nada que modificar: afecta a algún cliente según su caso (por ejemplo, las altas y bajas en la nómina de agentes de retención de IVA de la RG 2854, que solo le importan al cliente nombrado), es un antecedente de algo que todavía no rige, o es una versión nueva de un documento que al leerla no cambia nada de lo que la localización usa. **No se publica.** Se incluye igual en el archivo de avisos con `"impacto": "bajo"` y el script lo guarda en `estado/no_publicados.json` para poder revisar después qué se dejó pasar.

Antes de poner alto o medio hay que haber leído la norma o el documento, no solo el título. Si cambió un manual o un diseño de registro, leerlo con `leer` y buscar su historial de versiones o de modificaciones para saber qué cambió.

Para elegir entre medio y bajo, la pregunta es una sola: ¿alguien de Eynes tiene que tocar código, datos o configuración por esto? Si la respuesta es sí o «no se puede saber sin que lo mire un desarrollador», es medio. Si es no, es bajo y no se publica. Una mención a todo el canal por algo que no pide ninguna acción hace que se dejen de leer; un cambio de formato que no se avisa termina en una presentación rechazada.

## Cómo leer una novedad

`pendientes.json` trae cada novedad con `titulo`, `detalle`, `fecha`, `organismo` y `link`. Con el título suele alcanzar para descartar. Si puede ser relevante, leer la norma antes de avisar:

- `python buchon.py leer "<link>"` muestra el texto de una norma, de una página o de un PDF (las primeras 12 páginas).
- `python buchon.py leer bo:<página>` muestra el texto del Boletín Oficial del día desde esa página (el dato viene en el campo `leer`).

En el Boletín Oficial muchas resoluciones del Ministerio de Economía aparecen sin título: hay que leerlas para saber de qué tratan. Casi todas son designaciones o temas ajenos.

Las novedades de tipo «Cambió la página» traen las líneas agregadas y quitadas. Las líneas que empiezan con `DOCUMENTO` son archivos enlazados: si cambia el tamaño o la fecha de un manual, el organismo lo reemplazó aunque el nombre sea el mismo.

## Cómo escribir el aviso

Un archivo JSON con una lista. Cada aviso:

```json
{
  "frase": "che, arca tocó el manual de wsfe",
  "impacto": "medio",
  "titulo": "ARCA publicó la versión 4.8 del manual de WSFE",
  "resumen": "Qué cambió, en dos a cinco oraciones, con los números y fechas de la norma. Sin copiar párrafos enteros.",
  "modulo": "l10n_ar_eynes: factura electrónica (WSFE). Revisar si los campos nuevos son obligatorios.",
  "vigencia": "01/12/2026",
  "organismo": "ARCA",
  "link": "https://..."
}
```

- `frase`: una línea corta, en minúscula y como la diría un compañero. Sin signos de apertura ni emojis de más.
- `resumen`: concreto. Si la norma no dice algo (por ejemplo la fecha de vigencia), decir que no lo dice. No inventar.
- `modulo`: qué parte de la localización se vería afectada y qué habría que revisar. Si no está claro, decirlo.
- `link`: a la norma o a la página que cambió.
- `impacto`: `alto`, `medio` o `bajo`, según la sección de urgencia.

El archivo lleva todas las novedades que importan, también las de impacto bajo. Se pasa entero a `python buchon.py avisar <archivo.json>`: el script publica las de impacto alto y medio con la mención a todos y guarda las de impacto bajo sin publicarlas. Las novedades que no importan (la mayoría) no van al archivo.
