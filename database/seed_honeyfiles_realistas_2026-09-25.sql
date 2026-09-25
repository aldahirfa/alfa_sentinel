-- ============================================================
-- ALFA-Sentinel -- 12 plantillas de honeyfile realistas (2026-09-25)
--
-- 3 señuelos por cada carpeta donde se despliegan honeyfiles, además
-- de los 3 que ya existían (Dulce_Trampa.pdf, Ojito.docx,
-- No_Me_Toques.txt), que se mantienen activos:
--
--   ruta lógica  archivo                                        tipo
--   DESKTOP      Acta_Reunion_Directorio_Agosto_2026.docx       DOCX
--   DESKTOP      Informe_Avance_Proyecto_Q3_2026.pdf            PDF
--   DESKTOP      Planilla_Viaticos_Septiembre_2026.xlsx         XLSX
--   DOCUMENTS    Contrato_Servicios_Consultoria_2026.docx       DOCX
--   DOCUMENTS    Presupuesto_Institucional_2026.xlsx            XLSX
--   DOCUMENTS    Estados_Financieros_Gestion_2025.pdf           PDF
--   DOWNLOADS    Extracto_Bancario_Agosto_2026.pdf              PDF
--   DOWNLOADS    Planilla_Sueldos_Septiembre_2026.xlsx          XLSX
--   DOWNLOADS    Respaldo_Accesos_Sistemas_2026.zip             ZIP
--   PICTURES     Escaneo_Carnet_Identidad_Anverso.jpg           JPG
--   PICTURES     Comprobante_Transferencia_Bancaria_Agosto.jpg  JPG
--   PICTURES     Nota_Autorizacion_Firmada.png                  PNG
--
-- Son archivos REALES: el servidor genera un PDF, DOCX, XLSX, ZIP o
-- imagen válidos a partir de 'content' (ver server/honeyfile_content.py).
-- Formato de 'content': cada línea es un párrafo (la primera es el
-- título); en XLSX cada línea es una fila con celdas separadas por '|'.
--
-- Nombres, carnets, cuentas y montos son FICTICIOS. Temas elegidos por
-- lo que un atacante busca primero: finanzas, sueldos, contratos,
-- documentos de identidad y accesos.
--
-- auto_deploy = TRUE: los agentes existentes y nuevos los reciben solos
-- en su próxima sincronización (cada 45 s), sin reiniciar nada.
--
-- Seguro de correr más de una vez: cada INSERT va con NOT EXISTS por
-- 'file_name'.
--
--   psql -U <usuario> -d alfa_sentinel -f seed_honeyfiles_realistas_2026-09-25.sql
-- ============================================================

BEGIN;

