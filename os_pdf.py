def build_os_pdf(order, company, logo_path, public_url=None):
    from io import BytesIO
    import os
    from xml.sax.saxutils import escape

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as e:
        raise RuntimeError("ReportLab não está instalado no ambiente") from e

    buffer = BytesIO()

    def _text(value):
        if value is None:
            return ""
        return str(value)

    def _multiline_paragraph(text, style):
        t = (_text(text) or "").strip()
        if not t:
            t = "N/A"
        return Paragraph(escape(t).replace("\n", "<br/>"), style)

    def _money(value):
        try:
            v = float(value or 0)
        except Exception:
            v = 0.0
        s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {s}"

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="Ordem de Serviço",
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "os_title",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        spaceAfter=6,
        textColor=colors.HexColor("#111111"),
    )
    style_section = ParagraphStyle(
        "os_section",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        spaceBefore=10,
        spaceAfter=6,
        textColor=colors.HexColor("#111111"),
    )
    style_small = ParagraphStyle(
        "os_small",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#333333"),
    )
    style_value = ParagraphStyle(
        "os_value",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#111111"),
    )
    style_block = ParagraphStyle(
        "os_block",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#111111"),
    )

    company_name = (company.get("name") or "").strip() or "Clínica CELL"
    company_cnpj = (company.get("cnpj") or "").strip()
    company_phone = (company.get("phone") or "").strip()
    company_address = (company.get("address") or "").strip()
    company_city = (company.get("city") or "").strip()
    company_website = (company.get("website") or "").strip()

    header_right_lines = [
        f"<b>{company_name}</b>",
        f"CNPJ: {company_cnpj or 'N/A'}",
        f"Telefone: {company_phone or 'N/A'}",
        f"Endereço: {(company_address + (' - ' + company_city if company_city else '')).strip() or 'N/A'}",
    ]
    if company_website:
        header_right_lines.append(f"Site: {company_website}")

    header_right = Paragraph("<br/>".join(header_right_lines), style_small)

    logo_cell = ""
    try:
        if logo_path and os.path.exists(logo_path):
            from PIL import Image as _PILImage

            img = _PILImage.open(logo_path).convert("RGBA")
            bg = _PILImage.new("RGBA", img.size, (255, 255, 255, 255))
            bg.alpha_composite(img)
            rgb = bg.convert("RGB")

            img_buffer = BytesIO()
            rgb.save(img_buffer, format="PNG")
            img_buffer.seek(0)

            logo = Image(img_buffer)
            max_w = 30 * mm
            max_h = 18 * mm
            iw = float(getattr(logo, "imageWidth", 0) or 0)
            ih = float(getattr(logo, "imageHeight", 0) or 0)
            if iw > 0 and ih > 0:
                scale = min(max_w / iw, max_h / ih)
                logo.drawWidth = iw * scale
                logo.drawHeight = ih * scale
            else:
                logo.drawWidth = max_w
                logo.drawHeight = max_h

            logo_cell = logo
    except Exception:
        logo_cell = ""

    def _separator():
        return Table(
            [[""]],
            colWidths=[doc.width],
            style=TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#111111"))]),
        )

    def _kv_table(pairs):
        rows = []
        for k, v in pairs:
            rows.append([Paragraph(f"<b>{escape(_text(k))}</b>", style_small), _multiline_paragraph(v, style_value)])
        return Table(
            rows,
            colWidths=[48 * mm, doc.width - 48 * mm],
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F3F3")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            ),
        )

    def _block_box(title, body):
        table = Table(
            [
                [Paragraph(f"<b>{escape(_text(title))}</b>", style_small)],
                [_multiline_paragraph(body, style_block)],
            ],
            colWidths=[doc.width],
            style=TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F3F3")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            ),
        )
        return table

    header_table = Table(
        [[logo_cell, header_right, ""]],
        colWidths=[32 * mm, doc.width - 32 * mm - 28 * mm, 28 * mm],
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        ),
    )

    if public_url:
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics import renderPDF
        from reportlab.platypus import Flowable

        class _DrawingFlowable(Flowable):
            def __init__(self, drawing, width, height):
                super().__init__()
                self.drawing = drawing
                self.width = width
                self.height = height

            def wrap(self, availWidth, availHeight):
                return self.width, self.height

            def draw(self):
                renderPDF.draw(self.drawing, self.canv, 0, 0)

        qr_size = 24 * mm
        qr_widget = QrCodeWidget(public_url)
        bounds = qr_widget.getBounds()
        bw = bounds[2] - bounds[0]
        bh = bounds[3] - bounds[1]
        drawing = Drawing(qr_size, qr_size, transform=[qr_size / bw, 0, 0, qr_size / bh, 0, 0])
        drawing.add(qr_widget)

        qr_flow = _DrawingFlowable(drawing, qr_size, qr_size)
        qr_caption = Paragraph("Status da OS", style_small)
        header_table._cellvalues[0][2] = [qr_flow, Spacer(1, 2 * mm), qr_caption]

    elements = [header_table, Spacer(1, 6 * mm)]

    elements.append(_separator())
    elements.append(Spacer(1, 6 * mm))

    os_number = order.get("os_number")
    os_number_text = f"{int(os_number):06d}" if os_number not in [None, ""] else (order.get("id") or "N/A")
    opened_at = order.get("opened_at") or "N/A"
    status = order.get("status") or "N/A"

    customer = order.get("customer") or {}
    customer_snapshot = order.get("customer_snapshot") or {}
    customer_name = (customer.get("full_name") or customer_snapshot.get("full_name") or "").strip() or "N/A"
    customer_doc = (customer_snapshot.get("doc_number") or customer.get("doc_number") or "").strip() or "N/A"
    customer_phone = (customer_snapshot.get("phone_primary") or customer.get("phone_primary") or "").strip() or "N/A"
    customer_email = (customer_snapshot.get("email") or customer.get("email") or "").strip() or "N/A"

    equipment = order.get("equipment") or {}
    eq_type = (equipment.get("type") or "").strip() or "N/A"
    eq_brand = (equipment.get("brand") or "").strip() or "N/A"
    eq_model = (equipment.get("model") or "").strip() or "N/A"
    eq_serial = (equipment.get("serial_number") or "").strip() or "N/A"
    accessories = equipment.get("accessories") or []
    if isinstance(accessories, list):
        accessories_text = ", ".join([str(a).strip() for a in accessories if str(a).strip()]) or "N/A"
    else:
        accessories_text = str(accessories).strip() or "N/A"

    reported_issue = (order.get("reported_issue") or "").strip() or "N/A"
    technical_diagnosis = (order.get("technical_diagnosis") or "").strip() or "N/A"
    required_service = (order.get("required_service") or "").strip() or "N/A"

    labor_value = order.get("labor_value", 0)
    parts_value = order.get("parts_value", 0)
    total_value = order.get("total_value", 0)

    elements.append(Paragraph("Ordem de Serviço", style_title))
    elements.append(
        _kv_table(
            [
                ("Número da OS", os_number_text),
                ("Data de abertura", opened_at),
                ("Status", status),
            ]
        )
    )

    elements.append(Paragraph("Dados do Cliente", style_section))
    elements.append(
        _kv_table(
            [
                ("Nome", customer_name),
                ("CPF/CNPJ", customer_doc),
                ("Telefone", customer_phone),
                ("E-mail", customer_email),
            ]
        )
    )

    elements.append(Paragraph("Dados do Equipamento", style_section))
    elements.append(
        _kv_table(
            [
                ("Tipo de equipamento", eq_type),
                ("Marca", eq_brand),
                ("Modelo", eq_model),
                ("Número de série", eq_serial),
                ("Acessórios entregues", accessories_text),
            ]
        )
    )

    elements.append(Paragraph("Descrição do Serviço", style_section))
    elements.append(
        _kv_table(
            [
                ("Defeito relatado", reported_issue),
                ("Diagnóstico técnico", technical_diagnosis),
                ("Serviço executado", required_service),
            ]
        )
    )

    elements.append(Paragraph("Valores", style_section))
    values_table = Table(
        [
            ["Descrição", "Valor"],
            ["Mão de obra", _money(labor_value)],
            ["Peças", _money(parts_value)],
            ["Total", _money(total_value)],
        ],
        colWidths=[doc.width - 40 * mm, 40 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111111")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#F3F3F3")),
                ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
            ]
        ),
    )
    elements.append(values_table)

    warranty_notes = (order.get("warranty_notes") or "").strip()
    responsibility_term = (order.get("responsibility_term") or "").strip()

    elements.append(Paragraph("Observações da Garantia", style_section))
    elements.append(_block_box("Garantia", warranty_notes or "N/A"))

    elements.append(Paragraph("Termo de Responsabilidade", style_section))
    elements.append(_block_box("Termo", responsibility_term or "N/A"))

    elements.append(Spacer(1, 12 * mm))
    sign_table = Table(
        [
            [
                Paragraph("Assinatura do Cliente", style_small),
                Paragraph("Assinatura do Técnico", style_small),
            ],
            ["", ""],
            ["", ""],
        ],
        colWidths=[doc.width / 2, doc.width / 2],
        style=TableStyle(
            [
                ("LINEABOVE", (0, 2), (0, 2), 1, colors.HexColor("#111111")),
                ("LINEABOVE", (1, 2), (1, 2), 1, colors.HexColor("#111111")),
                ("TOPPADDING", (0, 1), (-1, 2), 18),
                ("BOTTOMPADDING", (0, 1), (-1, 2), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        ),
    )
    elements.append(sign_table)

    doc.build(elements)
    return buffer.getvalue()
