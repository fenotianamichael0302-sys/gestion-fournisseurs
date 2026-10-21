"""Rendu PDF des bons de commande."""
from html import escape
from io import BytesIO

from django.conf import settings
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _money(value):
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def _paragraph(value, style):
    return Paragraph(escape(str(value or "—")), style)


def purchase_order_pdf(order):
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Bon de commande {order.order_number}",
        author="Gestion Fournisseurs",
    )
    styles = getSampleStyleSheet()
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 12
    supplier = order.supplier
    company_block = [
        Paragraph(f"<b>{escape(settings.COMPANY_NAME)}</b>", styles["BodyText"]),
        *[
            Paragraph(escape(f"{label} : {value}"), styles["BodyText"])
            for label, value in (
                ("Adresse", settings.COMPANY_ADDRESS),
                ("E-mail", settings.COMPANY_EMAIL),
                ("Téléphone", settings.COMPANY_PHONE),
                ("NIF / STAT", settings.COMPANY_TAX_ID),
            )
            if value
        ],
    ]
    logo_style = ParagraphStyle(
        "OrderLogo",
        parent=styles["Heading2"],
        textColor=colors.white,
        alignment=1,
    )
    address = ", ".join(
        value
        for value in (
            supplier.street,
            supplier.city,
            supplier.postal_code,
            supplier.country,
        )
        if value
    )
    story = [
        Table(
            [[
                Paragraph("<b>F</b>", logo_style),
                Paragraph(f"<b>{escape(settings.COMPANY_NAME)}</b>", styles["Heading2"]),
            ]],
            colWidths=[14 * mm, 150 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#2457D6")),
                ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]),
        ),
        Spacer(1, 4 * mm),
        Paragraph("BON DE COMMANDE", styles["Title"]),
        Spacer(1, 4 * mm),
        Paragraph(f"<b>{escape(order.order_number)}</b>", styles["Heading2"]),
        Paragraph(
            f"Date : {order.order_date:%d/%m/%Y}"
            + (
                f" · Livraison prévue : {order.expected_delivery_date:%d/%m/%Y}"
                if order.expected_delivery_date
                else ""
            ),
            styles["BodyText"],
        ),
        Spacer(1, 5 * mm),
        Table(
            [[
                company_block,
                [
                    Paragraph("<b>Fournisseur</b>", styles["BodyText"]),
                    Paragraph(f"<b>{escape(supplier.company_name)}</b>", styles["BodyText"]),
                    Paragraph(f"Contact : {escape(supplier.contact_name or '—')}", styles["BodyText"]),
                    Paragraph(f"E-mail : {escape(supplier.email or '—')}", styles["BodyText"]),
                    Paragraph(f"Téléphone : {escape(supplier.phone or '—')}", styles["BodyText"]),
                    Paragraph(f"Adresse : {escape(address or '—')}", styles["BodyText"]),
                    Paragraph(f"NIF / STAT : {escape(supplier.tax_id or '—')}", styles["BodyText"]),
                ],
            ]],
            colWidths=[82 * mm, 82 * mm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (0, 0), 0.5, colors.HexColor("#D0D7E2")),
                ("BOX", (1, 0), (1, 0), 0.5, colors.HexColor("#D0D7E2")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]),
        ),
        Spacer(1, 6 * mm),
    ]
    headers = ["Désignation", "Quantité", "Prix unitaire HT", "Taxe", "Total HT", "Total TTC"]
    table_data = [[_paragraph(label, styles["BodyText"]) for label in headers]]
    for line in order.lines.all():
        table_data.append(
            [
                _paragraph(line.product_name, styles["BodyText"]),
                _paragraph(line.quantity, styles["BodyText"]),
                _paragraph(_money(line.unit_price), styles["BodyText"]),
                _paragraph(f"{_money(line.tax_rate)} %", styles["BodyText"]),
                _paragraph(_money(line.total_ht), styles["BodyText"]),
                _paragraph(_money(line.total_ttc), styles["BodyText"]),
            ]
        )
    table = Table(
        table_data,
        colWidths=[58 * mm, 18 * mm, 26 * mm, 16 * mm, 25 * mm, 25 * mm],
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2457D6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D0D7E2")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FB")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([table, Spacer(1, 5 * mm)])
    totals = [
        ["Total HT", _money(order.total_ht)],
        ["Total taxes", _money(order.total_tax)],
        ["Total TTC", _money(order.total_ttc)],
    ]
    total_table = Table(totals, colWidths=[36 * mm, 28 * mm], hAlign="RIGHT")
    total_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#344054")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend(
        [
            total_table,
            Spacer(1, 6 * mm),
            Paragraph(f"Statut : {escape(order.get_status_display())}", styles["BodyText"]),
        ]
    )
    if order.terms:
        story.extend(
            [
                Spacer(1, 4 * mm),
                Paragraph("Conditions", styles["Heading2"]),
                Paragraph(escape(order.terms).replace("\n", "<br/>"), styles["BodyText"]),
            ]
        )
    if order.notes:
        story.extend(
            [
                Spacer(1, 4 * mm),
                Paragraph("Notes", styles["Heading2"]),
                Paragraph(escape(order.notes).replace("\n", "<br/>"), styles["BodyText"]),
            ]
        )
    document.build(story)

    response = HttpResponse(output.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{order.order_number}.pdf"'
    return response