INSERT INTO honeyfile_templates (name, file_name, file_type, file_path, operating_system, content, auto_deploy, is_active, created_by)
SELECT v.name, v.file_name, v.file_type, v.file_path, 'ALL', v.content, TRUE, TRUE, NULL
FROM (VALUES

('Acta Reunion Directorio Agosto 2026', 'Acta_Reunion_Directorio_Agosto_2026.docx', 'DOCX', 'DESKTOP',
'ACTA DE REUNIÓN DE DIRECTORIO N° 08/2026
Fecha: 14 de agosto de 2026 - Hora: 09:30 - Lugar: Sala de reuniones, piso 3
Asistentes: Lic. Marcelo Quispe Rojas (Director General), Ing. Daniela Vargas Céspedes (Jefa de Tecnologías), Lic. Roberto Mamani Flores (Jefe Administrativo Financiero).

Orden del día:
1. Aprobación del presupuesto reformulado de la gestión 2026.
2. Avance del proyecto de modernización de plataformas institucionales.
3. Renovación de contratos de servicios de consultoría.

Resoluciones:
- Se aprueba el presupuesto reformulado por Bs 4.850.000.
- Se instruye concluir la migración de servidores antes del cierre del tercer trimestre.
- Se autoriza la renovación del contrato de soporte técnico por 12 meses.

Documento de uso interno. Prohibida su difusión.'),

('Informe Avance Proyecto Q3 2026', 'Informe_Avance_Proyecto_Q3_2026.pdf', 'PDF', 'DESKTOP',
'INFORME DE AVANCE - PROYECTO DE MODERNIZACIÓN DE PLATAFORMAS (TERCER TRIMESTRE 2026)
Elaborado por: Unidad de Tecnologías de la Información
Periodo: julio a septiembre de 2026

1. Resumen ejecutivo
El proyecto registra un avance físico del 68% y una ejecución presupuestaria del 61%.

2. Actividades concluidas
- Migración de 14 servidores virtuales al nuevo centro de datos.
- Implementación del sistema de gestión documental en 3 unidades.
- Capacitación a 42 funcionarios en el uso de las nuevas plataformas.

3. Riesgos identificados
- Retraso en la adquisición de licencias de respaldo.
- Dependencia de un único proveedor para el enlace de datos secundario.

4. Próximos pasos
Concluir la migración de bases de datos y el plan de continuidad antes del 15 de octubre.'),

('Planilla Viaticos Septiembre 2026', 'Planilla_Viaticos_Septiembre_2026.xlsx', 'XLSX', 'DESKTOP',
'N°|Funcionario|Cargo|Destino|Días|Viático diario (Bs)|Total (Bs)
1|Juan Carlos Choque Apaza|Técnico de Soporte|Cochabamba|3|371|1113
2|María Elena Gutiérrez Paz|Analista Financiera|Santa Cruz|4|371|1484
3|Luis Fernando Condori Ríos|Jefe de Proyecto|Sucre|2|464|928
4|Ana Lucía Torrez Vaca|Asistente Legal|Tarija|3|371|1113
5|Diego Alejandro Salazar Mendoza|Ingeniero de Redes|Oruro|1|371|371
|||||TOTAL|5009'),

('Contrato Servicios Consultoria 2026', 'Contrato_Servicios_Consultoria_2026.docx', 'DOCX', 'DOCUMENTS',
'CONTRATO ADMINISTRATIVO DE PRESTACIÓN DE SERVICIOS DE CONSULTORÍA INDIVIDUAL DE LÍNEA N° 045/2026
PRIMERA (PARTES): Suscriben el presente contrato la entidad contratante, representada por el Lic. Marcelo Quispe Rojas, y el consultor Ing. Carlos Eduardo Fernández Tapia, con C.I. 6184523 LP.
SEGUNDA (OBJETO): El consultor prestará servicios de administración de sistemas y seguridad de la información.
TERCERA (PLAZO): Desde el 1 de febrero hasta el 31 de diciembre de 2026.
CUARTA (MONTO): Bs 9.800 mensuales, con un total de Bs 107.800 por la gestión.
QUINTA (FORMA DE PAGO): Pago mensual mediante transferencia a la cuenta N° 1000-2587416 del Banco Unión S.A., previa presentación de informe aprobado.
SEXTA (CONFIDENCIALIDAD): El consultor no podrá divulgar información institucional a la que acceda en el ejercicio de sus funciones.

La Paz, 28 de enero de 2026.'),

('Presupuesto Institucional 2026', 'Presupuesto_Institucional_2026.xlsx', 'XLSX', 'DOCUMENTS',
'Partida|Descripción|Presupuesto vigente (Bs)|Ejecutado a agosto (Bs)|% Ejecución
11700|Sueldos y salarios|2150000|1433300|66.7
25200|Estudios, investigaciones y consultorías|780000|412500|52.9
26990|Otros servicios|315000|198400|63.0
39800|Otros repuestos y accesorios|96000|41200|42.9
43120|Equipo de computación|1250000|689000|55.1
43700|Otra maquinaria y equipo|259000|120750|46.6
|TOTAL|4850000|2895150|59.7'),

('Estados Financieros Gestion 2025', 'Estados_Financieros_Gestion_2025.pdf', 'PDF', 'DOCUMENTS',
'ESTADOS FINANCIEROS AL 31 DE DICIEMBRE DE 2025
Balance general (expresado en bolivianos)

ACTIVO
Disponibilidades: 1.284.530,40
Cuentas por cobrar: 312.870,00
Bienes de uso (neto): 3.906.215,75
Total activo: 5.503.616,15

PASIVO
Cuentas por pagar a corto plazo: 486.320,90
Previsiones: 214.000,00
Total pasivo: 700.320,90

PATRIMONIO
Capital institucional: 4.100.000,00
Resultados acumulados: 703.295,25
Total pasivo y patrimonio: 5.503.616,15

Documento sujeto a auditoría externa. Uso restringido.'),

('Extracto Bancario Agosto 2026', 'Extracto_Bancario_Agosto_2026.pdf', 'PDF', 'DOWNLOADS',
'EXTRACTO DE CUENTA CORRIENTE - AGOSTO 2026
Titular: Entidad Pública - Cuenta Única Institucional
Cuenta N°: 1000-4471902 - Moneda: Bolivianos

01/08/2026  Saldo inicial                              1.842.310,55
05/08/2026  Transferencia recibida - TGN                 950.000,00
07/08/2026  Pago planilla de sueldos julio            -1.071.620,30
12/08/2026  Pago proveedor - servicios de internet       -48.500,00
19/08/2026  Pago consultorías individuales               -98.000,00
26/08/2026  Pago proveedor - equipos de computación     -312.450,00
31/08/2026  Saldo final                                1.261.740,25'),

('Planilla Sueldos Septiembre 2026', 'Planilla_Sueldos_Septiembre_2026.xlsx', 'XLSX', 'DOWNLOADS',
'N°|C.I.|Nombre completo|Cargo|Haber básico (Bs)|Descuentos AFP (Bs)|Líquido pagable (Bs)|N° de cuenta
1|4829317 LP|Marcelo Quispe Rojas|Director General|18500|2359|16141|1000-3308841
2|5937102 LP|Daniela Vargas Céspedes|Jefa de Tecnologías|14200|1811|12389|1000-2764490
3|6184523 LP|Roberto Mamani Flores|Jefe Administrativo Financiero|14200|1811|12389|1000-1953207
4|7042861 CB|Juan Carlos Choque Apaza|Técnico de Soporte|7400|944|6456|1000-4127736
5|8315094 SC|María Elena Gutiérrez Paz|Analista Financiera|8900|1135|7765|1000-3589012
6|6620473 LP|Luis Fernando Condori Ríos|Jefe de Proyecto|12600|1607|10993|1000-2240678'),

('Respaldo Accesos Sistemas 2026', 'Respaldo_Accesos_Sistemas_2026.zip', 'ZIP', 'DOWNLOADS',
'Respaldo de accesos - Unidad de Tecnologías (actualizado 20/08/2026)
NO COMPARTIR - USO EXCLUSIVO DEL ÁREA DE SISTEMAS

Sistema contable (SIGEP local)     usuario: contab_admin     clave: Cont4b#2026Ago
Servidor de archivos (\\srv-archivos)  usuario: adm_archivos  clave: Arch!vos_2026
Correo institucional (admin)       usuario: postmaster      clave: M4il-Inst.2026
Consola de firewall                usuario: fw_operador     clave: Fw0p#Seg26
Base de datos de personal          usuario: rrhh_dba        clave: Rrhh_Db!2026'),

('Escaneo Carnet Identidad Anverso', 'Escaneo_Carnet_Identidad_Anverso.jpg', 'JPG', 'PICTURES',
'ESTADO PLURINACIONAL DE BOLIVIA - CÉDULA DE IDENTIDAD
Servicio General de Identificación Personal

N° 6184523 LP
Nombres: CARLOS EDUARDO
Apellidos: FERNÁNDEZ TAPIA
Fecha de nacimiento: 17 de marzo de 1989
Lugar de nacimiento: La Paz
Fecha de emisión: 04/05/2022    Válido hasta: 04/05/2032'),

('Comprobante Transferencia Bancaria Agosto', 'Comprobante_Transferencia_Bancaria_Agosto.jpg', 'JPG', 'PICTURES',
'COMPROBANTE DE TRANSFERENCIA ELECTRÓNICA
Banco Unión S.A.

Fecha y hora: 26/08/2026 15:42:08
N° de operación: 0098457213
Cuenta de origen: 1000-4471902 (Cuenta Única Institucional)
Cuenta de destino: 1000-6012845 - Tecnología Andina S.R.L.
Monto: Bs 312.450,00
Glosa: Pago factura N° 2291 - adquisición de equipos de computación
Estado: PROCESADA'),

('Nota Autorizacion Firmada', 'Nota_Autorizacion_Firmada.png', 'PNG', 'PICTURES',
'NOTA INTERNA N° 112/2026
A: Lic. Roberto Mamani Flores - Jefe Administrativo Financiero
DE: Lic. Marcelo Quispe Rojas - Director General
REF.: Autorización de pago

Por medio de la presente autorizo el pago a la empresa Tecnología Andina S.R.L.
por Bs 312.450,00 correspondiente a la adquisición de equipos de computación,
según contrato N° 031/2026.

La Paz, 25 de agosto de 2026

(firma) Lic. Marcelo Quispe Rojas
Director General')

) AS v(name, file_name, file_type, file_path, content)
WHERE NOT EXISTS (
    SELECT 1 FROM honeyfile_templates t WHERE t.file_name = v.file_name
);

COMMIT;

SELECT file_path, file_name, file_type FROM honeyfile_templates
WHERE is_active = TRUE ORDER BY file_path, file_name;
