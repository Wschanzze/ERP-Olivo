import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from django.http import HttpResponse
from django.utils import timezone
from apps.core.models import Empresa

def export_to_excel(queryset, columns, report_title, filename):
    """
    Exporta un QuerySet a un archivo Excel (.xlsx) corporativo.
    
    :param queryset: El QuerySet de Django o una lista de diccionarios/objetos.
    :param columns: Lista de tuplas (Titulo_Columna, Nombre_Atributo_o_Lambda)
    :param report_title: Titulo del reporte (ej. 'Reporte de Insumos')
    :param filename: Nombre base del archivo (ej. 'insumos') sin extension
    :return: HttpResponse con el archivo .xlsx adjunto
    """
    empresa = Empresa.objects.first()
    razon_social = empresa.razon_social if empresa else "Empresa S.A."
    cuit = empresa.cuit if empresa else "-"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = report_title[:31]  # Excel titles max 31 chars

    # Estilos
    title_font = Font(name='Arial', size=14, bold=True, color='003D4A2A')
    header_font = Font(name='Arial', size=10, bold=True, color='FFFFFFFF')
    header_fill = PatternFill(start_color='005A6E3F', end_color='005A6E3F', fill_type='solid')
    center_align = Alignment(horizontal='center', vertical='center')
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

    last_col_letter = openpyxl.utils.get_column_letter(len(columns))

    # Encabezado Empresa
    ws.merge_cells(f'A1:{last_col_letter}1')
    ws['A1'] = f"{razon_social.upper()} - CUIT {cuit}"
    ws['A1'].font = title_font
    ws['A1'].alignment = Alignment(horizontal='center')
    
    # Titulo de Reporte
    ws.merge_cells(f'A2:{last_col_letter}2')
    ws['A2'] = report_title.upper()
    ws['A2'].font = Font(name='Arial', size=12, bold=True)
    ws['A2'].alignment = Alignment(horizontal='center')

    # Fecha
    ws.merge_cells(f'A3:{last_col_letter}3')
    ws['A3'] = f"Fecha de Emisión: {timezone.now().strftime('%d/%m/%Y %H:%M')} | ERP Olivícola"
    ws['A3'].font = Font(name='Arial', size=9, italic=True)
    ws['A3'].alignment = Alignment(horizontal='center')

    ws.append([]) # Fila 4 vacia

    # Cabeceras
    headers = [col[0] for col in columns]
    ws.append(headers) # Fila 5
    
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=5, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border

    # Datos
    for item in queryset:
        row_data = []
        for col_title, accessor in columns:
            if callable(accessor):
                val = accessor(item)
            elif isinstance(item, dict):
                val = item.get(accessor, '')
            else:
                val = getattr(item, accessor, '')
                # Si es un modelo relacional o choice, intentar resolverlo
                if val is None:
                    val = ''
                elif hasattr(val, 'all'): # ManyToMany
                    val = ", ".join(str(v) for v in val.all())
                elif hasattr(item, f"get_{accessor}_display"):
                    val = getattr(item, f"get_{accessor}_display")()
            
            # Format numbers properly for excel
            if isinstance(val, bool):
                val = "Sí" if val else "No"
            row_data.append(val)
        ws.append(row_data)

    # Ajuste de ancho de columnas
    for col_idx, col in enumerate(ws.columns, 1):
        max_length = 0
        column = openpyxl.utils.get_column_letter(col_idx)
        for cell in col:
            if cell.row > 4 and cell.value is not None:
                max_length = max(max_length, len(str(cell.value)))
        ws.column_dimensions[column].width = min(max(max_length + 3, 12), 45)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    fecha_str = timezone.now().strftime('%Y%m%d_%H%M')
    response['Content-Disposition'] = f'attachment; filename="{filename}_{fecha_str}.xlsx"'
    wb.save(response)
    return response
