# -*- coding: utf-8 -*-
from odoo import models, api


def _get_stock_context(env):
    warehouse = env["stock.warehouse"].search([], limit=1)
    ctx = dict(env.context)

    if warehouse:
        ctx.update({
            "warehouse": warehouse.id,
            "warehouse_id": warehouse.id,
            "location": warehouse.lot_stock_id.id,
            "allowed_company_ids": [warehouse.company_id.id],
            "company_id": warehouse.company_id.id,
        })

    return warehouse, ctx


def _real_qty(env, product_ids, warehouse):
    if not product_ids or not warehouse:
        return 0.0

    quants = env["stock.quant"].sudo().search([
        ("product_id", "in", product_ids),
        ("location_id", "child_of", warehouse.lot_stock_id.id),
        ("location_id.usage", "=", "internal"),
    ])
    return sum(quants.mapped("quantity"))


def _get_template_from_doc(doc):
    if not hasattr(doc, "_name"):
        return False
    if doc._name == "product.template":
        return doc
    if hasattr(doc, "product_tmpl_id"):
        return doc.product_tmpl_id
    return False


class StockForecastedProductTemplate(models.AbstractModel):
    _inherit = "stock.forecasted_product_template"

    @api.model
    def get_report_values(self, docids=None, data=None):
        docids = docids or []
        warehouse, ctx = _get_stock_context(self.env)

        res = super(
            StockForecastedProductTemplate,
            self.with_context(ctx)
        ).get_report_values(docids, data=data)

        docs = res.get("docs", {})
        product_data = docs.get("product", {})

        for product_id, values in product_data.items():
            product = self.env["product.product"].browse(product_id)

            if not product.product_tmpl_id.is_medicament:
                continue

            qty = _real_qty(self.env, [product_id], warehouse)

            values["quantity_on_hand"] = qty
            values["virtual_available"] = qty
            values["free_qty"] = qty
            values["incoming_qty"] = 0.0
            values["outgoing_qty"] = 0.0
            values["qty"]["in"] = 0.0
            values["qty"]["out"] = 0.0
            values["draft_picking_qty"]["in"] = 0.0
            values["draft_picking_qty"]["out"] = 0.0
            values["draft_sale_qty"]["in"] = 0.0
            values["draft_sale_qty"]["out"] = 0.0

        for line in docs.get("lines", []):
            product_id = line.get("product", {}).get("id")
            if product_id in product_data:
                line["quantity"] = product_data[product_id]["quantity_on_hand"]

        return res

class StockForecastedProductProduct(models.AbstractModel):
    _inherit = "stock.forecasted_product_product"

    @api.model
    def get_report_values(self, docids=None, data=None):
        docids = docids or []
        warehouse, ctx = _get_stock_context(self.env)

        res = super(
            StockForecastedProductProduct,
            self.with_context(ctx)
        ).get_report_values(docids, data=data)

        if not isinstance(res, dict):
            return res

        for doc in res.get("docs", []):
            tmpl = _get_template_from_doc(doc)

            if not tmpl or not tmpl.is_medicament:
                continue

            variant_ids = tmpl.product_variant_ids.ids
            qty = _real_qty(self.env, variant_ids, warehouse)

            for product_info in res.get("product_infos", {}).values():
                if product_info.get("product_id") in variant_ids:
                    product_info["qty_on_hand"] = qty
                    product_info["forecasted_qty"] = qty
                    product_info["free_qty"] = qty

            for variant_data in res.get("product_variants", []):
                if variant_data.get("product_id") in variant_ids:
                    variant_data["qty_on_hand"] = qty
                    variant_data["forecasted_qty"] = qty
                    variant_data["free_qty"] = qty

        return res


class ReportStockQuantity(models.Model):
    _inherit = "report.stock.quantity"

    @api.model
    def formatted_read_group(self, domain, groupby, aggregates, **kwargs):
        warehouse, ctx = _get_stock_context(self.env)

        result = super(
            ReportStockQuantity,
            self.with_context(ctx)
        ).formatted_read_group(domain, groupby, aggregates, **kwargs)

        Product = self.env["product.product"].sudo()
        product_ids = []

        for row in result:
            pid = row.get("product_id")
            if isinstance(pid, (list, tuple)):
                pid = pid[0]
            if pid:
                product_ids.append(pid)

        products = Product.browse(list(set(product_ids))).filtered(
            lambda p: p.product_tmpl_id.is_medicament
        )

        for row in result:
            pid = row.get("product_id")
            if isinstance(pid, (list, tuple)):
                pid = pid[0]

            if pid in products.ids:
                qty = _real_qty(self.env, [pid], warehouse)
                for key in ["quantity", "qty_on_hand", "forecasted_qty", "free_qty", "available_quantity"]:
                    if key in row:
                        row[key] = qty

        return result

class ProductProduct(models.Model):
    _inherit = "product.product"

    def _compute_quantities_dict(self, lot_id, owner_id, package_id,
                                  from_date=False, to_date=False):
        """
        Override pour forcer le contexte warehouse/location sur les médicaments.
        Sans ça, qty_available retourne 0 quand il n'y a qu'une location interne.
        """
        warehouse = self.env["stock.warehouse"].search([], limit=1)

        medicaments = self.filtered(lambda p: p.product_tmpl_id.is_medicament)
        others = self - medicaments

        result = {}

        if others:
            result.update(
                super(ProductProduct, others)._compute_quantities_dict(
                    lot_id, owner_id, package_id, from_date, to_date
                )
            )

        if medicaments and warehouse:
            ctx_result = super(
                ProductProduct,
                medicaments.with_context(
                    location=warehouse.lot_stock_id.id,
                    warehouse=warehouse.id,
                )
            )._compute_quantities_dict(lot_id, owner_id, package_id, from_date, to_date)
            result.update(ctx_result)

        return result